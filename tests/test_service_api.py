"""Tests for the FastAPI extraction service with fake backends (no network)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from config.settings import Settings
from core.drug_lexicon import DrugLexicon
from core.extractors.base import ExtractorError
from core.ocr_engine import OCRResult
from core.prescription import RawPrescription
from database.db_manager import DatabaseManager

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).with_name("fixtures")
IMAGE = (FIXTURES / "sample_rx.jpg").read_bytes()
RAW = RawPrescription.model_validate(json.loads((FIXTURES / "claude_response.json").read_text()))


class FakeOCREngine:
    is_ready = True

    def warm_up(self):
        pass

    def detect(self, frame, min_confidence=0.0):
        texts = ("Tab. Dolo 650", "1-0-1", "A/F", "x 5 days", "Cap. Omez 20")
        return [
            OCRResult(
                t,
                0.9,
                [[10, 10 + 40 * i], [200, 10 + 40 * i], [200, 40 + 40 * i], [10, 40 + 40 * i]],
            )
            for i, t in enumerate(texts)
        ]


class FakeExtractor:
    def __init__(
        self, name="fake", model="fake-1", raw=RAW, error=None, healthy=(True, "fake ready")
    ):
        self.name, self.model, self.raw, self.error, self.healthy = name, model, raw, error, healthy
        self.calls = 0

    def extract(self, image_jpeg, ocr_hint):
        self.calls += 1
        if self.error:
            raise self.error
        return self.raw

    def health(self):
        return self.healthy


class FakeMySQLError(Exception):
    def __init__(self, msg, errno):
        super().__init__(msg)
        self.msg, self.errno = msg, errno


class DownConnector:
    Error = FakeMySQLError

    def connect(self, **kwargs):
        raise FakeMySQLError("down", 2003)


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    cfg = Settings.load(env_path=tmp_path / "nope.env", base_dir=tmp_path)
    cfg.lexicon_file = ROOT / "data" / "drug_lexicon_in.csv"
    cfg.ensure_directories()
    return cfg


def _client(settings, extractors=None, default="fake"):
    from service.api import create_app

    db = DatabaseManager(settings, connector_module=DownConnector())
    db.connect()
    app = create_app(
        settings,
        extractors=extractors or {"fake": FakeExtractor()},
        default_backend=default,
        engine=FakeOCREngine(),
        lexicon=DrugLexicon.load(settings.lexicon_path),
        db=db,
    )
    return TestClient(app)


def test_health(settings):
    with _client(settings) as client:
        body = client.get("/health").json()
    assert body["status"] == "ok" and body["backend"] == "fake" and body["model"] == "fake-1"
    assert body["backend_ready"] is True and body["lexicon_size"] >= 150
    assert body["database"] == "SQLite" and body["ocr_ready"] is True
    assert body["backends"] == ["fake"]


def test_extract_feedback_get_delete_cycle(settings):
    with _client(settings) as client:
        response = client.post("/extract", files={"image": ("rx.jpg", IMAGE, "image/jpeg")})
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["document_id"] == 1 and result["backend"] == "fake"
        assert [m["brand_matched"] for m in result["medications"]] == ["Dolo", "Omez", "Ascoril"]
        assert result["medications"][0]["frequency"]["slots"] == ["morning", "night"]
        assert (settings.documents_dir / "1.jpg").exists()

        got = client.get("/documents/1")
        assert got.status_code == 200
        body = got.json()
        assert body["document"]["backend"] == "fake" and body["result"]["document_id"] == 1
        assert body["correction"] is None

        corrected = dict(result)
        corrected["medications"][0]["dose"] = "2"
        feedback = client.post("/feedback", json={"document_id": 1, "corrected": corrected})
        assert feedback.status_code == 200 and feedback.json()["correction_id"] == 1

        body = client.get("/documents/1").json()
        assert body["correction"]["medications"][0]["dose"] == "2"

        assert client.delete("/documents/1").json() == {"deleted": True}
        assert not (settings.documents_dir / "1.jpg").exists()
        assert client.get("/documents/1").status_code == 404
        assert client.delete("/documents/1").status_code == 404


def test_feedback_for_unknown_document_is_404(settings):
    with _client(settings) as client:
        response = client.post(
            "/feedback", json={"document_id": 42, "corrected": {"backend": "x", "model": "y"}}
        )
    assert response.status_code == 404


def test_extract_rejects_bad_images_and_unknown_backend(settings):
    with _client(settings) as client:
        bad = client.post("/extract", files={"image": ("x.jpg", b"not an image", "image/jpeg")})
        assert bad.status_code == 422 and "image" in bad.json()["detail"].lower()
        huge = client.post(
            "/extract", files={"image": ("x.jpg", b"\xff" * (10 * 1024 * 1024 + 1), "image/jpeg")}
        )
        assert huge.status_code == 422 and "10 MB" in huge.json()["detail"]
        unknown = client.post(
            "/extract", files={"image": ("rx.jpg", IMAGE, "image/jpeg")}, data={"backend": "gpt"}
        )
        assert unknown.status_code == 422 and "gpt" in unknown.json()["detail"]


def test_extract_backend_override(settings):
    other = FakeExtractor(name="other", model="other-1")
    with _client(settings, extractors={"fake": FakeExtractor(), "other": other}) as client:
        response = client.post(
            "/extract", files={"image": ("rx.jpg", IMAGE, "image/jpeg")}, data={"backend": "other"}
        )
    assert (
        response.status_code == 200 and response.json()["backend"] == "other" and other.calls == 1
    )


def test_extract_backend_not_configured_is_503(settings):
    broken = FakeExtractor(
        healthy=(False, "Ollama model 'qwen3-vl:4b' is not installed. Run: ollama pull qwen3-vl:4b")
    )
    with _client(settings, extractors={"fake": broken}) as client:
        response = client.post("/extract", files={"image": ("rx.jpg", IMAGE, "image/jpeg")})
        health = client.get("/health").json()
    assert response.status_code == 503 and "ollama pull" in response.json()["detail"]
    assert health["status"] == "degraded" and health["backend_ready"] is False


def test_extract_backend_failure_is_502(settings):
    failing = FakeExtractor(
        error=ExtractorError("Could not reach Claude. Check your internet connection.")
    )
    with _client(settings, extractors={"fake": failing}) as client:
        response = client.post("/extract", files={"image": ("rx.jpg", IMAGE, "image/jpeg")})
    assert response.status_code == 502 and "internet" in response.json()["detail"]


def test_cors_allows_configured_web_origin(settings):
    settings.api_cors_origins = ["http://localhost:5175"]
    with _client(settings) as client:
        preflight = client.options(
            "/extract",
            headers={
                "Origin": "http://localhost:5175",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert preflight.status_code == 200
        assert preflight.headers["access-control-allow-origin"] == "http://localhost:5175"
        health = client.get("/health", headers={"Origin": "http://localhost:5175"})
        assert health.headers.get("access-control-allow-origin") == "http://localhost:5175"
        other = client.get("/health", headers={"Origin": "http://evil.example"})
        assert "access-control-allow-origin" not in other.headers


def test_document_image_is_served_and_404s_when_missing(settings):
    with _client(settings) as client:
        created = client.post("/extract", files={"image": ("rx.jpg", IMAGE, "image/jpeg")}).json()
        response = client.get(f"/documents/{created['document_id']}/image")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/jpeg"
        assert response.content[:2] == b"\xff\xd8"
        assert client.get("/documents/999/image").status_code == 404
