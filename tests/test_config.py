import textwrap

import pytest

from atado.config import (
    AtadoConfig,
    GlossaryTerm,
    load_config,
    dump_config_commented,
    default_config_text,
)


SAMPLE_YAML = textwrap.dedent(
    """
    project: "Reunião CGD 2026-06"
    language: pt
    model: large-v3
    diarize: true
    order: offset
    files:
      "audio_01.mp3":
        source_start: "08:00"
    glossary:
      context: >
        Reunião do Comitê Gestor de Dados (CGD), IFRS e UFSCar.
      terms:
        - term: CGD
          meaning: "Comitê Gestor de Dados"
        - term: CETEC
          meaning: null
          aliases: ["CETEQ", "SETEC"]
    track_extra: ["Space", "SWAP"]
    output:
      context_window_seconds: 20
    """
)


def test_loads_and_applies_defaults(tmp_path):
    p = tmp_path / "atado.yaml"
    p.write_text(SAMPLE_YAML, encoding="utf-8")
    cfg = load_config(p)
    assert cfg.project == "Reunião CGD 2026-06"
    assert cfg.language == "pt"
    assert cfg.model == "large-v3"
    assert cfg.diarize is True
    assert cfg.order == "offset"


def test_parses_glossary_terms_and_aliases(tmp_path):
    p = tmp_path / "atado.yaml"
    p.write_text(SAMPLE_YAML, encoding="utf-8")
    cfg = load_config(p)
    by_term = {t.term: t for t in cfg.glossary.terms}
    assert by_term["CGD"].meaning == "Comitê Gestor de Dados"
    assert by_term["CETEC"].meaning is None
    assert by_term["CETEC"].aliases == ["CETEQ", "SETEC"]


def test_parses_file_offsets(tmp_path):
    p = tmp_path / "atado.yaml"
    p.write_text(SAMPLE_YAML, encoding="utf-8")
    cfg = load_config(p)
    # source_start "08:00" deve virar 480.0 segundos
    assert cfg.source_start_for("audio_01.mp3") == 480.0
    assert cfg.source_start_for("desconhecido.mp3") is None


def test_rejects_invalid_order(tmp_path):
    p = tmp_path / "atado.yaml"
    p.write_text(SAMPLE_YAML.replace("order: offset", "order: aleatorio"), encoding="utf-8")
    with pytest.raises(Exception):
        load_config(p)


def test_default_config_text_is_loadable_and_commented(tmp_path):
    text = default_config_text(project="Meu Projeto")
    assert "#" in text  # tem comentários
    p = tmp_path / "atado.yaml"
    p.write_text(text, encoding="utf-8")
    cfg = load_config(p)
    assert cfg.project == "Meu Projeto"
    assert cfg.language == "pt"


def test_hf_token_never_in_config_schema():
    # E8: token é env-only; não deve haver campo de token no schema
    assert not any("token" in f.lower() for f in AtadoConfig.model_fields)
