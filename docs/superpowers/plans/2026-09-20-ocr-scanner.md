# Real-Time OCR Data Scanning Tool — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Tkinter desktop app that shows a live webcam feed, runs EasyOCR on frames in a worker thread, overlays detections, scans on demand, and persists scans to MySQL (SQLite fallback) with history, search, export and stats.

**Architecture:** Three layers. `core/` holds hardware/inference primitives (camera thread, OCR engine, preprocessing/drawing, audio, OCR worker thread, scan pipeline) with no Tk imports. `database/` holds a repository interface with MySQL and SQLite implementations behind a `DatabaseManager` that picks MySQL and falls back to SQLite. `gui/` holds Tk widgets that only ever touch Tk on the main thread; background threads post callables to a `queue.Queue` drained by `root.after`.

**Tech Stack:** Python 3.12, easyocr, opencv-python, Pillow, numpy, matplotlib (TkAgg), pygame, mysql-connector-python, python-dotenv, pytest, pytest-mock, ruff.

**Spec:** `docs/superpowers/specs/2026-09-20-ocr-scanner-spec.md` (verbatim copy of the user brief).

## Global Constraints

- Python 3.10–3.12 (developed on 3.12.13, uv-managed; Homebrew 3.12 on this Mac has a broken `pyexpat`).
- EasyOCR default `gpu=False`; `OCR_GPU=auto` probes `torch.cuda.is_available()`.
- Camera capture thread → bounded queue; OCR in a separate worker thread; **Tk touched only from main thread** via `root.after` + `queue.Queue`.
- Every DB query parameterized; credentials only from `.env`.
- MySQL unreachable → offline mode (SQLite at `data/offline_scans.sqlite3`), warning in console, app keeps working.
- Every exception logged with traceback to `logs/app.log`; user sees plain-language console line or messagebox.
- No `TODO`, stubs, placeholders, dead code. Typed, docstring'd, ruff-clean, `compileall` clean.
- Window title "OCR Data Scanning Tool", min size 1100x700, shortcuts L/S/Q/Esc.

---

## File Structure

| Path | Responsibility |
|---|---|
| `main.py` | CLI entry: args, logging, settings, dirs, Tk root, app, mainloop, top-level error dialog |
| `config/settings.py` | `Settings` dataclass loaded from `.env` with defaults + validation + `ensure_directories()` |
| `core/camera.py` | `CameraManager`: background capture thread, bounded frame queue, reconnect, FPS |
| `core/ocr_engine.py` | `OCRResult`, `OCREngine` (lazy EasyOCR reader, GPU resolution, `detect`) |
| `core/detector.py` | `PreprocessOptions`, `preprocess_frame`, `filter_by_confidence`, `scale_results`, `draw_detections` |
| `core/audio.py` | `AudioFeedback`: pygame beeps, no-op if mixer init fails |
| `core/ocr_worker.py` | `OCRWorker` thread: accepts live/scan jobs, drops stale live jobs, posts results via callbacks |
| `core/scan_pipeline.py` | `run_scan(...)`: capture → preprocess → OCR → save image → DB, emits progress steps; headless-testable |
| `database/models.py` | `ScanRecord`, `SessionRecord`, `ScanRepository` Protocol, `DatabaseError` |
| `database/mysql_repository.py` | `MySQLScanRepository`: pool, auto-create DB/tables, CRUD, search, stats, error mapping |
| `database/sqlite_repository.py` | `SQLiteScanRepository`: same interface on stdlib sqlite3 |
| `database/db_manager.py` | `DatabaseManager`: connect MySQL → fallback SQLite; `offline`, `backend_name`, `warning` |
| `database/schema.sql` | MySQL DDL (user-provided) |
| `gui/theme.py` | `apply_theme(root)`, palette + font constants, `build_app_icon()` |
| `gui/console_panel.py` | `ConsolePanel`: Listbox + Scrollbar, `insert(level, msg)`, `clear_screen()`, per-level colors |
| `gui/progress_panel.py` | `ProgressPanel`: Progressbar + status label; determinate steps / indeterminate / status text |
| `gui/control_panel.py` | `ControlPanel`: buttons, `set_state(AppState)`, settings vars (confidence, preprocess, camera index, live OCR) |
| `gui/video_canvas.py` | `VideoCanvas`: aspect-preserving frame display, "Camera Off" placeholder |
| `gui/history_view.py` | `HistoryWindow`: Treeview, search, delete, export, refresh |
| `gui/stats_view.py` | `StatsWindow`: matplotlib scans/day + confidence histogram via FigureCanvasTkAgg |
| `gui/app.py` | `OCRScannerApp`: wiring, state machine, UI queue pump, video loop, scan flow, clean shutdown |
| `utils/logger.py` | `setup_logging(logs_dir, level)`, `get_logger(name)` |
| `utils/helpers.py` | `timestamp_str`, `ensure_dir`, `is_blank_frame`, `fit_within`, `frame_to_pil`, `export_records` (csv/json/txt) |
| `tests/*` | see Tasks |
| `notebooks/demo.ipynb` | EasyOCR walkthrough on synthetic image |
| `README.md`, `CHANGELOG.md`, `requirements.txt`, `requirements-dev.txt`, `.env.example`, `.gitignore`, `pyproject.toml` (ruff+pytest config) | deliverables |

