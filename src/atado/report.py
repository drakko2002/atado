"""Relatório de execução (F4). Montador PURO + writer fino (E10 arch-test)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import AtadoConfig
from .timeutil import format_hms


def build_report_markdown(
    cfg: AtadoConfig,
    report: dict[str, Any],
    index: dict[str, list],
    suspects: list[dict],
) -> str:
    hw = report.get("hardware", {})
    lines: list[str] = []
    lines.append(f"# {cfg.project} — relatório de execução")
    lines.append("")
    lines.append("## Parâmetros")
    lines.append(f"- Modelo: `{report.get('model')}`  ·  device: `{report.get('device')}`  ·  "
                 f"compute: `{report.get('compute_type')}`  ·  diarize: `{report.get('diarize')}`")
    if hw.get("vram_total_gb"):
        lines.append(f"- GPU: {hw.get('reason','')}")
    if report.get("diarize_note"):
        lines.append(f"- ⚠️ {report['diarize_note']}")
    lines.append("")

    ok = [f for f in report.get("files", []) if f.get("status") == "ok"]
    lines.append("## Arquivos")
    lines.append(f"- Transcritos: {len(ok)}  ·  em cache: {len(report.get('skipped', []))}  "
                 f"·  com erro: {len(report.get('errors', []))}")
    for f in ok:
        lines.append(f"  - {f['file']}: {f.get('n_segments', 0)} segmentos, "
                     f"{format_hms(f.get('duration', 0))}, {f.get('elapsed', 0):.1f}s")
    if report.get("errors"):
        lines.append("")
        lines.append("### Erros")
        for name, msg in report["errors"]:
            lines.append(f"  - {name}: {msg}")
    lines.append("")

    subs = report.get("substitutions") or {}
    lines.append("## Passe de correção de siglas")
    if subs:
        for k, v in sorted(subs.items(), key=lambda kv: -kv[1]):
            lines.append(f"- {k} ({v}x)")
    else:
        lines.append("- (nenhuma substituição)")
    lines.append("")

    lines.append("## Cobertura do índice de termos")
    total_occ = sum(len(v) for v in index.values())
    lines.append(f"- {total_occ} ocorrências de {len(index)} termos rastreados.")
    lines.append("- ⚠️ Reflete apenas os recortes fornecidos, não a gravação completa.")
    lines.append("")

    lines.append("## Próximos passos")
    if suspects:
        lines.append(f"- {len(suspects)} termos suspeitos encontrados — rode `atado suspects` "
                     "e adicione ao glossário; depois `atado transcribe --force`.")
    lines.append("- Gere o kit para reconstrução: `atado kit` (leva ao seu agente de IA).")
    if not report.get("diarize"):
        lines.append("- Diarização desligada: peça ao agente para perguntar 'quem é SPEAKER_XX?'.")
    return "\n".join(lines).rstrip() + "\n"


def write_report(ws, cfg: AtadoConfig, report: dict, index: dict, suspects: list) -> Path:
    from .security import mask_secrets  # defesa em profundidade: nenhum segredo no relatório
    ws.out.mkdir(parents=True, exist_ok=True)
    path = ws.out / "report.md"
    path.write_text(mask_secrets(build_report_markdown(cfg, report, index, suspects)),
                    encoding="utf-8")
    return path
