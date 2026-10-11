"""Headless smoke tests for core.scan_pipeline: synthetic frame -> OCR -> image -> DB."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from core.detector import PreprocessOptions
from core.ocr_engine import OCREngine, OCRResult
from core.scan_pipeline import SCAN_STEPS, run_scan
from database.models import DatabaseError
from database.sqlite_repository import SQLiteScanRepository


class FakeEngine:
    def __init__(self, results=None):
        self.results = (
            results
            if results is not None
            else [
                OCRResult("HELLO", 0.95, [[10, 10], [60, 10], [60, 30], [10, 30]]),
                OCRResult("low", 0.2, [[0, 40], [20, 40], [20, 50], [0, 50]]),
            ]
        )
        self.received: list[np.ndarray] = []
        self.is_ready = True

    def warm_up(self):
        self.is_ready = True

    def detect(self, frame, min_confidence=0.0):
        self.received.append(frame)
        return [r for r in self.results if r.confidence >= min_confidence]


def _frame(h: int = 120, w: int = 160) -> np.ndarray:
    rng = np.random.default_rng(7)
    return rng.integers(50, 255, size=(h, w, 3), dtype=np.uint8)


@pytest.fixture()
def repo(tmp_path: Path):
    repository = SQLiteScanRepository(tmp_path / "scan.sqlite3")
    yield repository
    repository.close()


def _run(frame, engine, repo, tmp_path, **kwargs):
    steps: list[tuple[int, str]] = []
    defaults = dict(
        session_id=None,
        language="en",
        captures_dir=tmp_path / "captures",
        min_confidence=0.4,
        preprocess=PreprocessOptions(),
        progress=lambda i, label: steps.append((i, label)),
    )
    defaults.update(kwargs)
    outcome = run_scan(frame, engine, repo, **defaults)
    return outcome, steps


def test_full_scan_writes_image_and_db_rows(repo, tmp_path):
    engine = FakeEngine()
    session_id = repo.create_session(__import__("datetime").datetime.now())
    outcome, steps = _run(_frame(), engine, repo, tmp_path, session_id=session_id)

    assert [label for _, label in steps] == list(SCAN_STEPS)
    assert [i for i, _ in steps] == list(range(len(SCAN_STEPS)))

    assert outcome.skipped_reason is None
    assert [r.text for r in outcome.results] == ["HELLO"]
    assert outcome.image_path is not None
    assert outcome.image_path.parent == tmp_path / "captures"
    assert outcome.image_path.suffix == ".png"
    saved = cv2.imread(str(outcome.image_path))
    assert saved is not None and saved.shape == (120, 160, 3)

    assert len(outcome.scan_ids) == 1
    rows = repo.fetch_scans()
    assert len(rows) == 1
    assert rows[0].detected_text == "HELLO"
    assert rows[0].confidence == pytest.approx(0.95)
    assert rows[0].bbox == [[10, 10], [60, 10], [60, 30], [10, 30]]
    assert rows[0].image_path == str(outcome.image_path)
    assert rows[0].session_id == session_id
    assert rows[0].language == "en"


def test_preprocessing_scales_boxes_back_to_frame_coordinates(repo, tmp_path):
    engine = FakeEngine([OCRResult("BIG", 0.9, [[20, 20], [120, 20], [120, 60], [20, 60]])])
    outcome, _ = _run(
        _frame(), engine, repo, tmp_path, preprocess=PreprocessOptions(resize_width=320)
    )
    assert engine.received[0].shape == (240, 320)  # engine saw the upscaled grayscale image
    assert outcome.results[0].bbox == [[10, 10], [60, 10], [60, 30], [10, 30]]
    assert repo.fetch_scans()[0].bbox == [[10, 10], [60, 10], [60, 30], [10, 30]]


def test_preprocessing_disabled_sends_original_frame(repo, tmp_path):
    engine = FakeEngine()
    outcome, steps = _run(_frame(), engine, repo, tmp_path, preprocess=None)
    assert engine.received[0].shape == (120, 160, 3)
    assert outcome.skipped_reason is None
    assert [label for _, label in steps] == list(SCAN_STEPS)


def test_blank_frame_is_skipped_without_db_rows(repo, tmp_path):
    engine = FakeEngine()
    outcome, steps = _run(np.zeros((120, 160, 3), dtype=np.uint8), engine, repo, tmp_path)
    assert outcome.skipped_reason and "blank" in outcome.skipped_reason.lower()
    assert outcome.results == [] and outcome.scan_ids == [] and outcome.image_path is None
    assert engine.received == []
    assert repo.count_scans() == 0
    assert steps[-1][1] == SCAN_STEPS[-1]


def test_zero_detections_is_reported_not_crashed(repo, tmp_path):
    engine = FakeEngine(results=[])
    outcome, steps = _run(_frame(), engine, repo, tmp_path)
    assert outcome.skipped_reason == "No text detected"
    assert outcome.image_path is None and outcome.scan_ids == []
    assert repo.count_scans() == 0
    assert steps[-1][1] == SCAN_STEPS[-1]


def test_all_below_threshold_counts_as_no_detection(repo, tmp_path):
    engine = FakeEngine()
    outcome, _ = _run(_frame(), engine, repo, tmp_path, min_confidence=0.99)
    assert outcome.skipped_reason == "No text detected"
    assert repo.count_scans() == 0


def test_invalid_frame_raises_value_error(repo, tmp_path):
    with pytest.raises(ValueError):
        _run(None, FakeEngine(), repo, tmp_path)


def test_database_failure_propagates_after_image_saved(tmp_path):
    class BrokenRepo:
        backend_name = "Broken"

        def insert_scans(self, records):
            raise DatabaseError("MySQL went away")

    with pytest.raises(DatabaseError):
        _run(_frame(), FakeEngine(), BrokenRepo(), tmp_path)
    saved = list((tmp_path / "captures").glob("*.png"))
    assert len(saved) == 1


def _text_frame(text: str) -> np.ndarray:
    image = Image.new("RGB", (900, 220), "white")
    ImageDraw.Draw(image).text((40, 40), text, fill="black", font=ImageFont.load_default(size=110))
    return np.array(image)[:, :, ::-1].copy()


@pytest.mark.slow
def test_real_engine_end_to_end(repo, tmp_path):
    engine = OCREngine(["en"], gpu="false")
    outcome, _ = _run(_text_frame("HELLO WORLD"), engine, repo, tmp_path, min_confidence=0.3)
    assert outcome.skipped_reason is None
    texts = " ".join(r.detected_text.upper() for r in repo.fetch_scans())
    assert "HELLO" in texts
