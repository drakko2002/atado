from atado.config import AtadoConfig, Glossary, GlossaryTerm
from atado.manifest import transcription_signature, Manifest


def test_signature_changes_with_model():
    cfg = AtadoConfig()
    s1 = transcription_signature(cfg, model="large-v3", language="pt", diarize=False)
    s2 = transcription_signature(cfg, model="medium", language="pt", diarize=False)
    assert s1 != s2


def test_signature_changes_with_glossary():
    cfg_a = AtadoConfig(glossary=Glossary(terms=[GlossaryTerm(term="CGD")]))
    cfg_b = AtadoConfig(glossary=Glossary(terms=[GlossaryTerm(term="CGD"),
                                                 GlossaryTerm(term="CETEC")]))
    s1 = transcription_signature(cfg_a, model="large-v3", language="pt", diarize=True)
    s2 = transcription_signature(cfg_b, model="large-v3", language="pt", diarize=True)
    assert s1 != s2


def test_signature_changes_with_diarize_flag():
    cfg = AtadoConfig()
    s1 = transcription_signature(cfg, model="large-v3", language="pt", diarize=True)
    s2 = transcription_signature(cfg, model="large-v3", language="pt", diarize=False)
    assert s1 != s2


def test_needs_processing_new_file(tmp_path):
    m = Manifest.load(tmp_path / "manifest.json")
    assert m.needs_processing("a.mp3", input_hash="abc", signature="sig1") is True


def test_no_reprocess_when_unchanged(tmp_path):
    p = tmp_path / "manifest.json"
    m = Manifest.load(p)
    m.record("a.mp3", input_hash="abc", signature="sig1", outputs=["out/a.json"], status="ok")
    m.save(p)
    m2 = Manifest.load(p)
    assert m2.needs_processing("a.mp3", input_hash="abc", signature="sig1") is False


def test_reprocess_when_signature_changes(tmp_path):
    p = tmp_path / "manifest.json"
    m = Manifest.load(p)
    m.record("a.mp3", input_hash="abc", signature="sig1", outputs=[], status="ok")
    # glossário mudou -> nova assinatura -> reprocessa
    assert m.needs_processing("a.mp3", input_hash="abc", signature="sig2") is True


def test_reprocess_when_input_changes(tmp_path):
    m = Manifest.load(tmp_path / "manifest.json")
    m.record("a.mp3", input_hash="abc", signature="sig1", outputs=[], status="ok")
    assert m.needs_processing("a.mp3", input_hash="XYZ", signature="sig1") is True


def test_failed_status_reprocesses(tmp_path):
    m = Manifest.load(tmp_path / "manifest.json")
    m.record("a.mp3", input_hash="abc", signature="sig1", outputs=[], status="error")
    assert m.needs_processing("a.mp3", input_hash="abc", signature="sig1") is True


def test_signature_changes_with_max_speakers():
    from atado.config import AtadoConfig
    a = AtadoConfig(max_speakers=None)
    b = AtadoConfig(max_speakers=3)
    s1 = transcription_signature(a, model="large-v3", language="pt", diarize=True)
    s2 = transcription_signature(b, model="large-v3", language="pt", diarize=True)
    assert s1 != s2


def test_signature_changes_with_compute_type():
    from atado.config import AtadoConfig
    cfg = AtadoConfig()
    s1 = transcription_signature(cfg, "large-v3", "pt", True, compute_type="int8")
    s2 = transcription_signature(cfg, "large-v3", "pt", True, compute_type="float16")
    assert s1 != s2
