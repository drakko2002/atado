"""Autodetecção de device/compute_type (E10). torch é importado TARDIAMENTE.

Padrão (decisão do usuário + E10): `int8_float16` para large-v3 em cards ≤ ~12 GB;
baseado na VRAM livre com margem, nunca no limiar exato de 8 GB.
"""

from __future__ import annotations

from typing import Optional

_LARGE = ("large", "large-v2", "large-v3")


def detect_hardware(
    model: str = "large-v3",
    device: Optional[str] = None,
    compute_type: Optional[str] = None,
) -> dict:
    """Retorna {device, compute_type, cuda, vram_total_gb, reason}. Flags sobrepõem."""
    info = {
        "device": device,
        "compute_type": compute_type,
        "cuda": False,
        "vram_total_gb": None,
        "reason": "",
    }
    try:
        import torch  # noqa: PLC0415  (lazy — mantém caminho leve sem torch)
    except Exception:
        info["device"] = device or "cpu"
        info["compute_type"] = compute_type or "int8"
        info["reason"] = "torch ausente — caminho leve (sem ASR)."
        return info

    cuda = torch.cuda.is_available()
    info["cuda"] = cuda
    if cuda:
        props = torch.cuda.get_device_properties(0)
        vram_gb = props.total_memory / (1024 ** 3)
        info["vram_total_gb"] = round(vram_gb, 2)
        info["device"] = device or "cuda"
        if compute_type:
            info["compute_type"] = compute_type
        elif info["device"] == "cuda":
            is_large = any(model.startswith(x) for x in _LARGE)
            if is_large and vram_gb <= 12:
                info["compute_type"] = "int8_float16"
                info["reason"] = (
                    f"{props.name} {vram_gb:.1f} GB: large exige int8_float16 "
                    "para não estourar VRAM."
                )
            else:
                info["compute_type"] = "float16"
                info["reason"] = f"{props.name} {vram_gb:.1f} GB."
        else:  # device forçado p/ cpu
            info["compute_type"] = compute_type or "int8"
    else:
        info["device"] = device or "cpu"
        info["compute_type"] = compute_type or "int8"
        info["reason"] = "sem CUDA — CPU (int8)."
    return info
