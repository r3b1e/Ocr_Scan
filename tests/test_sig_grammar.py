"""Table-driven tests for core.sig_grammar (Indian prescription shorthand)."""

from __future__ import annotations

import pytest

from core.sig_grammar import (
    SigParse,
    normalise_strength,
    parse_duration,
    parse_form,
    parse_frequency,
    parse_timing,
    strip_form_prefix,
    validate_dose,
)

M, A, E, N = "morning", "afternoon", "evening", "night"


@pytest.mark.parametrize(
    ("text", "pattern", "times", "slots"),
    [
        ("1-0-1", "1-0-1", 2, [M, N]),
        ("1-1-1", "1-1-1", 3, [M, A, N]),
        ("0-0-1", "0-0-1", 1, [N]),
        ("1-0-0", "1-0-0", 1, [M]),
        ("0-1-0", "0-1-0", 1, [A]),
        ("1 - 0 - 1", "1-0-1", 2, [M, N]),
        ("1–0–1", "1-0-1", 2, [M, N]),
        ("1-0-0-1", "1-0-0-1", 2, [M, N]),
        ("1-1-1-1", "1-1-1-1", 4, [M, A, E, N]),
        ("2-0-2", "2-0-2", 2, [M, N]),
        ("OD", "OD", 1, [M]),
        ("od", "OD", 1, [M]),
        ("once daily", "OD", 1, [M]),
        ("once a day", "OD", 1, [M]),
        ("daily", "OD", 1, [M]),
        ("BD", "BD", 2, [M, N]),
        ("BID", "BD", 2, [M, N]),
        ("b.d.", "BD", 2, [M, N]),
        ("twice daily", "BD", 2, [M, N]),
        ("twice a day", "BD", 2, [M, N]),
        ("2 times a day", "BD", 2, [M, N]),
        ("TDS", "TDS", 3, [M, A, N]),
        ("TID", "TDS", 3, [M, A, N]),
        ("t.d.s", "TDS", 3, [M, A, N]),
        ("thrice daily", "TDS", 3, [M, A, N]),
        ("three times a day", "TDS", 3, [M, A, N]),
        ("3 times daily", "TDS", 3, [M, A, N]),
        ("QID", "QID", 4, [M, A, E, N]),
        ("four times a day", "QID", 4, [M, A, E, N]),
        ("4 times a day", "QID", 4, [M, A, E, N]),
        ("HS", "HS", 1, [N]),
        ("at bedtime", "HS", 1, [N]),
        ("nocte", "HS", 1, [N]),
        ("at night", "HS", 1, [N]),
        ("1-0-1 A/F", "1-0-1", 2, [M, N]),
        ("BD x 5 days", "BD", 2, [M, N]),
        ("Tab 1-0-1 after food for 5 days", "1-0-1", 2, [M, N]),
    ],
)
def test_parse_frequency_patterns(text, pattern, times, slots):
    result = parse_frequency(text)
    assert result.parsed is True
    assert result.frequency.pattern == pattern
    assert result.frequency.times_per_day == times
    assert result.frequency.slots == slots
    assert result.frequency.as_needed is False


@pytest.mark.parametrize("text", ["SOS", "sos", "PRN", "when required", "if needed", "as needed"])
def test_parse_frequency_as_needed(text):
    result = parse_frequency(text)
    assert result.parsed is True
    assert result.frequency.as_needed is True
    assert result.frequency.times_per_day is None


@pytest.mark.parametrize(
    ("text", "hours", "times"),
    [
        ("q6h", 6, 4),
        ("Q8H", 8, 3),
        ("every 8 hours", 8, 3),
        ("8 hourly", 8, 3),
        ("every 6 hrs", 6, 4),
        ("q12h", 12, 2),
    ],
)
def test_parse_frequency_intervals(text, hours, times):
    result = parse_frequency(text)
    assert result.parsed is True
    assert result.frequency.interval_hours == hours
    assert result.frequency.times_per_day == times
    assert result.frequency.slots == []


@pytest.mark.parametrize("text", ["once weekly", "weekly", "once a week"])
def test_parse_frequency_weekly(text):
    result = parse_frequency(text)
    assert result.parsed is True
    assert result.frequency.interval_hours == 168
    assert result.frequency.pattern == "weekly"


def test_parse_frequency_fraction_pattern_reports_dose():
    result = parse_frequency("1/2-0-1/2")
    assert result.parsed is True
    assert result.frequency.pattern == "1/2-0-1/2"
    assert result.frequency.times_per_day == 2
    assert result.frequency.slots == [M, N]
    assert result.dose_fraction == "1/2"


def test_parse_frequency_bedtime_sets_timing():
    assert parse_frequency("HS").timing == "bedtime"
    assert parse_frequency("1-0-1 after food").timing == "after_food"
    assert parse_frequency("BD").timing is None


