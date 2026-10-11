"""Stats window: scans per day and confidence distribution rendered with matplotlib."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from datetime import date
from tkinter import ttk

import numpy as np
from matplotlib.axes import Axes
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from database.models import DatabaseError
from gui.theme import FONT_TITLE, PALETTE, font_family
from utils.logger import get_logger

log = get_logger("gui.stats")

LogCallback = Callable[[str, str], None]
SERIES_COLOR = "#3987e5"  # single-series blue stepped for dark surfaces
_TEXT = PALETTE["fg"]
_MUTED = PALETTE["muted"]
_GRID = PALETTE["border"]
_DAYS = 30


def _style_axes(ax: Axes, title: str, ylabel: str) -> None:
    ax.set_facecolor(PALETTE["panel"])
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(_GRID)
    ax.tick_params(colors=_MUTED, labelsize=9, length=0)
    ax.yaxis.grid(True, color=_GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.set_title(title, color=_TEXT, fontsize=11, fontweight="bold", loc="left", pad=12)
    ax.set_ylabel(ylabel, color=_MUTED, fontsize=9)
    ax.yaxis.set_major_locator(
        __import__("matplotlib.ticker").ticker.MaxNLocator(integer=True, nbins=5)
    )


def _empty(ax: Axes, message: str) -> None:
    ax.set_xticks([])
    ax.set_yticks([])
    ax.yaxis.grid(False)
    ax.text(
        0.5,
        0.5,
        message,
        color=_MUTED,
        ha="center",
        va="center",
        transform=ax.transAxes,
        fontsize=11,
    )


class StatsWindow(tk.Toplevel):
    """Two small charts plus headline numbers."""

    def __init__(self, parent: tk.Misc, repo: object, on_log: LogCallback) -> None:
        super().__init__(parent)
        self.repo = repo
        self.on_log = on_log
        self.total_scans = 0
        self.average_confidence: float | None = None
        self.title("Scan Statistics")
        self.geometry("980x640")
        self.minsize(720, 480)
        self.configure(bg=PALETTE["bg"])

        header = ttk.Frame(self, style="Panel.TFrame", padding=(14, 10))
        header.grid(row=0, column=0, sticky="ew")
        self._tiles: dict[str, ttk.Label] = {}
        for key, label in (
            ("total", "Total scans"),
            ("avg", "Average confidence"),
            ("days", f"Active days (last {_DAYS})"),
        ):
            tile = ttk.Frame(header, style="Panel.TFrame", padding=(0, 0, 32, 0))
            tile.pack(side="left")
            ttk.Label(tile, text=label, style="Muted.TLabel").pack(anchor="w")
            value = ttk.Label(
                tile,
                text="-",
                style="Title.TLabel",
                font=(font_family(), FONT_TITLE[1] + 8, "bold"),
            )
            value.pack(anchor="w")
            self._tiles[key] = value
        ttk.Button(header, text="Refresh", command=self.refresh).pack(side="right")

        self.figure = Figure(figsize=(9.2, 4.6), dpi=100, facecolor=PALETTE["panel"])
        self.ax_days = self.figure.add_subplot(1, 2, 1)
        self.ax_conf = self.figure.add_subplot(1, 2, 2)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        widget = self.canvas.get_tk_widget()
        widget.configure(bg=PALETTE["panel"], highlightthickness=0)
        widget.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        self.refresh()

    def refresh(self) -> None:
        """Re-query the repository and redraw both charts."""
        try:
            per_day = self.repo.scans_per_day(_DAYS)  # type: ignore[attr-defined]
            confidences = self.repo.confidence_values()  # type: ignore[attr-defined]
            self.total_scans = self.repo.count_scans()  # type: ignore[attr-defined]
        except DatabaseError as exc:
            log.exception("Stats query failed")
            self.on_log("ERROR", f"Could not load statistics: {exc}")
            per_day, confidences, self.total_scans = [], [], 0
        self.average_confidence = float(np.mean(confidences)) if confidences else None
        self._tiles["total"]["text"] = f"{self.total_scans:,}"
        self._tiles["avg"]["text"] = (
            f"{self.average_confidence:.2f}" if self.average_confidence is not None else "-"
        )
        self._tiles["days"]["text"] = str(len(per_day))
        self._draw_days(per_day)
        self._draw_confidence(confidences)
        self.figure.tight_layout(pad=2.0)
        self.canvas.draw_idle()

    def _draw_days(self, per_day: list[tuple[date, int]]) -> None:
        ax = self.ax_days
        ax.clear()
        _style_axes(ax, f"Scans per day (last {_DAYS} days)", "Scans")
        if not per_day:
            _empty(ax, "No scans yet")
            return
        labels = [day.strftime("%d %b") for day, _ in per_day]
        counts = [count for _, count in per_day]
        positions = np.arange(len(counts))
        bars = ax.bar(positions, counts, width=0.8, color=SERIES_COLOR, linewidth=0)
        ax.set_xticks(positions)
        ax.set_xticklabels(
            labels,
            rotation=45 if len(labels) > 8 else 0,
            ha="right" if len(labels) > 8 else "center",
        )
        peak = int(np.argmax(counts))
        ax.annotate(
            f"{counts[peak]}",
            (positions[peak], counts[peak]),
            textcoords="offset points",
            xytext=(0, 4),
            ha="center",
            color=_TEXT,
            fontsize=9,
        )
        ax.set_ylim(0, max(counts) * 1.2)
        del bars

    def _draw_confidence(self, confidences: list[float]) -> None:
        ax = self.ax_conf
        ax.clear()
        _style_axes(ax, "Confidence distribution", "Scans")
        if not confidences:
            _empty(ax, "No scans yet")
            return
        bins = np.linspace(0.0, 1.0, 11)
        ax.hist(confidences, bins=bins, color=SERIES_COLOR, rwidth=0.92, linewidth=0)
        ax.set_xlim(0.0, 1.0)
        ax.set_xticks(bins[::2])
        ax.set_xlabel("Confidence", color=_MUTED, fontsize=9)
        mean = float(np.mean(confidences))
        ax.axvline(mean, color=_MUTED, linewidth=1.2, linestyle=(0, (4, 3)))
        ax.text(
            mean, ax.get_ylim()[1] * 0.97, f" mean {mean:.2f}", color=_TEXT, fontsize=9, va="top"
        )
