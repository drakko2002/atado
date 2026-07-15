from atado.config import AtadoConfig, FileEntry
from atado.models import TranscriptDoc, TranscriptMeta, Segment
from atado.merge import natural_key, order_docs, consolidate_markdown, consolidate_json


def doc(name, segs, source_start=None, duration=10.0):
    return TranscriptDoc(
        meta=TranscriptMeta(source_file=name, duration=duration, model="large-v3",
                            language="pt", diarized=bool(segs and segs[0].speaker),
                            atado_version="0.1.0", source_start=source_start),
        segments=segs,
    )


def seg(start, end, text, speaker=None):
    return Segment(start=start, end=end, text=text, speaker=speaker)


class TestNaturalKey:
    def test_numeric_ordering(self):
        names = ["audio_10.json", "audio_2.json", "audio_1.json"]
        assert sorted(names, key=natural_key) == ["audio_1.json", "audio_2.json", "audio_10.json"]

    def test_whatsapp_base_before_duplicate_suffixes(self):
        names = [
            "WhatsApp Audio 2026-07-15 at 17.07.36(2).mp3",
            "WhatsApp Audio 2026-07-15 at 17.07.36.mp3",
            "WhatsApp Audio 2026-07-15 at 17.07.36(1).mp3",
        ]
        got = sorted(names, key=natural_key)
        assert got[0].endswith("17.07.36.mp3")
        assert got[1].endswith("36(1).mp3")
        assert got[2].endswith("36(2).mp3")


class TestOrderDocs:
    def test_order_by_name(self):
        cfg = AtadoConfig(order="name")
        docs = [doc("b.mp3", []), doc("a.mp3", [])]
        got = [d.meta.source_file for d in order_docs(docs, cfg)]
        assert got == ["a.mp3", "b.mp3"]

    def test_order_by_offset(self):
        cfg = AtadoConfig(order="offset")
        docs = [doc("late.mp3", [], source_start=480.0),
                doc("early.mp3", [], source_start=60.0)]
        got = [d.meta.source_file for d in order_docs(docs, cfg)]
        assert got == ["early.mp3", "late.mp3"]

    def test_offset_missing_sorts_last(self):
        cfg = AtadoConfig(order="offset")
        docs = [doc("nooff.mp3", []), doc("withoff.mp3", [], source_start=60.0)]
        got = [d.meta.source_file for d in order_docs(docs, cfg)]
        assert got == ["withoff.mp3", "nooff.mp3"]

    def test_manual_order(self):
        cfg = AtadoConfig(order="manual", manual_order=["z.mp3", "a.mp3"])
        docs = [doc("a.mp3", []), doc("z.mp3", [])]
        got = [d.meta.source_file for d in order_docs(docs, cfg)]
        assert got == ["z.mp3", "a.mp3"]


class TestConsolidateMarkdown:
    def test_local_only_when_no_offset(self):
        cfg = AtadoConfig(order="name")
        docs = [doc("a.mp3", [seg(3.0, 5.0, "olá CETEC", "SPEAKER_00")])]
        md = consolidate_markdown(docs, cfg)
        assert "a.mp3" in md
        assert "00:03" in md
        assert "SPEAKER_00" in md
        assert "olá CETEC" in md

    def test_global_and_local_when_offset(self):
        cfg = AtadoConfig(order="offset")
        docs = [doc("a.mp3", [seg(3.0, 5.0, "olá", "SPEAKER_00")], source_start=480.0)]
        md = consolidate_markdown(docs, cfg)
        # 480 + 3 = 483s = 08:03 global; local 00:03
        assert "08:03" in md
        assert "00:03" in md

    def test_header_has_summary(self):
        cfg = AtadoConfig(order="name")
        docs = [doc("a.mp3", [seg(0.0, 1.0, "oi", "SPEAKER_00")]),
                doc("b.mp3", [seg(0.0, 1.0, "tchau", "SPEAKER_01")])]
        md = consolidate_markdown(docs, cfg)
        assert "2" in md  # nº de áudios no sumário


class TestConsolidateJson:
    def test_compact_no_words_and_global_start(self):
        cfg = AtadoConfig(order="offset")
        docs = [doc("a.mp3", [seg(3.0, 5.0, "oi", "SPEAKER_00")], source_start=480.0)]
        data = consolidate_json(docs, cfg)
        f0 = data["files"][0]
        assert f0["source_file"] == "a.mp3"
        s0 = f0["segments"][0]
        assert "words" not in s0
        assert s0["global_start"] == 483.0
