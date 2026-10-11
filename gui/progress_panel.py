"""Progress bar for scan steps plus a one-line status readout."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class ProgressPanel(ttk.Frame):
    """Determinate progress for scan steps, indeterminate while OCR runs."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, style="Panel.TFrame", padding=(10, 8))
        self._total = 1
        self._mode = "determinate"
        self.step_label = ttk.Label(self, text="Idle", style="Panel.TLabel")
        self.status_label = ttk.Label(self, text="", style="Status.TLabel", anchor="e")
        self.bar = ttk.Progressbar(self, orient="horizontal", mode="determinate", maximum=100)
        self.step_label.grid(row=0, column=0, sticky="w")
        self.status_label.grid(row=0, column=1, sticky="e")
        self.bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.update_status(
            fps=0.0, detections=0, last_confidence=None, camera="off", backend="none"
        )

    # ------------------------------------------------------------ properties
    @property
    def value(self) -> float:
        """Current bar value in percent."""
        return float(self.bar["value"])

    @property
    def mode(self) -> str:
        """`determinate` or `indeterminate`."""
        return self._mode

    @property
    def step_text(self) -> str:
        """Text shown above the bar."""
        return str(self.step_label["text"])

    @property
    def status_text(self) -> str:
        """The FPS / detections / confidence readout."""
        return str(self.status_label["text"])

    # ----------------------------------------------------------------- steps
    def _set_determinate(self) -> None:
        if self._mode == "indeterminate":
            self.bar.stop()
            self.bar.configure(mode="determinate")
            self._mode = "determinate"

    def begin(self, total_steps: int) -> None:
        """Start a new determinate sequence of `total_steps` steps."""
        self._total = max(1, total_steps)
        self._set_determinate()
        self.bar["value"] = 0

    def step(self, index: int, label: str) -> None:
        """Show step `index` (0-based) of the current sequence."""
        self._set_determinate()
        self.bar["value"] = min(100.0, (index + 1) / self._total * 100.0)
        self.step_label["text"] = f"{label} ({index + 1}/{self._total})"

    def start_indeterminate(self, label: str) -> None:
        """Animate the bar while a step of unknown duration runs."""
        if self._mode != "indeterminate":
            self.bar.configure(mode="indeterminate")
            self.bar.start(12)
            self._mode = "indeterminate"
        self.step_label["text"] = f"{label}..."

    def finish(self, label: str = "Done") -> None:
        """Fill the bar and show a final label."""
        self._set_determinate()
        self.bar["value"] = 100.0
        self.step_label["text"] = label

    def reset(self) -> None:
        """Return to the idle state."""
        self._set_determinate()
        self.bar["value"] = 0
        self.step_label["text"] = "Idle"

    # ---------------------------------------------------------------- status
    def update_status(
        self,
        *,
        fps: float,
        detections: int,
        last_confidence: float | None,
        camera: str,
        backend: str,
    ) -> None:
        """Refresh the status readout."""
        conf = f"{last_confidence:.2f}" if last_confidence is not None else "-"
        self.status_label["text"] = (
            f"FPS {fps:.1f}  |  Detections {detections}  |  Last conf {conf}  |  "
            f"Camera {camera}  |  DB {backend}"
        )
