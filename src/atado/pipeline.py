"""Orquestração transcribe/run (F2/F4). ASR entra por um seam injetável (testável).

Resiliência: falha em 1 áudio não aborta o lote (erro vai para o relatório).
Cache: pula áudios já processados (manifest) a menos que --force ou assinatura mude.
"""

from __future__ import annotations

import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Optional

from .audio import is_supported, normalize_audio, probe_duration
from .config import AtadoConfig, load_config
from .glossary import apply_corrections, build_initial_prompt, load_wordlist, default_wordlist_path
from .manifest import Manifest, file_input_hash, transcription_signature
from .merge import _fmt_ref, _effective_offset
from .models import TranscriptDoc
from .timeutil import format_hms
from .workspace import Workspace, load_dotenv, get_hf_token
from . import __version__

TranscribeFn = Callable[..., TranscriptDoc]
DiarizeFn = Callable[..., TranscriptDoc]


def render_transcript_markdown(doc: TranscriptDoc, cfg: AtadoConfig) -> str:
    offset = _effective_offset(doc, cfg)
    dur = format_hms(doc.meta.duration)
    head = f"## {doc.meta.source_file} (duração {dur}"
    if offset is not None:
        head += f", início no encontro {format_hms(offset)}"
    head += ")"
    lines = [head, ""]
    for s in doc.segments:
        who = f" {s.speaker}:" if s.speaker else ""
        lines.append(f"{_fmt_ref(s.start, offset)}{who} {s.text.strip()}")
    return "\n".join(lines).rstrip() + "\n"


def _apply_correction_pass(doc: TranscriptDoc, cfg: AtadoConfig, wordlist) -> Counter:
    subs_counter: Counter = Counter()
    if not cfg.correction.enabled:
        return subs_counter
    from .glossary import normalize
    for seg in doc.segments:
        new_text, subs = apply_corrections(seg.text, cfg.glossary, wordlist,
                                           threshold=cfg.correction.threshold)
        if subs:
            seg.text = new_text
            sub_map = {normalize(orig): canon for orig, canon in subs}
            for w in seg.words:  # mantém words[] consistente com o texto corrigido
                canon = sub_map.get(normalize(w.word))
                if canon:
                    w.word = canon
            for orig, canon in subs:
                subs_counter[f"{orig} → {canon}"] += 1
    return subs_counter


