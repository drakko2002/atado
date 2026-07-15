"""CLI do atado (typer). SEM import de torch no topo — o ASR é importado tardiamente
dentro dos comandos pesados, para o caminho leve (init/check/merge/terms/kit/interview)
funcionar sem a stack de GPU (E4)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .config import default_config_text, load_config
from .workspace import Workspace, find_workspace, load_dotenv, get_hf_token

app = typer.Typer(
    add_completion=False,
    help="atado — transcritor local de reuniões fragmentadas (PT-BR) + reconstrução.",
    no_args_is_help=True,
)
interview_app = typer.Typer(help="Importar a saída do agente de IA de volta ao projeto.")
app.add_typer(interview_app, name="interview")

console = Console()
err = Console(stderr=True)


def _load_cfg(ws: Workspace):
    try:
        return load_config(ws.config_path)
    except ValueError as e:
        err.print(f"[red]Erro no atado.yaml:[/red] {e}")
        raise typer.Exit(1)


# ============================================================ init
@app.command()
def init(dir: str = typer.Argument(".", help="Diretório do projeto.")):
    """Cria a estrutura do projeto + atado.yaml comentado."""
    ws = Workspace(Path(dir).resolve())
    ws.ensure_dirs()
    if ws.config_path.exists():
        console.print(f"[yellow]atado.yaml já existe em {ws.config_path} — não sobrescrito.[/yellow]")
    else:
        project = ws.root.name
        ws.config_path.write_text(default_config_text(project=project), encoding="utf-8")
        console.print(f"[green]✓[/green] atado.yaml criado em {ws.config_path}")
    # .env.example de conveniência
    example = ws.root / ".env.example"
    if not example.exists():
        example.write_text(
            "# HF_TOKEN necessário só para diarização (pyannote).\nHF_TOKEN=\n",
            encoding="utf-8",
        )
    console.print(f"[green]✓[/green] Estrutura: audios/  work/  out/transcripts/")
    console.print("\nPróximos passos:")
    console.print("  1) coloque os áudios em [cyan]audios/[/cyan]")
    console.print("  2) edite [cyan]atado.yaml[/cyan] (glossário, offsets)")
    console.print("  3) rode [cyan]atado check[/cyan] e depois [cyan]atado run[/cyan]")


# ============================================================ check
@app.command()
def check():
    """Valida o ambiente (ffmpeg, Python, disco, torch/CUDA, VRAM, token HF)."""
    ws = find_workspace()
    load_dotenv(ws.root)
    table = Table(title="atado check", show_header=True, header_style="bold")
    table.add_column("Item")
    table.add_column("Status")
    table.add_column("Detalhe / correção")

    ok_all = True

    def row(name, ok, detail):
        nonlocal ok_all
        mark = "[green]✅[/green]" if ok else "[red]❌[/red]"
        if ok is None:
            mark = "[yellow]➖[/yellow]"
        elif not ok:
            ok_all = False
        table.add_row(name, mark, detail)

    # Python
    import sys
    v = sys.version_info
    py_ok = (3, 10) <= (v.major, v.minor) < (3, 13)
    row("Python", py_ok, f"{v.major}.{v.minor}.{v.micro}" + ("" if py_ok else "  (requer 3.10–3.12)"))

    # ffmpeg
    ff = shutil.which("ffmpeg")
    row("ffmpeg", bool(ff), ff or "instale ffmpeg (ex.: sudo pacman -S ffmpeg)")

    # disco
    try:
        free_gb = shutil.disk_usage(ws.root).free / (1024 ** 3)
        row("disco livre", free_gb >= 15, f"{free_gb:.1f} GB livres (≥15 GB p/ caminho GPU)")
    except Exception as e:
        row("disco livre", None, str(e))

    # torch/cuda (lazy)
    try:
        from .hardware import detect_hardware
        cfg_model = "large-v3"
        if ws.config_path.exists():
            try:
                cfg_model = load_config(ws.config_path).model
            except Exception:
                pass
        hw = detect_hardware(model=cfg_model)
        try:
            import torch  # noqa
            trow = f"torch {torch.__version__}, cuda={hw['cuda']}"
            if hw["cuda"]:
                trow += f", {hw['vram_total_gb']} GB → {hw['compute_type']}"
            row("torch/CUDA", True, trow)
        except Exception:
            row("torch/CUDA", False, "não instalado — `pip install -e .[asr]` (só p/ transcrever)")
    except Exception as e:
        row("torch/CUDA", False, f"erro: {e}")

    # token HF
    tok = get_hf_token()
    row("HF_TOKEN", tok is not None,
        "presente (diarização OK)" if tok else "ausente — necessário só p/ diarização (.env)")

    # atado.yaml
    if ws.config_path.exists():
        try:
            cfg = load_config(ws.config_path)
            row("atado.yaml", True, f"projeto: {cfg.project}")
        except ValueError as e:
            row("atado.yaml", False, str(e).splitlines()[0])
    else:
        row("atado.yaml", None, f"nenhum (rode `atado init`) — buscado em {ws.root}")

    console.print(table)
    if not ok_all:
        console.print("\n[yellow]Alguns itens precisam de atenção antes de transcrever.[/yellow]")


# ============================================================ merge
@app.command()
def merge():
    """Consolida os transcripts em consolidated.{md,json}."""
    ws = find_workspace()
    cfg = _load_cfg(ws)
    docs = ws.load_transcripts()
    if not docs:
        err.print(f"[yellow]Nenhum transcript em {ws.transcripts} — rode `atado transcribe` antes.[/yellow]")
        raise typer.Exit(1)
    from .merge import consolidate_markdown, consolidate_json
    ws.out.mkdir(parents=True, exist_ok=True)
    mtimes = ws.audio_mtimes() if cfg.order == "mtime" else None
    (ws.out / "consolidated.md").write_text(consolidate_markdown(docs, cfg, mtimes), encoding="utf-8")
    (ws.out / "consolidated.json").write_text(
        json.dumps(consolidate_json(docs, cfg, mtimes), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    console.print(f"[green]✓[/green] {len(docs)} transcripts → out/consolidated.md, out/consolidated.json")


# ============================================================ terms
@app.command()
def terms():
    """Gera o índice de termos em terms.{md,csv}."""
    ws = find_workspace()
    cfg = _load_cfg(ws)
    docs = ws.load_transcripts()
    if not docs:
        err.print(f"[yellow]Nenhum transcript em {ws.transcripts}.[/yellow]")
        raise typer.Exit(1)
    from .terms import find_occurrences, render_terms_markdown, render_terms_csv

    term_pairs = [(t.term, t.meaning) for t in cfg.glossary.terms]
    term_pairs += [(t, None) for t in cfg.track_extra]
    meanings = {t: m for t, m in term_pairs}
    index = find_occurrences(docs, term_pairs, cfg)
    ws.out.mkdir(parents=True, exist_ok=True)
    (ws.out / "terms.md").write_text(
        render_terms_markdown(index, meanings, cfg, n_files=len(docs)), encoding="utf-8"
    )
    (ws.out / "terms.csv").write_text(render_terms_csv(index, meanings), encoding="utf-8")
    total = sum(len(v) for v in index.values())
    console.print(f"[green]✓[/green] {total} ocorrências de {len(index)} termos → out/terms.md, out/terms.csv")


# ============================================================ suspects
@app.command()
def suspects():
    """Lista tokens suspeitos (prováveis siglas mal transcritas fora do glossário)."""
    ws = find_workspace()
    cfg = _load_cfg(ws)
    docs = ws.load_transcripts()
    if not docs:
        err.print(f"[yellow]Nenhum transcript em {ws.transcripts}.[/yellow]")
        raise typer.Exit(1)
    from .glossary import normalize, load_wordlist, default_wordlist_path
    from .terms import find_suspects, render_suspects_markdown

    wordlist = load_wordlist(default_wordlist_path())
    known = set()
    for t in cfg.glossary.terms:
        known.add(normalize(t.term))
        for a in t.aliases:
            known.add(normalize(a))
    for t in cfg.track_extra:
        known.add(normalize(t))
    sus = find_suspects(docs, known, wordlist, min_count=2)
    ws.out.mkdir(parents=True, exist_ok=True)
    (ws.out / "suspects.md").write_text(
        render_suspects_markdown(sus, cfg.project), encoding="utf-8"
    )
    if not sus:
        console.print("Nenhum suspeito (≥2 ocorrências) encontrado.")
    for s in sus[:30]:
        flag = " [magenta](sigla?)[/magenta]" if s["acronym_like"] else ""
        console.print(f'  [bold]{s["token"]}[/bold] — {s["count"]}x{flag}')
    console.print(f"[green]✓[/green] out/suspects.md")


# ============================================================ heavy stubs (fases seguintes)
def _todo(cmd: str, phase: str):
    err.print(f"[yellow]`atado {cmd}` é implementado na fase {phase}.[/yellow]")
    raise typer.Exit(2)


@app.command()
def transcribe(
    only: Optional[str] = typer.Option(None, "--only", help="Transcrever só este arquivo."),
    force: bool = typer.Option(False, "--force", help="Reprocessar mesmo se em cache."),
    no_diarize: bool = typer.Option(False, "--no-diarize", help="Não diarizar."),
    device: Optional[str] = typer.Option(None, "--device"),
    model: Optional[str] = typer.Option(None, "--model"),
    compute_type: Optional[str] = typer.Option(None, "--compute-type"),
):
    """Normaliza + transcreve (+ diariza) os áudios novos. (F2/F3)"""
    from .pipeline import cmd_transcribe
    cmd_transcribe(find_workspace(), only=only, force=force, no_diarize=no_diarize,
                   device=device, model=model, compute_type=compute_type, console=console, err=err)


@app.command()
def run(
    no_diarize: bool = typer.Option(False, "--no-diarize"),
    force: bool = typer.Option(False, "--force"),
    device: Optional[str] = typer.Option(None, "--device"),
    model: Optional[str] = typer.Option(None, "--model"),
    compute_type: Optional[str] = typer.Option(None, "--compute-type"),
):
    """Pipeline completo: transcribe → merge → terms → report. (F4)"""
    from .pipeline import cmd_run
    cmd_run(find_workspace(), no_diarize=no_diarize, force=force, device=device,
            model=model, compute_type=compute_type, console=console, err=err)


@app.command()
def kit(
    compact: bool = typer.Option(False, "--compact"),
    terms_only: bool = typer.Option(False, "--terms-only"),
    redact: bool = typer.Option(False, "--redact"),
    yes: bool = typer.Option(False, "--yes", help="Pular a confirmação de consentimento."),
):
    """Gera o kit portátil para um agente de IA (SPEC B). (F6/F8)"""
    from .kit import cmd_kit
    cmd_kit(find_workspace(), compact=compact, terms_only=terms_only, redact=redact,
            yes=yes, console=console, err=err)


@interview_app.command("import")
def interview_import(
    file: str = typer.Argument(..., help="Arquivo .md com a saída do agente."),
):
    """Parseia a saída do agente e atualiza o atado.yaml + out/context.yaml. (F7)"""
    from .kit import cmd_interview_import
    cmd_interview_import(find_workspace(), Path(file), console=console, err=err)


@app.command()
def reconstruct(
    provider: str = typer.Option("anthropic", "--provider"),
    model: Optional[str] = typer.Option(None, "--model"),
    resume: Optional[str] = typer.Option(None, "--resume"),
    yes: bool = typer.Option(False, "--yes"),
):
    """Sessão interativa via API de um provedor (Modo 2). (F9)"""
    from .reconstruct import cmd_reconstruct
    cmd_reconstruct(find_workspace(), provider=provider, model=model, resume=resume,
                    yes=yes, console=console, err=err)


@app.command()
def version():
    """Mostra a versão."""
    console.print(f"atado {__version__}")


if __name__ == "__main__":
    app()
