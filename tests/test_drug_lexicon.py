"""Tests for core.drug_lexicon (Indian brand/composition matching)."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.drug_lexicon import DrugEntry, DrugLexicon, LexiconMatch

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "data" / "drug_lexicon_in.csv"


@pytest.fixture(scope="module")
def lexicon() -> DrugLexicon:
    return DrugLexicon.load(SEED)


def test_seed_lexicon_loads(lexicon):
    assert len(lexicon) >= 150
    dolo = lexicon.match("Dolo")
    assert dolo.entry is not None
    assert dolo.entry.strengths == ("500 mg", "650 mg")
    assert dolo.entry.form == "tablet" and dolo.entry.source == "seed-verify"


def test_missing_file_gives_empty_lexicon(tmp_path):
    empty = DrugLexicon.load(tmp_path / "nope.csv")
    assert len(empty) == 0
    match = empty.match("Dolo 650")
    assert match.status == "unverified" and match.entry is None and match.matched_on == "none"


@pytest.mark.parametrize("name", ["Dolo 650", "Tab. Dolo 650", "DOLO-650", "dolo", "Dolo 650 mg"])
def test_exact_brand_matches_ignore_strength_and_form(lexicon, name):
    match = lexicon.match(name)
    assert isinstance(match, LexiconMatch)
    assert match.status == "ok" and match.matched_on == "brand"
    assert match.entry.brand == "Dolo" and match.canonical == "Dolo"
    assert match.entry.composition == "Paracetamol"
    assert match.score >= 90


def test_combination_brand(lexicon):
    match = lexicon.match("Augmentin 625")
    assert match.status == "ok" and match.entry.brand == "Augmentin"
    assert match.entry.composition == "Amoxicillin + Clavulanic Acid"


def test_generic_name_matches_composition(lexicon):
    match = lexicon.match("Paracetamol 650")
    assert match.status == "ok" and match.matched_on == "composition"
    assert match.canonical == "Paracetamol"
    assert match.entry is not None and match.entry.composition == "Paracetamol"


def test_misspelled_generic_is_corrected(lexicon):
    match = lexicon.match("Azythromicin 500")
    assert match.status == "corrected" and match.matched_on == "composition"
    assert match.canonical == "Azithromycin"
    assert 75 <= match.score < 90


def test_close_misspelling_of_brand_is_ok(lexicon):
    match = lexicon.match("Azithrall 500")
    assert match.status == "ok" and match.canonical == "Azithral"


def test_unknown_name_is_unverified(lexicon):
    match = lexicon.match("Xyzabc 10")
    assert match.status == "unverified" and match.entry is None and match.score < 75


@pytest.mark.parametrize("name", [None, "", "   ", "650"])
def test_empty_or_numeric_names_are_unverified(lexicon, name):
    match = lexicon.match(name)
    assert match.status == "unverified" and match.matched_on == "none"


def test_custom_entries_and_component_matching():
    custom = DrugLexicon([DrugEntry("Combo-X", "Alpha + Beta", ("10 mg",), "tablet", "test")])
    assert len(custom) == 1
    match = custom.match("Beta")
    assert match.status == "ok" and match.matched_on == "composition" and match.canonical == "Beta"
    assert custom.match("Combo X").entry.brand == "Combo-X"
