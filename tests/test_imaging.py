"""Tests for core.imaging (loading, EXIF rotation, downscaling, JPEG encoding, OCR prep)."""

from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

from core.imaging import ImageError, encode_jpeg, load_image, prepare_for_ocr


def _png_bytes(width: int, height: int) -> bytes:
    image = Image.new("RGB", (width, height), (10, 200, 30))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_with_orientation(width: int, height: int, orientation: int) -> bytes:
    image = Image.new("RGB", (width, height), "white")
    exif = image.getexif()
    exif[0x0112] = orientation
    buf = io.BytesIO()
    image.save(buf, format="JPEG", exif=exif.tobytes())
    return buf.getvalue()


def test_load_image_returns_bgr_array():
    frame = load_image(_png_bytes(64, 48))
    assert frame.shape == (48, 64, 3) and frame.dtype == np.uint8
    assert tuple(int(v) for v in frame[0, 0]) == (30, 200, 10)  # BGR order


def test_load_image_downscales_to_max_side():
    frame = load_image(_png_bytes(3200, 1600), max_side=1600)
    assert frame.shape == (800, 1600, 3)
    small = load_image(_png_bytes(300, 200), max_side=1600)
    assert small.shape == (200, 300, 3)


def test_load_image_applies_exif_rotation():
    frame = load_image(_jpeg_with_orientation(200, 100, orientation=6))
    assert frame.shape[:2] == (200, 100)


def test_load_image_rejects_invalid_data():
    with pytest.raises(ImageError):
        load_image(b"not an image")
    with pytest.raises(ImageError):
        load_image(b"")


def test_encode_jpeg_produces_jpeg_bytes():
    data = encode_jpeg(load_image(_png_bytes(64, 48)))
    assert data[:2] == b"\xff\xd8"
    assert Image.open(io.BytesIO(data)).size == (64, 48)


def test_prepare_for_ocr_keeps_shape_and_channels():
    rng = np.random.default_rng(1)
    frame = rng.integers(0, 255, size=(120, 160, 3), dtype=np.uint8)
    out = prepare_for_ocr(frame)
    assert out.shape == frame.shape and out.dtype == np.uint8


def test_prepare_for_ocr_straightens_tilted_text():
    canvas = Image.new("RGB", (400, 200), "white")
    from PIL import ImageDraw, ImageFont

    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=28)
    for i in range(4):
        draw.text((40, 30 + i * 36), "Tab Dolo 650 1-0-1 x 5 days", fill="black", font=font)
    tilted = canvas.rotate(6, expand=False, fillcolor="white")
    frame = np.array(tilted)[:, :, ::-1].copy()
    out = prepare_for_ocr(frame)
    assert out.shape == frame.shape
    from core.imaging import estimate_skew_angle

    assert abs(estimate_skew_angle(out)) < abs(estimate_skew_angle(frame))
    assert abs(estimate_skew_angle(out)) < 2.0
