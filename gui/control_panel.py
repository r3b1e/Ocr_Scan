"""Right-hand column of action buttons and quick settings."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from tkinter import ttk

Action = Callable[[], None]


class AppState(Enum):
    """Coarse UI state that drives which buttons are enabled."""

    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    SCANNING = "scanning"


@dataclass(frozen=True)
class ControlCallbacks:
    """Handlers for each button."""

    launch: Action
    scan: Action
    stop: Action
    clear: Action
    history: Action
    stats: Action
    export: Action
    quit: Action


_BUTTONS: tuple[tuple[str, str, str], ...] = (
    ("launch", "Launch Camera  (L)", "Primary.TButton"),
    ("scan", "Scan  (S)", "Primary.TButton"),
    ("stop", "Stop  (Esc)", "TButton"),
    ("clear", "Clear Screen", "TButton"),
    ("history", "History", "TButton"),
    ("stats", "Stats", "TButton"),
    ("export", "Export", "TButton"),
    ("quit", "Quit  (Q)", "Danger.TButton"),
)
_ALWAYS = {"clear", "history", "stats", "export", "quit"}
_ENABLED: dict[AppState, set[str]] = {
    AppState.IDLE: _ALWAYS | {"launch"},
    AppState.STARTING: _ALWAYS | {"stop"},
    AppState.RUNNING: _ALWAYS | {"scan", "stop"},
    AppState.SCANNING: set(_ALWAYS),
}


class ControlPanel(ttk.Frame):
    """Stacked buttons plus camera index, confidence slider and preprocessing toggles."""

    def __init__(
        self,
        parent: tk.Misc,
        callbacks: ControlCallbacks,
        *,
        confidence: float,
        preprocess: bool,
        camera_index: int,
        live_ocr: bool = True,
    ) -> None:
        super().__init__(parent, style="Panel.TFrame", padding=(12, 10))
        self.state_value = AppState.IDLE
        self.buttons: dict[str, ttk.Button] = {}
        self.confidence_var = tk.DoubleVar(master=self, value=confidence)
        self.preprocess_var = tk.BooleanVar(master=self, value=preprocess)
        self.camera_index_var = tk.IntVar(master=self, value=camera_index)
        self.live_ocr_var = tk.BooleanVar(master=self, value=live_ocr)

        ttk.Label(self, text="Controls", style="Title.TLabel").pack(anchor="w", pady=(0, 8))
        for key, text, style in _BUTTONS:
            button = ttk.Button(self, text=text, style=style, command=getattr(callbacks, key))
            button.pack(fill="x", pady=4)
            self.buttons[key] = button

        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=12)
        ttk.Label(self, text="Settings", style="Title.TLabel").pack(anchor="w", pady=(0, 6))

        camera_row = ttk.Frame(self, style="Panel.TFrame")
        camera_row.pack(fill="x", pady=2)
        ttk.Label(camera_row, text="Camera index", style="Panel.TLabel").pack(side="left")
        self.camera_spinbox = ttk.Spinbox(
            camera_row, from_=0, to=10, width=5, textvariable=self.camera_index_var, wrap=False
        )
        self.camera_spinbox.pack(side="right")

        self.confidence_label = ttk.Label(self, style="Panel.TLabel")
        self.confidence_label.pack(anchor="w", pady=(8, 0))
        self.confidence_scale = ttk.Scale(
            self,
            from_=0.1,
            to=1.0,
            orient="horizontal",
            variable=self.confidence_var,
            command=lambda _value: self._refresh_confidence_label(),
        )
        self.confidence_scale.pack(fill="x", pady=(2, 4))
        self._refresh_confidence_label()

        ttk.Checkbutton(self, text="Preprocess before scan", variable=self.preprocess_var).pack(
            anchor="w", pady=2
        )
        ttk.Checkbutton(self, text="Live OCR overlay", variable=self.live_ocr_var).pack(
            anchor="w", pady=2
        )
        self.set_state(AppState.IDLE)

    def _refresh_confidence_label(self) -> None:
        self.confidence_label["text"] = f"Confidence threshold: {self.confidence_var.get():.2f}"

    def set_state(self, state: AppState) -> None:
        """Enable exactly the buttons that make sense in `state`."""
        self.state_value = state
        enabled = _ENABLED[state]
        for key, button in self.buttons.items():
            button.state(["!disabled"] if key in enabled else ["disabled"])
        self.camera_spinbox.state(["!disabled"] if state is AppState.IDLE else ["disabled"])

    def is_enabled(self, key: str) -> bool:
        """True when the button `key` accepts clicks."""
        return "disabled" not in self.buttons[key].state()