## Shared Interfaces (exact)

```python
# config/settings.py
@dataclass
class Settings:
    db_host: str = "localhost"; db_port: int = 3306; db_user: str = "root"; db_password: str = ""; db_name: str = "ocr_scanner"
    camera_index: int = 0; camera_width: int = 1280; camera_height: int = 720
    ocr_languages: list[str] = ["en"]; ocr_gpu: str = "auto"; ocr_every_n_frames: int = 10
    confidence_threshold: float = 0.4; preprocess_enabled: bool = True; audio_enabled: bool = True
    log_level: str = "INFO"
    base_dir: Path; captures_dir: Path; exports_dir: Path; logs_dir: Path; data_dir: Path; offline_db_path: Path; model_dir: Path | None
    @classmethod
    def load(cls, env_path: Path | None = None, base_dir: Path | None = None) -> "Settings"
    def ensure_directories(self) -> None
    @property
    def language_label(self) -> str  # "en" or "en+hi"

# core/ocr_engine.py
@dataclass
class OCRResult:
    text: str; confidence: float; bbox: list[list[int]]   # 4 points [[x,y],...]
    def to_dict(self) -> dict
class OCRInitError(RuntimeError)
class OCREngine:
    def __init__(self, languages: Sequence[str], gpu: str | bool = "auto", model_storage_dir: Path | None = None, reader_factory: Callable[..., Any] | None = None)
    @staticmethod
    def resolve_gpu(setting: str | bool) -> bool
    def warm_up(self) -> None            # loads reader; raises OCRInitError with plain message
    @property
    def is_ready(self) -> bool
    def detect(self, frame: np.ndarray, min_confidence: float = 0.0) -> list[OCRResult]

# core/detector.py
@dataclass
class PreprocessOptions: resize_width: int | None = None; denoise: bool = True; clahe: bool = True; adaptive_threshold: bool = False
def to_grayscale(frame) -> np.ndarray
def resize_to_width(gray, width) -> tuple[np.ndarray, float]   # returns (image, scale)
def preprocess_frame(frame, options: PreprocessOptions | None = None) -> tuple[np.ndarray, float]
def filter_by_confidence(results, threshold) -> list[OCRResult]
def scale_results(results, scale: float) -> list[OCRResult]     # divide coords by scale to map back
def draw_detections(frame, results, color=(0,255,0), thickness=2) -> np.ndarray

# core/camera.py
class CameraError(RuntimeError)
class CameraManager:
    def __init__(self, index: int = 0, width: int = 1280, height: int = 720, capture_factory=None, reconnect_attempts: int = 3, reconnect_delay: float = 1.0, on_status: Callable[[str, str], None] | None = None)
    def start(self) -> None          # raises CameraError
    def stop(self) -> None
    def read_latest(self) -> np.ndarray | None
    @property
    def is_running(self) -> bool
    @property
    def fps(self) -> float
    @property
    def last_error(self) -> str | None

# core/audio.py
class AudioFeedback:
    def __init__(self, enabled: bool = True)
    def init(self) -> bool
    @property
    def available(self) -> bool
    def beep_success(self) -> None
    def beep_error(self) -> None
    def shutdown(self) -> None

# core/ocr_worker.py
class OCRJob: kind: Literal["live","scan"]; frame: np.ndarray; job_id: int; min_confidence: float; payload: Any
class OCRWorker(threading.Thread):
    def __init__(self, engine: OCREngine, on_result: Callable[[OCRJob, list[OCRResult]], None], on_error: Callable[[OCRJob, Exception], None])
    def submit_live(self, frame, min_confidence) -> bool   # False if dropped (busy)
    def submit_scan(self, frame, min_confidence, payload=None) -> int
    def stop(self, timeout: float = 5.0) -> None

# core/scan_pipeline.py
SCAN_STEPS = ("Capturing frame", "Preprocessing", "Running OCR", "Saving image", "Writing to DB", "Done")
@dataclass
class ScanOutcome: results: list[OCRResult]; image_path: Path | None; scan_ids: list[int]; skipped_reason: str | None
def run_scan(frame, engine, repo, *, session_id, language, captures_dir, min_confidence, preprocess: PreprocessOptions | None, progress: Callable[[int, str], None]) -> ScanOutcome

# database/models.py
@dataclass
class ScanRecord: id: int | None; session_id: int | None; detected_text: str; confidence: float; bbox: list | None; image_path: str | None; language: str; created_at: datetime
class DatabaseError(RuntimeError)
class ScanRepository(Protocol):
    backend_name: str
    def create_session(self, started_at: datetime) -> int
    def end_session(self, session_id: int, ended_at: datetime, total_detections: int) -> None
    def insert_scan(self, record: ScanRecord) -> int
    def insert_scans(self, records: list[ScanRecord]) -> list[int]
    def fetch_scans(self, limit: int = 500, offset: int = 0) -> list[ScanRecord]
    def search_scans(self, query: str, limit: int = 500) -> list[ScanRecord]
    def delete_scan(self, scan_id: int) -> bool
    def count_scans(self) -> int
    def scans_per_day(self, days: int = 30) -> list[tuple[date, int]]
    def confidence_values(self, limit: int = 5000) -> list[float]
    def close(self) -> None

# database/db_manager.py
class DatabaseManager:
    def __init__(self, settings: Settings, connector_module=None)
    def connect(self) -> None      # never raises; sets .repo, .offline, .warning
    repo: ScanRepository; offline: bool; warning: str | None; backend_name: str
    def close(self) -> None

# utils/helpers.py
def timestamp_str(dt: datetime | None = None, for_filename: bool = False) -> str
def ensure_dir(path: Path) -> Path
def is_blank_frame(frame, mean_threshold: float = 8.0, std_threshold: float = 3.0) -> bool
def fit_within(src_w, src_h, max_w, max_h) -> tuple[int, int]
def frame_to_pil(frame_bgr) -> PIL.Image.Image
def export_records(records: Iterable[ScanRecord], path: Path, fmt: Literal["csv","json","txt"]) -> Path
```

