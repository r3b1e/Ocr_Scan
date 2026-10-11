"""Widget-level tests for the Tk panels (skipped when no display is available)."""

from __future__ import annotations

import tkinter as tk

import numpy as np
import pytest

pytestmark = pytest.mark.gui


@pytest.fixture()
def root():
    try:
        window = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - depends on the CI machine
        pytest.skip(f"Tk display unavailable: {exc}")
    window.withdraw()
    yield window
    window.destroy()


def test_console_insert_formats_and_colours(root):
    from gui.console_panel import ConsolePanel

    panel = ConsolePanel(root)
    panel.insert("INFO", "hello")
    panel.insert("OK", "done")
    panel.insert("WARN", "careful")
    panel.insert("ERROR", "boom")
    lines = panel.lines()
    assert len(lines) == 4
    assert lines[0].endswith("[INFO] hello") and lines[0].startswith("[")
    assert "[OK] done" in lines[1]
    assert "[WARN] careful" in lines[2]
    assert "[ERROR] boom" in lines[3]
    assert panel.listbox.itemcget(3, "foreground") != panel.listbox.itemcget(0, "foreground")


def test_console_clear_and_cap(root):
    from gui.console_panel import ConsolePanel

    panel = ConsolePanel(root, max_lines=5)
    for i in range(8):
        panel.insert("INFO", f"line {i}")
    lines = panel.lines()
    assert len(lines) == 5
    assert lines[0].endswith("line 3") and lines[-1].endswith("line 7")
    panel.clear_screen()
    assert panel.lines() == []


def test_console_unknown_level_falls_back_to_info(root):
    from gui.console_panel import ConsolePanel

    panel = ConsolePanel(root)
    panel.insert("weird", "x")
    assert "[INFO] x" in panel.lines()[0]


def test_progress_panel_steps(root):
    from gui.progress_panel import ProgressPanel

    panel = ProgressPanel(root)
    assert panel.value == 0
    panel.begin(6)
    panel.step(0, "Capturing frame")
    assert panel.value == pytest.approx(100 / 6, abs=0.5)
    assert panel.step_text == "Capturing frame (1/6)"
    panel.start_indeterminate("Running OCR")
    assert panel.mode == "indeterminate"
    assert panel.step_text == "Running OCR..."
    panel.step(4, "Writing to DB")
    assert panel.mode == "determinate"
    panel.finish("Done")
    assert panel.value == 100 and panel.step_text == "Done"
    panel.reset()
    assert panel.value == 0 and panel.step_text == "Idle"


def test_progress_panel_status_line(root):
    from gui.progress_panel import ProgressPanel

    panel = ProgressPanel(root)
    panel.update_status(
        fps=12.34, detections=3, last_confidence=0.876, camera="0", backend="SQLite"
    )
    text = panel.status_text
    assert "FPS 12.3" in text and "Detections 3" in text
    assert "Last conf 0.88" in text and "DB SQLite" in text and "Camera 0" in text
    panel.update_status(fps=0.0, detections=0, last_confidence=None, camera="off", backend="MySQL")
    assert "Last conf -" in panel.status_text


def test_control_panel_state_machine(root):
    from gui.control_panel import AppState, ControlCallbacks, ControlPanel

    calls: list[str] = []
    callbacks = ControlCallbacks(
        launch=lambda: calls.append("launch"),
        scan=lambda: calls.append("scan"),
        stop=lambda: calls.append("stop"),
        clear=lambda: calls.append("clear"),
        history=lambda: calls.append("history"),
        stats=lambda: calls.append("stats"),
        export=lambda: calls.append("export"),
        quit=lambda: calls.append("quit"),
    )
    panel = ControlPanel(root, callbacks, confidence=0.4, preprocess=True, camera_index=1)
    assert set(panel.buttons) == {
        "launch",
        "scan",
        "stop",
        "clear",
        "history",
        "stats",
        "export",
        "quit",
    }
    assert panel.confidence_var.get() == pytest.approx(0.4)
    assert panel.preprocess_var.get() is True
    assert panel.camera_index_var.get() == 1
    assert panel.live_ocr_var.get() is True

    panel.set_state(AppState.IDLE)
    assert (
        panel.is_enabled("launch") and not panel.is_enabled("scan") and not panel.is_enabled("stop")
    )
    assert panel.is_enabled("quit") and panel.is_enabled("history")

    panel.set_state(AppState.STARTING)
    assert (
        not panel.is_enabled("launch") and not panel.is_enabled("scan") and panel.is_enabled("stop")
    )

    panel.set_state(AppState.RUNNING)
    assert not panel.is_enabled("launch") and panel.is_enabled("scan") and panel.is_enabled("stop")

    panel.set_state(AppState.SCANNING)
    assert (
        not panel.is_enabled("scan") and not panel.is_enabled("stop") and panel.is_enabled("quit")
    )

    panel.set_state(AppState.RUNNING)
    for key in ("launch", "scan", "stop", "clear", "history", "stats", "export", "quit"):
        panel.buttons[key].invoke()
    assert calls == ["scan", "stop", "clear", "history", "stats", "export", "quit"]


def test_video_canvas_placeholder_and_frame(root):
    from gui.video_canvas import VideoCanvas

    canvas = VideoCanvas(root, width=400, height=300)
    assert canvas.has_frame is False
    assert canvas.find_withtag("placeholder")

    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    canvas.show_frame(frame)
    assert canvas.has_frame is True
    assert canvas.displayed_size == (400, 225)
    assert not canvas.find_withtag("placeholder")

    canvas.show_placeholder("Camera Off")
    assert canvas.has_frame is False
    assert canvas.find_withtag("placeholder")
