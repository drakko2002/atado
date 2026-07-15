from atado.reconstruct import run_session, last_assistant_message
from atado.providers.base import get_provider, ProviderError, ChatProvider


class FakeProvider:
    name = "fake"

    def __init__(self):
        self.calls = 0
        self.seen_system = None

    def supports_search(self):
        return False

    def chat(self, messages, *, model=None, system=None):
        self.calls += 1
        self.seen_system = system
        if self.calls == 1:
            return "Plano: vou pesquisar CETEC e perguntar sobre SIAPE."
        return "## TABELA_RESOLVIDA\n| Sigla | Significado |\n|---|---|\n| CETEC | X |"


def test_fake_provider_satisfies_protocol():
    assert isinstance(FakeProvider(), ChatProvider)


def test_session_loops_until_stop():
    prov = FakeProvider()
    inputs = iter(["quem é SPEAKER_00?", "encerrar"])
    outputs = []
    session = run_session(
        prov, system_prompt="PROTO", initial_user="corpus aqui",
        input_fn=lambda: next(inputs), output_fn=outputs.append,
    )
    assert prov.calls == 2               # respondeu 2x, parou no 'encerrar'
    assert prov.seen_system == "PROTO"   # protocolo injetado como system
    assert len(outputs) == 2
    # mensagens: user(corpus), assistant, user(pergunta), assistant
    roles = [m["role"] for m in session["messages"]]
    assert roles == ["user", "assistant", "user", "assistant"]


def test_last_assistant_message_extracts_final_block():
    prov = FakeProvider()
    inputs = iter(["ok", "encerrar"])
    session = run_session(prov, "P", "c", input_fn=lambda: next(inputs),
                          output_fn=lambda x: None)
    assert "TABELA_RESOLVIDA" in last_assistant_message(session)


def test_eof_input_stops_session():
    prov = FakeProvider()
    session = run_session(prov, "P", "c", input_fn=lambda: None, output_fn=lambda x: None)
    assert prov.calls == 1  # 1 resposta, depois EOF encerra


def test_unknown_provider_raises():
    import pytest
    with pytest.raises(ProviderError):
        get_provider("inexistente")


def test_resume_from_assistant_ending_reads_user_first():
    # regressão: sessão salva termina em 'assistant'; ao resumir, NÃO pode haver
    # dois 'assistant' seguidos (quebraria a Messages API).
    prov = FakeProvider()
    prior = [
        {"role": "user", "content": "corpus"},
        {"role": "assistant", "content": "plano"},
    ]
    inputs = iter(["minha resposta", "encerrar"])
    session = run_session(prov, "P", "corpus", input_fn=lambda: next(inputs),
                          output_fn=lambda x: None, prior_messages=prior)
    roles = [m["role"] for m in session["messages"]]
    # nunca dois 'assistant' consecutivos
    assert not any(roles[i] == roles[i + 1] == "assistant" for i in range(len(roles) - 1))
    # a fala do usuário entra antes do próximo assistant
    assert roles[:4] == ["user", "assistant", "user", "assistant"]
