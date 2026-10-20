"""HTTP API: `/extract`, `/feedback`, `/documents/{id}`, `/health`."""

from __future__ import annotations

import json
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config.settings import Settings
from core.drug_lexicon import DrugLexicon
from core.extractors import build_extractor
from core.extractors.base import ExtractorError, PrescriptionExtractor
from core.imaging import ImageError
from core.ocr_engine import OCREngine
from core.prescription import PrescriptionExtraction
from core.prescription_pipeline import run_extraction
from database.db_manager import DatabaseManager
from database.models import DatabaseError
from utils.logger import get_logger

log = get_logger("service.api")

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
BACKEND_NAMES = ("claude", "ollama")


class FeedbackRequest(BaseModel):
    """Body of `POST /feedback`."""

    document_id: int
    corrected: PrescriptionExtraction


class ServiceState:
    """Everything the endpoints share."""

    def __init__(
        self,
        settings: Settings,
        extractors: dict[str, PrescriptionExtractor],
        default_backend: str,
        engine: Any,
        lexicon: DrugLexicon,
        db: DatabaseManager,
    ) -> None:
        self.settings = settings
        self.extractors = extractors
        self.default_backend = default_backend
        self.engine = engine
        self.lexicon = lexicon
        self.db = db
        self.lock = threading.Lock()
        self.ocr_error: str | None = None

    @property
    def ocr_ready(self) -> bool:
        """True once EasyOCR has loaded its models."""
        return bool(getattr(self.engine, "is_ready", False))

    def warm_up_ocr(self) -> None:
        """Load OCR models (runs on a background thread at start-up)."""
        try:
            self.engine.warm_up()
        except Exception as exc:
            self.ocr_error = str(exc)
            log.exception("OCR warm-up failed")


def _default_extractors(settings: Settings) -> dict[str, PrescriptionExtractor]:
    return {
        name: build_extractor(replace(settings, extractor_backend=name)) for name in BACKEND_NAMES
    }


