"""History window: browse, search, delete and export past scans."""

from __future__ import annotations

import subprocess
import sys
import tkinter as tk
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

from database.models import DatabaseError, ScanRecord
from gui.theme import PALETTE
from utils.helpers import EXPORT_FORMATS, ExportFormat, export_records, timestamp_str
from utils.logger import get_logger

log = get_logger("gui.history")

LogCallback = Callable[[str, str], None]
_COLUMNS: tuple[tuple[str, str, int, str], ...] = (
    ("id", "ID", 60, "e"),
    ("created_at", "Time", 160, "w"),
    ("detected_text", "Text", 360, "w"),
    ("confidence", "Confidence", 100, "e"),
    ("language", "Lang", 60, "center"),
    ("image_path", "Image", 260, "w"),
)


def open_with_default_app(path: Path) -> None:
    """Open a file with the operating system's default viewer."""
    if sys.platform.startswith("win"):
        import os

        os.startfile(str(path))  # type: ignore[attr-defined]  # noqa: S606 - user-initiated open
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])  # noqa: S603,S607 - fixed command, user action
    else:
        subprocess.Popen(["xdg-open", str(path)])  # noqa: S603,S607


class HistoryWindow(tk.Toplevel):
    """Treeview of scans with search, delete and export."""

    def __init__(
        self, parent: tk.Misc, repo: object, exports_dir: Path, on_log: LogCallback
    ) -> None:
        super().__init__(parent)
        self.repo = repo
        self.exports_dir = exports_dir
        self.on_log = on_log
        self._rows: dict[int, ScanRecord] = {}
        self.title("Scan History")
        self.geometry("1040x620")
        self.minsize(760, 420)
        self.configure(bg=PALETTE["bg"])

        toolbar = ttk.Frame(self, style="Panel.TFrame", padding=(10, 8))
        toolbar.grid(row=0, column=0, sticky="ew")
        ttk.Label(toolbar, text="Search", style="Panel.TLabel").pack(side="left")
        self.search_var = tk.StringVar(master=self)
        entry = ttk.Entry(toolbar, textvariable=self.search_var, width=32)
        entry.pack(side="left", padx=(6, 6))
        entry.bind("<Return>", lambda _e: self.search())
        ttk.Button(toolbar, text="Search", command=self.search).pack(side="left")
        ttk.Button(toolbar, text="Show All", command=self.show_all).pack(side="left", padx=(6, 0))
        ttk.Button(toolbar, text="Delete Selected", command=self.delete_selected).pack(
            side="left", padx=(18, 0)
        )
        ttk.Button(toolbar, text="Open Image", command=self.open_selected_image).pack(
            side="left", padx=(6, 0)
        )
        self.format_var = tk.StringVar(master=self, value="csv")
        ttk.Button(toolbar, text="Export", command=lambda: self.export()).pack(side="right")
        ttk.Combobox(
            toolbar,
            textvariable=self.format_var,
            values=list(EXPORT_FORMATS),
            width=6,
            state="readonly",
        ).pack(side="right", padx=(0, 6))
        ttk.Label(toolbar, text="Format", style="Panel.TLabel").pack(side="right", padx=(0, 6))

        body = ttk.Frame(self, padding=(10, 8))
        body.grid(row=1, column=0, sticky="nsew")
        self.tree = ttk.Treeview(
            body, columns=[c[0] for c in _COLUMNS], show="headings", selectmode="extended"
        )
        for key, heading, width, anchor in _COLUMNS:
            self.tree.heading(key, text=heading)
            self.tree.column(
                key, width=width, anchor=anchor, stretch=key in {"detected_text", "image_path"}
            )
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)
        self.tree.bind("<Double-1>", lambda _e: self.open_selected_image())
        self.tree.bind("<Delete>", lambda _e: self.delete_selected())

        self.status_label = ttk.Label(self, text="", style="Muted.TLabel", padding=(12, 6))
        self.status_label.grid(row=2, column=0, sticky="ew")
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        self.refresh()

    # ------------------------------------------------------------------ data
    @property
    def status_text(self) -> str:
        """The footer text (row count)."""
        return str(self.status_label["text"])

    def row_count(self) -> int:
        """Number of rows currently shown."""
        return len(self.tree.get_children())

    def _load(self, records: list[ScanRecord], label: str) -> None:
        self.tree.delete(*self.tree.get_children())
        self._rows = {}
        for record in records:
            if record.id is None:
                continue
            self._rows[record.id] = record
            self.tree.insert(
                "",
                "end",
                iid=str(record.id),
                values=(
                    record.id,
                    timestamp_str(record.created_at),
                    record.detected_text,
                    f"{record.confidence:.2f}",
                    record.language,
                    record.image_path or "",
                ),
            )
        self.status_label["text"] = f"{len(records)} scan(s) {label}"

    def refresh(self) -> None:
        """Reload the newest scans."""
        try:
            self._load(self.repo.fetch_scans(limit=2000), "shown")  # type: ignore[attr-defined]
        except DatabaseError as exc:
            log.exception("History load failed")
            self._load([], "shown")
            self.on_log("ERROR", f"Could not load scan history: {exc}")

    def show_all(self) -> None:
        """Clear the search box and reload."""
        self.search_var.set("")
        self.refresh()

    def search(self) -> None:
        """Filter rows by the search box."""
        query = self.search_var.get().strip()
        if not query:
            self.refresh()
            return
        try:
            self._load(self.repo.search_scans(query, limit=2000), f'matching "{query}"')  # type: ignore[attr-defined]
        except DatabaseError as exc:
            log.exception("History search failed")
            self.on_log("ERROR", f"Search failed: {exc}")

    def selected_ids(self) -> list[int]:
        """Ids of the selected rows."""
        return [int(iid) for iid in self.tree.selection()]

    def delete_selected(self, confirm: bool = True) -> int:
        """Delete the selected scans (after confirmation) and return how many were removed."""
        ids = self.selected_ids()
        if not ids:
            self.on_log("WARN", "Select one or more rows to delete.")
            return 0
        if confirm and not messagebox.askyesno(
            "Delete scans",
            f"Delete {len(ids)} selected scan(s)? This cannot be undone.",
            parent=self,
        ):
            return 0
        removed = 0
        try:
            for scan_id in ids:
                if self.repo.delete_scan(scan_id):  # type: ignore[attr-defined]
                    removed += 1
        except DatabaseError as exc:
            log.exception("History delete failed")
            self.on_log("ERROR", f"Delete failed: {exc}")
        self.on_log("OK", f"Deleted {removed} scan(s).")
        self.search() if self.search_var.get().strip() else self.refresh()
        return removed

    def export(self, fmt: str | None = None) -> Path | None:
        """Export the rows currently shown to `exports/scans_<timestamp>.<fmt>`."""
        chosen = (fmt or self.format_var.get()).lower()
        if chosen not in EXPORT_FORMATS:
            self.on_log("ERROR", f"Unknown export format {chosen!r}.")
            return None
        export_format: ExportFormat = chosen  # type: ignore[assignment]
        path = (
            self.exports_dir / f"scans_{timestamp_str(datetime.now(), for_filename=True)}.{chosen}"
        )
        try:
            out = export_records(list(self._rows.values()), path, export_format)
        except OSError as exc:
            log.exception("History export failed")
            self.on_log("ERROR", f"Export failed: {exc}")
            return None
        self.on_log("OK", f"Exported {len(self._rows)} scan(s) to {out}")
        return out

    def open_selected_image(self) -> None:
        """Open the capture image of the first selected row."""
        ids = self.selected_ids()
        if not ids:
            self.on_log("WARN", "Select a row to open its image.")
            return
        record = self._rows.get(ids[0])
        if record is None or not record.image_path or not Path(record.image_path).exists():
            self.on_log("WARN", "This scan has no image on disk.")
            return
        try:
            open_with_default_app(Path(record.image_path))
        except OSError as exc:
            log.exception("Could not open image")
            self.on_log("ERROR", f"Could not open the image: {exc}")