def transcribe_workspace(
    ws: Workspace,
    cfg: AtadoConfig,
    *,
    only: Optional[str] = None,
    force: bool = False,
    no_diarize: bool = False,
    device: Optional[str] = None,
    model: Optional[str] = None,
    compute_type: Optional[str] = None,
    hf_token: Optional[str] = None,
    transcribe_fn: Optional[TranscribeFn] = None,
    diarize_fn: Optional[DiarizeFn] = None,
    wordlist: Optional[set] = None,
    log: Callable[[str], None] = lambda s: None,
) -> dict[str, Any]:
    """Transcreve os áudios novos do workspace. Retorna dados do relatório."""
    from .hardware import detect_hardware

    model_name = model or cfg.model
    # precedência: flag > config > autodetecção
    device = device or cfg.device
    compute_type = compute_type or cfg.compute_type
    hw = detect_hardware(model=model_name, device=device, compute_type=compute_type)
    if transcribe_fn is None:
        from .asr import whisperx_transcribe
        transcribe_fn = whisperx_transcribe
    if wordlist is None:
        wordlist = load_wordlist(default_wordlist_path())

    diarize_enabled = (not no_diarize) and cfg.diarize
    diarize_note = None
    if diarize_enabled and diarize_fn is None:
        try:
            from .asr_diarize import diarize_doc  # F3
            diarize_fn = diarize_doc
        except Exception:
            diarize_fn = None
    if diarize_enabled and hf_token is None:
        diarize_enabled = False
        diarize_note = "diarização desativada: HF_TOKEN ausente (ver .env.example)."

    audios = [p for p in sorted(ws.audios.glob("*")) if p.is_file() and is_supported(p)]
    if only:
        audios = [p for p in audios if p.name == only or p.stem == only]

    # aviso E9: clipes curtos
    if audios:
        durs = sorted(probe_duration(p) for p in audios)
        median = durs[len(durs) // 2]
        if median and median < 30 and diarize_enabled:
            log(f"⚠️ duração mediana {median:.0f}s < 30s: diarização terá valor limitado.")

    manifest = Manifest.load(ws.manifest_path)
    signature = transcription_signature(cfg, model_name, cfg.language, diarize_enabled,
                                        compute_type=hw["compute_type"])
    initial_prompt = build_initial_prompt(cfg.glossary)

    report: dict[str, Any] = {
        "hardware": hw, "model": model_name, "device": hw["device"],
        "compute_type": hw["compute_type"], "diarize": diarize_enabled,
        "diarize_note": diarize_note, "files": [], "skipped": [],
        "substitutions": Counter(), "errors": [],
    }

    ws.transcripts.mkdir(parents=True, exist_ok=True)
    ws.work.mkdir(parents=True, exist_ok=True)

    for audio in audios:
        name = audio.name
        try:
            in_hash = file_input_hash(audio)
        except OSError as e:
            report["errors"].append((name, f"leitura: {e}"))
            continue
        if not force and not manifest.needs_processing(name, in_hash, signature):
            report["skipped"].append(name)
            log(f"• {name}: em cache (pulado)")
            continue

        t0 = time.time()
        try:
            wav = ws.work / (audio.stem + ".wav")
            normalize_audio(audio, wav)
            duration = probe_duration(wav)
            source_start = cfg.source_start_for(name)
            doc = transcribe_fn(
                wav, source_file=name, model=model_name, device=hw["device"],
                compute_type=hw["compute_type"], language=cfg.language,
                initial_prompt=initial_prompt, duration=duration,
                source_start=source_start, atado_version=__version__,
            )
            if diarize_enabled and diarize_fn is not None:
                try:
                    doc = diarize_fn(doc, wav, hf_token=hf_token,
                                     min_speakers=cfg.min_speakers, max_speakers=cfg.max_speakers)
                except Exception as de:
                    # degrada com elegância: desliga diarização p/ os próximos e mantém
                    # a transcrição (sem falantes) em vez de perder o arquivo.
                    diarize_enabled = False
                    report["diarize_note"] = f"diarização desativada após falha: {de}"
                    log(f"⚠️ diarização falhou ({de}); seguindo SEM diarização.")
            subs = _apply_correction_pass(doc, cfg, wordlist)
            report["substitutions"].update(subs)

            json_path = ws.transcripts / (audio.stem + ".json")
            md_path = ws.transcripts / (audio.stem + ".md")
            json_path.write_text(doc.model_dump_json(indent=2), encoding="utf-8")
            md_path.write_text(render_transcript_markdown(doc, cfg), encoding="utf-8")

            manifest.record(name, in_hash, signature,
                            outputs=[str(json_path), str(md_path)], status="ok",
                            atado_version=__version__)
            manifest.save(ws.manifest_path)
            elapsed = time.time() - t0
            report["files"].append({
                "file": name, "status": "ok", "duration": duration,
                "elapsed": elapsed, "n_segments": len(doc.segments),
            })
            log(f"✓ {name}: {len(doc.segments)} segmentos em {elapsed:.1f}s")
        except Exception as e:  # resiliência: não aborta o lote
            from .asr import map_asr_error
            msg = map_asr_error(e)
            manifest.record(name, in_hash, signature, outputs=[], status="error", error=msg)
            manifest.save(ws.manifest_path)
            report["files"].append({"file": name, "status": "error", "error": msg})
            report["errors"].append((name, msg))
            log(f"✗ {name}: ERRO — {msg}")

    return report


# ------------------------------------------------------------------ CLI glue
def cmd_transcribe(ws, *, only, force, no_diarize, device, model, compute_type,
                   console, err, output_dir=None):
    load_dotenv(ws.root)
    try:
        cfg = load_config(ws.config_path)
    except ValueError as e:
        err.print(f"[red]{e}[/red]"); raise SystemExit(1)
    ws.set_output_dir(output_dir or cfg.output_dir)
    if cfg.diarize and not no_diarize:
        from .notices import LGPD_DIARIZATION
        console.print(f"[yellow]{LGPD_DIARIZATION}[/yellow]\n")
    hf = get_hf_token()
    report = transcribe_workspace(
        ws, cfg, only=only, force=force, no_diarize=no_diarize, device=device,
        model=model, compute_type=compute_type, hf_token=hf,
        log=lambda s: console.print("  " + s),
    )
    _print_transcribe_summary(report, console)
    return report


def _print_transcribe_summary(report, console):
    ok = [f for f in report["files"] if f["status"] == "ok"]
    errs = report["errors"]
    console.print(
        f"[green]✓[/green] {len(ok)} transcritos, "
        f"{len(report['skipped'])} em cache, {len(errs)} com erro "
        f"[{report['device']}/{report['compute_type']}, diarize={report['diarize']}]"
    )
    if report.get("diarize_note"):
        console.print(f"  [yellow]{report['diarize_note']}[/yellow]")
    if report["substitutions"]:
        top = ", ".join(f"{k} ({v}x)" for k, v in report["substitutions"].most_common(8))
        console.print(f"  correções: {top}")
    for name, msg in errs:
        console.print(f"  [red]erro[/red] {name}: {msg}")


def cmd_run(ws, *, no_diarize, force, device, model, compute_type, console, err, output_dir=None):
    from .report import write_report
    from .merge import consolidate_markdown, consolidate_json
    from .terms import (find_occurrences, render_terms_markdown, render_terms_csv,
                        find_suspects, render_suspects_markdown)
    from .glossary import normalize
    import json as _json

    report = cmd_transcribe(ws, only=None, force=force, no_diarize=no_diarize, device=device,
                            model=model, compute_type=compute_type, output_dir=output_dir,
                            console=console, err=err)
    cfg = load_config(ws.config_path)
    ws.set_output_dir(output_dir or cfg.output_dir)
    docs = ws.load_transcripts()
    if not docs:
        err.print("[yellow]Nenhum transcript gerado — nada a consolidar.[/yellow]")
        return
    ws.out.mkdir(parents=True, exist_ok=True)
    mtimes = ws.audio_mtimes() if cfg.order == "mtime" else None
    (ws.out / "consolidated.md").write_text(consolidate_markdown(docs, cfg, mtimes), encoding="utf-8")
    (ws.out / "consolidated.json").write_text(
        _json.dumps(consolidate_json(docs, cfg, mtimes), ensure_ascii=False, indent=2), encoding="utf-8")

    term_pairs = [(t.term, t.meaning) for t in cfg.glossary.terms] + [(t, None) for t in cfg.track_extra]
    meanings = {t: m for t, m in term_pairs}
    index = find_occurrences(docs, term_pairs, cfg)
    (ws.out / "terms.md").write_text(render_terms_markdown(index, meanings, cfg, len(docs)), encoding="utf-8")
    (ws.out / "terms.csv").write_text(render_terms_csv(index, meanings), encoding="utf-8")

    known = set()
    for t in cfg.glossary.terms:
        known.add(normalize(t.term))
        known.update(normalize(a) for a in t.aliases)
    known.update(normalize(t) for t in cfg.track_extra)
    from .glossary import load_wordlist, default_wordlist_path
    sus = find_suspects(docs, known, load_wordlist(default_wordlist_path()), min_count=2)
    (ws.out / "suspects.md").write_text(render_suspects_markdown(sus, cfg.project), encoding="utf-8")

    write_report(ws, cfg, report, index, sus)
    console.print(f"[green]✓[/green] run completo → out/ (consolidated, terms, suspects, report)")
