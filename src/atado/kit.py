"""Geração do kit portátil (F6) + import da entrevista (F7) + consentimento (F8).

O kit é autocontido e agent-agnóstico. O protocolo (00_PROTOCOLO.md) é a única fonte do
comportamento do agente, com as sentinelas de bloco vindas de `interview.SENTINELS` (E5).
Privacidade (E8): consentimento antes de gerar; redação opcional; mapa de redação nunca
entra no kit; consolidated bruto não é a via de hand-off (só o kit).
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import __version__
from .config import AtadoConfig, load_config, load_commented, dumps_commented
from .interview import SENTINELS, parse_agent_output, import_into_config, build_context_yaml
from .merge import consolidate_markdown, _effective_offset
from .models import TranscriptDoc
from .redact import Redactor
from .terms import (find_occurrences, render_terms_markdown, find_suspects,
                    render_suspects_markdown)
from .glossary import normalize, load_wordlist, default_wordlist_path
from .timeutil import format_hms
from .workspace import Workspace, load_dotenv

_TEMPLATES = Path(__file__).with_name("templates")


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES)),
        autoescape=select_autoescape(enabled_extensions=()),
        trim_blocks=False, lstrip_blocks=False,
        keep_trailing_newline=True,
    )


def estimate_tokens(text: str) -> int:
    return max(1, round(len(text) / 4))


def render_protocol(cfg: AtadoConfig, *, has_suspects: bool, diarized: bool,
                    example_ref: str = "audio @ mm:ss",
                    example_terms: Optional[list[str]] = None) -> str:
    tmpl = _env().get_template("00_PROTOCOLO.md.j2")
    return tmpl.render(
        project=cfg.project, version=__version__, S=SENTINELS,
        has_suspects=has_suspects, diarized=diarized,
        example_ref=example_ref, example_terms=example_terms or [t.term for t in cfg.glossary.terms][:3],
    )


def render_leiame(cfg: AtadoConfig, *, terms_only: bool, has_suspects: bool,
                  redacted: bool, approx_tokens: int) -> str:
    tmpl = _env().get_template("LEIA-ME.txt.j2")
    return tmpl.render(
        project=cfg.project, version=__version__, S=SENTINELS,
        terms_only=terms_only, has_suspects=has_suspects,
        redacted=redacted, approx_tokens=approx_tokens,
    )


def build_context_user_md(cfg: AtadoConfig, index: dict[str, list]) -> str:
    """01_contexto_usuario.md: contexto + tabela de siglas no estado atual."""
    lines = [f"# {cfg.project} — contexto do usuário", ""]
    if cfg.glossary.context:
        lines += ["## Contexto", cfg.glossary.context.strip(), ""]
    lines += ["## Tabela de siglas (estado atual)", ""]
    lines.append("| Sigla | Significado atual | Ocorrências (timestamps) | Aliases conhecidos |")
    lines.append("|-------|-------------------|--------------------------|--------------------|")
    all_terms = [(t.term, t.meaning, t.aliases) for t in cfg.glossary.terms]
    all_terms += [(t, None, []) for t in cfg.track_extra]
    for term, meaning, aliases in all_terms:
        occs = index.get(term, [])
        stamps = ", ".join(
            format_hms(o["global_start"]) if o["global_start"] is not None
            else format_hms(o["local_start"]) for o in occs[:8]
        ) or "—"
        lines.append(f"| {term} | {meaning or '???'} | {stamps} | {', '.join(aliases) or '—'} |")
    return "\n".join(lines).rstrip() + "\n"


_LOW_INFO = {"sim", "não", "nao", "tá", "ta", "ok", "certo", "isso", "aham", "uhum", "obrigado",
             "obrigada", "oi", "olá", "ola", "tchau", "então", "entao", "né", "ne"}


def compact_transcript_md(docs: list[TranscriptDoc], cfg: AtadoConfig,
                          tracked_norms: set[str]) -> str:
    """Versão compacta: remove falas curtas de baixa informação, PRESERVANDO qualquer
    segmento que contenha um termo rastreado (nunca remove ocorrências de termos)."""
    import copy
    kept: list[TranscriptDoc] = []
    for d in docs:
        nd = copy.deepcopy(d)
        new_segs = []
        for s in nd.segments:
            toks = [normalize(t) for t in s.text.split()]
            has_tracked = any(t in tracked_norms for t in toks)
            words = [t for t in toks if t]
            low_info = len(words) <= 3 and all(w in _LOW_INFO for w in words)
            if has_tracked or not low_info:
                new_segs.append(s)
        nd.segments = new_segs
        kept.append(nd)
    return consolidate_markdown(kept, cfg)


def generate_kit(ws: Workspace, cfg: AtadoConfig, docs: list[TranscriptDoc],
                 *, compact: bool = False, terms_only: bool = False,
                 redact: bool = False) -> dict[str, Any]:
    """Gera out/kit/ e retorna um resumo (arquivos, tokens estimados)."""
    term_pairs = [(t.term, t.meaning) for t in cfg.glossary.terms] + [(t, None) for t in cfg.track_extra]
    meanings = {t: m for t, m in term_pairs}
    index = find_occurrences(docs, term_pairs, cfg)

    known = set()
    for t in cfg.glossary.terms:
        known.add(normalize(t.term)); known.update(normalize(a) for a in t.aliases)
    known.update(normalize(t) for t in cfg.track_extra)
    suspects = find_suspects(docs, known, load_wordlist(default_wordlist_path()), min_count=2)
    diarized = any(s.speaker for d in docs for s in d.segments)

    tracked_norms = {normalize(t) for t, _ in term_pairs}
    terms_md = render_terms_markdown(index, meanings, cfg, n_files=len(docs))
    context_md = build_context_user_md(cfg, index)
    if compact:
        transcript_md = compact_transcript_md(docs, cfg, tracked_norms)
    else:
        transcript_md = consolidate_markdown(docs, cfg)
    suspects_md = render_suspects_markdown(suspects, cfg.project)

    # redação opcional (E8): mapa em work/, NUNCA no kit
    redactor = Redactor() if redact else None
    if redactor:
        context_md = redactor.redact(context_md)
        terms_md = redactor.redact(terms_md)
        transcript_md = redactor.redact(transcript_md)
        suspects_md = redactor.redact(suspects_md)

    example_ref = "audio @ mm:ss"
    for occs in index.values():
        if occs:
            o = occs[0]
            t = o["global_start"] if o["global_start"] is not None else o["local_start"]
            example_ref = f"{o['file']} @ {format_hms(t)}"
            break

    protocol_md = render_protocol(cfg, has_suspects=bool(suspects), diarized=diarized,
                                  example_ref=example_ref)

    # monta o kit
    kit_dir = ws.kit
    if kit_dir.exists():
        shutil.rmtree(kit_dir)
    kit_dir.mkdir(parents=True, exist_ok=True)

    files: dict[str, str] = {
        "00_PROTOCOLO.md": protocol_md,
        "01_contexto_usuario.md": context_md,
        "02_termos.md": terms_md,
    }
    if not terms_only:
        files["03_transcricao.md"] = transcript_md
    if suspects:
        files["04_suspeitos.md"] = suspects_md

    approx = sum(estimate_tokens(v) for v in files.values())
    files["LEIA-ME.txt"] = render_leiame(cfg, terms_only=terms_only, has_suspects=bool(suspects),
                                         redacted=redact, approx_tokens=approx)
    for name, content in files.items():
        (kit_dir / name).write_text(content, encoding="utf-8")

    # mapa de redação -> work/ (0600), nunca no kit
    if redactor and redactor.mapping:
        ws.work.mkdir(parents=True, exist_ok=True)
        mp = ws.work / "redaction_map.json"
        mp.write_text(json.dumps(redactor.mapping, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            os.chmod(mp, 0o600)
        except OSError:
            pass

    return {
        "kit_dir": str(kit_dir), "files": list(files.keys()),
        "approx_tokens": approx, "redacted": redact,
        "n_pii": len(redactor.mapping) if redactor else 0,
        "over_budget": approx > 150_000,
    }


# ------------------------------------------------------------------ CLI: kit
def cmd_kit(ws, *, compact, terms_only, redact, yes, console, err):
    load_dotenv(ws.root)
    try:
        cfg = load_config(ws.config_path)
    except ValueError as e:
        err.print(f"[red]{e}[/red]"); raise SystemExit(1)
    docs = ws.load_transcripts()
    if not docs:
        err.print("[yellow]Nenhum transcript — rode `atado transcribe` antes.[/yellow]")
        raise SystemExit(1)

    # consentimento (E8/§7.1)
    if not yes:
        console.print("[yellow]⚠️ O kit CONTÉM conteúdo da reunião e SAIRÁ da sua máquina "
                      "quando você o enviar a um agente de terceiros.[/yellow]")
        if not redact:
            console.print("   (sem --redact: PII não será mascarada)")
        import typer
        if not typer.confirm("Gerar o kit mesmo assim?"):
            console.print("Cancelado.")
            raise SystemExit(0)

    summary = generate_kit(ws, cfg, docs, compact=compact, terms_only=terms_only, redact=redact)
    console.print(f"[green]✓[/green] kit gerado em {summary['kit_dir']} "
                  f"({len(summary['files'])} arquivos, ~{summary['approx_tokens']} tokens)")
    if summary["redacted"]:
        console.print(f"  redação: {summary['n_pii']} itens de PII → [[PII-N]] "
                      f"(mapa em work/redaction_map.json, fora do kit)")
    if summary["over_budget"]:
        console.print("  [yellow]kit > ~150k tokens: considere --compact ou --terms-only.[/yellow]")
    return summary


# ------------------------------------------------------------------ CLI: interview import (F7)
def cmd_interview_import(ws, file: Path, *, console, err):
    if not Path(file).exists():
        err.print(f"[red]Arquivo não encontrado: {file}[/red]"); raise SystemExit(1)
    text = Path(file).read_text(encoding="utf-8")
    try:
        parsed = parse_agent_output(text)
    except ValueError as e:
        err.print(f"[red]Não consegui parsear a saída do agente:[/red] {e}")
        raise SystemExit(1)

    # backup do atado.yaml antes de qualquer escrita
    if ws.config_path.exists():
        backup = ws.config_path.with_suffix(".yaml.bak")
        shutil.copy2(ws.config_path, backup)
        cmap = load_commented(ws.config_path)
    else:
        err.print("[red]atado.yaml não encontrado.[/red]"); raise SystemExit(1)

    try:
        updated, summary = import_into_config(cmap, parsed)
    except ValueError as e:
        err.print(f"[red]Import rejeitado (conteúdo suspeito):[/red] {e}")
        raise SystemExit(1)

    # escreve em tmp, re-parseia, então substitui (nunca corromper o yaml)
    tmp = ws.config_path.with_suffix(".yaml.tmp")
    tmp.write_text(dumps_commented(updated), encoding="utf-8")
    try:
        load_config(tmp)  # valida
    except ValueError as e:
        err.print(f"[red]Resultado inválido, atado.yaml preservado:[/red] {e}")
        tmp.unlink(missing_ok=True)
        raise SystemExit(1)
    tmp.replace(ws.config_path)

    # context.yaml + narrative.md
    ws.out.mkdir(parents=True, exist_ok=True)
    ctx = build_context_yaml(parsed, prior_path=ws.out / "context.yaml")
    (ws.out / "context.yaml").write_text(ctx, encoding="utf-8")
    if parsed.get("narrativa"):
        (ws.out / "narrative.md").write_text(parsed["narrativa"] + "\n", encoding="utf-8")

    console.print(f"[green]✓[/green] import: {len(summary['updated'])} atualizados, "
                  f"{len(summary['added'])} novos, {len(summary['aliases_added'])} aliases "
                  f"(backup: {ws.config_path.name}.bak)")
    console.print(f"  → atado.yaml, out/context.yaml"
                  + (", out/narrative.md" if parsed.get('narrativa') else ""))
