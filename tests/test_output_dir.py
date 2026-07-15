import textwrap

from atado.config import load_config, AtadoConfig
from atado.workspace import Workspace


def test_config_parses_output_dir_and_long_audio(tmp_path):
    p = tmp_path / "atado.yaml"
    p.write_text(textwrap.dedent("""
        project: "T"
        output_dir: "/tmp/saida"
        long_audio:
          chunk_length: 300
          chunk_overlap: 5
    """), encoding="utf-8")
    cfg = load_config(p)
    assert cfg.output_dir == "/tmp/saida"
    assert cfg.long_audio.chunk_length == 300
    assert cfg.long_audio.chunk_overlap == 5


def test_default_output_dir_is_project_out(tmp_path):
    ws = Workspace(tmp_path)
    assert ws.out == tmp_path / "out"


def test_absolute_output_dir(tmp_path):
    ws = Workspace(tmp_path).set_output_dir("/var/data/saida")
    from pathlib import Path
    assert ws.out == Path("/var/data/saida")
    # transcripts/kit derivam do out
    assert ws.transcripts == Path("/var/data/saida") / "transcripts"


def test_relative_output_dir_is_under_root(tmp_path):
    ws = Workspace(tmp_path).set_output_dir("resultados")
    assert ws.out == tmp_path / "resultados"


def test_work_never_follows_output_dir(tmp_path):
    # segredos/PII (redaction_map) ficam em work/, nunca no output_dir
    ws = Workspace(tmp_path).set_output_dir("/tmp/qualquer")
    assert ws.work == tmp_path / "work"


def test_terms_writes_to_output_dir(tmp_path):
    from atado.models import TranscriptDoc, TranscriptMeta, Segment
    ws = Workspace(tmp_path)
    ws.ensure_dirs()
    ws.config_path.write_text('project: "T"\noutput_dir: "saida_custom"\n', encoding="utf-8")
    # coloca 1 transcript
    doc = TranscriptDoc(
        meta=TranscriptMeta(source_file="a.mp3", duration=1.0, model="m", language="pt",
                            diarized=False, atado_version="0.1.0"),
        segments=[Segment(start=0.0, end=1.0, text="oi")],
    )
    (ws.transcripts).mkdir(parents=True, exist_ok=True)
    (ws.transcripts / "a.json").write_text(doc.model_dump_json(), encoding="utf-8")

    cfg = load_config(ws.config_path)
    ws.set_output_dir(cfg.output_dir)
    from atado.terms import find_occurrences, render_terms_markdown
    idx = find_occurrences([doc], [("oi", None)], cfg)
    ws.out.mkdir(parents=True, exist_ok=True)
    (ws.out / "terms.md").write_text(render_terms_markdown(idx, {"oi": None}, cfg, 1), encoding="utf-8")
    assert (tmp_path / "saida_custom" / "terms.md").exists()
