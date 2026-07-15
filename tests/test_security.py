from atado.security import mask_secrets, scan_text, looks_like_secret


def test_masks_hf_token():
    t = "erro ao usar hf_abcdefghijklmnopqrstuvwxyz0123456789 no download"
    out = mask_secrets(t)
    assert "hf_abcdefghijklmnopqrstuvwxyz" not in out
    assert "[[HF_TOKEN_REDACTED]]" in out


def test_masks_provider_keys():
    assert "[[ANTHROPIC_KEY_REDACTED]]" in mask_secrets("sk-ant-abc123def456ghi789jkl012mno")
    assert "[[OPENAI_KEY_REDACTED]]" in mask_secrets("sk-abcdefghij0123456789ABCDEFXYZ")


def test_scan_detects_and_labels():
    assert "HF_TOKEN" in scan_text("token hf_abcdefghijklmnopqrstuvwxyz0123456789")
    assert scan_text("nada de segredo aqui") == []


def test_looks_like_secret():
    assert looks_like_secret("hf_abcdefghijklmnopqrstuvwxyz0123456789")
    assert not looks_like_secret("Comitê Gestor de Dados")


def test_non_secret_text_unchanged():
    t = "A reunião do CGD discutiu o Portal Integra e o SIAPE."
    assert mask_secrets(t) == t
