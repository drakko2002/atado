"""Config do projeto (`atado.yaml`): schema pydantic + I/O com ruamel.yaml.

- Leitura: ruamel -> dict -> validação pydantic (mensagens claras).
- Escrita/patch (interview import, E6): ruamel round-trip preserva comentários/ordem.
- HF token é env-only (E8): NÃO existe campo de token aqui.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from ruamel.yaml import YAML

from .timeutil import parse_timestamp

Order = Literal["name", "mtime", "manual", "offset"]


def _yaml() -> YAML:
    y = YAML()
    y.preserve_quotes = True
    y.indent(mapping=2, sequence=4, offset=2)
    y.width = 4096
    return y


class GlossaryTerm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    term: str
    meaning: Optional[str] = None
    aliases: list[str] = Field(default_factory=list)


class Glossary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    context: str = ""
    terms: list[GlossaryTerm] = Field(default_factory=list)


class FileEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Offset da posição do recorte na gravação-mãe (E1): "HH:MM:SS" | "MM:SS" | segundos.
    source_start: Optional[Union[str, float, int]] = None


class OutputCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    context_window_seconds: float = 20.0


class CorrectionCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # E2: limiar recalibrado (~80) sobre rapidfuzz.fuzz.ratio após casefold+sem-acento.
    threshold: int = 80
    enabled: bool = True


class LongAudioCfg(BaseModel):
    """Parâmetros de processamento por-chunk para arquivos longos (SPEC D, D1)."""
    model_config = ConfigDict(extra="forbid")
    chunk_length: float = 600.0    # segundos por bloco (padrão 10 min)
    chunk_overlap: float = 3.0     # sobreposição entre blocos
    silence_snap: float = 30.0     # janela p/ buscar silêncio perto da fronteira


class AtadoConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project: str = "Projeto atado"
    language: str = "pt"
    model: str = "large-v3"
    diarize: bool = True
    min_speakers: Optional[int] = None
    max_speakers: Optional[int] = None
    order: Order = "name"
    manual_order: list[str] = Field(default_factory=list)

    # Overrides de hardware (E10) — opcionais; flags de CLI ainda sobrepõem.
    device: Optional[str] = None
    compute_type: Optional[str] = None

    files: dict[str, FileEntry] = Field(default_factory=dict)
    glossary: Glossary = Field(default_factory=Glossary)
    track_extra: list[str] = Field(default_factory=list)
    output: OutputCfg = Field(default_factory=OutputCfg)
    correction: CorrectionCfg = Field(default_factory=CorrectionCfg)

    # ------------------------------------------------------------------ helpers
    def source_start_for(self, filename: str) -> Optional[float]:
        """Offset (segundos) do arquivo, ou None se não configurado."""
        entry = self.files.get(filename)
        if entry is None or entry.source_start is None:
            return None
        return parse_timestamp(entry.source_start)

    def has_offsets(self) -> bool:
        return any(e.source_start is not None for e in self.files.values())


def load_config(path: Union[str, Path]) -> AtadoConfig:
    """Lê e valida o atado.yaml. Levanta ValueError com mensagem legível."""
    path = Path(path)
    if not path.exists():
        raise ValueError(f"atado.yaml não encontrado em {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = _yaml().load(fh) or {}
    # ruamel entrega CommentedMap; pydantic aceita como mapping.
    try:
        return AtadoConfig.model_validate(dict(data))
    except ValidationError as exc:
        raise ValueError(f"atado.yaml inválido:\n{exc}") from exc


def dump_config_commented(cfg_map: Any, path: Union[str, Path]) -> None:
    """Escreve um CommentedMap (round-trip ruamel) preservando comentários."""
    with Path(path).open("w", encoding="utf-8") as fh:
        _yaml().dump(cfg_map, fh)


def load_commented(path: Union[str, Path]) -> Any:
    """Carrega o atado.yaml como CommentedMap (para patch preservando comentários)."""
    with Path(path).open("r", encoding="utf-8") as fh:
        return _yaml().load(fh)


def dumps_commented(cfg_map: Any) -> str:
    buf = io.StringIO()
    _yaml().dump(cfg_map, buf)
    return buf.getvalue()


def default_config_text(project: str = "Projeto atado") -> str:
    """Gera o texto comentado do atado.yaml para o `atado init`."""
    # Escrito à mão para máximo de comentários instrutivos (E10 defaults consolidados).
    return f'''\
# ============================================================================
# atado.yaml — configuração do projeto
# ============================================================================
project: "{project}"
language: pt                 # idioma dos áudios (WhisperX)
model: large-v3              # tiny|base|small|medium|large-v2|large-v3
diarize: true               # identificar falantes (requer HF_TOKEN via env; ver .env.example)
min_speakers: null          # opcional (nº mínimo de falantes)
max_speakers: null          # opcional (nº máximo de falantes)

# Ordem de consolidação (merge):
#   name   -> ordem natural do nome do arquivo
#   mtime  -> data de modificação
#   manual -> lista manual_order abaixo
#   offset -> tempo do encontro (usa files[].source_start; recomendado p/ recortes)
order: name
manual_order: []

# Overrides de hardware (opcionais; flags --device/--compute-type sobrepõem):
device: null                # cuda | cpu | null (autodetecta)
compute_type: null          # int8_float16 | int8 | float16 | float32 | null

# Offset de cada recorte na gravação-mãe (E1). Permite reconstruir o tempo
# GLOBAL do encontro e cruzar com sua tabela de siglas em escala de horas.
# Ex.: um recorte tirado aos 8min do vídeo -> source_start: "08:00".
files: {{}}
  # "meu_audio.mp3":
  #   source_start: "08:00"

# Glossário: alimenta o initial_prompt (grafia correta das siglas) e o passe
# de correção fuzzy pós-transcrição.
glossary:
  context: >
    Descreva aqui o contexto da reunião (instituições, tema).
  terms: []
    # - term: CGD
    #   meaning: "Comitê Gestor de Dados"
    # - term: CETEC
    #   meaning: null            # desconhecido: só ajuda o ASR a grafar certo
    #   aliases: ["CETEQ", "SETEC"]   # erros prováveis, corrigidos no pós-processo

# Termos a rastrear no índice mesmo fora do glossário:
track_extra: []

output:
  context_window_seconds: 20   # janela de contexto ao redor de cada ocorrência

correction:
  enabled: true
  threshold: 80                # rapidfuzz.fuzz.ratio mínimo (após casefold+sem-acento)
'''
