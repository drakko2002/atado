from atado.chunks import plan_chunks, merge_chunks, Chunk
from atado.models import TranscriptDoc, TranscriptMeta, Segment, Word


def _doc(segs):
    return TranscriptDoc(
        meta=TranscriptMeta(source_file="x", duration=10.0, model="m", language="pt",
                            diarized=False, atado_version="0.1.0"),
        segments=segs,
    )


class TestPlanChunks:
    def test_short_file_single_chunk(self):
        chunks = plan_chunks(duration=120.0, chunk_length=600.0, chunk_overlap=3.0)
        assert len(chunks) == 1
        assert chunks[0].start == 0.0 and chunks[0].end == 120.0

    def test_long_file_covers_full_duration_with_overlap(self):
        chunks = plan_chunks(duration=1500.0, chunk_length=600.0, chunk_overlap=3.0)
        assert chunks[0].start == 0.0
        assert chunks[-1].end == 1500.0            # cobre até o fim
        # cada chunk seguinte começa com overlap (antes do fim do anterior)
        for a, b in zip(chunks, chunks[1:]):
            assert b.start < a.end
            assert abs((a.end - b.start) - 3.0) < 1e-6

    def test_snaps_boundary_to_silence(self):
        # fronteira alvo 600; há silêncio em 590 dentro da janela de 30s → corta em 590
        chunks = plan_chunks(duration=1200.0, chunk_length=600.0, chunk_overlap=3.0,
                             silences=[590.0], silence_snap=30.0)
        assert abs(chunks[0].end - 590.0) < 1e-6


class TestMergeChunks:
    def test_shifts_and_dedups_overlap(self):
        c0 = Chunk(0, 0.0, 10.0)
        c1 = Chunk(1, 7.0, 17.0)
        d0 = _doc([Segment(start=0.0, end=4.0, text="a"),
                   Segment(start=4.0, end=8.0, text="b fronteira")])
        # chunk1 local: "b fronteira" em 0-1 (=file 7-8, duplicata) e "c" em 1-5 (=file 8-12)
        d1 = _doc([Segment(start=0.0, end=1.0, text="b fronteira"),
                   Segment(start=1.0, end=5.0, text="c")])
        merged = merge_chunks([c0, c1], [d0, d1])
        texts = [s.text for s in merged]
        assert texts == ["a", "b fronteira", "c"]      # sem duplicata
        # timestamps em tempo local-do-arquivo
        assert merged[2].start == 8.0 and merged[2].end == 12.0

    def test_shifts_words(self):
        c0 = Chunk(0, 100.0, 110.0)
        d0 = _doc([Segment(start=2.0, end=4.0, text="oi",
                           words=[Word(word="oi", start=2.0, end=2.5)])])
        merged = merge_chunks([c0], [d0])
        assert merged[0].start == 102.0
        assert merged[0].words[0].start == 102.0


def test_dedups_temporally_overlapping_boundary_duplicates():
    # chunk0 [0,600] e chunk1 [597,1197] ambos transcrevem o trecho 597-600 (fronteira)
    c0 = Chunk(0, 0.0, 600.0)
    c1 = Chunk(1, 597.0, 1197.0)
    d0 = _doc([Segment(start=594.0, end=600.0, text="e nesse momento em 2024")])
    d1 = _doc([Segment(start=0.0, end=3.0, text="e nesse momento em 2024"),   # =file 597-600 (dup)
               Segment(start=3.0, end=8.0, text="nos comecamos a conversar")])
    merged = merge_chunks([c0, c1], [d0, d1])
    texts = [s.text for s in merged]
    assert texts.count("e nesse momento em 2024") == 1     # dup de fronteira removida
    assert "nos comecamos a conversar" in texts


def test_disjoint_repeats_are_kept():
    # fala legitimamente repetida em tempos DISJUNTOS não pode ser removida
    c0 = Chunk(0, 0.0, 600.0)
    d0 = _doc([Segment(start=10.0, end=12.0, text="obrigado"),
               Segment(start=300.0, end=302.0, text="obrigado")])
    merged = merge_chunks([c0], [d0])
    assert [s.text for s in merged].count("obrigado") == 2
