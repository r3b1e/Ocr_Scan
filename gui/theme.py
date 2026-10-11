"""Colours, fonts, ttk styles and the programmatic app icon."""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageDraw, ImageTk

PALETTE: dict[str, str] = {
    "bg": "#1b1e27",
    "panel": "#232734",
    "panel_alt": "#2e3342",
    "canvas": "#0f1116",
    "fg": "#e6e9f0",
    "muted": "#9aa3b5",
    "border": "#3a4052",
    "accent": "#4f8cff",
    "accent_active": "#6c9eff",
    "danger": "#b03a48",
    "danger_active": "#c94b5a",
    "ok": "#54d38a",
    "warn": "#f2c14e",
    "error": "#ff6b6b",
    "info": "#c7cedb",
}
LEVEL_COLORS: dict[str, str] = {
    "INFO": PALETTE["info"],
    "OK": PALETTE["ok"],
    "WARN": PALETTE["warn"],
    "ERROR": PALETTE["error"],
}


def font_family() -> str:
    """Pick a readable UI font that exists on the current platform."""
    if sys.platform.startswith("win"):
        return "Segoe UI"
    if sys.platform == "darwin":
        return "Helvetica Neue"
    return "DejaVu Sans"


def mono_family() -> str:
    """Pick a monospaced font for the console and status line."""
    if sys.platform.startswith("win"):
        return "Consolas"
    if sys.platform == "darwin":
        return "Menlo"
    return "DejaVu Sans Mono"


BASE_SIZE = 12 if sys.platform == "darwin" else 10
FONT_UI: tuple[str, int] = (font_family(), BASE_SIZE)
FONT_UI_BOLD: tuple[str, int, str] = (font_family(), BASE_SIZE, "bold")
FONT_TITLE: tuple[str, int, str] = (font_family(), BASE_SIZE + 2, "bold")
FONT_MONO: tuple[str, int] = (mono_family(), BASE_SIZE - 1)


def apply_theme(root: tk.Tk) -> ttk.Style:
    """Configure a consistent dark `clam`-based ttk theme on `root`."""
    style = ttk.Style(root)
    style.theme_use("clam")
    p = PALETTE
    root.configure(bg=p["bg"])
    style.configure(".", background=p["bg"], foreground=p["fg"], font=FONT_UI, borderwidth=0)
    style.configure("TFrame", background=p["bg"])
    style.configure("Panel.TFrame", background=p["panel"])
    style.configure("TLabel", background=p["bg"], foreground=p["fg"])
    style.configure("Panel.TLabel", background=p["panel"], foreground=p["fg"])
    style.configure("Title.TLabel", background=p["panel"], foreground=p["fg"], font=FONT_TITLE)
    style.configure("Muted.TLabel", background=p["panel"], foreground=p["muted"])
    style.configure("Status.TLabel", background=p["panel"], foreground=p["muted"], font=FONT_MONO)
    style.configure("TSeparator", background=p["border"])

    style.configure(
        "TButton",
        background=p["panel_alt"],
        foreground=p["fg"],
        padding=(12, 8),
        borderwidth=0,
        focusthickness=1,
        focuscolor=p["accent"],
        font=FONT_UI_BOLD,
    )
    style.map(
        "TButton",
        background=[("disabled", p["panel"]), ("pressed", p["accent"]), ("active", p["border"])],
        foreground=[("disabled", p["muted"])],
    )
    style.configure("Primary.TButton", background=p["accent"], foreground="#ffffff")
    style.map(
        "Primary.TButton",
        background=[
            ("disabled", p["panel"]),
            ("pressed", p["accent"]),
            ("active", p["accent_active"]),
        ],
        foreground=[("disabled", p["muted"])],
    )
    style.configure("Danger.TButton", background=p["danger"], foreground="#ffffff")
    style.map(
        "Danger.TButton",
        background=[
            ("disabled", p["panel"]),
            ("pressed", p["danger"]),
            ("active", p["danger_active"]),
        ],
        foreground=[("disabled", p["muted"])],
    )

    style.configure("TCheckbutton", background=p["panel"], foreground=p["fg"], padding=(2, 4))
    style.map(
        "TCheckbutton",
        background=[("active", p["panel"])],
        indicatorcolor=[("selected", p["accent"]), ("!selected", p["panel_alt"])],
    )
    style.configure("Horizontal.TScale", background=p["panel"], troughcolor=p["panel_alt"])
    style.configure(
        "Horizontal.TProgressbar", troughcolor=p["panel_alt"], background=p["accent"], thickness=14
    )
    style.configure(
        "TSpinbox",
        fieldbackground=p["panel_alt"],
        background=p["panel_alt"],
        foreground=p["fg"],
        arrowcolor=p["fg"],
        insertcolor=p["fg"],
    )
    style.configure(
        "TEntry", fieldbackground=p["panel_alt"], foreground=p["fg"], insertcolor=p["fg"], padding=4
    )
    style.configure(
        "Treeview",
        background=p["panel"],
        fieldbackground=p["panel"],
        foreground=p["fg"],
        rowheight=26,
        borderwidth=0,
    )
    style.configure(
        "Treeview.Heading", background=p["panel_alt"], foreground=p["fg"], font=FONT_UI_BOLD
    )
    style.map(
        "Treeview", background=[("selected", p["accent"])], foreground=[("selected", "#ffffff")]
    )
    style.configure(
        "TCombobox", fieldbackground=p["panel_alt"], foreground=p["fg"], arrowcolor=p["fg"]
    )
    style.configure(
        "Vertical.TScrollbar", background=p["panel_alt"], troughcolor=p["panel"], arrowcolor=p["fg"]
    )
    return style


def build_app_icon(master: tk.Misc, size: int = 128) -> ImageTk.PhotoImage:
    """Draw a scanner-style icon (viewfinder corners + text lines) as a PhotoImage."""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    radius = size // 5
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=PALETTE["accent"])
    margin, arm, width = size // 6, size // 5, max(3, size // 16)
    corners = (
        ((margin, margin + arm), (margin, margin), (margin + arm, margin)),
        ((size - margin - arm, margin), (size - margin, margin), (size - margin, margin + arm)),
        ((margin, size - margin - arm), (margin, size - margin), (margin + arm, size - margin)),
        (
            (size - margin - arm, size - margin),
            (size - margin, size - margin),
            (size - margin, size - margin - arm),
        ),
    )
    for corner in corners:
        draw.line(corner, fill="#ffffff", width=width, joint="curve")
    line_left, line_right = margin + arm // 2, size - margin - arm // 2
    for i, fraction in enumerate((0.42, 0.55, 0.68)):
        y = int(size * fraction)
        right = line_right if i != 2 else line_left + (line_right - line_left) * 2 // 3
        draw.line(((line_left, y), (right, y)), fill="#ffffff", width=width)
    return ImageTk.PhotoImage(image, master=master)
