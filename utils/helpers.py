"""Small, pure helper functions used across the application."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Literal

import cv2
import numpy as np
from PIL import Image

from database.models import ScanRecord

ExportFormat = Literal["csv", "json", "txt"]
EXPORT_FORMATS: tuple[ExportFormat, ...] = ("csv", "json", "txt")
CSV_COLUMNS = (
    "id",
    "session_id",
    "detected_text",
    "confidence",
    "bbox",
    "image_path",
    "language",
    "created_at",
)


def timestamp_str(dt: datetime | None = None, for_filename: bool = False) -> str:
    """Format a datetime for display (`2026-09-20 12:30:45`) or filenames (`20260920_123045`)."""
    moment = dt or datetime.now()
    return moment.strftime("%Y%m%d_%H%M%S" if for_filename else "%Y-%m-%d %H:%M:%S")


def ensure_dir(path: Path) -> Path:
    """Create `path` (and parents) if needed and return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def is_blank_frame(
    frame: np.ndarray | None, mean_threshold: float = 8.0, std_threshold: float = 3.0
) -> bool:
    """Return True for missing, empty, black or featureless frames.

    A covered camera produces near-black frames (low mean) and a frozen or
    saturated sensor produces flat frames (low standard deviation).
    """
    if frame is None or frame.size == 0:
        return True
    gray = frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return bool(gray.mean() < mean_threshold or gray.std() < std_threshold)


def fit_within(src_w: int, src_h: int, max_w: int, max_h: int) -> tuple[int, int]:
    """Return the largest size with the source aspect ratio that fits in the box."""
    if src_w <= 0 or src_h <= 0:
        return (1, 1)
    scale = min(max(max_w, 1) / src_w, max(max_h, 1) / src_h)
    return (max(1, round(src_w * scale)), max(1, round(src_h * scale)))


def frame_to_pil(frame_bgr: np.ndarray) -> Image.Image:
    """Convert an OpenCV BGR frame to a PIL RGB image."""
    if frame_bgr.ndim == 2:
        return Image.fromarray(frame_bgr).convert("RGB")
    return Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))


def _write_csv(records: list[ScanRecord], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for record in records:
            row = record.to_dict()
            row["bbox"] = json.dumps(record.bbox) if record.bbox is not None else ""
            row["created_at"] = timestamp_str(record.created_at)
            writer.writerow({key: row[key] for key in CSV_COLUMNS})


def _write_json(records: list[ScanRecord], path: Path) -> None:
    path.write_text(
        json.dumps([record.to_dict() for record in records], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _write_txt(records: list[ScanRecord], path: Path) -> None:
    lines = [
        f"[{timestamp_str(record.created_at)}] ({record.confidence:.2f}) {record.detected_text}"
        for record in records
    ]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def export_records(records: Iterable[ScanRecord], path: Path, fmt: ExportFormat) -> Path:
    """Write `records` to `path` as CSV, JSON or TXT and return the path.

    Raises:
        ValueError: if `fmt` is not one of `EXPORT_FORMATS`.
    """
    if fmt not in EXPORT_FORMATS:
        raise ValueError(f"Unsupported export format {fmt!r}; use one of {EXPORT_FORMATS}")
    rows = list(records)
    ensure_dir(path.parent)
    if fmt == "csv":
        _write_csv(rows, path)
    elif fmt == "json":
        _write_json(rows, path)
    else:
        _write_txt(rows, path)
    return path
