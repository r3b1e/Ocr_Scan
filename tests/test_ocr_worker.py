"""Tests for core.ocr_worker - the background inference thread."""

from __future__ import annotations

import threading
import time

import numpy as np

from core.ocr_engine import OCRInitError, OCRResult
from core.ocr_worker import OCRJob, OCRWorker


class FakeEngine:
    def __init__(self, delay: float = 0.0, results=None, fail: bool = False, warm_fail=False):
        self.delay = delay
        self.results = results or [OCRResult("X", 0.9, [[0, 0], [1, 0], [1, 1], [0, 1]])]
        self.fail = fail
        self.warm_fail = warm_fail
        self.calls = 0
        self.is_ready = False

    def warm_up(self):
        if self.warm_fail:
            raise OCRInitError("EasyOCR could not download its models")
        self.is_ready = True

    def detect(self, frame, min_confidence=0.0):
        self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        if self.fail:
            raise RuntimeError("inference failed")
        return list(self.results)


def _frame() -> np.ndarray:
    return np.zeros((8, 8, 3), dtype=np.uint8)


def _wait_for(predicate, timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()


def _make_worker(engine):
    results: list[tuple[OCRJob, object]] = []
    errors: list[tuple[OCRJob | None, Exception]] = []
    ready: list[Exception | None] = []
    worker = OCRWorker(
        engine,
        on_result=lambda job, res: results.append((job, res)),
        on_error=lambda job, exc: errors.append((job, exc)),
        on_ready=lambda exc: ready.append(exc),
    )
    worker.start()
    return worker, results, errors, ready


def test_worker_warms_up_engine_and_reports_ready():
    engine = FakeEngine()
    worker, _, _, ready = _make_worker(engine)
    try:
        assert _wait_for(lambda: ready == [None])
        assert engine.is_ready is True
    finally:
        worker.stop()


def test_warm_up_failure_is_reported_and_jobs_error_out():
    engine = FakeEngine(warm_fail=True)
    worker, results, errors, ready = _make_worker(engine)
    try:
        assert _wait_for(lambda: len(ready) == 1)
        assert isinstance(ready[0], OCRInitError)
        assert worker.submit_live(_frame(), 0.0) is False
        worker.submit_task(lambda: 1)
        assert _wait_for(lambda: len(errors) == 1)
        assert isinstance(errors[0][1], OCRInitError)
        assert results == []
    finally:
        worker.stop()


def test_live_job_delivers_results_via_callback():
    engine = FakeEngine()
    worker, results, errors, _ = _make_worker(engine)
    try:
        assert _wait_for(lambda: engine.is_ready)
        assert worker.submit_live(_frame(), min_confidence=0.4) is True
        assert _wait_for(lambda: len(results) == 1)
        job, res = results[0]
        assert job.kind == "live"
        assert job.min_confidence == 0.4
        assert res[0].text == "X"
        assert errors == []
    finally:
        worker.stop()


def test_live_job_is_dropped_while_busy():
    engine = FakeEngine(delay=0.15)
    worker, results, _, _ = _make_worker(engine)
    try:
        assert _wait_for(lambda: engine.is_ready)
        assert worker.submit_live(_frame(), 0.0) is True
        assert _wait_for(lambda: worker.busy)
        assert worker.submit_live(_frame(), 0.0) is False
        assert _wait_for(lambda: len(results) == 1)
        time.sleep(0.05)
        assert len(results) == 1 and engine.calls == 1
    finally:
        worker.stop()


def test_task_job_is_queued_even_when_busy_and_returns_value():
    engine = FakeEngine(delay=0.1)
    worker, results, _, _ = _make_worker(engine)
    try:
        assert _wait_for(lambda: engine.is_ready)
        worker.submit_live(_frame(), 0.0)
        job_id = worker.submit_task(lambda: "scan-outcome", payload={"tag": 1})
        assert isinstance(job_id, int)
        assert _wait_for(lambda: len(results) == 2)
        assert [job.kind for job, _ in results] == ["live", "task"]
        task_job, value = results[1]
        assert task_job.job_id == job_id and task_job.payload == {"tag": 1}
        assert value == "scan-outcome"
    finally:
        worker.stop()


def test_engine_failure_reports_error_and_keeps_running():
    engine = FakeEngine(fail=True)
    worker, results, errors, _ = _make_worker(engine)
    try:
        assert _wait_for(lambda: engine.is_ready)
        worker.submit_live(_frame(), 0.0)
        assert _wait_for(lambda: len(errors) == 1)
        assert isinstance(errors[0][1], RuntimeError) and errors[0][0].kind == "live"
        assert worker.is_alive()
        engine.fail = False
        worker.submit_live(_frame(), 0.0)
        assert _wait_for(lambda: len(results) == 1)
    finally:
        worker.stop()


def test_task_failure_reports_error():
    worker, _, errors, _ = _make_worker(FakeEngine())

    def boom():
        raise ValueError("bad frame")

    try:
        worker.submit_task(boom)
        assert _wait_for(lambda: len(errors) == 1)
        assert isinstance(errors[0][1], ValueError) and errors[0][0].kind == "task"
    finally:
        worker.stop()


def test_stop_joins_thread_and_is_idempotent():
    worker, _, _, _ = _make_worker(FakeEngine())
    before = threading.active_count()
    worker.stop()
    assert worker.is_alive() is False
    assert threading.active_count() == before - 1
    worker.stop()