---

## Tasks (TDD: write test → run red → implement → run green)

### Task 1: Scaffold + config + logging + helpers
- [x] `pyproject.toml` (ruff line-length 100, target py310; pytest testpaths, markers `slow`, `mysql`, `gui`), `.gitignore`, `.env.example`, `requirements*.txt`
- [x] `tests/conftest.py` adds repo root to `sys.path`, provides `tmp_settings` fixture
- [x] `tests/test_settings.py`: defaults, `.env` override, languages parsing `"en, hi"` → `["en","hi"]`, invalid ints fall back to defaults, `ensure_directories` creates dirs
- [x] `tests/test_helpers.py`: `is_blank_frame` (zeros → True, noise → False, None → True), `fit_within` aspect, `frame_to_pil` RGB size, `export_records` csv/json/txt validity (csv module parse, json.loads, txt contains text), `timestamp_str` filename-safe
- [x] Implement `config/settings.py`, `utils/logger.py`, `utils/helpers.py`
- [x] Run: `pytest tests/test_settings.py tests/test_helpers.py -q`

### Task 2: Detector / preprocessing
- [x] `tests/test_detector.py`: grayscale shape (H,W) uint8 from BGR and from gray; `resize_to_width` scale; `preprocess_frame` with every option combo returns uint8 2-D; `filter_by_confidence`; `scale_results` maps coords; `draw_detections` returns same shape copy and does not mutate input; label drawn above box stays in-frame (y ≥ 0)
- [x] Implement `core/detector.py`

### Task 3: OCR engine
- [x] `tests/test_ocr_engine.py`: `resolve_gpu("false")→False`, `("true")→True`, `("auto")` → bool; fake `reader_factory` returning object with `readtext` → `detect` converts tuples into `OCRResult` with int bbox, filters by threshold; invalid frame (None, empty, 1-D) → `ValueError`; reader construction failure → `OCRInitError` with friendly message; `@pytest.mark.slow` real EasyOCR on synthetic PIL image "HELLO WORLD" asserts `"HELLO"` in joined upper text
- [x] Implement `core/ocr_engine.py`

### Task 4: Camera manager
- [x] `tests/test_camera.py`: `FakeCapture` class (isOpened/read/set/get/release) driven by lists; open failure → `CameraError`; `start` then `read_latest` returns frame within 1s; `stop` joins thread and releases; read failures trigger reconnect (factory called again) and `on_status` gets "warn" then "ok"; exhausted reconnects → `is_running` False, `last_error` set, `on_status("error", ...)`
- [x] Implement `core/camera.py`

