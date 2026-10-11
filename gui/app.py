"""Main window: wires camera, OCR worker, database, audio and the Tk panels together.

Threading contract: everything in this module runs on the Tk main thread. Other
threads (camera, OCR worker, camera opener) never touch widgets - they call
`_post(callable)`, and `_pump()` executes those callables on the main thread.
"""

from __future__ import annotations

import queue
import sys
import threading
import tkinter as tk
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Any

import cv2

from config.settings import Settings
from core.audio import AudioFeedback
from core.camera import CameraError, CameraManager
from core.detector import PreprocessOptions, draw_detections
from core.ocr_engine import OCREngine, OCRInitError, OCRResult
from core.ocr_worker import OCRJob, OCRWorker
from core.scan_pipeline import SCAN_STEPS, STEP_OCR, ScanOutcome, run_scan
from database.db_manager import DatabaseManager
from database.models import DatabaseError, ScanRecord
from gui.console_panel import ConsolePanel
from gui.control_panel import AppState, ControlCallbacks, ControlPanel
from gui.history_view import HistoryWindow
from gui.progress_panel import ProgressPanel
from gui.stats_view import StatsWindow
from gui.theme import apply_theme, build_app_icon
from gui.video_canvas import VideoCanvas
from utils.helpers import EXPORT_FORMATS, ExportFormat, export_records
from utils.logger import get_logger

log = get_logger("gui.app")

CameraFactory = Callable[[int, Callable[[str, str], None]], Any]
_TEXT_WIDGETS = (tk.Entry, ttk.Entry, ttk.Spinbox, tk.Text, ttk.Combobox)
_STATUS_LEVELS = {"ok": "OK", "warn": "WARN", "error": "ERROR", "info": "INFO"}
# macOS: AVFoundation can only show the camera-permission prompt from the main thread, and
# OpenCV refuses to open the device from any other thread until permission is granted.
OPEN_CAMERA_ON_MAIN_THREAD = sys.platform == "darwin"


class _NoStorage:
    """Repository stand-in used when both MySQL and SQLite are unavailable."""

    backend_name = "none"

    def insert_scans(self, records: list[ScanRecord]) -> list[int]:
        """Store nothing and return no ids."""
        return []


