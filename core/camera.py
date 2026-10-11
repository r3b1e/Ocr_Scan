"""Threaded webcam capture with automatic reconnection.

`CameraManager` owns a background thread that reads frames from
`cv2.VideoCapture` into a small bounded queue. Consumers call `read_latest()`
from any thread; the newest frame always wins and stale frames are dropped.
"""

from __future__ import annotations

import contextlib
import queue
import threading
import time
from collections.abc import Callable
from typing import Any

import cv2
import numpy as np

from utils.logger import get_logger

log = get_logger("core.camera")

CaptureFactory = Callable[[int], Any]
StatusCallback = Callable[[str, str], None]


class CameraError(RuntimeError):
    """Raised with a plain-language message when the camera cannot be used."""


class CameraManager:
    """Open a camera, stream frames on a background thread and reconnect on failure."""

    def __init__(
        self,
        index: int = 0,
        width: int = 1280,
        height: int = 720,
        capture_factory: CaptureFactory | None = None,
        reconnect_attempts: int = 3,
        reconnect_delay: float = 1.0,
        on_status: StatusCallback | None = None,
        read_failure_limit: int = 5,
    ) -> None:
        self.index = index
        self.width = width
        self.height = height
        self.reconnect_attempts = reconnect_attempts
        self.reconnect_delay = reconnect_delay
        self.read_failure_limit = read_failure_limit
        self._factory: CaptureFactory = capture_factory or cv2.VideoCapture
        self._on_status = on_status
        self._capture: Any | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._frames: queue.Queue[np.ndarray] = queue.Queue(maxsize=2)
        self._latest: np.ndarray | None = None
        self._lock = threading.Lock()
        self._running = False
        self._fps = 0.0
        self._last_error: str | None = None

    # ------------------------------------------------------------------ public
    @property
    def is_running(self) -> bool:
        """True while the capture thread is delivering (or trying to deliver) frames."""
        return self._running

    @property
    def fps(self) -> float:
        """Smoothed frames-per-second measured from the capture thread."""
        return self._fps

    @property
    def last_error(self) -> str | None:
        """Plain-language description of why the camera stopped, if it did."""
        return self._last_error

    def start(self) -> None:
        """Open the camera and start streaming.

        Raises:
            CameraError: if the device is missing, busy or the backend fails.
        """
        if self._running:
            return
        self._capture = self._open()
        self._stop_event.clear()
        self._last_error = None
        self._fps = 0.0
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="camera-capture", daemon=True)
        self._thread.start()
        log.info("Camera %s started (%sx%s requested)", self.index, self.width, self.height)

    def stop(self) -> None:
        """Stop streaming, join the thread and release the device. Safe to call twice."""
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=5.0)
        self._thread = None
        self._release()
        self._running = False
        self._clear_frames()

    def read_latest(self) -> np.ndarray | None:
        """Return the newest available frame, or None when nothing has arrived yet."""
        newest: np.ndarray | None = None
        while True:
            try:
                newest = self._frames.get_nowait()
            except queue.Empty:
                break
        with self._lock:
            if newest is not None:
                self._latest = newest
            return self._latest

    # ----------------------------------------------------------------- private
    def _notify(self, level: str, message: str) -> None:
        if self._on_status is not None:
            try:
                self._on_status(level, message)
            except Exception:  # pragma: no cover - callback bugs must not kill capture
                log.exception("Camera status callback failed")

    def _open(self) -> Any:
        try:
            capture = self._factory(self.index)
        except Exception as exc:
            raise CameraError(
                f"Camera {self.index} could not be opened: {exc}. Check that the camera is "
                "connected and that no other application is using it."
            ) from exc
        if capture is None or not capture.isOpened():
            if capture is not None:
                with contextlib.suppress(Exception):
                    capture.release()
            raise CameraError(
                f"Camera {self.index} was not found or is already in use by another application."
            )
        with contextlib.suppress(Exception):
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        return capture

    def _release(self) -> None:
        with self._lock:
            capture, self._capture = self._capture, None
        if capture is not None:
            with contextlib.suppress(Exception):
                capture.release()

    def _clear_frames(self) -> None:
        while True:
            try:
                self._frames.get_nowait()
            except queue.Empty:
                break
        with self._lock:
            self._latest = None

    def _publish(self, frame: np.ndarray) -> None:
        while True:
            try:
                self._frames.put_nowait(frame)
                return
            except queue.Full:
                with contextlib.suppress(queue.Empty):
                    self._frames.get_nowait()

    def _read(self) -> np.ndarray | None:
        capture = self._capture
        if capture is None:
            return None
        try:
            ok, frame = capture.read()
        except Exception:
            log.exception("Camera read raised")
            return None
        if not ok or frame is None or getattr(frame, "size", 0) == 0:
            return None
        return frame

    def _update_fps(self, previous: float) -> float:
        now = time.perf_counter()
        delta = now - previous
        if delta > 0:
            instant = 1.0 / delta
            self._fps = instant if self._fps == 0.0 else 0.9 * self._fps + 0.1 * instant
        return now

    def _reconnect(self) -> bool:
        self._release()
        for attempt in range(1, self.reconnect_attempts + 1):
            if self._stop_event.wait(self.reconnect_delay):
                return False
            try:
                self._capture = self._open()
            except CameraError as exc:
                log.warning(
                    "Reconnect attempt %s/%s failed: %s", attempt, self.reconnect_attempts, exc
                )
                continue
            return True
        return False

    def _loop(self) -> None:
        failures = 0
        last_tick = time.perf_counter()
        while not self._stop_event.is_set():
            frame = self._read()
            if frame is not None:
                failures = 0
                self._publish(frame)
                last_tick = self._update_fps(last_tick)
                continue
            failures += 1
            if failures < self.read_failure_limit:
                self._stop_event.wait(0.01)
                continue
            self._notify(
                "warn", f"Camera {self.index} stopped delivering frames; trying to reconnect..."
            )
            if self._reconnect():
                failures = 0
                self._notify("ok", f"Camera {self.index} reconnected.")
                continue
            if not self._stop_event.is_set():
                self._last_error = (
                    f"Camera {self.index} was disconnected and could not be reconnected after "
                    f"{self.reconnect_attempts} attempts. Check the cable and press Launch again."
                )
                log.error(self._last_error)
                self._running = False
                self._release()
                self._notify("error", self._last_error)
            break
        self._release()
        self._running = False