@pytest.mark.parametrize("text", [None, "", "   ", "blah", "take", "---"])
def test_parse_frequency_unparseable(text):
    result = parse_frequency(text)
    assert isinstance(result, SigParse)
    assert result.parsed is False
    assert result.frequency.times_per_day is None and result.frequency.slots == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("A/F", "after_food"),
        ("AF", "after_food"),
        ("after food", "after_food"),
        ("after meals", "after_food"),
        ("after meal", "after_food"),
        ("PC", "after_food"),
        ("p.c.", "after_food"),
        ("post meal", "after_food"),
        ("B/F", "before_food"),
        ("BF", "before_food"),
        ("before food", "before_food"),
        ("before meals", "before_food"),
        ("AC", "before_food"),
        ("a.c.", "before_food"),
        ("empty stomach", "empty_stomach"),
        ("on empty stomach", "empty_stomach"),
        ("with food", "with_food"),
        ("with meals", "with_food"),
        ("with milk", "with_food"),
        ("HS", "bedtime"),
        ("at bedtime", "bedtime"),
        ("at night", "bedtime"),
        ("anytime", "any"),
        (None, None),
        ("", None),
        ("xyz", None),
    ],
)
def test_parse_timing(text, expected):
    assert parse_timing(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("x 5 days", 5),
        ("x5days", 5),
        ("5 days", 5),
        ("for 7 days", 7),
        ("10 d", 10),
        ("for 1 week", 7),
        ("1 week", 7),
        ("2 weeks", 14),
        ("3 wks", 21),
        ("1 wk", 7),
        ("1 month", 30),
        ("2 months", 60),
        ("5/7", 5),
        ("3/52", 21),
        ("1/12", 30),
        ("15 days", 15),
        ("BD x 5 days", 5),
        ("continue", None),
        ("till review", None),
        (None, None),
        ("", None),
        ("0 days", None),
        ("400 days", None),
    ],
)
def test_parse_duration(text, expected):
    assert parse_duration(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Tab", "tablet"),
        ("Tab.", "tablet"),
        ("T.", "tablet"),
        ("TAB", "tablet"),
        ("tablet", "tablet"),
        ("Cap", "capsule"),
        ("caps", "capsule"),
        ("capsule", "capsule"),
        ("Syp", "syrup"),
        ("Syr", "syrup"),
        ("syrup", "syrup"),
        ("susp", "syrup"),
        ("Inj", "injection"),
        ("injection", "injection"),
        ("Oint", "cream"),
        ("ointment", "cream"),
        ("cream", "cream"),
        ("gel", "cream"),
        ("Drops", "drops"),
        ("gtt", "drops"),
        ("eye drops", "drops"),
        ("e/d", "drops"),
        ("Inh", "inhaler"),
        ("inhaler", "inhaler"),
        ("MDI", "inhaler"),
        ("rotacap", "inhaler"),
        ("Pwd", "powder"),
        ("powder", "powder"),
        ("sachet", "powder"),
        ("lotion", None),
        (None, None),
        ("", None),
    ],
)
def test_parse_form(text, expected):
    assert parse_form(text) == expected


@pytest.mark.parametrize(
    ("name", "form", "clean"),
    [
        ("Tab. Dolo 650", "tablet", "Dolo 650"),
        ("TAB DOLO 650", "tablet", "DOLO 650"),
        ("Cap Omez 20", "capsule", "Omez 20"),
        ("Syp Ascoril", "syrup", "Ascoril"),
        ("Dolo 650", None, "Dolo 650"),
        ("Tablet", None, "Tablet"),
        ("", None, ""),
    ],
)
def test_strip_form_prefix(name, form, clean):
    assert strip_form_prefix(name) == (form, clean)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("500MG", "500 mg"),
        ("650 mg", "650 mg"),
        ("5ml", "5 ml"),
        ("1 g", "1 g"),
        ("1gm", "1 g"),
        ("0.5%", "0.5 %"),
        ("250mcg", "250 mcg"),
        ("250 µg", "250 mcg"),
        ("10 IU", "10 IU"),
        ("500/125 mg", "500/125 mg"),
        ("625", None),
        ("abc", None),
        (None, None),
        ("", None),
        ("2.5 mg", "2.5 mg"),
        ("100 mg/5 ml", "100 mg/5 ml"),
    ],
)
def test_normalise_strength(text, expected):
    assert normalise_strength(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1", True),
        ("1/2", True),
        ("2", True),
        ("2 tsp", True),
        ("5 ml", True),
        ("10 ml", True),
        ("half", True),
        ("one", True),
        ("1 tab", True),
        ("2 puffs", True),
        ("1 drop", True),
        ("", False),
        (None, False),
        ("lots", False),
        ("1-0-1", False),
        ("100", False),
    ],
)
def test_validate_dose(text, expected):
    assert validate_dose(text) is expected