class OCRScannerApp:
    """The application controller and main window."""

    TITLE = "OCR Data Scanning Tool"
    MIN_SIZE = (1100, 700)
    UI_PUMP_MS = 30
    VIDEO_TICK_MS = 33

    def __init__(
        self,
        root: tk.Tk,
        settings: Settings,
        *,
        camera_factory: CameraFactory | None = None,
        engine: OCREngine | Any | None = None,
        db: DatabaseManager | None = None,
        audio: AudioFeedback | None = None,
    ) -> None:
        self.root = root
        self.settings = settings
        self.state = AppState.IDLE
        self.closed = False
        self._ui_queue: queue.Queue[Callable[[], None]] = queue.Queue()
        self._after_ids: dict[str, str] = {}
        self._camera: Any | None = None
        self._camera_thread: threading.Thread | None = None
        self._camera_factory: CameraFactory = camera_factory or self._default_camera_factory
        self._frame_counter = 0
        self._live_results: list[OCRResult] = []
        self._detections_count = 0
        self._last_confidence: float | None = None
        self._session_id: int | None = None
        self._session_detections = 0
        self._history: HistoryWindow | None = None
        self._stats: StatsWindow | None = None

        root.title(self.TITLE)
        root.minsize(*self.MIN_SIZE)
        apply_theme(root)
        try:
            self._icon = build_app_icon(root)
            root.iconphoto(True, self._icon)
        except tk.TclError:  # pragma: no cover - platform specific
            log.warning("Could not set the window icon", exc_info=True)
        self._build_layout()

        self.db = db or DatabaseManager(settings)
        if self.db.repo is None:
            self.db.connect()
        self.engine = engine or OCREngine(
            settings.ocr_languages, gpu=settings.ocr_gpu, model_storage_dir=settings.model_dir
        )
        self.audio = audio or AudioFeedback(enabled=settings.audio_enabled)
        self.audio.init()
        self.worker = OCRWorker(
            self.engine,
            on_result=self._on_worker_result,
            on_error=self._on_worker_error,
            on_ready=self._on_engine_ready,
        )
        self._log_startup()
        self.worker.start()

        root.protocol("WM_DELETE_WINDOW", self.quit_app)
        root.bind_all("<Key>", self._on_key)
        self._schedule("pump", self.UI_PUMP_MS, self._pump)
        self._schedule("video", self.VIDEO_TICK_MS, self._video_tick)
        self._update_status()

    # ================================================================ layout
    def _build_layout(self) -> None:
        root = self.root
        root.columnconfigure(0, weight=1)
        root.columnconfigure(1, weight=0)
        root.rowconfigure(0, weight=1)
        root.rowconfigure(1, weight=0)
        root.rowconfigure(2, weight=0)

        self.video = VideoCanvas(root, width=960, height=540)
        self.video.grid(row=0, column=0, sticky="nsew", padx=(10, 6), pady=(10, 6))

        callbacks = ControlCallbacks(
            launch=self.launch_camera,
            scan=self.scan,
            stop=self.stop_camera,
            clear=self.clear_screen,
            history=self.open_history,
            stats=self.open_stats,
            export=self.export_all,
            quit=self.quit_app,
        )
        self.controls = ControlPanel(
            root,
            callbacks,
            confidence=self.settings.confidence_threshold,
            preprocess=self.settings.preprocess_enabled,
            camera_index=self.settings.camera_index,
        )
        self.controls.grid(row=0, column=1, rowspan=3, sticky="ns", padx=(6, 10), pady=10)

        self.progress = ProgressPanel(root)
        self.progress.grid(row=1, column=0, sticky="ew", padx=(10, 6), pady=(0, 6))

        self.console = ConsolePanel(root)
        self.console.grid(row=2, column=0, sticky="nsew", padx=(10, 6), pady=(0, 10))

    def _log_startup(self) -> None:
        self.console.insert(
            "INFO", f"{self.TITLE} started. Logs: {self.settings.logs_dir / 'app.log'}"
        )
        if self.db.repo is None:
            self.console.insert("ERROR", self.db.warning or "No database available.")
        elif self.db.offline:
            self.console.insert("WARN", self.db.warning or "Running in offline mode.")
        else:
            self.console.insert(
                "OK",
                f"Connected to MySQL database '{self.settings.db_name}' at "
                f"{self.settings.db_host}:{self.settings.db_port}.",
            )
        if self.settings.audio_enabled and not self.audio.available:
            self.console.insert(
                "WARN", "Audio feedback unavailable (no audio device); continuing silently."
            )
        device = getattr(self.engine, "device_label", "CPU")
        self.console.insert(
            "INFO",
            f"Loading EasyOCR models for {'+'.join(self.settings.ocr_languages)} on {device}...",
        )
        self.console.insert("INFO", "Shortcuts: L = launch camera, S = scan, Esc = stop, Q = quit.")

    # ============================================================ threading
    def _post(self, callback: Callable[[], None]) -> None:
        """Queue `callback` to run on the Tk main thread."""
        self._ui_queue.put(callback)

    def process_pending(self) -> None:
        """Run every queued main-thread callback now (also used by tests)."""
        while True:
            try:
                callback = self._ui_queue.get_nowait()
            except queue.Empty:
                return
            if self.closed:
                continue
            try:
                callback()
            except tk.TclError:
                log.debug("UI callback hit a destroyed widget", exc_info=True)
            except Exception as exc:
                log.exception("UI callback failed")
                self._safe_console("ERROR", f"Internal error: {exc} (see logs/app.log)")

    def _pump(self) -> None:
        self.process_pending()
        self._schedule("pump", self.UI_PUMP_MS, self._pump)

    def _schedule(self, key: str, delay_ms: int, callback: Callable[[], None]) -> None:
        if self.closed:
            return
        self._after_ids[key] = self.root.after(delay_ms, callback)

    def _safe_console(self, level: str, message: str) -> None:
        try:
            self.console.insert(level, message)
        except tk.TclError:  # pragma: no cover - window already gone
            pass

    # ================================================================ state
    def _set_state(self, state: AppState) -> None:
        self.state = state
        self.controls.set_state(state)

    def _update_status(self, fps: float | None = None) -> None:
        camera = self._camera
        running = camera is not None and camera.is_running
        self.progress.update_status(
            fps=fps if fps is not None else (camera.fps if running else 0.0),
            detections=self._detections_count,
            last_confidence=self._last_confidence,
            camera=str(self._camera_index()) if running else "off",
            backend=self.db.backend_name,
        )

    def _camera_index(self) -> int:
        try:
            return max(0, int(self.controls.camera_index_var.get()))
        except (tk.TclError, ValueError):
            return self.settings.camera_index

    def _default_camera_factory(
        self, index: int, on_status: Callable[[str, str], None]
    ) -> CameraManager:
        return CameraManager(
            index=index,
            width=self.settings.camera_width,
            height=self.settings.camera_height,
            on_status=on_status,
        )

    # =============================================================== camera
    def launch_camera(self) -> None:
        """Open the selected camera on a helper thread and start streaming."""
        if self.state is not AppState.IDLE:
            return
        index = self._camera_index()
        self._set_state(AppState.STARTING)
        self.console.insert("INFO", f"Launching camera {index}...")
        camera = self._camera_factory(index, self._on_camera_status)
        if OPEN_CAMERA_ON_MAIN_THREAD:
            self.root.update_idletasks()
            self._open_camera(camera, index)
            self.process_pending()
            return
        self._camera_thread = threading.Thread(
            target=self._open_camera, args=(camera, index), name="camera-open", daemon=True
        )
        self._camera_thread.start()

    def _open_camera(self, camera: Any, index: int) -> None:
        """Open the device (blocking) and report back to the main thread via the UI queue."""
        try:
            camera.start()
        except CameraError as exc:
            message = str(exc)
            log.error("Camera %s failed to start: %s", index, message)
            self._post(lambda: self._camera_failed(message))
        except Exception as exc:
            message = f"Unexpected camera error: {exc}"
            log.exception("Unexpected camera failure")
            self._post(lambda: self._camera_failed(message))
        else:
            self._post(lambda: self._camera_started(camera, index))

    def _camera_started(self, camera: Any, index: int) -> None:
        if self.state is not AppState.STARTING:
            camera.stop()
            return
        self._camera = camera
        self._frame_counter = 0
        self._live_results = []
        self._start_session()
        self._set_state(AppState.RUNNING)
        self.console.insert("OK", f"Camera {index} is live.")
        self._update_status()

    def _camera_failed(self, message: str) -> None:
        self._set_state(AppState.IDLE)
        self.console.insert("ERROR", message)
        self.video.show_placeholder("Camera Off")
        self._update_status()

    def _on_camera_status(self, level: str, message: str) -> None:
        """Called from the camera thread on reconnects/disconnects."""

        def handle() -> None:
            self.console.insert(_STATUS_LEVELS.get(level, "INFO"), message)
            if level == "error":
                self._camera_lost()

        self._post(handle)

    def _camera_lost(self) -> None:
        camera, self._camera = self._camera, None
        if camera is not None:
            camera.stop()
        self._end_session()
        self._live_results = []
        if self.state is not AppState.SCANNING:
            self._set_state(AppState.IDLE)
        self.video.show_placeholder("Camera disconnected")
        self._update_status()

    def stop_camera(self) -> None:
        """Stop streaming and release the camera."""
        if self.state is AppState.IDLE:
            return
        if self.state is AppState.SCANNING:
            self.console.insert(
                "WARN", "A scan is in progress; wait for it to finish before stopping."
            )
            return
        camera, self._camera = self._camera, None
        if camera is not None:
            camera.stop()
        self._end_session()
        self._live_results = []
        self.video.show_placeholder("Camera Off")
        self.progress.reset()
        self._set_state(AppState.IDLE)
        self.console.insert("INFO", "Camera stopped.")
        self._update_status()

    def _video_tick(self) -> None:
        camera = self._camera
        if camera is not None and self.state in (AppState.RUNNING, AppState.SCANNING):
            frame = camera.read_latest()
            if frame is not None:
                self._frame_counter += 1
                if (
                    self.state is AppState.RUNNING
                    and self.controls.live_ocr_var.get()
                    and self.worker.ready
                    and self._frame_counter % self.settings.ocr_every_n_frames == 0
                ):
                    self.worker.submit_live(frame.copy(), float(self.controls.confidence_var.get()))
                display = (
                    draw_detections(frame, self._live_results) if self._live_results else frame
                )
                self.video.show_frame(display)
            self._update_status(fps=camera.fps)
        self._schedule("video", self.VIDEO_TICK_MS, self._video_tick)

    # ============================================================= sessions
    def _start_session(self) -> None:
        self._session_detections = 0
        if self.db.repo is None:
            return
        try:
            self._session_id = self.db.repo.create_session(datetime.now())
        except DatabaseError as exc:
            log.exception("Could not create scan session")
            self._session_id = None
            self.console.insert("WARN", f"Could not record the session in the database: {exc}")

    def _end_session(self) -> None:
        session_id, self._session_id = self._session_id, None
        if session_id is None or self.db.repo is None:
            return
        try:
            self.db.repo.end_session(session_id, datetime.now(), self._session_detections)
        except DatabaseError as exc:
            log.exception("Could not close scan session")
            self._safe_console("WARN", f"Could not close the session in the database: {exc}")

    # ================================================================= scan
    def scan(self) -> None:
        """Grab the current frame and run the full scan pipeline on the worker thread."""
        if self.state is AppState.IDLE or self.state is AppState.STARTING:
            self.console.insert("WARN", "Launch the camera before scanning.")
            return
        if self.state is AppState.SCANNING:
            self.console.insert("WARN", "A scan is already running.")
            return
        frame = self._camera.read_latest() if self._camera is not None else None
        if frame is None:
            self.console.insert("WARN", "No camera frame available yet - try again in a moment.")
            return
        if not self.worker.ready:
            reason = self.worker.init_error
            self.console.insert(
                "WARN" if reason is None else "ERROR",
                "The OCR engine is still loading; try again shortly."
                if reason is None
                else f"Cannot scan: {reason}",
            )
            return

        repo = self.db.repo if self.db.repo is not None else _NoStorage()
        if isinstance(repo, _NoStorage):
            self.console.insert(
                "WARN", "No database available - results will be shown but not saved."
            )
        preprocess = PreprocessOptions() if self.controls.preprocess_var.get() else None
        min_confidence = float(self.controls.confidence_var.get())
        snapshot = frame.copy()
        self._set_state(AppState.SCANNING)
        self.progress.begin(len(SCAN_STEPS))
        self.console.insert(
            "INFO",
            f"Scan started (threshold {min_confidence:.2f}, preprocessing "
            f"{'on' if preprocess else 'off'}).",
        )
        self.worker.submit_task(
            lambda: run_scan(
                snapshot,
                self.engine,
                repo,
                session_id=self._session_id,
                language=self.settings.language_label,
                captures_dir=self.settings.captures_dir,
                min_confidence=min_confidence,
                preprocess=preprocess,
                progress=self._scan_progress,
            ),
            payload="scan",
        )

    def _scan_progress(self, index: int, label: str) -> None:
        """Called from the worker thread for every pipeline step."""

        def handle() -> None:
            if index == STEP_OCR:
                self.progress.start_indeterminate(label)
            else:
                self.progress.step(index, label)
            if index < len(SCAN_STEPS) - 1:
                self.console.insert("INFO", f"Step {index + 1}/{len(SCAN_STEPS)}: {label}")

        self._post(handle)

    def _after_scan_state(self) -> None:
        running = self._camera is not None and self._camera.is_running
        self._set_state(AppState.RUNNING if running else AppState.IDLE)

    def _handle_scan_outcome(self, outcome: ScanOutcome) -> None:
        self._after_scan_state()
        if outcome.skipped_reason:
            self.progress.finish("Nothing stored")
            self.console.insert("WARN", outcome.skipped_reason)
            self.audio.beep_error()
            self._update_status()
            return
        for result in outcome.results:
            self.console.insert(
                "OK", f"Detected '{result.text}' (confidence {result.confidence:.2f})"
            )
        self.console.insert("INFO", f"Saved annotated image: {outcome.image_path}")
        if outcome.scan_ids:
            self.console.insert(
                "OK", f"Stored {len(outcome.scan_ids)} detection(s) in {self.db.backend_name}."
            )
        self._detections_count = len(outcome.results)
        self._session_detections += len(outcome.results)
        self._last_confidence = max(result.confidence for result in outcome.results)
        self.progress.finish("Done")
        self.audio.beep_success()
        self._update_status()

    def _handle_scan_error(self, exc: Exception) -> None:
        self._after_scan_state()
        self.progress.finish("Failed")
        self.audio.beep_error()
        if isinstance(exc, DatabaseError):
            message = f"Scan finished but the results could not be saved: {exc}"
        elif isinstance(exc, OSError):
            message = f"Could not save the capture image: {exc}"
        elif isinstance(exc, ValueError):
            message = f"Scan skipped: {exc}"
        elif isinstance(exc, OCRInitError):
            message = str(exc)
        else:
            message = f"Scan failed: {exc} (see logs/app.log)"
        self.console.insert("ERROR", message)
        self._update_status()

    # ======================================================= worker callbacks
    def _on_worker_result(self, job: OCRJob, result: Any) -> None:
        if job.kind == "live":
            results: list[OCRResult] = result

            def show_live() -> None:
                self._live_results = results
                self._detections_count = len(results)
                if results:
                    self._last_confidence = max(r.confidence for r in results)

            self._post(show_live)
        else:
            self._post(lambda: self._handle_scan_outcome(result))

    def _on_worker_error(self, job: OCRJob, exc: Exception) -> None:
        if job.kind == "live":
            log.warning("Live OCR error: %s", exc)
            return
        self._post(lambda: self._handle_scan_error(exc))

    def _on_engine_ready(self, exc: Exception | None) -> None:
        def handle() -> None:
            if exc is None:
                device = getattr(self.engine, "device_label", "CPU")
                self.console.insert("OK", f"OCR engine ready ({device}).")
            else:
                self.console.insert("ERROR", f"{exc} Scanning is unavailable until this is fixed.")

        self._post(handle)

    # ============================================================ utilities
    def clear_screen(self) -> None:
        """Clear the console and reset the progress bar."""
        self.console.clear_screen()
        self.progress.reset()

    def open_history(self) -> None:
        """Open (or focus) the history window."""
        if self.db.repo is None:
            self.console.insert("ERROR", "No database available; history cannot be shown.")
            return
        if self._history is not None and self._history.winfo_exists():
            self._history.refresh()
            self._history.lift()
            return
        self._history = HistoryWindow(
            self.root, self.db.repo, self.settings.exports_dir, self.console.insert
        )

    def open_stats(self) -> None:
        """Open (or refresh) the statistics window."""
        if self.db.repo is None:
            self.console.insert("ERROR", "No database available; statistics cannot be shown.")
            return
        if self._stats is not None and self._stats.winfo_exists():
            self._stats.refresh()
            self._stats.lift()
            return
        self._stats = StatsWindow(self.root, self.db.repo, self.console.insert)

    def export_all(self, fmt: str | None = None, path: Path | None = None) -> Path | None:
        """Export every scan. Without `path`, ask the user where to save (format = extension)."""
        if self.db.repo is None:
            self.console.insert("ERROR", "No database available; nothing to export.")
            return None
        if path is None:
            chosen = filedialog.asksaveasfilename(
                parent=self.root,
                title="Export all scans",
                initialdir=str(self.settings.exports_dir),
                initialfile=f"scans_{datetime.now():%Y%m%d_%H%M%S}.csv",
                defaultextension=".csv",
                filetypes=[("CSV", "*.csv"), ("JSON", "*.json"), ("Text", "*.txt")],
            )
            if not chosen:
                return None
            path = Path(chosen)
        export_format = (fmt or path.suffix.lstrip(".")).lower()
        if export_format not in EXPORT_FORMATS:
            export_format = "csv"
            path = path.with_suffix(".csv")
        typed_format: ExportFormat = export_format  # type: ignore[assignment]
        try:
            records = self.db.repo.fetch_scans(limit=1_000_000)
            out = export_records(records, path, typed_format)
        except (DatabaseError, OSError) as exc:
            log.exception("Export failed")
            self.console.insert("ERROR", f"Export failed: {exc}")
            return None
        self.console.insert("OK", f"Exported {len(records)} scan(s) to {out}")
        return out

    # ============================================================ keyboard
    def _on_key(self, event: tk.Event) -> None:
        if isinstance(event.widget, _TEXT_WIDGETS):
            return
        self.handle_shortcut(str(event.keysym).lower())

    def handle_shortcut(self, key: str) -> None:
        """Dispatch a keyboard shortcut: l/s/q/escape."""
        if key == "l":
            self.launch_camera()
        elif key == "s":
            self.scan()
        elif key == "q":
            self.quit_app()
        elif key == "escape":
            self.stop_camera()

    # ============================================================ shutdown
    def quit_app(self) -> None:
        """Stop every thread, release the camera, close the database and destroy the window."""
        if self.closed:
            return
        self.closed = True
        log.info("Shutting down")
        for after_id in self._after_ids.values():
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                pass
        self._after_ids.clear()
        if self._camera_thread is not None and self._camera_thread.is_alive():
            self._camera_thread.join(timeout=5.0)
        camera, self._camera = self._camera, None
        if camera is not None:
            camera.stop()
        self.worker.stop(timeout=10.0)
        self._end_session()
        self.db.close()
        self.audio.shutdown()
        try:
            cv2.destroyAllWindows()
        except cv2.error:  # pragma: no cover - headless OpenCV builds
            pass
        for window in (self._history, self._stats):
            if window is not None:
                try:
                    window.destroy()
                except tk.TclError:
                    pass
        try:
            self.root.destroy()
        except tk.TclError:
            pass
