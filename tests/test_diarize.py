import pytest

from atado.models import Segment
from atado.asr_diarize import assign_speakers_by_overlap, diarize_doc, DiarizationError
from atado.models import TranscriptDoc, TranscriptMeta


def test_assigns_speaker_by_max_overlap():
    segs = [Segment(start=0.0, end=2.0, text="oi"), Segment(start=2.0, end=4.0, text="tchau")]
    turns = [(0.0, 1.9, "SPEAKER_00"), (2.0, 4.0, "SPEAKER_01")]
    assign_speakers_by_overlap(segs, turns)
    assert segs[0].speaker == "SPEAKER_00"
    assert segs[1].speaker == "SPEAKER_01"


def test_segment_without_overlap_stays_unassigned():
    segs = [Segment(start=10.0, end=12.0, text="x")]
    turns = [(0.0, 1.0, "SPEAKER_00")]
    assign_speakers_by_overlap(segs, turns)
    assert segs[0].speaker is None


def test_diarize_without_token_raises_friendly():
    doc = TranscriptDoc(
        meta=TranscriptMeta(source_file="a.wav", duration=1.0, model="m",
                            language="pt", diarized=False, atado_version="0.1.0"),
        segments=[Segment(start=0.0, end=1.0, text="oi")],
    )
    with pytest.raises(DiarizationError) as exc:
        diarize_doc(doc, "a.wav", hf_token=None)
    assert "HF_TOKEN" in str(exc.value)
