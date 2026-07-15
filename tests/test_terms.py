from atado.config import AtadoConfig, Glossary, GlossaryTerm, OutputCfg
from atado.models import TranscriptDoc, TranscriptMeta, Segment, Word
from atado.terms import find_occurrences, render_terms_markdown, render_terms_csv, find_suspects


def doc(name, segs, source_start=None, duration=10.0):
    return TranscriptDoc(
        meta=TranscriptMeta(source_file=name, duration=duration, model="m",
                            language="pt", diarized=True, atado_version="0.1.0",
                            source_start=source_start),
        segments=segs,
    )


def seg(start, end, text, speaker="SPEAKER_00", words=None):
    return Segment(start=start, end=end, text=text, speaker=speaker, words=words or [])


class TestFindOccurrences:
    def test_finds_term_case_insensitive(self):
        cfg = AtadoConfig(output=OutputCfg(context_window_seconds=20))
        docs = [doc("a.mp3", [seg(3.0, 6.0, "então a cetec vai encaminhar")])]
        idx = find_occurrences(docs, [("CETEC", None)], cfg)
        assert len(idx["CETEC"]) == 1
        occ = idx["CETEC"][0]
        assert occ["file"] == "a.mp3"
        assert occ["speaker"] == "SPEAKER_00"

    def test_global_time_with_offset(self):
        cfg = AtadoConfig()
        docs = [doc("a.mp3", [seg(3.0, 6.0, "a CETEC respondeu")], source_start=480.0)]
        idx = find_occurrences(docs, [("CETEC", None)], cfg)
        assert idx["CETEC"][0]["global_start"] == 483.0

    def test_whole_word_only(self):
        cfg = AtadoConfig()
        docs = [doc("a.mp3", [seg(0.0, 2.0, "o CGDX não é CGD")])]
        idx = find_occurrences(docs, [("CGD", None)], cfg)
        assert len(idx["CGD"]) == 1  # casa CGD, não CGDX

    def test_context_window_gathers_neighbors(self):
        cfg = AtadoConfig(output=OutputCfg(context_window_seconds=20))
        docs = [doc("a.mp3", [
            seg(0.0, 4.0, "contexto antes"),
            seg(4.0, 8.0, "aqui fala da CETEC agora"),
            seg(8.0, 12.0, "contexto depois"),
        ], duration=12.0)]
        idx = find_occurrences(docs, [("CETEC", None)], cfg)
        ctx = idx["CETEC"][0]["context"]
        assert "antes" in ctx and "depois" in ctx


class TestRender:
    def test_markdown_has_term_section_and_coverage(self):
        cfg = AtadoConfig()
        docs = [doc("a.mp3", [seg(3.0, 6.0, "a CETEC vai")])]
        idx = find_occurrences(docs, [("CETEC", "significado?")], cfg)
        md = render_terms_markdown(idx, {"CETEC": "significado?"}, cfg, n_files=1)
        assert "## CETEC" in md
        assert "1 ocorrência" in md
        assert "recortes" in md.lower()  # nota de cobertura

    def test_csv_has_header_and_rows(self):
        cfg = AtadoConfig()
        docs = [doc("a.mp3", [seg(3.0, 6.0, "a CETEC vai")], source_start=480.0)]
        idx = find_occurrences(docs, [("CETEC", None)], cfg)
        csv_text = render_terms_csv(idx, {"CETEC": None})
        lines = csv_text.strip().splitlines()
        assert lines[0].startswith("term,")
        assert "CETEC" in lines[1]


class TestSuspects:
    def test_flags_unknown_repeated_token(self):
        wordlist = {"a", "o", "vai", "de", "que", "e"}
        known = {"cetec"}
        docs = [doc("a.mp3", [
            seg(0.0, 2.0, "o ORSID respondeu"),
            seg(2.0, 4.0, "de novo o ORSID"),
        ])]
        sus = find_suspects(docs, known, wordlist, min_count=2)
        terms = [s["token"] for s in sus]
        assert any(normalize_eq(t, "ORSID") for t in terms)

    def test_excludes_glossary_and_wordlist(self):
        wordlist = {"secretaria", "a", "vai"}
        known = {"cetec"}
        docs = [doc("a.mp3", [
            seg(0.0, 2.0, "a CETEC e a secretaria"),
            seg(2.0, 4.0, "a CETEC e a secretaria"),
        ])]
        sus = find_suspects(docs, known, wordlist, min_count=2)
        toks = [s["token"].lower() for s in sus]
        assert "cetec" not in toks
        assert "secretaria" not in toks


def normalize_eq(a, b):
    return a.casefold() == b.casefold()
