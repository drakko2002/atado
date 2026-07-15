import pytest

from atado.timeutil import parse_timestamp, format_hms, to_global


class TestParseTimestamp:
    def test_parses_seconds_float(self):
        assert parse_timestamp(12.5) == 12.5

    def test_parses_mm_ss(self):
        assert parse_timestamp("08:03") == 8 * 60 + 3

    def test_parses_h_mm_ss(self):
        assert parse_timestamp("2:28:07") == 2 * 3600 + 28 * 60 + 7

    def test_parses_bare_seconds_string(self):
        assert parse_timestamp("45") == 45.0

    def test_parses_hh_mm_ss_with_leading_zero(self):
        assert parse_timestamp("00:08:03") == 8 * 60 + 3

    def test_rejects_garbage(self):
        with pytest.raises(ValueError):
            parse_timestamp("banana")

    def test_rejects_none(self):
        with pytest.raises(ValueError):
            parse_timestamp(None)


class TestFormatHms:
    def test_under_one_hour_is_mm_ss(self):
        assert format_hms(8 * 60 + 3) == "08:03"

    def test_over_one_hour_is_h_mm_ss(self):
        assert format_hms(2 * 3600 + 0 * 60 + 27) == "2:00:27"

    def test_rounds_to_whole_seconds(self):
        assert format_hms(8 * 60 + 3.6) == "08:04"


class TestToGlobal:
    def test_adds_offset_to_local(self):
        # recorte começa em 08:00 do encontro; termo aos 3s locais -> 08:03 global
        assert to_global(parse_timestamp("08:00"), 3.0) == 8 * 60 + 3

    def test_none_offset_returns_none(self):
        assert to_global(None, 3.0) is None
