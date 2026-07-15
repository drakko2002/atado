"""Layout do workspace do projeto e utilidades de I/O leves (sem torch)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .models import TranscriptDoc


class Workspace:
    def __init__(self, root: Path):
        self.root = Path(root)

    @property
    def config_path(self) -> Path:
        return self.root / "atado.yaml"

    @property
    def audios(self) -> Path:
        return self.root / "audios"

    @property
    def work(self) -> Path:
        return self.root / "work"

    @property
    def out(self) -> Path:
        return self.root / "out"

    @property
    def transcripts(self) -> Path:
        return self.out / "transcripts"

    @property
    def kit(self) -> Path:
        return self.out / "kit"

    @property
    def manifest_path(self) -> Path:
        return self.work / "manifest.json"

    def ensure_dirs(self) -> None:
        for d in (self.audios, self.work, self.transcripts, self.out):
            d.mkdir(parents=True, exist_ok=True)

    def load_transcripts(self) -> list[TranscriptDoc]:
        docs: list[TranscriptDoc] = []
        if not self.transcripts.exists():
            return docs
        for p in sorted(self.transcripts.glob("*.json")):
            docs.append(TranscriptDoc.model_validate_json(p.read_text(encoding="utf-8")))
        return docs


def find_workspace(start: Optional[Path] = None) -> Workspace:
    """Sobe diretórios procurando um atado.yaml; se não achar, usa o cwd."""
    start = Path(start or Path.cwd()).resolve()
    for d in [start, *start.parents]:
        if (d / "atado.yaml").exists():
            return Workspace(d)
    return Workspace(start)


def load_dotenv(root: Path) -> None:
    """Carrega .env do projeto para o ambiente (não sobrescreve o que já existe).

    NUNCA imprime valores. Usado para HF_TOKEN e chaves de provedores.
    """
    env = Path(root) / ".env"
    if not env.exists():
        return
    try:
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
    except Exception:
        pass


def get_hf_token() -> Optional[str]:
    for var in ("HF_TOKEN", "HUGGINGFACE_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HF_HUB_TOKEN"):
        v = os.environ.get(var)
        if v:
            return v
    return None
