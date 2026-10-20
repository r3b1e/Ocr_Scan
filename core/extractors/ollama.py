"""Local open-weight backend through Ollama (fully offline)."""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import ValidationError

from core.extractors.base import ExtractorError
from core.extractors.prompt import SYSTEM_PROMPT, build_instruction
from core.prescription import RawPrescription
from utils.logger import get_logger

log = get_logger("core.extractors.ollama")

_ATTEMPTS = 2
_TIMEOUT_SECONDS = 600
# Reasoning models (qwen3-vl) otherwise spend the whole output budget "thinking" and return
# an empty answer with done_reason="length"; keep thinking off and leave room for the JSON.
_NUM_PREDICT = 4096


def _optional(obj: Any, key: str) -> Any:
    try:
        return _field(obj, key)
    except (KeyError, AttributeError, TypeError):
        return None


def _field(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return obj[key]
    try:
        return obj[key]
    except (KeyError, TypeError, IndexError):
        return getattr(obj, key)


class OllamaExtractor:
    """`ollama.Client.chat` with the JSON schema in `format` and temperature 0."""

    name = "ollama"

    def __init__(self, model: str, host: str, client: Any | None = None) -> None:
        self.model = model
        self.host = host.rstrip("/")
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            import ollama

            self._client = ollama.Client(host=self.host, timeout=_TIMEOUT_SECONDS)
        return self._client

    def _translate(self, exc: Exception) -> ExtractorError:
        import ollama

        if isinstance(exc, ollama.ResponseError):
            if exc.status_code == 404 or "not found" in str(exc).lower():
                return ExtractorError(
                    f"Ollama model '{self.model}' is not installed. Run: ollama pull {self.model}"
                )
            return ExtractorError(f"Ollama error: {exc}")
        if isinstance(exc, httpx.ConnectError | httpx.ConnectTimeout | ConnectionError):
            return ExtractorError(
                f"Ollama is not running at {self.host}. Start it with: ollama serve"
            )
        if isinstance(exc, httpx.TimeoutException):
            return ExtractorError(
                "Ollama timed out; a smaller model (qwen3-vl:2b) may be faster on this machine."
            )
        if isinstance(exc, httpx.HTTPError):
            return ExtractorError(f"Ollama request failed: {exc}")
        return ExtractorError(f"Ollama failed: {exc}")

    def health(self) -> tuple[bool, str]:
        """Check the server answers and the model is pulled."""
        try:
            listing = self._get_client().list()
        except Exception as exc:
            return False, str(self._translate(exc))
        names = {str(_field(m, "model")) for m in _field(listing, "models")}
        if self.model in names or f"{self.model}:latest" in names:
            return True, f"ollama ready ({self.model} at {self.host})"
        return False, f"Ollama model '{self.model}' is not installed. Run: ollama pull {self.model}"

    def extract(self, image_jpeg: bytes, ocr_hint: str | None) -> RawPrescription:
        """Ask the local model for schema-constrained JSON; retry once on malformed output."""
        client = self._get_client()
        schema = RawPrescription.model_json_schema()
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_instruction(ocr_hint, include_schema=True),
                "images": [image_jpeg],
            },
        ]
        hit_limit = False
        for attempt in range(1, _ATTEMPTS + 1):
            try:
                response = client.chat(
                    model=self.model,
                    messages=messages,
                    format=schema,
                    think=False,
                    options={"temperature": 0, "num_predict": _NUM_PREDICT},
                )
            except Exception as exc:
                log.warning("Ollama request failed: %s", exc)
                raise self._translate(exc) from exc
            content = str(_field(_field(response, "message"), "content") or "")
            done_reason = _optional(response, "done_reason")
            if not content.strip():
                hit_limit = done_reason == "length"
                log.warning(
                    "Ollama returned no content (attempt %s/%s, done_reason=%s)",
                    attempt,
                    _ATTEMPTS,
                    done_reason,
                )
                continue
            try:
                return RawPrescription.model_validate_json(content)
            except ValidationError as exc:
                hit_limit = False
                log.warning(
                    "Ollama returned invalid JSON (attempt %s/%s): %s", attempt, _ATTEMPTS, exc
                )
        if hit_limit:
            raise ExtractorError(
                f"Ollama model '{self.model}' hit its output token limit before answering "
                f"after {_ATTEMPTS} attempts; try a smaller image or another model."
            )
        raise ExtractorError(
            f"Ollama did not return valid JSON for the prescription schema after {_ATTEMPTS} "
            "attempts; try again or use a larger model."
        )
