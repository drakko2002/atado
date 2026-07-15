"""Sessão interativa via API (Modo 2, F9). O agente segue o MESMO 00_PROTOCOLO.md
(single source of truth), injetado como system prompt. Loop testável via injeção."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Optional

from .config import load_config
from .workspace import Workspace, load_dotenv

_STOP = {"encerrar", "encerrar entrevista", "sair", "exit", "quit", ":q"}


def run_session(
    provider,
    system_prompt: str,
    initial_user: str,
    *,
    input_fn: Callable[[], Optional[str]],
    output_fn: Callable[[str], None],
    model: Optional[str] = None,
    prior_messages: Optional[list[dict]] = None,
    max_rounds: int = 200,
) -> dict[str, Any]:
    """Conduz a entrevista: system=protocolo, 1ª mensagem=corpus, depois loop até 'encerrar'."""
    messages: list[dict] = list(prior_messages or [])
    if not messages:
        messages.append({"role": "user", "content": initial_user})

    session = {"provider": getattr(provider, "name", "?"), "model": model, "messages": messages}
    rounds = 0
    while rounds < max_rounds:
        rounds += 1
        reply = provider.chat(messages, model=model, system=system_prompt)
        messages.append({"role": "assistant", "content": reply})
        output_fn(reply)
        user = input_fn()
        if user is None or user.strip().lower() in _STOP:
            break
        messages.append({"role": "user", "content": user})
    session["messages"] = messages
    return session


def last_assistant_message(session: dict) -> str:
    for m in reversed(session.get("messages", [])):
        if m.get("role") == "assistant":
            return m.get("content", "")
    return ""


def _build_corpus(ws: Workspace, cfg, docs) -> tuple[str, str]:
    """Retorna (system_prompt=protocolo, initial_user=contexto+termos+transcrição)."""
    from .kit import render_protocol, build_context_user_md
    from .terms import find_occurrences, render_terms_markdown
    from .merge import consolidate_markdown

    term_pairs = [(t.term, t.meaning) for t in cfg.glossary.terms] + [(t, None) for t in cfg.track_extra]
    meanings = {t: m for t, m in term_pairs}
    index = find_occurrences(docs, term_pairs, cfg)
    diarized = any(s.speaker for d in docs for s in d.segments)
    system = render_protocol(cfg, has_suspects=False, diarized=diarized)
    parts = [
        build_context_user_md(cfg, index),
        render_terms_markdown(index, meanings, cfg, n_files=len(docs)),
        consolidate_markdown(docs, cfg),
        "\nSiga o 00_PROTOCOLO.md à risca. Comece pela Fase R1 (triagem + plano).",
    ]
    return system, "\n\n---\n\n".join(parts)


def cmd_reconstruct(ws, *, provider, model, resume, yes, console, err):
    from .providers import get_provider, ProviderError, DEFAULT_MODELS
    from rich.prompt import Prompt

    load_dotenv(ws.root)
    try:
        cfg = load_config(ws.config_path)
    except ValueError as e:
        err.print(f"[red]{e}[/red]"); raise SystemExit(1)
    docs = ws.load_transcripts()
    if not docs:
        err.print("[yellow]Nenhum transcript — rode `atado transcribe` antes.[/yellow]")
        raise SystemExit(1)

    if not yes:
        console.print("[yellow]⚠️ O conteúdo da reunião será enviado ao provedor "
                      f"'{provider}' (sai da sua máquina).[/yellow]")
        if not Prompt.ask("Continuar? [s/N]", default="n").lower().startswith("s"):
            raise SystemExit(0)

    try:
        prov = get_provider(provider)
    except ProviderError as e:
        err.print(f"[red]{e}[/red]"); raise SystemExit(1)
    model = model or DEFAULT_MODELS.get(provider)

    prior = None
    if resume:
        prior = json.loads(Path(resume).read_text(encoding="utf-8")).get("messages")
        system, initial = _build_corpus(ws, cfg, docs)
    else:
        system, initial = _build_corpus(ws, cfg, docs)

    if not prov.supports_search():
        console.print("[yellow]Provedor sem busca: o agente pedirá queries "
                      "(PESQUISAR:) para você colar resultados.[/yellow]")

    def _input():
        try:
            return Prompt.ask("\n[bold cyan]você[/bold cyan]")
        except (EOFError, KeyboardInterrupt):
            return None

    def _output(text):
        console.print(f"\n[bold green]{provider}[/bold green]: {text}")

    console.print(f"[dim]Sessão com {provider}/{model}. Digite 'encerrar' para finalizar.[/dim]")
    session = run_session(prov, system, initial, input_fn=_input, output_fn=_output,
                          model=model, prior_messages=prior)

    sessions_dir = ws.out / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    path = sessions_dir / f"{ts}.json"
    path.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")

    final = last_assistant_message(session)
    final_path = sessions_dir / f"{ts}_final.md"
    final_path.write_text(final + "\n", encoding="utf-8")
    console.print(f"\n[green]✓[/green] sessão salva em {path}")
    console.print(f"  para fechar o loop: [cyan]atado interview import {final_path}[/cyan]")
