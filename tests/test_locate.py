"""Tests for core.locate (map extracted values back to OCR boxes)."""

from __future__ import annotations

from core.locate import Fragment, line_union, locate

F1 = Fragment("Tab. Dolo 650", [[10, 10], [200, 10], [200, 40], [10, 40]])
F2 = Fragment("1-0-1", [[260, 12], [330, 12], [330, 40], [260, 40]])
F3 = Fragment("x 5 days", [[400, 11], [500, 11], [500, 40], [400, 40]])
F4 = Fragment("Azithral 500", [[10, 60], [200, 60], [200, 90], [10, 90]])
FRAGMENTS = [F1, F2, F3, F4]
LINE_1 = [[10, 10], [500, 10], [500, 40], [10, 40]]


def test_exact_value_returns_whole_line_box():
    bbox, score = locate("Dolo 650", FRAGMENTS)
    assert bbox == LINE_1 and score >= 80


def test_value_on_second_line():
    bbox, score = locate("Azithral 500", FRAGMENTS)
    assert bbox == [[10, 60], [200, 60], [200, 90], [10, 90]] and score == 100


def test_partial_and_fuzzy_values():
    assert locate("Dolo", FRAGMENTS)[0] == LINE_1
    bbox, score = locate("Dollo 650", FRAGMENTS)
    assert bbox == LINE_1 and 80 <= score < 100


def test_frequency_token_locates_its_line():
    bbox, score = locate("1-0-1", FRAGMENTS)
    assert bbox == LINE_1 and score == 100


def test_no_match_returns_none():
    bbox, score = locate("Metformin", FRAGMENTS)
    assert bbox is None and score < 80


def test_empty_inputs():
    assert locate(None, FRAGMENTS) == (None, 0.0)
    assert locate("", FRAGMENTS) == (None, 0.0)
    assert locate("Dolo", []) == (None, 0.0)
    assert locate("ab", FRAGMENTS) == (None, 0.0)  # too short to be meaningful


def test_line_union_merges_fragments_with_vertical_overlap():
    assert line_union(F1, FRAGMENTS) == LINE_1
    assert line_union(F4, FRAGMENTS) == F4.bbox
