"""Tests for utils.helpers."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from database.models import ScanRecord
from utils.helpers import (
    ensure_dir,
    export_records,
    fit_within,
    frame_to_pil,
    is_blank_frame,
    timestamp_str,
)


def _records() -> list[ScanRecord]:
    return [
        ScanRecord(
            id=1,
            session_id=1,
            detected_text="HELLO, world",
            confidence=0.912345,
            bbox=[[0, 0], [10, 0], [10, 5], [0, 5]],
            image_path="captures/a.png",
            language="en",
            created_at=datetime(2026, 9, 20, 12, 30, 45),
        ),
        ScanRecord(
            id=2,
            session_id=None,
            detected_text='quote "inside"\nnewline',
            confidence=0.5,
            bbox=None,
            image_path=None,
            language="en",
            created_at=datetime(2026, 9, 21, 8, 0, 0),
        ),
    ]


def test_is_blank_frame_true_for_black_image():
    assert is_blank_frame(np.zeros((48, 64, 3), dtype=np.uint8)) is True


def test_is_blank_frame_true_for_none_or_empty():
    assert is_blank_frame(None) is True
    assert is_blank_frame(np.zeros((0, 0, 3), dtype=np.uint8)) is True


def test_is_blank_frame_false_for_textured_image():
    rng = np.random.default_rng(0)
    frame = rng.integers(0, 255, size=(48, 64, 3), dtype=np.uint8)
    assert is_blank_frame(frame) is False


def test_fit_within_preserves_aspect_ratio():
    assert fit_within(1280, 720, 640, 640) == (640, 360)
    assert fit_within(720, 1280, 640, 640) == (360, 640)
    assert fit_within(100, 50, 1000, 1000) == (1000, 500)


def test_fit_within_never_returns_zero():
    assert fit_within(1280, 720, 0, 0) == (1, 1)


def test_frame_to_pil_converts_bgr_to_rgb():
    frame = np.zeros((4, 6, 3), dtype=np.uint8)
    frame[..., 0] = 255  # blue channel in BGR
    image = frame_to_pil(frame)
    assert image.size == (6, 4)
    assert image.mode == "RGB"
    assert image.getpixel((0, 0)) == (0, 0, 255)


def test_timestamp_str_formats():
    dt = datetime(2026, 9, 20, 12, 30, 45)
    assert timestamp_str(dt) == "2026-09-20 12:30:45"
    assert timestamp_str(dt, for_filename=True) == "20260920_123045"


def test_ensure_dir_creates_nested(tmp_path: Path):
    target = tmp_path / "a" / "b" / "c"
    assert ensure_dir(target) == target
    assert target.is_dir()


def test_export_csv_is_valid(tmp_path: Path):
    path = export_records(_records(), tmp_path / "out.csv", "csv")
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 2
    assert rows[0]["detected_text"] == "HELLO, world"
    assert rows[1]["detected_text"] == 'quote "inside"\nnewline'
    assert float(rows[0]["confidence"]) == pytest.approx(0.912345)
    assert rows[0]["created_at"] == "2026-09-20 12:30:45"


def test_export_json_is_valid(tmp_path: Path):
    path = export_records(_records(), tmp_path / "out.json", "json")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, list) and len(data) == 2
    assert data[0]["bbox"] == [[0, 0], [10, 0], [10, 5], [0, 5]]
    assert data[1]["bbox"] is None
    assert data[0]["created_at"] == "2026-09-20T12:30:45"


def test_export_txt_contains_text_lines(tmp_path: Path):
    path = export_records(_records(), tmp_path / "out.txt", "txt")
    content = path.read_text(encoding="utf-8")
    assert "HELLO, world" in content
    assert "0.91" in content


def test_export_rejects_unknown_format(tmp_path: Path):
    with pytest.raises(ValueError):
        export_records(_records(), tmp_path / "out.xml", "xml")  # type: ignore[arg-type]
