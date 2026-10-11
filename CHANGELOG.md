# Changelog

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
