"""Scrollable, colour-coded log console built on a Listbox."""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import ttk

from gui.theme import FONT_MONO, LEVEL_COLORS, PALETTE


class ConsolePanel(ttk.Frame):
    """Timestamped `[LEVEL] message` lines with auto-scroll and a line cap."""

    def __init__(self, parent: tk.Misc, max_lines: int = 2000) -> None:
        super().__init__(parent, style="Panel.TFrame", padding=(10, 8))
        self.max_lines = max_lines
        ttk.Label(self, text="Console", style="Title.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6)
        )
        self.listbox = tk.Listbox(
            self,
            bg=PALETTE["canvas"],
            fg=PALETTE["info"],
            font=FONT_MONO,
            selectbackground=PALETTE["accent"],
            selectforeground="#ffffff",
            highlightthickness=0,
            borderwidth=0,
            activestyle="none",
            height=8,
        )
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.grid(row=1, column=0, sticky="nsew")
        scrollbar.grid(row=1, column=1, sticky="ns", padx=(4, 0))
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

    def insert(self, level: str, message: str) -> None:
        """Append a line; unknown levels are shown as INFO."""
        key = level.upper()
        if key not in LEVEL_COLORS:
            key = "INFO"
        line = f"[{datetime.now():%H:%M:%S}] [{key}] {message}"
        self.listbox.insert("end", line)
        self.listbox.itemconfig("end", foreground=LEVEL_COLORS[key])
        while self.listbox.size() > self.max_lines:
            self.listbox.delete(0)
        self.listbox.see("end")

    def clear_screen(self) -> None:
        """Remove every line."""
        self.listbox.delete(0, "end")

    def lines(self) -> list[str]:
        """Return the visible lines (oldest first)."""
        return list(self.listbox.get(0, "end"))
