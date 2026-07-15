from atado.config import Glossary, GlossaryTerm
from atado.glossary import (
    normalize,
    build_initial_prompt,
    apply_corrections,
    is_acronym_like,
)


WORDLIST = {"a", "nossa", "secretaria", "vai", "encaminhar", "e", "o", "de", "que", "gente"}


def gloss():
    return Glossary(
        context="Reunião do Comitê Gestor de Dados (CGD), IFRS e UFSCar.",
        terms=[
            GlossaryTerm(term="CGD", meaning="Comitê Gestor de Dados"),
            GlossaryTerm(term="CETEC", meaning=None, aliases=["CETEQ", "SETEC"]),
            GlossaryTerm(term="PROSAS", meaning="Plataforma de editais"),
        ],
    )


class TestNormalize:
    def test_casefold_and_strip_accents(self):
        assert normalize("Secretária") == "secretaria"

    def test_upper_acronym_lowercased(self):
        assert normalize("CETEQ") == "ceteq"


class TestInitialPrompt:
    def test_includes_context_and_terms_with_meanings(self):
        p = build_initial_prompt(gloss())
        assert "Comitê Gestor de Dados" in p
        assert "CGD" in p and "CETEC" in p and "PROSAS" in p

    def test_aliases_not_in_prompt(self):
        # §4.1: aliases NÃO entram no prompt (só no passe de correção)
        p = build_initial_prompt(gloss())
        assert "CETEQ" not in p
        assert "SETEC" not in p

    def test_respects_token_budget_by_truncating_context(self):
        g = gloss()
        g.context = "palavra " * 500  # contexto enorme
        p = build_initial_prompt(g, max_tokens=60)
        # termos preservados, contexto truncado
        assert "CGD" in p and "CETEC" in p
        assert len(p) < len("palavra " * 500)


class TestIsAcronymLike:
    def test_all_caps_short(self):
        assert is_acronym_like("CETEC")

    def test_internal_caps(self):
        assert is_acronym_like("DSpace")

    def test_common_lowercase_word_is_not(self):
        assert not is_acronym_like("secretaria")


class TestApplyCorrections:
    def test_corrects_exact_alias_lowercased_by_whisper(self):
        # Whisper emite minúsculo: "ceteq" deve virar "CETEC" (alias exato após normalizar)
        text = "a nossa ceteq vai encaminhar"
        out, subs = apply_corrections(text, gloss(), WORDLIST, threshold=80)
        assert "CETEC" in out
        assert ("ceteq", "CETEC") in [(o, c) for o, c in subs]

    def test_corrects_unlisted_near_variant_at_threshold(self):
        # "cetece" não está listado mas casa por similaridade com CETEC
        text = "o cetece respondeu"
        out, subs = apply_corrections(text, gloss(), WORDLIST, threshold=80)
        assert "CETEC" in out

    def test_never_touches_common_wordlist_words(self):
        # "secretaria" está na wordlist — nunca corrigir, mesmo perto de alguma sigla
        text = "a nossa secretaria vai encaminhar"
        out, subs = apply_corrections(text, gloss(), WORDLIST, threshold=80)
        assert out == text
        assert subs == []

    def test_counts_multiple_occurrences(self):
        text = "ceteq e ceteq e ceteq"
        out, subs = apply_corrections(text, gloss(), WORDLIST, threshold=80)
        pairs = [(o, c) for o, c in subs]
        assert pairs.count(("ceteq", "CETEC")) == 3

    def test_already_correct_token_not_counted(self):
        text = "o CETEC respondeu"
        out, subs = apply_corrections(text, gloss(), WORDLIST, threshold=80)
        assert "CETEC" in out
        assert subs == []  # já estava certo, sem substituição

    def test_every_listed_alias_crosses_threshold(self):
        # E2: garantia de que todo alias listado é corrigível
        g = gloss()
        for term in g.terms:
            for alias in term.aliases:
                out, subs = apply_corrections(alias.lower(), g, WORDLIST, threshold=80)
                assert term.term in out, f"alias {alias} não corrigiu para {term.term}"
