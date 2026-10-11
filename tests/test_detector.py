"""Tests for core.detector (preprocessing + drawing)."""

from __future__ import annotations

import numpy as np
import pytest

from core.detector import (
    PreprocessOptions,
    draw_detections,
    filter_by_confidence,
    preprocess_frame,
    resize_to_width,
    scale_results,
    to_grayscale,
)
from core.ocr_engine import OCRResult


def _bgr(h: int = 120, w: int = 160) -> np.ndarray:
    rng = np.random.default_rng(1)
    return rng.integers(0, 255, size=(h, w, 3), dtype=np.uint8)


def _results() -> list[OCRResult]:
    return [
        OCRResult(text="HI", confidence=0.9, bbox=[[10, 10], [60, 10], [60, 30], [10, 30]]),
        OCRResult(text="lo", confidence=0.3, bbox=[[0, 0], [20, 0], [20, 8], [0, 8]]),
    ]


def test_to_grayscale_from_bgr_returns_2d_uint8():
    gray = to_grayscale(_bgr())
    assert gray.shape == (120, 160)
    assert gray.dtype == np.uint8


def test_to_grayscale_passes_through_gray():
    gray_in = np.full((10, 12), 128, dtype=np.uint8)
    gray = to_grayscale(gray_in)
    assert gray.shape == (10, 12)
    assert gray.dtype == np.uint8


def test_resize_to_width_returns_scale():
    gray = to_grayscale(_bgr(120, 160))
    resized, scale = resize_to_width(gray, 320)
    assert resized.shape == (240, 320)
    assert scale == pytest.approx(2.0)


def test_resize_to_width_noop_when_same_width():
    gray = to_grayscale(_bgr(120, 160))
    resized, scale = resize_to_width(gray, 160)
    assert resized.shape == (120, 160)
    assert scale == 1.0


@pytest.mark.parametrize("denoise", [True, False])
@pytest.mark.parametrize("clahe", [True, False])
@pytest.mark.parametrize("threshold", [True, False])
def test_preprocess_frame_all_option_combinations(denoise: bool, clahe: bool, threshold: bool):
    options = PreprocessOptions(denoise=denoise, clahe=clahe, adaptive_threshold=threshold)
    processed, scale = preprocess_frame(_bgr(), options)
    assert processed.ndim == 2
    assert processed.dtype == np.uint8
    assert processed.shape == (120, 160)
    assert scale == 1.0


def test_preprocess_frame_with_resize_reports_scale():
    processed, scale = preprocess_frame(_bgr(120, 160), PreprocessOptions(resize_width=480))
    assert processed.shape == (360, 480)
    assert scale == pytest.approx(3.0)


def test_preprocess_frame_default_options():
    processed, scale = preprocess_frame(_bgr())
    assert processed.shape == (120, 160) and processed.dtype == np.uint8 and scale == 1.0


def test_preprocess_frame_rejects_invalid_input():
    with pytest.raises(ValueError):
        preprocess_frame(np.zeros((0, 0, 3), dtype=np.uint8))
    with pytest.raises(ValueError):
        preprocess_frame(None)  # type: ignore[arg-type]


def test_filter_by_confidence_keeps_at_or_above_threshold():
    kept = filter_by_confidence(_results(), 0.4)
    assert [r.text for r in kept] == ["HI"]
    assert len(filter_by_confidence(_results(), 0.3)) == 2
    assert filter_by_confidence(_results(), 0.95) == []


def test_scale_results_maps_coordinates_back():
    scaled = scale_results(_results()[:1], scale=2.0)
    assert scaled[0].bbox == [[5, 5], [30, 5], [30, 15], [5, 15]]
    assert scaled[0].text == "HI" and scaled[0].confidence == 0.9


def test_scale_results_identity_for_scale_one():
    assert scale_results(_results(), 1.0) == _results()


def test_draw_detections_returns_annotated_copy():
    frame = _bgr()
    before = frame.copy()
    annotated = draw_detections(frame, _results())
    assert annotated.shape == frame.shape
    assert annotated.dtype == np.uint8
    assert np.array_equal(frame, before), "input frame must not be mutated"
    assert not np.array_equal(annotated, frame), "boxes must be drawn"


def test_draw_detections_handles_box_at_top_edge_and_empty_list():
    frame = _bgr()
    top = [OCRResult(text="TOP", confidence=0.8, bbox=[[0, 0], [40, 0], [40, 5], [0, 5]])]
    annotated = draw_detections(frame, top)
    assert annotated.shape == frame.shape
    assert np.array_equal(draw_detections(frame, []), frame)
