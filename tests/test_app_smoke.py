"""Headless smoke test: boot the full app with a synthetic camera and fake OCR engine."""

from __future__ import annotations

import threading
import time
import tkinter as tk
from pathlib import Path

import numpy as np
import pytest

from config.settings import Settings
from core.audio import AudioFeedback
from core.ocr_engine import OCRResult
from database.db_manager import DatabaseManager
from gui.control_panel import AppState

pytestmark = pytest.mark.gui


class FakeCamera:
    def __init__(self, frame: np.ndarray | None, fail_open: bool = False):
        self._frame = frame
        self._running = False
        self.fail_open = fail_open
        self.fps = 30.0
        self.last_error: str | None = None

    def start(self):
        if self.fail_open:
            from core.camera import CameraError

            raise CameraError("Camera 0 could not be opened")
        self._running = True

    def stop(self):
        self._running = False

    def read_latest(self):
        return self._frame.copy() if (self._running and self._frame is not None) else None

    @property
    def is_running(self):
        return self._running


class FakeEngine:
    def __init__(self):
        self.calls = 0
        self.is_ready = False

    def warm_up(self):
        self.is_ready = True

    def detect(self, frame, min_confidence=0.0):
        self.calls += 1
        results = [
            OCRResult("HELLO", 0.95, [[10, 10], [60, 10], [60, 30], [10, 30]]),
            OCRResult("faint", 0.2, [[0, 40], [20, 40], [20, 50], [0, 50]]),
        ]
        return [r for r in results if r.confidence >= min_confidence]


class FakeMySQLError(Exception):
    def __init__(self, msg, errno):
        super().__init__(msg)
        self.msg, self.errno = msg, errno


class DownConnector:
    Error = FakeMySQLError

    def connect(self, **kwargs):
        raise FakeMySQLError("Can't connect", 2003)


def _frame() -> np.ndarray:
    rng = np.random.default_rng(3)
    return rng.integers(60, 255, size=(120, 160, 3), dtype=np.uint8)


def _pump(root: tk.Tk, app, predicate, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.process_pending()
        if predicate():
            return True
        root.update()
        time.sleep(0.01)
    return predicate()


@pytest.fixture()
def root():
    try:
        window = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover
        pytest.skip(f"Tk display unavailable: {exc}")
    window.withdraw()
    yield window
    try:
        window.destroy()
    except tk.TclError:
        pass


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    env = tmp_path / ".env"
    env.write_text("OCR_EVERY_N_FRAMES=2\nAUDIO_ENABLED=false\n")
    cfg = Settings.load(env_path=env, base_dir=tmp_path)
    cfg.ensure_directories()
    return cfg


def _build(root, settings, camera: FakeCamera):
    from gui.app import OCRScannerApp

    db = DatabaseManager(settings, connector_module=DownConnector())
    db.connect()
    engine = FakeEngine()
    app = OCRScannerApp(
        root,
        settings,
        camera_factory=lambda index, on_status: camera,
        engine=engine,
        db=db,
        audio=AudioFeedback(enabled=False),
    )
    return app, engine, db


def test_full_scan_cycle_headless(root, settings):
    camera = FakeCamera(_frame())
    app, engine, db = _build(root, settings, camera)
    threads_before = {t.ident for t in threading.enumerate()}
    try:
        assert app.state is AppState.IDLE
        assert _pump(root, app, lambda: engine.is_ready)
        assert any("offline" in line.lower() for line in app.console.lines())

        app.launch_camera()
        assert _pump(root, app, lambda: app.video.has_frame)
        assert app.state is AppState.RUNNING
        assert _pump(root, app, lambda: engine.calls >= 2), "live OCR should run every Nth frame"

        app.scan()
        assert _pump(
            root, app, lambda: app.state is AppState.RUNNING and db.repo.count_scans() >= 1
        )
        rows = db.repo.fetch_scans()
        assert [r.detected_text for r in rows] == ["HELLO"]
        assert rows[0].image_path and Path(rows[0].image_path).exists()
        assert list(settings.captures_dir.glob("*.png"))
        lines = app.console.lines()
        assert any("HELLO" in line for line in lines)
        assert any("[OK]" in line and "SQLite" in line for line in lines)
        assert app.progress.value == 100
        assert "Detections 1" in app.progress.status_text

        app.stop_camera()
        assert app.state is AppState.IDLE
        assert camera.is_running is False
        assert app.video.has_frame is False
    finally:
        app.quit_app()
    assert app.worker.is_alive() is False
    leftover = [t for t in threading.enumerate() if t.ident not in threads_before and t.is_alive()]
    assert leftover == []


def test_scan_without_camera_is_reported(root, settings):
    app, _, db = _build(root, settings, FakeCamera(_frame()))
    try:
        assert _pump(root, app, lambda: app.worker.engine.is_ready)
        app.scan()
        app.process_pending()
        assert app.state is AppState.IDLE
        assert any("[WARN]" in line and "camera" in line.lower() for line in app.console.lines())
        assert db.repo.count_scans() == 0
    finally:
        app.quit_app()


def test_camera_open_failure_is_reported(root, settings):
    app, _, _ = _build(root, settings, FakeCamera(None, fail_open=True))
    try:
        app.launch_camera()
        assert _pump(
            root,
            app,
            lambda: (
                app.state is AppState.IDLE
                and any("[ERROR]" in line for line in app.console.lines())
            ),
        )
        assert any("could not be opened" in line for line in app.console.lines())
    finally:
        app.quit_app()


def test_keyboard_shortcuts_map_to_actions(root, settings):
    camera = FakeCamera(_frame())
    app, _, _ = _build(root, settings, camera)
    try:
        assert _pump(root, app, lambda: app.worker.engine.is_ready)
        app.handle_shortcut("l")
        assert _pump(root, app, lambda: app.state is AppState.RUNNING)
        app.handle_shortcut("escape")
        assert app.state is AppState.IDLE
        app.handle_shortcut("q")
        assert _pump(root, app, lambda: app.closed, timeout=2.0)
    finally:
        app.quit_app()


def test_clear_screen_and_export_all(root, settings, tmp_path):
    camera = FakeCamera(_frame())
    app, _, db = _build(root, settings, camera)
    try:
        assert _pump(root, app, lambda: app.worker.engine.is_ready)
        app.launch_camera()
        assert _pump(root, app, lambda: app.video.has_frame)
        app.scan()
        assert _pump(
            root, app, lambda: db.repo.count_scans() >= 1 and app.state is AppState.RUNNING
        )
        out = app.export_all(path=tmp_path / "all.json")
        assert out is not None and out.exists() and out.stat().st_size > 2
        app.clear_screen()
        assert app.console.lines() == []
    finally:
        app.quit_app()
