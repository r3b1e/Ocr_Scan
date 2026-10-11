"""Frame preprocessing, confidence filtering and overlay drawing."""

from __future__ import annotations

from dataclasses import dataclass, replace

import cv2
import numpy as np

from core.ocr_engine import OCRResult

BoxColor = tuple[int, int, int]
GREEN: BoxColor = (0, 255, 0)


@dataclass(frozen=True)
class PreprocessOptions:
    """Switches for the scan-time preprocessing pipeline."""

    resize_width: int | None = None
    denoise: bool = True
    clahe: bool = True
    adaptive_threshold: bool = False


def _validate(frame: np.ndarray | None) -> np.ndarray:
    if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
        raise ValueError("Cannot preprocess an empty frame")
    return frame


def to_grayscale(frame: np.ndarray) -> np.ndarray:
    """Return a 2-D uint8 grayscale image from a BGR, BGRA or gray frame."""
    frame = _validate(frame)
    if frame.ndim == 2:
        gray = frame
    elif frame.shape[2] == 3:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    elif frame.shape[2] == 4:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
    else:
        raise ValueError(f"Unsupported channel count {frame.shape[2]}")
    return gray if gray.dtype == np.uint8 else np.clip(gray, 0, 255).astype(np.uint8)


def resize_to_width(gray: np.ndarray, width: int) -> tuple[np.ndarray, float]:
    """Resize keeping aspect ratio; return `(image, scale)` where `scale = new/old`."""
    height, current = gray.shape[:2]
    if width <= 0 or width == current:
        return gray, 1.0
    scale = width / current
    new_size = (width, max(1, round(height * scale)))
    interpolation = cv2.INTER_CUBIC if scale > 1 else cv2.INTER_AREA
    return cv2.resize(gray, new_size, interpolation=interpolation), scale


def preprocess_frame(
    frame: np.ndarray, options: PreprocessOptions | None = None
) -> tuple[np.ndarray, float]:
    """Grayscale -> optional resize -> denoise -> CLAHE -> optional adaptive threshold.

    Returns the processed 2-D uint8 image and the scale factor applied by the
    resize step (1.0 when no resize happened) so boxes can be mapped back.
    """
    opts = options or PreprocessOptions()
    gray = to_grayscale(_validate(frame))
    scale = 1.0
    if opts.resize_width:
        gray, scale = resize_to_width(gray, opts.resize_width)
    if opts.denoise:
        gray = cv2.fastNlMeansDenoising(gray, None, h=10, templateWindowSize=7, searchWindowSize=21)
    if opts.clahe:
        gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    if opts.adaptive_threshold:
        gray = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10
        )
    return gray, scale


def filter_by_confidence(results: list[OCRResult], threshold: float) -> list[OCRResult]:
    """Keep detections whose confidence is at or above `threshold`."""
    return [result for result in results if result.confidence >= threshold]


def scale_results(results: list[OCRResult], scale: float) -> list[OCRResult]:
    """Map boxes detected on a resized image back to original-frame coordinates."""
    if scale == 1.0:
        return list(results)
    return [
        replace(result, bbox=[[round(x / scale), round(y / scale)] for x, y in result.bbox])
        for result in results
    ]


def _font_scale(frame_height: int) -> float:
    return float(np.clip(frame_height / 900.0, 0.45, 0.9))


def draw_detections(
    frame: np.ndarray,
    results: list[OCRResult],
    color: BoxColor = GREEN,
    thickness: int = 2,
) -> np.ndarray:
    """Return a copy of `frame` with boxes and `text (confidence)` labels drawn."""
    annotated = frame.copy()
    if not results:
        return annotated
    height = annotated.shape[0]
    scale = _font_scale(height)
    font = cv2.FONT_HERSHEY_SIMPLEX
    for result in results:
        points = np.array(result.bbox, dtype=np.int32).reshape(-1, 1, 2)
        cv2.polylines(annotated, [points], isClosed=True, color=color, thickness=thickness)
        label = f"{result.text} ({result.confidence:.2f})"
        (text_w, text_h), baseline = cv2.getTextSize(label, font, scale, 1)
        x = max(0, int(points[:, 0, 0].min()))
        top = int(points[:, 0, 1].min())
        bottom = int(points[:, 0, 1].max())
        y = top - 6
        if y - text_h < 0:
            y = min(height - baseline - 1, bottom + text_h + 6)
        cv2.rectangle(
            annotated,
            (x, y - text_h - 4),
            (min(annotated.shape[1] - 1, x + text_w + 4), y + baseline),
            color,
            cv2.FILLED,
        )
        cv2.putText(annotated, label, (x + 2, y), font, scale, (0, 0, 0), 1, cv2.LINE_AA)
    return annotated
