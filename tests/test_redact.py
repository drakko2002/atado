from atado.redact import redact_text, Redactor


class TestRedactText:
    def test_redacts_email(self):
        red = Redactor()
        out = red.redact("meu contato é fulano@ufscar.br ok")
        assert "fulano@ufscar.br" not in out
        assert "[[PII-" in out

    def test_redacts_formatted_cpf(self):
        red = Redactor()
        out = red.redact("CPF 123.456.789-09 registrado")
        assert "123.456.789-09" not in out
        assert "[[PII-" in out

    def test_redacts_phone(self):
        red = Redactor()
        out = red.redact("ligue (16) 99123-4567 hoje")
        assert "99123-4567" not in out

    def test_same_pii_same_placeholder(self):
        red = Redactor()
        out = red.redact("a@b.com e de novo a@b.com")
        # mesmo e-mail -> mesmo placeholder
        placeholders = [p for p in out.split() if p.startswith("[[PII-")]
        assert len(set(placeholders)) == 1

    def test_mapping_is_populated_and_reversible(self):
        red = Redactor()
        red.redact("email a@b.com")
        # o mapa guarda placeholder -> original
        assert any(v == "a@b.com" for v in red.mapping.values())

    def test_non_pii_preserved(self):
        red = Redactor()
        out = red.redact("a reunião discutiu o Portal Integra")
        assert out == "a reunião discutiu o Portal Integra"

    def test_module_helper_roundtrips(self):
        text = "contato x@y.com"
        out, mapping = redact_text(text)
        assert "x@y.com" not in out
        assert "x@y.com" in mapping.values()