### Task 5: Audio
- [x] `tests/test_audio.py`: mixer init raising → `available` False and `beep_success` no-op; `enabled=False` never imports pygame mixer init
- [x] Implement `core/audio.py` (numpy sine → `pygame.sndarray.make_sound`, `PYGAME_HIDE_SUPPORT_PROMPT`)

### Task 6: Database layer
- [x] `database/schema.sql` verbatim from spec
- [x] `tests/test_db_manager.py`: parametrized over SQLite (always) and MySQL (skipped unless reachable via `OCR_TEST_MYSQL_*` env or `.env`): create_session → int; insert_scan/insert_scans → ids; fetch_scans ordering newest first; search_scans substring (case-insensitive); delete_scan True then False; count; scans_per_day; confidence_values; end_session updates. Mocked connector: errno 1045 → `DatabaseError` mentioning credentials; 2003 → mentions host/port. `DatabaseManager` with failing connector → `offline True`, `backend_name == "SQLite"`, `warning` non-empty, repo works
- [x] Implement `database/models.py`, `sqlite_repository.py`, `mysql_repository.py`, `db_manager.py`

### Task 7: OCR worker + scan pipeline (headless smoke test)
- [x] `tests/test_ocr_worker.py`: fake engine; `submit_live` twice quickly → second dropped while busy; results delivered via callback; error path via `on_error`; `stop()` joins
- [x] `tests/test_scan_pipeline.py`: synthetic frame + fake engine + SQLite repo → progress callback receives all 6 step labels in order; annotated PNG exists in captures dir; rows in DB match detections; blank frame → `skipped_reason` and no rows; zero detections → `skipped_reason="No text detected"` and no rows; `@pytest.mark.slow` real engine variant
- [x] Implement `core/ocr_worker.py`, `core/scan_pipeline.py`

### Task 8: GUI panels
- [x] `gui/theme.py`, `console_panel.py`, `progress_panel.py`, `control_panel.py`, `video_canvas.py`, `history_view.py`, `stats_view.py` (load `dataviz` skill before charts)
- [x] `tests/test_gui_panels.py` (`@pytest.mark.gui`, skip if `tk.Tk()` raises `TclError`): ConsolePanel insert/clear + cap; ProgressPanel step bounds; ControlPanel `set_state` toggles buttons; VideoCanvas shows placeholder then frame

### Task 9: App wiring + main
- [x] `gui/app.py`: `OCRScannerApp(root, settings, *, camera_factory=None, engine=None, db=None, audio=None)` — DI for tests; `AppState` enum IDLE/STARTING/RUNNING/SCANNING; UI queue pump 30 ms; video loop 33 ms; live OCR every N frames; scan flow using `run_scan` on worker thread with `progress` posting to UI queue; `quit_app()` full teardown; `WM_DELETE_WINDOW`; shortcuts
- [x] `main.py`
- [x] `tests/test_app_smoke.py` (`gui` marker): construct app with fake camera factory + fake engine + SQLite db, `root.withdraw()`, call `launch_camera()`, pump `root.update()` until frame shown, call `scan()`, pump until state returns RUNNING, assert `db.repo.count_scans() >= 1`, call `quit_app()`, assert no non-daemon threads left besides main

### Task 10: Static checks, real-GUI run, docs, notebook
- [x] `ruff check . && ruff format --check .`; `python -m compileall -q .`
- [x] Run GUI for real with camera (macOS permission), exercise buttons; record in CHANGELOG
- [x] `notebooks/demo.ipynb` via nbformat; execute with `jupyter nbconvert --execute`
- [x] `README.md` (overview, requirements, setup incl. VS Code + MySQL Workbench, run, tests, config table, troubleshooting table, screenshots section, Design Decisions), `CHANGELOG.md`
- [x] Final: full `pytest -q`, tree, summary

## Self-review notes
- Spec §5 shortcuts, min size, icon, placeholder canvas → Task 8/9. §6 every-Nth-frame, slider, preprocessing toggle, zero-detection → Tasks 7/9. §7 offline mode → Task 6. §8 error list → each module maps errors to plain messages; app logs traceback via `logger.exception`. §9 items 1–6 → Task 10.

## Execution log (2026-09-20)

All tasks executed in-session with test-first development. Final state: 119 tests passing
(`pytest -q`), `ruff check` / `ruff format --check` / `compileall` clean, notebook executed,
two GUI acceptance runs (real camera; synthetic frames through real EasyOCR into MySQL 8.4).
Deviation from Task 9: on macOS the camera is opened on the Tk main thread because AVFoundation
cannot show the permission prompt from a helper thread (see README → Design decisions #7).
