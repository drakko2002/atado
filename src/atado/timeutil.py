"""Utilidades de tempo: parse/format de timestamps e reconstrução de tempo global (E1).

Convenção de exibição (para casar com a tabela do usuário, ex.: 08:03 e 2:00:27):
- < 1 hora  -> "MM:SS" (com zero à esquerda nos minutos)
- >= 1 hora -> "H:MM:SS"
"""

from __future__ import annotations

from typing import Optional, Union

Number = Union[int, float]


def parse_timestamp(value: Union[str, Number, None]) -> float:
    """Converte "HH:MM:SS" | "MM:SS" | "SS" | número em segundos (float).

    Levanta ValueError para entradas inválidas (inclui None).
    """
    if value is None:
        raise ValueError("timestamp não pode ser None")
    if isinstance(value, bool):  # bool é subclasse de int — rejeitar explicitamente
        raise ValueError(f"timestamp inválido: {value!r}")
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        raise ValueError(f"timestamp inválido: {value!r}")

    s = value.strip()
    if not s:
        raise ValueError("timestamp vazio")

    parts = s.split(":")
    if len(parts) > 3:
        raise ValueError(f"timestamp inválido: {value!r}")
    try:
        nums = [float(p) for p in parts]
    except ValueError as exc:
        raise ValueError(f"timestamp inválido: {value!r}") from exc

    seconds = 0.0
    for n in nums:  # base-60 posicional: [h,m,s] | [m,s] | [s]
        seconds = seconds * 60 + n
    return seconds


def format_hms(seconds: Number) -> str:
    """Formata segundos como MM:SS (< 1h) ou H:MM:SS (>= 1h)."""
    total = int(round(float(seconds)))
    if total < 0:
        total = 0
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def to_global(offset_seconds: Optional[Number], local_seconds: Number) -> Optional[float]:
    """Soma o offset do arquivo (posição na gravação-mãe) ao tempo local do segmento.

    Retorna None quando não há offset conhecido (mantém só o tempo local).
    """
    if offset_seconds is None:
        return None
    return float(offset_seconds) + float(local_seconds)
