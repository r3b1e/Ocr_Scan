"""Single background thread that serialises all OCR inference.

Live-preview frames are dropped while the worker is busy so the queue can
never grow; scan tasks are always queued. Results are delivered through
callbacks that run *on the worker thread* - the GUI forwards them to Tk via its
own thread-safe queue.
"""

from __future__ import annotations

import itertools
import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from core.ocr_engine import OCREngine, OCRResult
from utils.logger import get_logger

log = get_logger("core.ocr_worker")

JobKind = Literal["live", "task"]
ResultCallback = Callable[["OCRJob", Any], None]
ErrorCallback = Callable[["OCRJob", Exception], None]
ReadyCallback = Callable[[Exception | None], None]


@dataclass
class OCRJob:
    """A unit of work for the worker: a live frame or an arbitrary task callable."""

    kind: JobKind
    job_id: int
    frame: np.ndarray | None = None
    min_confidence: float = 0.0
    task: Callable[[], Any] | None = None
    payload: Any = None


class _Stop:
    """Sentinel placed on the queue to wake the thread up during shutdown."""


class OCRWorker(threading.Thread):
    """Warm up the engine, then process jobs until `stop()` is called."""

    def __init__(
        self,
        engine: OCREngine | Any,
        on_result: ResultCallback,
        on_error: ErrorCallback,
        on_ready: ReadyCallback | None = None,
    ) -> None:
        super().__init__(name="ocr-worker", daemon=True)
        self.engine = engine
        self._on_result = on_result
        self._on_error = on_error
        self._on_ready = on_ready
        self._queue: queue.Queue[OCRJob | _Stop] = queue.Queue()
        self._ids = itertools.count(1)
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._busy = False
        self._live_pending = False
        self._ready = False
        self._init_error: Exception | None = None

    # ------------------------------------------------------------------ state
    @property
    def busy(self) -> bool:
        """True while a job is executing."""
        return self._busy

    @property
    def ready(self) -> bool:
        """True once the engine warmed up successfully."""
        return self._ready

    @property
    def init_error(self) -> Exception | None:
        """The warm-up exception, if the engine failed to initialise."""
        return self._init_error

    # ------------------------------------------------------------- submitting
    def submit_live(self, frame: np.ndarray, min_confidence: float) -> bool:
        """Queue a live-preview frame; returns False when dropped (busy or not ready)."""
        with self._lock:
            if (
                self._stop_event.is_set()
                or not self._ready
                or self._init_error is not None
                or self._busy
                or self._live_pending
            ):
                return False
            self._live_pending = True
        self._queue.put(OCRJob("live", next(self._ids), frame=frame, min_confidence=min_confidence))
        return True

    def submit_task(self, task: Callable[[], Any], payload: Any = None) -> int:
        """Queue a callable to run on the worker thread; its return value goes to `on_result`."""
        job = OCRJob("task", next(self._ids), task=task, payload=payload)
        self._queue.put(job)
        return job.job_id

    # ---------------------------------------------------------------- running
    def run(self) -> None:  # noqa: D102 - Thread API
        try:
            self.engine.warm_up()
            with self._lock:
                self._ready = True
            self._callback(self._on_ready, None)
        except Exception as exc:
            with self._lock:
                self._init_error = exc
            log.error("OCR engine failed to initialise: %s", exc)
            self._callback(self._on_ready, exc)

        while not self._stop_event.is_set():
            try:
                job = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if isinstance(job, _Stop):
                break
            self._process(job)

    def _process(self, job: OCRJob) -> None:
        with self._lock:
            self._busy = True
            if job.kind == "live":
                self._live_pending = False
        try:
            if self._init_error is not None:
                raise self._init_error
            if job.kind == "live":
                assert job.frame is not None
                result: Any = self.engine.detect(job.frame, job.min_confidence)
            else:
                assert job.task is not None
                result = job.task()
        except Exception as exc:
            if job.kind == "task":
                log.exception("OCR task %s failed", job.job_id)
            else:
                log.warning("Live OCR failed: %s", exc)
            self._callback(self._on_error, job, exc)
        else:
            self._callback(self._on_result, job, result)
        finally:
            with self._lock:
                self._busy = False

    @staticmethod
    def _callback(callback: Callable[..., None] | None, *args: Any) -> None:
        if callback is None:
            return
        try:
            callback(*args)
        except Exception:  # pragma: no cover - a callback bug must not kill the worker
            log.exception("OCR worker callback raised")

    def stop(self, timeout: float = 5.0) -> None:
        """Ask the thread to finish and join it. Safe to call repeatedly."""
        self._stop_event.set()
        self._queue.put(_Stop())
        if self.is_alive() and threading.current_thread() is not self:
            self.join(timeout=timeout)


__all__ = ["OCRJob", "OCRResult", "OCRWorker"]
