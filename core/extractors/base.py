"""Backend-neutral contract for prescription extraction."""

from __future__ import annotations

from typing import Protocol

from core.prescription import RawPrescription


class ExtractorError(RuntimeError):
    """A backend failed; the message is safe to show to users."""


class PrescriptionExtractor(Protocol):
    """One vision backend."""

    name: str
    model: str

    def extract(self, image_jpeg: bytes, ocr_hint: str | None) -> RawPrescription:
        """Read the prescription image; raises `ExtractorError` on any failure."""

    def health(self) -> tuple[bool, str]:
        """Cheap readiness check: `(ok, human-readable message)`."""
