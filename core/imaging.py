"""Image loading and preparation for prescription extraction."""

from __future__ import annotations

import io

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_SKEW_DEGREES = 15.0
SKEW_STEP_DEGREES = 0.5
MIN_CORRECTION_DEGREES = 0.3


class ImageError(ValueError):
    """Raised when uploaded bytes are not a usable image."""


def load_image(data: bytes, max_side: int = 1600) -> np.ndarray:
    """Decode bytes into a BGR array, honouring EXIF orientation and capping the longest side.

    Raises:
        ImageError: for empty, corrupt or unsupported data.
    """
    if not data:
        raise ImageError("The uploaded file is empty")
    try:
        with Image.open(io.BytesIO(data)) as opened:
            image = ImageOps.exif_transpose(opened) or opened
            image = image.convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise ImageError("The file is not a readable image (JPEG, PNG or WebP expected)") from exc
    width, height = image.size
    scale = max_side / max(width, height)
    if scale < 1.0:
        image = image.resize(
            (max(1, round(width * scale)), max(1, round(height * scale))), Image.LANCZOS
        )
    return np.array(image)[:, :, ::-1].copy()


def encode_jpeg(frame: np.ndarray, quality: int = 85) -> bytes:
    """Encode a BGR frame as JPEG bytes."""
    ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise ImageError("Could not encode the image as JPEG")
    return buffer.tobytes()


def _binary_text_mask(frame: np.ndarray, width: int = 800) -> np.ndarray:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    height, current = gray.shape[:2]
    if current > width:
        gray = cv2.resize(
            gray, (width, max(1, round(height * width / current))), interpolation=cv2.INTER_AREA
        )
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return mask


def _rotate(image: np.ndarray, angle: float, border: int) -> np.ndarray:
    height, width = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    return cv2.warpAffine(
        image,
        matrix,
        (width, height),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=border,
    )


def estimate_skew_angle(frame: np.ndarray, max_angle: float = MAX_SKEW_DEGREES) -> float:
    """Return the rotation (degrees, counter-clockwise positive) that best straightens text lines.

    Uses the projection-profile method: the rotation whose row sums have the highest variance
    aligns text lines with the image rows.
    """
    mask = _binary_text_mask(frame)
    if mask.sum() == 0:
        return 0.0
    best_angle, best_score = 0.0, -1.0
    for angle in np.arange(-max_angle, max_angle + SKEW_STEP_DEGREES, SKEW_STEP_DEGREES):
        rotated = _rotate(mask, float(angle), border=0)
        score = float(np.var(rotated.sum(axis=1, dtype=np.int64)))
        if score > best_score:
            best_angle, best_score = float(angle), score
    return best_angle


def prepare_for_ocr(frame: np.ndarray) -> np.ndarray:
    """Deskew (up to +-15 degrees) and lightly denoise a BGR frame without changing its shape."""
    angle = estimate_skew_angle(frame)
    result = _rotate(frame, angle, border=255) if abs(angle) >= MIN_CORRECTION_DEGREES else frame
    return cv2.bilateralFilter(result, 5, 40, 40)
