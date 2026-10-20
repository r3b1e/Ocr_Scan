"""Tests for the vision backends with fake clients (no network, no API key)."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import httpx
import httpx2
import pytest

from config.settings import Settings
from core.extractors import build_extractor
from core.extractors.base import ExtractorError
from core.extractors.claude import ClaudeExtractor
from core.extractors.ollama import OllamaExtractor
from core.extractors.prompt import SYSTEM_PROMPT, build_instruction
from core.prescription import RawPrescription

FIXTURES = Path(__file__).with_name("fixtures")
IMAGE = (FIXTURES / "sample_rx.jpg").read_bytes()
RAW = json.loads((FIXTURES / "claude_response.json").read_text())


# ------------------------------------------------------------------ prompt
def test_system_prompt_mentions_indian_conventions():
    assert "1-0-1" in SYSTEM_PROMPT and "null" in SYSTEM_PROMPT
    assert "TDS" in SYSTEM_PROMPT and "guess" in SYSTEM_PROMPT.lower()


def test_instruction_includes_hint_and_schema_when_asked():
    plain = build_instruction(None, include_schema=False)
    assert "medications" in plain and "Tab Dolo" not in plain
    hinted = build_instruction("Tab Dolo 650 1-0-1", include_schema=False)
    assert "Tab Dolo 650 1-0-1" in hinted
    with_schema = build_instruction(None, include_schema=True)
    assert '"frequency_text"' in with_schema


# ------------------------------------------------------------------ Claude
class _Usage:
    input_tokens = 1200
    output_tokens = 300
    cache_read_input_tokens = 900
    cache_creation_input_tokens = 0


class _Parsed:
    def __init__(self, parsed_output, stop_reason="end_turn"):
        self.parsed_output = parsed_output
        self.stop_reason = stop_reason
        self.usage = _Usage()
        self._request_id = "req_123"


class _FakeMessages:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.calls = result, error, []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.result


class _FakeClaudeClient:
    def __init__(self, result=None, error=None, api_key="sk-test"):
        self.messages = _FakeMessages(result, error)
        self.api_key = api_key


def _sdk_error(cls, status: int):
    import anthropic

    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    if cls is anthropic.APIConnectionError:
        return cls(request=request)
    response = httpx2.Response(status, request=request)
    return cls("boom", response=response, body=None)


def test_claude_extract_sends_image_hint_and_schema():
    client = _FakeClaudeClient(result=_Parsed(RawPrescription.model_validate(RAW)))
    extractor = ClaudeExtractor(model="claude-opus-5-5", client=client)
    result = extractor.extract(IMAGE, ocr_hint="Tab Dolo 650 1-0-1")

    assert isinstance(result, RawPrescription) and result.medications[0].name == "Tab. Dolo 650"
    call = client.messages.calls[0]
    assert call["model"] == "claude-opus-5-5" and call["output_format"] is RawPrescription
    assert call["system"][0]["cache_control"] == {"type": "ephemeral"}
    content = call["messages"][0]["content"]
    image_block = next(b for b in content if b["type"] == "image")
    assert image_block["source"]["media_type"] == "image/jpeg"
    assert base64.b64decode(image_block["source"]["data"]) == IMAGE
    text_block = next(b for b in content if b["type"] == "text")
    assert "Tab Dolo 650 1-0-1" in text_block["text"]
    assert extractor.last_usage == {
        "input_tokens": 1200,
        "output_tokens": 300,
        "cache_read_input_tokens": 900,
        "cache_creation_input_tokens": 0,
    }
    assert extractor.name == "claude" and extractor.model == "claude-opus-5-5"


def test_claude_refusal_is_a_plain_error():
    client = _FakeClaudeClient(result=_Parsed(None, stop_reason="refusal"))
    with pytest.raises(ExtractorError, match="declined"):
        ClaudeExtractor(model="claude-opus-5-5", client=client).extract(IMAGE, None)


@pytest.mark.parametrize(
    ("exc_name", "status", "expected"),
    [
        ("AuthenticationError", 401, "ANTHROPIC_API_KEY"),
        ("RateLimitError", 429, "rate limit"),
        ("InternalServerError", 500, "Claude service"),
        ("APIConnectionError", 0, "internet"),
        ("BadRequestError", 400, "rejected"),
    ],
)
def test_claude_sdk_errors_are_translated(exc_name, status, expected):
    import anthropic

    client = _FakeClaudeClient(error=_sdk_error(getattr(anthropic, exc_name), status))
    with pytest.raises(ExtractorError) as excinfo:
        ClaudeExtractor(model="claude-opus-5-5", client=client).extract(IMAGE, None)
    assert expected.lower() in str(excinfo.value).lower()
    assert "Traceback" not in str(excinfo.value)


def test_claude_health_reports_missing_credentials():
    assert ClaudeExtractor(model="m", client=_FakeClaudeClient()).health() == (
        True,
        "claude ready (m)",
    )
    ok, message = ClaudeExtractor(model="m", client=_FakeClaudeClient(api_key=None)).health()
    assert ok is False and "ANTHROPIC_API_KEY" in message


# ------------------------------------------------------------------ Ollama
class _FakeOllamaClient:
    def __init__(self, contents=(), errors=(), models=("qwen3-vl:4b",)):
        self.contents, self.errors, self.models = list(contents), list(errors), models
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        if self.errors:
            raise self.errors.pop(0)
        content = self.contents.pop(0)
        return {"message": {"role": "assistant", "content": content}}

    def list(self):
        if self.errors:
            raise self.errors.pop(0)
        return {"models": [{"model": name} for name in self.models]}


def test_ollama_extract_uses_schema_image_and_zero_temperature():
    content = json.loads((FIXTURES / "ollama_response.json").read_text())["message"]["content"]
    client = _FakeOllamaClient(contents=[content])
    extractor = OllamaExtractor(model="qwen3-vl:4b", host="http://127.0.0.1:11434", client=client)
    result = extractor.extract(IMAGE, ocr_hint=None)
    assert result.medications[1].name == "Cap. Omez 20"
    call = client.calls[0]
    assert call["model"] == "qwen3-vl:4b"
    assert call["format"] == RawPrescription.model_json_schema()
    assert call["options"]["temperature"] == 0
    assert call["think"] is False, "reasoning must be off or the model spends its budget thinking"
    assert call["options"]["num_predict"] >= 4096
    assert (
        call["messages"][0]["role"] == "system" and call["messages"][0]["content"] == SYSTEM_PROMPT
    )
    assert call["messages"][1]["images"] == [IMAGE]
    assert '"medications"' in call["messages"][1]["content"]
    assert extractor.name == "ollama"


def test_ollama_invalid_json_is_retried_once():
    good = json.dumps(RAW)
    client = _FakeOllamaClient(contents=["not json", good])
    result = OllamaExtractor("qwen3-vl:4b", "http://127.0.0.1:11434", client=client).extract(
        IMAGE, None
    )
    assert len(result.medications) == 3 and len(client.calls) == 2

    client = _FakeOllamaClient(contents=["nope", "{bad"])
    with pytest.raises(ExtractorError, match="valid JSON"):
        OllamaExtractor("qwen3-vl:4b", "http://127.0.0.1:11434", client=client).extract(IMAGE, None)


def test_ollama_empty_content_reports_token_limit():
    class _LengthClient(_FakeOllamaClient):
        def chat(self, **kwargs):
            self.calls.append(kwargs)
            return {
                "message": {"role": "assistant", "content": "", "thinking": "Okay..."},
                "done_reason": "length",
            }

    client = _LengthClient()
    with pytest.raises(ExtractorError, match="output token limit"):
        OllamaExtractor("qwen3-vl:4b", "http://127.0.0.1:11434", client=client).extract(IMAGE, None)
    assert len(client.calls) == 2


def test_ollama_connection_and_missing_model_errors():
    import ollama

    client = _FakeOllamaClient(errors=[httpx.ConnectError("refused")])
    with pytest.raises(ExtractorError, match="ollama serve"):
        OllamaExtractor("qwen3-vl:4b", "http://127.0.0.1:11434", client=client).extract(IMAGE, None)

    client = _FakeOllamaClient(errors=[ollama.ResponseError("model 'qwen3-vl:4b' not found", 404)])
    with pytest.raises(ExtractorError, match="ollama pull qwen3-vl:4b"):
        OllamaExtractor("qwen3-vl:4b", "http://127.0.0.1:11434", client=client).extract(IMAGE, None)


def test_ollama_health():
    ok, msg = OllamaExtractor("qwen3-vl:4b", "http://h", client=_FakeOllamaClient()).health()
    assert ok is True and "qwen3-vl:4b" in msg
    ok, msg = OllamaExtractor("qwen3-vl:2b", "http://h", client=_FakeOllamaClient()).health()
    assert ok is False and "ollama pull qwen3-vl:2b" in msg
    ok, msg = OllamaExtractor(
        "qwen3-vl:4b", "http://h", client=_FakeOllamaClient(errors=[httpx.ConnectError("x")])
    ).health()
    assert ok is False and "ollama serve" in msg


# ------------------------------------------------------------------ factory
def test_build_extractor_selects_backend(tmp_path):
    settings = Settings.load(env_path=tmp_path / "nope.env", base_dir=tmp_path)
    claude = build_extractor(settings)
    assert isinstance(claude, ClaudeExtractor) and claude.model == "claude-opus-5-5"

    settings.extractor_backend = "ollama"
    settings.ollama_model = "qwen3-vl:2b"
    local = build_extractor(settings)
    assert isinstance(local, OllamaExtractor) and local.model == "qwen3-vl:2b"
    assert local.host == "http://127.0.0.1:11434"

    settings.extractor_backend = "gpt"
    with pytest.raises(ExtractorError):
        build_extractor(settings)
