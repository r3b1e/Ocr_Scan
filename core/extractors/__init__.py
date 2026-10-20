"""Vision backends that turn a prescription image into `RawPrescription`."""

from __future__ import annotations

from config.settings import Settings
from core.extractors.base import ExtractorError, PrescriptionExtractor
from core.extractors.claude import ClaudeExtractor
from core.extractors.ollama import OllamaExtractor


def build_extractor(settings: Settings) -> PrescriptionExtractor:
    """Instantiate the backend named by `EXTRACTOR_BACKEND` (no network access here)."""
    if settings.extractor_backend == "claude":
        return ClaudeExtractor(model=settings.claude_model)
    if settings.extractor_backend == "ollama":
        return OllamaExtractor(model=settings.ollama_model, host=settings.ollama_host)
    raise ExtractorError(
        f"Unknown EXTRACTOR_BACKEND {settings.extractor_backend!r}; use 'claude' or 'ollama'."
    )


__all__ = [
    "ClaudeExtractor",
    "ExtractorError",
    "OllamaExtractor",
    "PrescriptionExtractor",
    "build_extractor",
]
