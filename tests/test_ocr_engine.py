"""Tests for core.ocr_engine."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from core.ocr_engine import OCREngine, OCRInitError, OCRResult


class FakeReader:
    """Stands in for easyocr.Reader; records calls and returns canned detections."""

    def __init__(self, detections=None):
        self.calls: list[np.ndarray] = []
        self.detections = (
            detections
            if detections is not None
            else [
                ([[0.0, 0.0], [50.0, 0.0], [50.0, 20.0], [0.0, 20.0]], "HELLO", np.float64(0.95)),
                ([[0, 30], [40, 30], [40, 50], [0, 50]], "low", 0.2),
            ]
        )

    def readtext(self, image, **kwargs):
        self.calls.append(image)
        return list(self.detections)


def _engine(reader: FakeReader | None = None, **kwargs) -> tuple[OCREngine, FakeReader]:
    reader = reader or FakeReader()
    engine = OCREngine(["en"], gpu="false", reader_factory=lambda *a, **k: reader, **kwargs)
    return engine, reader


def _frame(h: int = 60, w: int = 80) -> np.ndarray:
    return np.full((h, w, 3), 255, dtype=np.uint8)


def test_resolve_gpu_explicit_strings():
    assert OCREngine.resolve_gpu("false") is False
    assert OCREngine.resolve_gpu("FALSE") is False
    assert OCREngine.resolve_gpu("true") is True
    assert OCREngine.resolve_gpu(True) is True
    assert OCREngine.resolve_gpu(False) is False


def test_resolve_gpu_auto_returns_bool():
    assert isinstance(OCREngine.resolve_gpu("auto"), bool)


def test_engine_is_not_ready_until_warm_up():
    engine, _ = _engine()
    assert engine.is_ready is False
    engine.warm_up()
    assert engine.is_ready is True


def test_detect_converts_reader_output_to_results():
    engine, reader = _engine()
    results = engine.detect(_frame(), min_confidence=0.4)
    assert len(reader.calls) == 1
    assert results == [
        OCRResult(text="HELLO", confidence=0.95, bbox=[[0, 0], [50, 0], [50, 20], [0, 20]])
    ]
    assert all(isinstance(v, int) for point in results[0].bbox for v in point)
    assert isinstance(results[0].confidence, float)


def test_detect_without_threshold_returns_all():
    engine, _ = _engine()
    assert [r.text for r in engine.detect(_frame())] == ["HELLO", "low"]


def test_detect_skips_blank_text_entries():
    engine, _ = _engine(FakeReader([([[0, 0], [1, 0], [1, 1], [0, 1]], "   ", 0.9)]))
    assert engine.detect(_frame()) == []


def test_detect_rejects_invalid_frames():
    engine, _ = _engine()
    for bad in (None, np.zeros((0, 0, 3), dtype=np.uint8), np.zeros(10, dtype=np.uint8)):
        with pytest.raises(ValueError):
            engine.detect(bad)  # type: ignore[arg-type]


def test_warm_up_wraps_reader_failure_in_friendly_error():
    def boom(*args, **kwargs):
        raise ConnectionError("Failed to establish a new connection")

    engine = OCREngine(["en"], gpu="false", reader_factory=boom)
    with pytest.raises(OCRInitError) as excinfo:
        engine.warm_up()
    message = str(excinfo.value)
    assert "EasyOCR" in message
    assert "internet" in message.lower() or "download" in message.lower()
    assert engine.is_ready is False


def test_result_to_dict_roundtrip():
    result = OCRResult(text="A", confidence=0.5, bbox=[[1, 2], [3, 4], [5, 6], [7, 8]])
    assert result.to_dict() == {
        "text": "A",
        "confidence": 0.5,
        "bbox": [[1, 2], [3, 4], [5, 6], [7, 8]],
    }


def _synthetic_text_image(text: str) -> np.ndarray:
    image = Image.new("RGB", (900, 220), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=110)
    draw.text((40, 40), text, fill="black", font=font)
    rgb = np.array(image)
    return rgb[:, :, ::-1].copy()  # PIL RGB -> OpenCV BGR


@pytest.mark.slow
def test_real_easyocr_recognises_synthetic_text():
    engine = OCREngine(["en"], gpu="false")
    engine.warm_up()
    results = engine.detect(_synthetic_text_image("HELLO WORLD"), min_confidence=0.3)
    joined = " ".join(r.text.upper() for r in results)
    assert "HELLO" in joined
    assert "WORLD" in joined
    assert all(0.0 <= r.confidence <= 1.0 for r in results)
