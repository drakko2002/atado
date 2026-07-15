"""atado — transcritor local de reuniões fragmentadas (PT-BR) + reconstrução de contexto.

Regra de arquitetura: este pacote é importável SEM torch/whisperx.
`init`, `check`, `merge`, `terms`, `kit`, `interview` funcionam no caminho leve;
o ASR (torch/whisperx/pyannote) é importado tardiamente dentro de `asr.py`/`hardware.py`.
"""

__version__ = "0.2.0"
