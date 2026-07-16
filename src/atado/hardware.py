"""Autodetecção de device/compute_type (E10). torch é importado TARDIAMENTE.

Padrão (decisão do usuário + E10): `int8_float16` para large-v3 em cards ≤ ~12 GB;
baseado na VRAM livre com margem, nunca no limiar exato de 8 GB.
"""

from __future__ import annotations

from typing import Optional

_LARGE = ("large", "large-v2", "large-v3")


def _default_batch_size(is_large: bool, cuda: bool, vram_gb: Optional[float]) -> int:
    """batch_size seguro por VRAM. Batch alto + initial_prompt grande + chunk longo
    estoura os 8 GB (e o OOM envenena o contexto CUDA), então somos conservadores."""
    if not cuda or vram_gb is None:
        return 4  # CPU: batch não estoura VRAM, mas mantemos moderado
    if is_large:
        if vram_gb <= 5:
            return 1
        if vram_gb <= 9:      # RTX 4060 8 GB cai aqui → 4
            return 4
        if vram_gb <= 16:
            return 8
        return 16
    return 8 if vram_gb <= 9 else 16


def detect_hardware(
    model: str = "large-v3",
    device: Optional[str] = None,
    compute_type: Optional[str] = None,
    batch_size: Optional[int] = None,
) -> dict:
    """Retorna {device, compute_type, batch_size, cuda, vram_total_gb, reason}. Flags sobrepõem."""
    info = {
        "device": device,
        "compute_type": compute_type,
        "batch_size": batch_size,
        "cuda": False,
        "vram_total_gb": None,
        "reason": "",
    }
    try:
        import torch  # noqa: PLC0415  (lazy — mantém caminho leve sem torch)
    except Exception:
        info["device"] = device or "cpu"
        info["compute_type"] = compute_type or "int8"
        info["batch_size"] = batch_size or 4
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

    is_large = any(model.startswith(x) for x in _LARGE)
    info["batch_size"] = batch_size or _default_batch_size(
        is_large, info["cuda"], info["vram_total_gb"])
    return info
