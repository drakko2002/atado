import shutil
import subprocess

import pytest

from atado.config import AtadoConfig, LongAudioCfg
from atado.models import TranscriptDoc, TranscriptMeta, Segment
from atado.pipeline import transcribe_long_file

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg ausente")


def _make_wav(path, seconds=25):
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
         "-i", f"sine=frequency=300:duration={seconds}", "-ac", "1", "-ar", "16000", str(path)],
        check=True,
    )


def _cfg():
    return AtadoConfig(long_audio=LongAudioCfg(chunk_length=10, chunk_overlap=2, silence_snap=5))


class CountingFake:
    def __init__(self):
        self.calls = []

    def __call__(self, wav, *, source_file, duration=0.0, **kw):
        self.calls.append(source_file)
        return TranscriptDoc(
            meta=TranscriptMeta(source_file=source_file, duration=duration, model="m",
                                language="pt", diarized=False, atado_version="0.1.0"),
            segments=[Segment(start=0.0, end=1.0, text=f"bloco {source_file}")],
        )


def test_long_file_transcribes_all_chunks(tmp_path):
    wav = tmp_path / "long.wav"; _make_wav(wav, 25)
    fake = CountingFake()
    doc = transcribe_long_file(
        wav, _cfg(), source_file="long.wav", model="m", device="cpu", compute_type="int8",
        language="pt", initial_prompt=None, source_start=None, transcribe_fn=fake,
        chunk_dir=tmp_path / "chunks", signature="sig1",
    )
    assert len(fake.calls) == 3        # 25s / 10s → 3 blocos
    assert doc.meta.extra["chunks"] == 3
    assert len(doc.segments) >= 1


def test_second_run_uses_cache(tmp_path):
    wav = tmp_path / "long.wav"; _make_wav(wav, 25)
    chunk_dir = tmp_path / "chunks"
    transcribe_long_file(wav, _cfg(), source_file="long.wav", model="m", device="cpu",
                         compute_type="int8", language="pt", initial_prompt=None,
                         source_start=None, transcribe_fn=CountingFake(),
                         chunk_dir=chunk_dir, signature="sig1")
    fake2 = CountingFake()
    transcribe_long_file(wav, _cfg(), source_file="long.wav", model="m", device="cpu",
                         compute_type="int8", language="pt", initial_prompt=None,
                         source_start=None, transcribe_fn=fake2, chunk_dir=chunk_dir,
                         signature="sig1")
    assert fake2.calls == []           # tudo em cache


def test_resume_after_crash_only_missing_chunks(tmp_path):
    wav = tmp_path / "long.wav"; _make_wav(wav, 25)
    chunk_dir = tmp_path / "chunks"

    class FailsOnChunk1:
        def __init__(self): self.calls = []
        def __call__(self, wav, *, source_file, duration=0.0, **kw):
            self.calls.append(source_file)
            if source_file.endswith("#chunk1"):
                raise RuntimeError("crash simulado no bloco 1")
            return TranscriptDoc(
                meta=TranscriptMeta(source_file=source_file, duration=duration, model="m",
                                    language="pt", diarized=False, atado_version="0.1.0"),
                segments=[Segment(start=0.0, end=1.0, text="ok")])

    with pytest.raises(RuntimeError):
        transcribe_long_file(wav, _cfg(), source_file="long.wav", model="m", device="cpu",
                             compute_type="int8", language="pt", initial_prompt=None,
                             source_start=None, transcribe_fn=FailsOnChunk1(),
                             chunk_dir=chunk_dir, signature="sig1")

    good = CountingFake()
    transcribe_long_file(wav, _cfg(), source_file="long.wav", model="m", device="cpu",
                         compute_type="int8", language="pt", initial_prompt=None,
                         source_start=None, transcribe_fn=good, chunk_dir=chunk_dir,
                         signature="sig1")
    # bloco 0 já estava em cache → só 1 e 2 são (re)transcritos
    assert "long.wav#chunk0" not in good.calls
    assert set(good.calls) == {"long.wav#chunk1", "long.wav#chunk2"}
