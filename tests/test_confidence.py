from atado.config import AtadoConfig
from atado.models import TranscriptDoc, TranscriptMeta, Segment, Word
from atado.confidence import (segment_confidence, overall_confidence,
                              low_confidence_segments, render_confidence_markdown)


def _seg(start, end, text, scores):
    return Segment(start=start, end=end, text=text,
                   words=[Word(word=w, start=start, end=end, score=sc)
                          for w, sc in zip(text.split(), scores)])


def _doc(name, segs, source_start=None):
    return TranscriptDoc(
        meta=TranscriptMeta(source_file=name, duration=100.0, model="m", language="pt",
                            diarized=False, atado_version="0.1.0", source_start=source_start),
        segments=segs)


def test_segment_confidence_is_mean_word_score():
    s = _seg(0, 1, "a b c", [0.9, 0.8, 0.7])
    assert abs(segment_confidence(s) - 0.8) < 1e-6


def test_segment_without_scores_returns_none():
    s = Segment(start=0, end=1, text="oi")
    assert segment_confidence(s) is None


def test_overall_confidence_mean_over_segments():
    doc = _doc("a", [_seg(0, 1, "x y", [1.0, 1.0]), _seg(1, 2, "z w", [0.0, 0.0])])
    assert abs(overall_confidence([doc]) - 0.5) < 1e-6


def test_low_confidence_flags_below_threshold_sorted():
    doc = _doc("a", [
        _seg(0, 1, "alta conf", [0.95, 0.95]),
        _seg(1, 2, "baixa aqui", [0.30, 0.40]),
        _seg(2, 3, "media coisa", [0.60, 0.62]),
    ])
    flagged = low_confidence_segments([doc], threshold=0.7, max_items=10)
    confs = [f["confidence"] for f in flagged]
    assert confs == sorted(confs)               # ordenado por confiança asc
    assert all(c < 0.7 for c in confs)
    assert flagged[0]["text"] == "baixa aqui"   # o pior primeiro


def test_low_confidence_has_global_time_with_offset():
    doc = _doc("a", [_seg(3.0, 4.0, "baixa aqui", [0.2, 0.3])], source_start=480.0)
    cfg = AtadoConfig()
    flagged = low_confidence_segments([doc], threshold=0.7, cfg=cfg)
    assert flagged[0]["global_start"] == 483.0


def test_render_markdown_lists_flagged():
    doc = _doc("a", [_seg(1, 2, "duvidoso trecho", [0.2, 0.3])])
    md = render_confidence_markdown([doc], AtadoConfig(), threshold=0.7)
    assert "duvidoso trecho" in md
    assert "confiança" in md.lower()
