import textwrap

import pytest

from atado.config import load_config, dumps_commented, load_commented
from atado.interview import (
    parse_agent_output,
    import_into_config,
    validate_field,
    SENTINELS,
)


AGENT_OUTPUT = textwrap.dedent(
    """
    Aqui está o resultado.

    ## TABELA_RESOLVIDA
    | Sigla | Significado | Confiança | Proveniência | Variantes/Aliases |
    |-------|-------------|-----------|--------------|-------------------|
    | ORCID | Identificador de pesquisador | confirmada | transcrição @ 28:18 | ORSID |
    | SETEC | Secretaria de Educação Profissional e Tecnológica | alta | web:mec.gov.br | CETEC |

    ## NARRATIVA
    A reunião tratou do Portal Integra e sua adoção pela UFSCar.

    ## PENDENCIAS
    - Confirmar quem é SPEAKER_01.
    """
)


class TestParse:
    def test_extracts_table_rows(self):
        parsed = parse_agent_output(AGENT_OUTPUT)
        rows = parsed["tabela"]
        assert len(rows) == 2
        assert rows[0]["sigla"] == "ORCID"
        assert rows[0]["significado"].startswith("Identificador")
        assert rows[0]["confianca"] == "confirmada"
        assert rows[0]["aliases"] == ["ORSID"]

    def test_captures_narrativa_and_pendencias(self):
        parsed = parse_agent_output(AGENT_OUTPUT)
        assert "Portal Integra" in parsed["narrativa"]
        assert "SPEAKER_01" in parsed["pendencias"]

    def test_tolerant_to_heading_level_and_accents(self):
        variant = AGENT_OUTPUT.replace("## TABELA_RESOLVIDA", "### TABELA_RESOLVIDA")
        variant = variant.replace("## PENDENCIAS", "### PENDÊNCIAS")
        parsed = parse_agent_output(variant)
        assert len(parsed["tabela"]) == 2
        assert "SPEAKER_01" in parsed["pendencias"]

    def test_missing_table_raises_informative(self):
        with pytest.raises(ValueError) as exc:
            parse_agent_output("nenhum bloco aqui")
        assert "TABELA_RESOLVIDA" in str(exc.value)

    def test_second_table_header_not_parsed_as_data(self):
        # bug real: uma 2ª tabela no mesmo bloco não pode virar um termo "Sigla"
        out = textwrap.dedent(
            """
            ## TABELA_RESOLVIDA
            | Sigla | Significado | Confiança | Proveniência |
            |---|---|---|---|
            | CGD | Comitê | confirmada | ref |

            ### Termos novos
            | Sigla | Significado provável | Confiança | Proveniência |
            |---|---|---|---|
            | SEI | Sistema Eletrônico | média | transcrição |
            """
        )
        parsed = parse_agent_output(out)
        siglas = [r["sigla"] for r in parsed["tabela"]]
        assert "Sigla" not in siglas          # header repetido ignorado
        assert "CGD" in siglas and "SEI" in siglas


class TestValidateField:
    def test_rejects_yaml_tag_injection(self):
        with pytest.raises(ValueError):
            validate_field("!!python/object/apply:os.system ['rm -rf /']")

    def test_rejects_newline_and_control_chars(self):
        with pytest.raises(ValueError):
            validate_field("linha1\nlinha2")

    def test_accepts_normal_meaning(self):
        assert validate_field("Comitê Gestor de Dados") == "Comitê Gestor de Dados"


class TestImport:
    def _cfg_text(self):
        return textwrap.dedent(
            """
            project: "Teste"
            glossary:
              context: "ctx"
              terms:
                - term: ORCID   # já existia
                  meaning: null
                  aliases: []
            """
        )

    def test_updates_meaning_preserving_comment(self, tmp_path):
        p = tmp_path / "atado.yaml"
        p.write_text(self._cfg_text(), encoding="utf-8")
        cmap = load_commented(p)
        parsed = parse_agent_output(AGENT_OUTPUT)
        updated, summary = import_into_config(cmap, parsed)
        out_text = dumps_commented(updated)
        assert "Identificador de pesquisador" in out_text
        assert "# já existia" in out_text  # comentário preservado (E6)

    def test_adds_new_term_and_merges_aliases(self, tmp_path):
        p = tmp_path / "atado.yaml"
        p.write_text(self._cfg_text(), encoding="utf-8")
        cmap = load_commented(p)
        parsed = parse_agent_output(AGENT_OUTPUT)
        updated, summary = import_into_config(cmap, parsed)
        out_text = dumps_commented(updated)
        # SETEC era novo termo -> adicionado; alias CETEC presente
        assert "SETEC" in out_text
        assert "CETEC" in out_text
        # ORSID veio como alias de ORCID
        p2 = tmp_path / "out.yaml"
        p2.write_text(out_text, encoding="utf-8")
        cfg = load_config(p2)
        orcid = [t for t in cfg.glossary.terms if t.term == "ORCID"][0]
        assert "ORSID" in orcid.aliases

    def test_sentinels_are_canonical(self):
        assert SENTINELS["tabela"] == "TABELA_RESOLVIDA"
        assert SENTINELS["narrativa"] == "NARRATIVA"
        assert SENTINELS["pendencias"] == "PENDENCIAS"
