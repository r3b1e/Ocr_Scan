"""Claude API backend using structured outputs (`messages.parse`)."""

from __future__ import annotations

import base64
from typing import Any

from core.extractors.base import ExtractorError
from core.extractors.prompt import SYSTEM_PROMPT, build_instruction
from core.prescription import RawPrescription
from utils.logger import get_logger

log = get_logger("core.extractors.claude")

_USAGE_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)
_MISSING_CREDENTIALS = (
    "Claude credentials are missing. Set ANTHROPIC_API_KEY in .env (or run `ant auth login`)."
)


class ClaudeExtractor:
    """Send the image plus the fixed system prompt and parse the typed response."""

    name = "claude"

    def __init__(self, model: str, client: Any | None = None) -> None:
        self.model = model
        self._client = client
        self.last_usage: dict[str, int] | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                import anthropic

                self._client = anthropic.Anthropic()
            except Exception as exc:
                raise ExtractorError(_MISSING_CREDENTIALS) from exc
        return self._client

    def health(self) -> tuple[bool, str]:
        """True when a client with credentials can be built (no network call)."""
        try:
            client = self._get_client()
        except ExtractorError as exc:
            return False, str(exc)
        if not (getattr(client, "api_key", None) or getattr(client, "auth_token", None)):
            return False, _MISSING_CREDENTIALS
        return True, f"claude ready ({self.model})"

    def _translate(self, exc: Exception) -> ExtractorError:
        import anthropic

        if isinstance(exc, anthropic.AuthenticationError):
            return ExtractorError(
                "Claude rejected the credentials. Set a valid ANTHROPIC_API_KEY in .env."
            )
        if isinstance(exc, anthropic.RateLimitError):
            return ExtractorError("Claude rate limit reached; try again in a minute.")
        if isinstance(exc, anthropic.APIStatusError):
            if exc.status_code >= 500:
                return ExtractorError(
                    "The Claude service is temporarily unavailable; try again shortly."
                )
            return ExtractorError(f"Claude rejected the request ({exc.status_code}): {exc.message}")
        if isinstance(exc, anthropic.APIConnectionError):
            return ExtractorError(
                "Could not reach Claude. Check your internet connection and try again."
            )
        return ExtractorError(f"Claude request failed: {exc}")

    def extract(self, image_jpeg: bytes, ocr_hint: str | None) -> RawPrescription:
        """Run one structured-output request; raises `ExtractorError` with a plain message."""
        client = self._get_client()
        content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": base64.standard_b64encode(image_jpeg).decode("ascii"),
                },
            },
            {"type": "text", "text": build_instruction(ocr_hint, include_schema=False)},
        ]
        try:
            response = client.messages.parse(
                model=self.model,
                max_tokens=4096,
                system=[
                    {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
                ],
                messages=[{"role": "user", "content": content}],
                output_format=RawPrescription,
            )
        except Exception as exc:
            log.warning("Claude request failed: %s", exc)
            raise self._translate(exc) from exc

        usage = getattr(response, "usage", None)
        self.last_usage = (
            {field: int(getattr(usage, field, 0) or 0) for field in _USAGE_FIELDS}
            if usage is not None
            else None
        )
        log.info(
            "Claude usage %s request_id=%s", self.last_usage, getattr(response, "_request_id", None)
        )
        if getattr(response, "stop_reason", None) == "refusal":
            raise ExtractorError("The model declined to read this image.")
        parsed = getattr(response, "parsed_output", None)
        if parsed is None:
            raise ExtractorError("Claude returned no structured output; please try again.")
        return (
            parsed
            if isinstance(parsed, RawPrescription)
            else RawPrescription.model_validate(parsed)
        )
