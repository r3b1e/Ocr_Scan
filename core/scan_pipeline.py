"""The on-demand scan: frame -> preprocess -> OCR -> annotated image -> database rows.

`run_scan` is a plain function with injected collaborators so it can be
exercised headlessly in tests and executed on the OCR worker thread in the app.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from core.detector import (
    PreprocessOptions,
    draw_detections,
    filter_by_confidence,
    preprocess_frame,
    scale_results,
)
from core.ocr_engine import OCRResult
from database.models import ScanRecord
from utils.helpers import ensure_dir, is_blank_frame, timestamp_str
from utils.logger import get_logger

log = get_logger("core.scan_pipeline")

SCAN_STEPS: tuple[str, ...] = (
    "Capturing frame",
    "Preprocessing",
    "Running OCR",
    "Saving image",
    "Writing to DB",
    "Done",
)
STEP_OCR = SCAN_STEPS.index("Running OCR")
NO_TEXT_REASON = "No text detected"
BLANK_FRAME_REASON = "Frame is blank - is the lens covered or the room too dark?"

ProgressCallback = Callable[[int, str], None]


@dataclass
class ScanOutcome:
    """What a scan produced. `skipped_reason` is set when nothing was stored."""

    results: list[OCRResult] = field(default_factory=list)
    image_path: Path | None = None
    scan_ids: list[int] = field(default_factory=list)
    skipped_reason: str | None = None


def save_capture(image: np.ndarray, captures_dir: Path, moment: datetime) -> Path:
    """Write `image` as PNG into `captures_dir` and return the path.

    Raises:
        OSError: if the directory cannot be created or the file cannot be written.
    """
    ensure_dir(captures_dir)
    name = f"scan_{timestamp_str(moment, for_filename=True)}_{moment.microsecond // 1000:03d}.png"
    path = captures_dir / name
    if not cv2.imwrite(str(path), image):
        raise OSError(f"Could not write the capture image to {path}")
    return path


def run_scan(
    frame: np.ndarray,
    engine: Any,
    repo: Any,
    *,
    session_id: int | None,
    language: str,
    captures_dir: Path,
    min_confidence: float,
    preprocess: PreprocessOptions | None,
    progress: ProgressCallback,
    now: Callable[[], datetime] = datetime.now,
) -> ScanOutcome:
    """Execute one full scan and persist the detections.

    Args:
        frame: BGR frame grabbed from the camera.
        engine: object with `detect(image, min_confidence) -> list[OCRResult]`.
        repo: object with `insert_scans(list[ScanRecord]) -> list[int]`.
        session_id: current camera session id (or None when unknown).
        language: language label stored with each row.
        captures_dir: where the annotated PNG is written.
        min_confidence: detections below this are discarded.
        preprocess: preprocessing switches, or None to feed the raw frame to OCR.
        progress: called as `progress(step_index, step_label)` for every step.
        now: clock (injectable for tests).

    Raises:
        ValueError: for an invalid frame.
        DatabaseError / OSError: when persistence fails (the image may already be saved).
    """

    def report(index: int) -> None:
        progress(index, SCAN_STEPS[index])

    report(0)
    if (
        frame is None
        or not isinstance(frame, np.ndarray)
        or frame.size == 0
        or frame.ndim not in (2, 3)
    ):
        raise ValueError("The captured frame is empty or invalid")
    if is_blank_frame(frame):
        report(len(SCAN_STEPS) - 1)
        return ScanOutcome(skipped_reason=BLANK_FRAME_REASON)
    moment = now()

    report(1)
    if preprocess is not None:
        ocr_input, scale = preprocess_frame(frame, preprocess)
    else:
        ocr_input, scale = frame, 1.0

    report(STEP_OCR)
    detections = engine.detect(ocr_input, min_confidence=min_confidence)
    results = scale_results(filter_by_confidence(detections, min_confidence), scale)
    if not results:
        report(len(SCAN_STEPS) - 1)
        return ScanOutcome(skipped_reason=NO_TEXT_REASON)

    report(3)
    image_path = save_capture(draw_detections(frame, results), captures_dir, moment)

    report(4)
    records = [
        ScanRecord(
            id=None,
            session_id=session_id,
            detected_text=result.text,
            confidence=result.confidence,
            bbox=result.bbox,
            image_path=str(image_path),
            language=language,
            created_at=moment,
        )
        for result in results
    ]
    scan_ids = repo.insert_scans(records)

    report(len(SCAN_STEPS) - 1)
    log.info("Scan stored %s detections -> %s", len(scan_ids), image_path.name)
    return ScanOutcome(results=results, image_path=image_path, scan_ids=scan_ids)
