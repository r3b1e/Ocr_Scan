# Changelog

## 1.1.0 - 2026-10-21 - remainRX prescription extraction (phase 1)

### Added
- `core/prescription.py` - Pydantic schema: `RawPrescription` (what the vision model fills) and
  `PrescriptionExtraction` (validated API response with per-field `ok` / `corrected` /
  `unverified` status, confidence and image boxes).
- `core/extractors/` - one `PrescriptionExtractor` interface with two backends switchable via
  `EXTRACTOR_BACKEND`: Claude API structured outputs (`messages.parse`, default
  `claude-opus-5-5`) and local Ollama (`qwen3-vl:4b`, JSON-schema `format`, temperature 0).
  Plain-language errors for missing keys, rate limits, refusals, Ollama not running or model
  not pulled; no silent fallback between backends.
- `core/sig_grammar.py` - parser for Indian prescription shorthand (`1-0-1`, `OD/BD/TDS/QID/HS/
  SOS`, `q8h`, `A/F B/F AC PC`, durations, dosage forms, strengths, doses) with 180 tests.
- `core/drug_lexicon.py` + `data/drug_lexicon_in.csv` - 220 common Indian brands with
  compositions and strengths (seed list, `source=seed-verify`), fuzzy matched with RapidFuzz.
- `core/imaging.py` - EXIF-aware loading, downscaling, projection-profile deskew, denoise.
- `core/locate.py` - maps extracted values back to EasyOCR text lines for highlighting.
- `core/prescription_pipeline.py` - printed/handwritten detection, OCR hint, validation layer,
  confidence formula, persistence.
- `database/prescription_repository.py` - `documents`, `extractions`, `corrections` tables for
  MySQL and SQLite; `DatabaseManager.prescriptions`; shared `MySQLConnectionBase`.
- `service/` - FastAPI app: `POST /extract`, `POST /feedback`, `GET|DELETE /documents/{id}`,
  `GET /health`; `python -m service` runs it with uvicorn.
- New `.env` keys (see `.env.example`), pinned dependencies, README section, design spec and
  phase 1 plan under `docs/superpowers/`.

### Verified
- `pytest -q` -> 384 passed (SQLite + MySQL 8.4 + real EasyOCR; backends tested with fake
  clients and recorded fixtures, no network). `ruff check`, `ruff format --check`,
  `compileall` clean.
- Live backend check (`pytest -m live`): see the entry below once recorded.


## 1.0.0 - 2026-09-20

First complete release of the OCR Data Scanning Tool.

### Added
- Tkinter desktop app (`main.py`, `gui/`) with live webcam canvas, control panel, progress bar +
  status line, colour-coded console, History window (search / delete / export / open image) and
  Stats window (scans per day, confidence histogram via matplotlib).
- `core/camera.py` - threaded `CameraManager` with bounded frame queue, FPS, automatic reconnect
  and plain-language `CameraError`s.
- `core/ocr_engine.py` - lazy EasyOCR wrapper with CUDA auto-detection and `OCRInitError`.
- `core/ocr_worker.py` - single inference thread; live frames dropped when busy, scan tasks queued.
- `core/detector.py` - preprocessing pipeline (grayscale, optional resize, denoise, CLAHE, optional
  adaptive threshold), confidence filtering, box scaling and overlay drawing.
- `core/scan_pipeline.py` - the six-step scan (`Capturing frame → … → Done`) as a testable function.
- `core/audio.py` - pygame beeps that degrade to silence when no audio device exists.
- `database/` - `ScanRepository` protocol with MySQL (pooled, auto-creates DB + tables from
  `schema.sql`, translated error messages) and SQLite implementations; `DatabaseManager` falls back
  to SQLite when MySQL is unreachable.
- `config/settings.py` - validated `.env` loading with defaults; `.env.example`.
- `utils/` - rotating file logging, export to CSV / JSON / TXT, blank-frame detection.
- 119 pytest tests: unit tests for every module, a headless full-app smoke test with a synthetic
  camera, MySQL integration tests (auto-skip), and real-EasyOCR recognition tests on a Pillow image.
- `notebooks/demo.ipynb` - executed EasyOCR walkthrough.
- Documentation: README (setup, configuration, troubleshooting, design decisions).

### Verified (2026-09-20, macOS 26.2 / Apple Silicon, CPU inference, MySQL 8.4 in Docker)
- `pytest -q` → 119 passed, no warnings (SQLite + MySQL integration + real EasyOCR recognition
  of a Pillow-rendered "HELLO WORLD").
- `ruff check .`, `ruff format --check .`, `python -m compileall` → clean.
- `notebooks/demo.ipynb` executed with nbconvert: 7 code cells, 0 errors.
- GUI acceptance run **with the real MacBook Air camera**: MySQL connected, EasyOCR ready in 2 s,
  camera live at ~17 FPS, scan pipeline ran to `No text detected` (nothing readable in view),
  History/Stats/Export opened, window resized, Stop → Idle, Quit → zero leftover threads.
- GUI acceptance run **with synthetic 1280×720 frames through the real EasyOCR engine**: live
  overlay showed `INVOICE 2026-0917 (0.83)` and `TOTAL DUE 1,249.00 (0.60)`, Scan stored 2 rows
  per scan in MySQL (`scans` + `scan_sessions` verified with the mysql client), annotated PNGs
  written to `captures/`, CSV export produced, clean shutdown.
- Found and fixed during acceptance: on macOS the camera must be opened on the Tk main thread so
  AVFoundation can show the permission prompt (`OPEN_CAMERA_ON_MAIN_THREAD`).
- Not done: screenshots (the automated session had no screen-recording permission; see README).
