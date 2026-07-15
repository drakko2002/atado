import textwrap

from atado.config import load_config
from atado.interview import SENTINELS, parse_agent_output, build_context_yaml
from atado.kit import generate_kit, render_protocol
from atado.models import TranscriptDoc, TranscriptMeta, Segment
from atado.workspace import Workspace


CFG = textwrap.dedent(
    """
    project: "Reunião CGD"
    language: pt
    diarize: true
    glossary:
      context: "Reunião do Comitê Gestor de Dados."
      terms:
        - term: CGD
          meaning: "Comitê Gestor de Dados"
        - term: CETEC
          meaning: null
          aliases: ["CETEQ"]
    track_extra: ["SIAPE"]
    output:
      context_window_seconds: 20
    """
)


def _ws(tmp_path):
    ws = Workspace(tmp_path)
    ws.ensure_dirs()
    ws.config_path.write_text(CFG, encoding="utf-8")
    return ws


def _docs():
    return [TranscriptDoc(
        meta=TranscriptMeta(source_file="a.mp3", duration=10.0, model="large-v3",
                            language="pt", diarized=True, atado_version="0.1.0"),
        segments=[
            Segment(start=0.0, end=3.0, text="a CETEC vai responder", speaker="SPEAKER_00"),
            Segment(start=3.0, end=4.0, text="sim", speaker="SPEAKER_01"),
            Segment(start=4.0, end=7.0, text="contato fulano@ufscar.br", speaker="SPEAKER_00"),
        ],
    )]


class TestProtocol:
    def test_contains_sentinels_and_rules(self):
        cfg = load_config_from(CFG)
        p = render_protocol(cfg, has_suspects=True, diarized=True)
        assert f"## {SENTINELS['tabela']}" in p
        assert f"## {SENTINELS['narrativa']}" in p
        assert "3–4 perguntas" in p  # regra de lotes pequenos
        assert "nunca apresenta especulação como fato" in p.lower() or "REGRA DE OURO" in p


class TestKit:
    def test_generates_expected_files(self, tmp_path):
        ws = _ws(tmp_path)
        cfg = load_config(ws.config_path)
        summary = generate_kit(ws, cfg, _docs())
        names = set(summary["files"])
        assert {"00_PROTOCOLO.md", "01_contexto_usuario.md", "02_termos.md",
                "03_transcricao.md", "LEIA-ME.txt"} <= names
        assert (ws.kit / "00_PROTOCOLO.md").exists()

    def test_terms_only_omits_transcript(self, tmp_path):
        ws = _ws(tmp_path)
        cfg = load_config(ws.config_path)
        summary = generate_kit(ws, cfg, _docs(), terms_only=True)
        assert "03_transcricao.md" not in summary["files"]
        assert not (ws.kit / "03_transcricao.md").exists()

    def test_redact_removes_pii_and_map_not_in_kit(self, tmp_path):
        ws = _ws(tmp_path)
        cfg = load_config(ws.config_path)
        generate_kit(ws, cfg, _docs(), redact=True)
        transcript = (ws.kit / "03_transcricao.md").read_text()
        assert "fulano@ufscar.br" not in transcript
        assert "[[PII-" in transcript
        # mapa em work/, NUNCA no kit
        assert (ws.work / "redaction_map.json").exists()
        assert not (ws.kit / "redaction_map.json").exists()

    def test_context_table_lists_terms(self, tmp_path):
        ws = _ws(tmp_path)
        cfg = load_config(ws.config_path)
        generate_kit(ws, cfg, _docs())
        ctx = (ws.kit / "01_contexto_usuario.md").read_text()
        assert "CGD" in ctx and "CETEC" in ctx and "SIAPE" in ctx


class TestContextYaml:
    def test_roundtrip_import_then_context(self):
        agent_out = textwrap.dedent(
            """
            ## TABELA_RESOLVIDA
            | Sigla | Significado | Confiança | Proveniência | Variantes/Aliases |
            |---|---|---|---|---|
            | CETEC | Nome resolvido | alta | web:x | CETEQ |

            ## NARRATIVA
            Reunião sobre X.

            ## PENDENCIAS
            - Confirmar Y.
            """
        )
        parsed = parse_agent_output(agent_out)
        ctx = build_context_yaml(parsed)
        assert "CETEC" in ctx
        assert "narrative_present" in ctx


def load_config_from(text):
    import tempfile, os
    from atado.config import load_config
    fd, path = tempfile.mkstemp(suffix=".yaml")
    os.write(fd, text.encode()); os.close(fd)
    return load_config(path)
