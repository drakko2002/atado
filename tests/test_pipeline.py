import shutil
import subprocess
import textwrap

import pytest

from atado.config import load_config
from atado.models import TranscriptDoc, TranscriptMeta, Segment
from atado.pipeline import transcribe_workspace
from atado.workspace import Workspace

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg ausente")

CFG = textwrap.dedent(
    """
    project: "Teste Pipeline"
    language: pt
    model: large-v3
    diarize: false
    order: name
    files:
      "clip1.wav":
        source_start: "08:00"
    glossary:
      context: "Reunião de teste"
      terms:
        - term: CETEC
          meaning: null
          aliases: ["CETEQ"]
    track_extra: []
    output:
      context_window_seconds: 20
    correction:
      enabled: true
      threshold: 80
    """
)


def _make_ws(tmp_path):
    ws = Workspace(tmp_path)
    ws.ensure_dirs()
    ws.config_path.write_text(CFG, encoding="utf-8")
    for name in ("clip1.wav", "clip2.wav"):
        subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
             "-i", "sine=frequency=440:duration=1", "-ac", "1", "-ar", "16000",
             str(ws.audios / name)],
            check=True,
        )
    return ws


def fake_transcribe(wav, *, source_file, model, device, compute_type, language,
                    initial_prompt=None, duration=0.0, source_start=None,
                    atado_version="0.1.0", **kw):
    # Whisper emitiria "ceteq" (minúsculo) — o passe de correção deve virar CETEC
    return TranscriptDoc(
        meta=TranscriptMeta(source_file=source_file, duration=duration, model=model,
                            language=language, diarized=False, atado_version=atado_version,
                            source_start=source_start),
        segments=[Segment(start=0.0, end=1.0, text="a ceteq vai encaminhar")],
    )


def test_transcribes_and_applies_correction(tmp_path):
    ws = _make_ws(tmp_path)
    cfg = load_config(ws.config_path)
    report = transcribe_workspace(ws, cfg, transcribe_fn=fake_transcribe)
    assert len([f for f in report["files"] if f["status"] == "ok"]) == 2
    doc = TranscriptDoc.model_validate_json((ws.transcripts / "clip1.json").read_text())
    assert "CETEC" in doc.segments[0].text
    assert doc.meta.source_start == 480.0  # offset aplicado (E1)
    assert sum(report["substitutions"].values()) >= 2  # ceteq->CETEC nos 2 arquivos


def test_cache_skips_second_run(tmp_path):
    ws = _make_ws(tmp_path)
    cfg = load_config(ws.config_path)
    transcribe_workspace(ws, cfg, transcribe_fn=fake_transcribe)
    report2 = transcribe_workspace(ws, cfg, transcribe_fn=fake_transcribe)
    assert len(report2["skipped"]) == 2
    assert len([f for f in report2["files"] if f["status"] == "ok"]) == 0


def test_force_reprocesses(tmp_path):
    ws = _make_ws(tmp_path)
    cfg = load_config(ws.config_path)
    transcribe_workspace(ws, cfg, transcribe_fn=fake_transcribe)
    report2 = transcribe_workspace(ws, cfg, transcribe_fn=fake_transcribe, force=True)
    assert len([f for f in report2["files"] if f["status"] == "ok"]) == 2


def test_resilience_one_file_fails(tmp_path):
    ws = _make_ws(tmp_path)
    cfg = load_config(ws.config_path)

    def flaky(wav, *, source_file, **kw):
        if source_file == "clip2.wav":
            raise RuntimeError("boom")
        return fake_transcribe(wav, source_file=source_file, **kw)

    report = transcribe_workspace(ws, cfg, transcribe_fn=flaky)
    statuses = {f["file"]: f["status"] for f in report["files"]}
    assert statuses["clip1.wav"] == "ok"
    assert statuses["clip2.wav"] == "error"
    assert (ws.transcripts / "clip1.json").exists()
    assert not (ws.transcripts / "clip2.json").exists()


def fake_transcribe_with_words(wav, *, source_file, model, device, compute_type, language,
                               initial_prompt=None, duration=0.0, source_start=None,
                               atado_version="0.1.0", **kw):
    from atado.models import Word
    return TranscriptDoc(
        meta=TranscriptMeta(source_file=source_file, duration=duration, model=model,
                            language=language, diarized=False, atado_version=atado_version,
                            source_start=source_start, extra={"device": device}),
        segments=[Segment(start=0.0, end=1.0, text="a ceteq vai",
                          words=[Word(word="a", start=0.0, end=0.1),
                                 Word(word="ceteq", start=0.1, end=0.5),
                                 Word(word="vai", start=0.5, end=1.0)])],
    )


def test_correction_updates_words(tmp_path):
    ws = _make_ws(tmp_path)
    cfg = load_config(ws.config_path)
    transcribe_workspace(ws, cfg, transcribe_fn=fake_transcribe_with_words)
    doc = TranscriptDoc.model_validate_json((ws.transcripts / "clip1.json").read_text())
    words = [w.word for w in doc.segments[0].words]
    assert "CETEC" in words       # word[] corrigido junto com o texto
    assert "ceteq" not in words


def test_config_device_used_without_flag(tmp_path):
    ws = _make_ws(tmp_path)
    cfg = load_config(ws.config_path)
    cfg.device = "cpu"; cfg.compute_type = "int8"
    report = transcribe_workspace(ws, cfg, transcribe_fn=fake_transcribe_with_words)
    assert report["device"] == "cpu"       # precedência: config quando não há flag
    assert report["compute_type"] == "int8"
