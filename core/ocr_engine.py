"""Thin, lazily-initialised wrapper around `easyocr.Reader`.

EasyOCR (and PyTorch behind it) takes several seconds to import and load its
models, so the reader is created on first use - ideally from a background
thread via `warm_up()` - and never on the Tk main thread.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from utils.logger import get_logger

log = get_logger("core.ocr_engine")

ReaderFactory = Callable[..., Any]


class OCRInitError(RuntimeError):
    """Raised when EasyOCR cannot be initialised (typically a failed model download)."""


@dataclass(frozen=True)
class OCRResult:
    """One recognised text fragment with its confidence and quadrilateral box."""

    text: str
    confidence: float
    bbox: list[list[int]]

    def to_dict(self) -> dict[str, Any]:
        """Return a plain mapping for JSON storage."""
        return asdict(self)


def _validate_frame(frame: Any) -> np.ndarray:
    if frame is None or not isinstance(frame, np.ndarray):
        raise ValueError("OCR input must be a numpy image array")
    if frame.size == 0 or frame.ndim not in (2, 3):
        raise ValueError(f"OCR input has an invalid shape {frame.shape}")
    return frame


def _to_result(entry: Sequence[Any]) -> OCRResult | None:
    bbox_raw, text, confidence = entry[0], str(entry[1]), float(entry[2])
    cleaned = text.strip()
    if not cleaned:
        return None
    bbox = [[int(round(float(x))), int(round(float(y)))] for x, y in bbox_raw]
    return OCRResult(text=cleaned, confidence=confidence, bbox=bbox)


class OCREngine:
    """Detect and recognise text in images using EasyOCR."""

    def __init__(
        self,
        languages: Sequence[str],
        gpu: str | bool = "auto",
        model_storage_dir: Path | None = None,
        reader_factory: ReaderFactory | None = None,
    ) -> None:
        self.languages: list[str] = list(languages) or ["en"]
        self.use_gpu: bool = self.resolve_gpu(gpu)
        self.model_storage_dir = model_storage_dir
        self._reader_factory = reader_factory
        self._reader: Any | None = None

    @staticmethod
    def resolve_gpu(setting: str | bool) -> bool:
        """Turn the `auto|true|false` config value into a concrete boolean.

        `auto` asks PyTorch whether CUDA is available; any failure means CPU.
        """
        if isinstance(setting, bool):
            return setting
        normalized = str(setting).strip().lower()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
        try:
            import torch

            return bool(torch.cuda.is_available())
        except Exception:  # pragma: no cover - depends on the local torch build
            log.warning("Could not query CUDA availability; falling back to CPU", exc_info=True)
            return False

    @property
    def device_label(self) -> str:
        """Human-readable compute device."""
        return "GPU (CUDA)" if self.use_gpu else "CPU"

    @property
    def is_ready(self) -> bool:
        """True once the EasyOCR reader has been created."""
        return self._reader is not None

    def warm_up(self) -> None:
        """Create the EasyOCR reader (downloads models on first ever run).

        Raises:
            OCRInitError: with a plain-language message when EasyOCR cannot start.
        """
        if self._reader is not None:
            return
        try:
            factory = self._reader_factory or self._default_factory()
            kwargs: dict[str, Any] = {"gpu": self.use_gpu, "verbose": False}
            if self.model_storage_dir is not None:
                kwargs["model_storage_directory"] = str(self.model_storage_dir)
            self._reader = factory(self.languages, **kwargs)
        except Exception as exc:
            log.exception("EasyOCR initialisation failed")
            raise OCRInitError(
                "EasyOCR could not be initialised. On the first run it downloads about "
                "100 MB of models, so check your internet connection (or copy the models "
                f"into ~/.EasyOCR/model) and try again. Details: {exc}"
            ) from exc
        log.info("EasyOCR ready: languages=%s device=%s", self.languages, self.device_label)

    @staticmethod
    def _default_factory() -> ReaderFactory:
        import easyocr

        return easyocr.Reader

    def detect(self, frame: np.ndarray, min_confidence: float = 0.0) -> list[OCRResult]:
        """Run OCR on a BGR or grayscale frame and return detections above `min_confidence`.

        Raises:
            ValueError: for `None`, empty or non-image input.
            OCRInitError: if the reader cannot be created lazily.
        """
        image = _validate_frame(frame)
        self.warm_up()
        assert self._reader is not None
        raw = self._reader.readtext(image)
        results: list[OCRResult] = []
        for entry in raw:
            result = _to_result(entry)
            if result is not None and result.confidence >= min_confidence:
                results.append(result)
        return results
