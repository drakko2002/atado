import json

import pytest
from pydantic import ValidationError

from atado.models import TranscriptDoc, Segment, Word, TranscriptMeta


def make_seg(**kw):
    base = dict(start=0.0, end=1.0, text="olá")
    base.update(kw)
    return Segment(**base)


class TestSegment:
    def test_minimal_segment_has_no_speaker(self):
        seg = make_seg()
        assert seg.speaker is None
        assert seg.words == []

    def test_speaker_optional_present(self):
        seg = make_seg(speaker="SPEAKER_01")
        assert seg.speaker == "SPEAKER_01"

    def test_words_carry_timings(self):
        seg = make_seg(words=[Word(word="olá", start=0.0, end=0.4, score=0.9)])
        assert seg.words[0].word == "olá"
        assert seg.words[0].score == 0.9

    def test_end_before_start_is_rejected(self):
        with pytest.raises(ValidationError):
            make_seg(start=5.0, end=1.0)


class TestTranscriptDoc:
    def test_roundtrip_json(self):
        doc = TranscriptDoc(
            meta=TranscriptMeta(
                source_file="audio_01.mp3",
                duration=10.0,
                model="large-v3",
                language="pt",
                diarized=False,
                atado_version="0.1.0",
            ),
            segments=[make_seg(text="a CETEC vai encaminhar", speaker="SPEAKER_00")],
        )
        raw = doc.model_dump_json()
        back = TranscriptDoc.model_validate_json(raw)
        assert back.segments[0].text == "a CETEC vai encaminhar"
        assert back.meta.source_file == "audio_01.mp3"

    def test_from_plain_dict(self):
        # simula o shape que o whisperx/asr.py entrega
        data = {
            "meta": {"source_file": "x.wav", "duration": 3.0, "model": "large-v3",
                     "language": "pt", "diarized": True, "atado_version": "0.1.0"},
            "segments": [{"start": 0.0, "end": 3.0, "text": "oi", "speaker": "SPEAKER_00",
                          "words": [{"word": "oi", "start": 0.0, "end": 0.5}]}],
        }
        doc = TranscriptDoc.model_validate(data)
        assert doc.meta.diarized is True
        assert doc.segments[0].words[0].word == "oi"

    def test_compact_dump_drops_words(self):
        # consolidated.json compacto: sem words[] (SPEC A §7)
        doc = TranscriptDoc(
            meta=TranscriptMeta(source_file="x", duration=1.0, model="m",
                                language="pt", diarized=False, atado_version="0.1.0"),
            segments=[make_seg(words=[Word(word="oi", start=0.0, end=0.5)])],
        )
        compact = doc.compact_dict()
        assert "words" not in compact["segments"][0]
        assert compact["segments"][0]["text"] == "olá"
