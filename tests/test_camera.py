"""Tests for core.camera using a fake cv2.VideoCapture (no hardware)."""

from __future__ import annotations

import threading
import time

import numpy as np
import pytest

from core.camera import CameraError, CameraManager


def _frame(value: int = 100) -> np.ndarray:
    return np.full((48, 64, 3), value, dtype=np.uint8)


class FakeCapture:
    """Minimal stand-in for cv2.VideoCapture driven by a sequence of read outcomes."""

    def __init__(self, outcomes, opened: bool = True):
        self._outcomes = list(outcomes)
        self._opened = opened
        self.released = False
        self.props: dict[int, float] = {}

    def isOpened(self):  # noqa: N802 - mirrors cv2 API
        return self._opened

    def read(self):
        if self._outcomes:
            self._last = self._outcomes.pop(0)
        frame = getattr(self, "_last", None)
        if frame is None:
            return False, None
        return True, frame.copy()

    def set(self, prop, value):
        self.props[prop] = value
        return True

    def get(self, prop):
        return self.props.get(prop, 0.0)

    def release(self):
        self.released = True
        self._opened = False


def _wait_for(predicate, timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def test_start_raises_camera_error_when_device_missing():
    cam = CameraManager(index=3, capture_factory=lambda idx: FakeCapture([], opened=False))
    with pytest.raises(CameraError) as excinfo:
        cam.start()
    assert "3" in str(excinfo.value)
    assert cam.is_running is False


def test_start_raises_camera_error_when_factory_explodes():
    def factory(idx):
        raise RuntimeError("backend exploded")

    cam = CameraManager(index=0, capture_factory=factory)
    with pytest.raises(CameraError):
        cam.start()


def test_read_latest_returns_frames_after_start():
    capture = FakeCapture([_frame(10), _frame(20), _frame(30)])
    cam = CameraManager(index=0, width=64, height=48, capture_factory=lambda idx: capture)
    cam.start()
    try:
        assert cam.is_running is True
        assert _wait_for(lambda: cam.read_latest() is not None)
        frame = cam.read_latest()
        assert frame.shape == (48, 64, 3)
        assert _wait_for(lambda: cam.fps > 0)
    finally:
        cam.stop()


def test_stop_joins_thread_and_releases_capture():
    capture = FakeCapture([_frame()])
    cam = CameraManager(index=0, capture_factory=lambda idx: capture)
    cam.start()
    before = threading.active_count()
    cam.stop()
    assert capture.released is True
    assert cam.is_running is False
    assert threading.active_count() == before - 1
    assert cam.read_latest() is None


def test_read_latest_before_start_is_none_and_stop_is_idempotent():
    cam = CameraManager(index=0, capture_factory=lambda idx: FakeCapture([_frame()]))
    assert cam.read_latest() is None
    cam.stop()
    cam.stop()


def test_reconnects_after_read_failures():
    statuses: list[tuple[str, str]] = []
    first = FakeCapture([_frame(1), None, None, None, None, None, None])
    second = FakeCapture([_frame(2)])
    captures = [first, second]

    def factory(idx):
        return captures.pop(0) if captures else FakeCapture([_frame(3)])

    cam = CameraManager(
        index=0,
        capture_factory=factory,
        reconnect_attempts=3,
        reconnect_delay=0.01,
        on_status=lambda level, msg: statuses.append((level, msg)),
    )
    cam.start()
    try:
        assert _wait_for(
            lambda: (
                first.released
                and cam.read_latest() is not None
                and int(cam.read_latest()[0, 0, 0]) == 2
            )
        )
        levels = [level for level, _ in statuses]
        assert "warn" in levels and "ok" in levels
        assert levels.index("warn") < levels.index("ok")
        assert cam.is_running is True
    finally:
        cam.stop()


def test_gives_up_after_exhausting_reconnect_attempts():
    statuses: list[tuple[str, str]] = []
    calls = {"n": 0}

    def factory(idx):
        calls["n"] += 1
        if calls["n"] == 1:
            return FakeCapture([_frame(), None])
        return FakeCapture([], opened=False)

    cam = CameraManager(
        index=0,
        capture_factory=factory,
        reconnect_attempts=2,
        reconnect_delay=0.01,
        on_status=lambda level, msg: statuses.append((level, msg)),
    )
    cam.start()
    try:
        assert _wait_for(lambda: cam.is_running is False, timeout=3.0)
        assert cam.last_error
        assert calls["n"] == 3  # initial open + 2 reconnect attempts
        assert statuses and statuses[-1][0] == "error"
    finally:
        cam.stop()