def create_app(
    settings: Settings,
    *,
    extractors: dict[str, PrescriptionExtractor] | None = None,
    default_backend: str | None = None,
    engine: Any | None = None,
    lexicon: DrugLexicon | None = None,
    db: DatabaseManager | None = None,
) -> FastAPI:
    """Build the FastAPI application; every collaborator can be injected for tests."""
    backends = extractors if extractors is not None else _default_extractors(settings)
    default = default_backend or settings.extractor_backend
    if default not in backends:
        raise ValueError(f"default backend {default!r} is not one of {sorted(backends)}")
    ocr_engine = engine or OCREngine(
        settings.ocr_languages, gpu=settings.ocr_gpu, model_storage_dir=settings.model_dir
    )
    drug_lexicon = lexicon or DrugLexicon.load(settings.lexicon_path)
    database = db
    if database is None:
        database = DatabaseManager(settings)
        database.connect()
    state = ServiceState(settings, backends, default, ocr_engine, drug_lexicon, database)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        threading.Thread(target=state.warm_up_ocr, name="ocr-warmup", daemon=True).start()
        if database.warning:
            log.warning(database.warning)
        yield
        database.close()

    app = FastAPI(title="remainRX Prescription Extraction", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.api_cors_origins),
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    app.state.service = state

    @app.get("/health")
    def health(request: Request) -> dict[str, Any]:
        service: ServiceState = request.app.state.service
        extractor = service.extractors[service.default_backend]
        ready, message = extractor.health()
        return {
            "status": "ok" if ready and service.ocr_error is None else "degraded",
            "backend": extractor.name,
            "model": extractor.model,
            "backend_ready": ready,
            "backend_message": message,
            "backends": sorted(service.extractors),
            "lexicon_size": len(service.lexicon),
            "database": service.db.backend_name,
            "database_offline": service.db.offline,
            "ocr_ready": service.ocr_ready,
            "ocr_error": service.ocr_error,
        }

    @app.post("/extract", response_model=PrescriptionExtraction)
    async def extract(
        request: Request,
        image: UploadFile = File(...),  # noqa: B008 - FastAPI dependency idiom
        backend: str | None = Form(None),  # noqa: B008
    ) -> PrescriptionExtraction:
        service: ServiceState = request.app.state.service
        name = backend or service.default_backend
        if name not in service.extractors:
            raise HTTPException(
                422, f"Unknown backend '{name}'; available: {sorted(service.extractors)}"
            )
        data = await image.read()
        if not data:
            raise HTTPException(422, "The uploaded image is empty")
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(422, "The image is larger than 10 MB; please upload a smaller file")
        extractor = service.extractors[name]
        ready, message = extractor.health()
        if not ready:
            raise HTTPException(503, message)

        def work() -> PrescriptionExtraction:
            with service.lock:
                return run_extraction(
                    data,
                    engine=service.engine,
                    extractor=extractor,
                    lexicon=service.lexicon,
                    settings=service.settings,
                    repo=service.db.prescriptions,
                    source="api",
                )

        try:
            return await run_in_threadpool(work)
        except ImageError as exc:
            raise HTTPException(422, str(exc)) from exc
        except ExtractorError as exc:
            raise HTTPException(502, str(exc)) from exc
        except DatabaseError as exc:
            log.exception("Database error during extraction")
            raise HTTPException(500, f"Database error: {exc}") from exc

    @app.post("/feedback")
    def feedback(body: FeedbackRequest, request: Request) -> dict[str, int]:
        repo = _repo(request)
        if repo.get_document(body.document_id) is None:
            raise HTTPException(404, f"Document {body.document_id} does not exist")
        try:
            correction_id = repo.save_correction(body.document_id, body.corrected.model_dump_json())
        except DatabaseError as exc:
            log.exception("Could not store correction")
            raise HTTPException(500, f"Database error: {exc}") from exc
        return {"correction_id": correction_id}

    @app.get("/documents/{document_id}")
    def get_document(document_id: int, request: Request) -> dict[str, Any]:
        repo = _repo(request)
        stored = repo.get_document(document_id)
        if stored is None:
            raise HTTPException(404, f"Document {document_id} does not exist")
        document, result_json, correction_json = stored
        payload = asdict(document)
        payload["created_at"] = document.created_at.isoformat()
        return {
            "document": payload,
            "result": json.loads(result_json) if result_json else None,
            "correction": json.loads(correction_json) if correction_json else None,
        }

    @app.get("/documents/{document_id}/image")
    def get_document_image(document_id: int, request: Request) -> FileResponse:
        """The processed (downscaled, deskewed) JPEG that the returned boxes refer to."""
        stored = _repo(request).get_document(document_id)
        if stored is None or not stored[0].image_path or not Path(stored[0].image_path).exists():
            raise HTTPException(404, f"No image stored for document {document_id}")
        return FileResponse(stored[0].image_path, media_type="image/jpeg")

    @app.delete("/documents/{document_id}")
    def delete_document(document_id: int, request: Request) -> dict[str, bool]:
        service: ServiceState = request.app.state.service
        repo = _repo(request)
        stored = repo.get_document(document_id)
        if stored is None:
            raise HTTPException(404, f"Document {document_id} does not exist")
        image_path = Path(stored[0].image_path) if stored[0].image_path else None
        if image_path is not None and image_path.exists():
            try:
                image_path.relative_to(service.settings.documents_dir)
                image_path.unlink()
            except (ValueError, OSError):
                log.warning("Did not delete image outside documents dir: %s", image_path)
        return {"deleted": repo.delete_document(document_id)}

    return app


def _repo(request: Request) -> Any:
    service: ServiceState = request.app.state.service
    if service.db.prescriptions is None:
        raise HTTPException(503, "No database available; see the service log for details")
    return service.db.prescriptions
