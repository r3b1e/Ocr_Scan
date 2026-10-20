"""Tests for core.prescription_pipeline: OCR pass, validation and the end-to-end run."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from config.settings import Settings
from core.drug_lexicon import DrugLexicon
from core.extractors.base import ExtractorError
from core.imaging import ImageError
from core.locate import Fragment
from core.ocr_engine import OCRResult
from core.prescription import RawMedication, RawPrescription
from core.prescription_pipeline import run_extraction, run_ocr_pass, validate_medication
from database.prescription_repository import SQLitePrescriptionRepository

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).with_name("fixtures")
IMAGE = (FIXTURES / "sample_rx.jpg").read_bytes()
RAW = RawPrescription.model_validate(json.loads((FIXTURES / "claude_response.json").read_text()))
LEXICON = DrugLexicon.load(ROOT / "data" / "drug_lexicon_in.csv")

LINE_FRAGMENTS = [
    Fragment("Tab. Dolo 650", [[80, 310], [330, 310], [330, 345], [80, 345]]),
    Fragment("1-0-1", [[420, 312], [500, 312], [500, 345], [420, 345]]),
    Fragment("A/F", [[560, 312], [610, 312], [610, 345], [560, 345]]),
    Fragment("x 5 days", [[680, 311], [800, 311], [800, 345], [680, 345]]),
    Fragment("Cap. Omez 20", [[80, 380], [330, 380], [330, 415], [80, 415]]),
]


class FakeOCREngine:
    def __init__(self, results):
        self.results = results
        self.is_ready = True
        self.calls = 0

    def warm_up(self):
        pass

    def detect(self, frame, min_confidence=0.0):
        self.calls += 1
        return [r for r in self.results if r.confidence >= min_confidence]


class FakeExtractor:
    name = "fake"
    model = "fake-1"

    def __init__(self, raw=RAW, error=None):
        self.raw, self.error, self.calls = raw, error, []

    def extract(self, image_jpeg, ocr_hint):
        self.calls.append((len(image_jpeg), ocr_hint))
        if self.error:
            raise self.error
        return self.raw

    def health(self):
        return True, "fake"


def _ocr(conf: float, texts=("Tab. Dolo 650", "1-0-1", "A/F", "x 5 days", "Cap. Omez 20")):
    return [
        OCRResult(
            text,
            conf,
            [[10, 10 + 40 * i], [200, 10 + 40 * i], [200, 40 + 40 * i], [10, 40 + 40 * i]],
        )
        for i, text in enumerate(texts)
    ]


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    cfg = Settings.load(env_path=tmp_path / "nope.env", base_dir=tmp_path)
    cfg.ensure_directories()
    return cfg


def _frame() -> np.ndarray:
    rng = np.random.default_rng(0)
    return rng.integers(200, 255, size=(120, 160, 3), dtype=np.uint8)


# ----------------------------------------------------------------- OCR pass
def test_ocr_pass_printed_document_builds_hint_in_reading_order():
    results = _ocr(0.9)
    results.append(OCRResult("Rx", 0.95, [[10, 0], [40, 0], [40, 8], [10, 8]]))  # above everything
    ocr = run_ocr_pass(_frame(), FakeOCREngine(results))
    assert ocr.handwritten is False
    assert ocr.hint.startswith("Rx\n")
    assert "Tab. Dolo 650" in ocr.hint and ocr.mean_confidence == pytest.approx(0.9083, abs=0.01)
    assert [f.text for f in ocr.fragments][:2] == ["Rx", "Tab. Dolo 650"]


def test_ocr_pass_low_confidence_or_sparse_is_handwritten():
    low = run_ocr_pass(_frame(), FakeOCREngine(_ocr(0.3)))
    assert low.handwritten is True and low.hint is None and len(low.fragments) == 5
    sparse = run_ocr_pass(_frame(), FakeOCREngine(_ocr(0.9, texts=("Rx", "Dolo"))))
    assert sparse.handwritten is True
    nothing = run_ocr_pass(_frame(), FakeOCREngine([]))
    assert (
        nothing.handwritten is True and nothing.fragments == [] and nothing.mean_confidence == 0.0
    )


def test_ocr_pass_can_skip_hint_for_printed():
    ocr = run_ocr_pass(_frame(), FakeOCREngine(_ocr(0.9)), hint_for_printed=False)
    assert ocr.handwritten is False and ocr.hint is None


def test_ocr_pass_survives_engine_failure():
    class Broken(FakeOCREngine):
        def detect(self, frame, min_confidence=0.0):
            raise RuntimeError("model missing")

    ocr = run_ocr_pass(_frame(), Broken([]))
    assert ocr.fragments == [] and ocr.handwritten is True and ocr.hint is None


# --------------------------------------------------------------- validation
def test_validate_known_brand_fills_everything():
    med, warnings = validate_medication(RAW.medications[0], LEXICON, LINE_FRAGMENTS)
    assert med.name == "Dolo 650" and med.form == "tablet"
    assert med.brand_matched == "Dolo" and med.composition == "Paracetamol"
    assert med.strength == "650 mg"
    assert med.frequency.pattern == "1-0-1" and med.frequency.times_per_day == 2
    assert med.frequency.slots == ["morning", "night"]
    assert med.timing == "after_food" and med.duration_days == 5
    assert med.status == "ok"
    assert med.field_status == {
        "name": "ok",
        "strength": "ok",
        "frequency": "ok",
        "timing": "ok",
        "duration": "ok",
    }
    assert med.bbox == [[80, 310], [800, 310], [800, 345], [80, 345]]
    assert med.confidence == pytest.approx(0.4 * 0.92 + 0.3 + 0.2 + 0.1, abs=0.01)
    assert warnings == []


def test_validate_unknown_brand_and_bad_frequency():
    raw = RawMedication(
        name="Xyzabc 10",
        frequency_text="blah",
        duration_text="400 days",
        strength="abc",
        confidence=0.5,
    )
    med, warnings = validate_medication(raw, LEXICON, [])
    assert med.status == "unverified"
    assert (
        med.field_status["name"] == "unverified" and med.field_status["frequency"] == "unverified"
    )
    assert (
        med.field_status["duration"] == "unverified"
        and med.field_status["strength"] == "unverified"
    )
    assert med.bbox is None and med.brand_matched is None
    assert any("Xyzabc" in w for w in warnings) and any("blah" in w for w in warnings)
    assert med.confidence < 0.4


def test_validate_misspelled_generic_is_corrected():
    raw = RawMedication(
        name="Azythromicin 500", frequency_text="OD", duration_text="3 days", confidence=0.7
    )
    med, warnings = validate_medication(raw, LEXICON, [])
    assert med.status == "corrected" and med.composition == "Azithromycin"
    assert med.brand_matched is None and med.name == "Azythromicin 500"
    assert any("Azithromycin" in w for w in warnings)


def test_validate_misspelled_brand_is_replaced_and_recorded():
    raw = RawMedication(name="Augmentn 625", frequency_text="BD", confidence=0.7)
    med, warnings = validate_medication(raw, LEXICON, [])
    assert med.status in {"ok", "corrected"}
    assert med.brand_matched == "Augmentin" and med.composition == "Amoxicillin + Clavulanic Acid"
    if med.status == "corrected":
        assert med.name == "Augmentin 625" and any("Augmentn" in w for w in warnings)


def test_validate_sos_hs_and_fraction_dose():
    sos, _ = validate_medication(
        RawMedication(name="Dolo 650", frequency_text="SOS", confidence=0.9), LEXICON, []
    )
    assert sos.frequency.as_needed is True and sos.field_status["frequency"] == "ok"
    hs, _ = validate_medication(
        RawMedication(name="Alprax 0.25", frequency_text="HS", confidence=0.9), LEXICON, []
    )
    assert hs.timing == "bedtime" and hs.frequency.slots == ["night"]
    half, _ = validate_medication(
        RawMedication(name="Ecosprin 75", frequency_text="1/2-0-1/2", confidence=0.9), LEXICON, []
    )
    assert half.dose == "1/2" and half.frequency.times_per_day == 2


def test_validate_missing_optional_fields_do_not_fail():
    raw = RawMedication(name="Becosules", confidence=0.6)
    med, warnings = validate_medication(raw, LEXICON, [])
    assert med.status == "ok" and med.brand_matched == "Becosules"
    assert med.field_status == {"name": "ok"}
    assert med.frequency.times_per_day is None and med.duration_days is None


# ------------------------------------------------------------- end to end
def test_run_extraction_end_to_end_with_persistence(settings, tmp_path):
    engine = FakeOCREngine(_ocr(0.9))
    extractor = FakeExtractor()
    repo = SQLitePrescriptionRepository(tmp_path / "rx.sqlite3")
    try:
        result = run_extraction(
            IMAGE,
            engine=engine,
            extractor=extractor,
            lexicon=LEXICON,
            settings=settings,
            repo=repo,
            source="api",
        )
    finally:
        repo.close()
    assert result.backend == "fake" and result.model == "fake-1"
    assert result.handwritten is False and result.processing_ms >= 0
    assert result.patient_name == "Suman" and len(result.medications) == 3
    assert result.medications[0].brand_matched == "Dolo" and result.medications[0].bbox is not None
    assert (
        result.medications[1].brand_matched == "Omez"
        and result.medications[1].timing == "before_food"
    )
    assert result.medications[2].frequency.times_per_day == 3
    assert extractor.calls[0][1] is not None and "Dolo" in extractor.calls[0][1]
    assert result.document_id == 1
    assert (settings.documents_dir / "1.jpg").exists()


def test_run_extraction_without_repository(settings):
    result = run_extraction(
        IMAGE,
        engine=FakeOCREngine(_ocr(0.9)),
        extractor=FakeExtractor(),
        lexicon=LEXICON,
        settings=settings,
    )
    assert (
        result.document_id is None
        and not settings.documents_dir.exists()
        or not any(settings.documents_dir.iterdir())
    )


def test_run_extraction_handwritten_skips_hint(settings):
    extractor = FakeExtractor()
    result = run_extraction(
        IMAGE,
        engine=FakeOCREngine(_ocr(0.2)),
        extractor=extractor,
        lexicon=LEXICON,
        settings=settings,
    )
    assert result.handwritten is True and extractor.calls[0][1] is None


def test_run_extraction_zero_medications_warns(settings):
    empty = RawPrescription(medications=[])
    result = run_extraction(
        IMAGE,
        engine=FakeOCREngine(_ocr(0.9)),
        extractor=FakeExtractor(raw=empty),
        lexicon=LEXICON,
        settings=settings,
    )
    assert result.medications == [] and any("No medications" in w for w in result.warnings)


def test_run_extraction_errors_propagate(settings):
    with pytest.raises(ExtractorError):
        run_extraction(
            IMAGE,
            engine=FakeOCREngine([]),
            extractor=FakeExtractor(error=ExtractorError("down")),
            lexicon=LEXICON,
            settings=settings,
        )
    with pytest.raises(ImageError):
        run_extraction(
            b"garbage",
            engine=FakeOCREngine([]),
            extractor=FakeExtractor(),
            lexicon=LEXICON,
            settings=settings,
        )


@pytest.mark.slow
def test_run_extraction_with_real_easyocr(settings):
    from core.ocr_engine import OCREngine

    engine = OCREngine(["en"], gpu="false")
    extractor = FakeExtractor()
    result = run_extraction(
        IMAGE, engine=engine, extractor=extractor, lexicon=LEXICON, settings=settings
    )
    assert result.handwritten is False
    assert "Dolo" in (extractor.calls[0][1] or "")
    assert result.medications[0].bbox is not None
