"""Tests for the History and Stats windows against a SQLite repository."""

from __future__ import annotations

import tkinter as tk
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from database.models import ScanRecord
from database.sqlite_repository import SQLiteScanRepository

pytestmark = pytest.mark.gui


@pytest.fixture()
def root():
    try:
        window = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover
        pytest.skip(f"Tk display unavailable: {exc}")
    window.withdraw()
    yield window
    window.destroy()


@pytest.fixture()
def repo(tmp_path: Path):
    repository = SQLiteScanRepository(tmp_path / "h.sqlite3")
    now = datetime.now().replace(microsecond=0)
    repository.insert_scans(
        [
            ScanRecord(None, None, "Invoice 42", 0.91, None, None, "en", now),
            ScanRecord(None, None, "Receipt", 0.55, None, None, "en", now - timedelta(days=1)),
            ScanRecord(
                None, None, "invoice total", 0.78, None, None, "en", now - timedelta(days=2)
            ),
        ]
    )
    yield repository
    repository.close()


def test_history_lists_searches_deletes_and_exports(root, repo, tmp_path):
    from gui.history_view import HistoryWindow

    logs: list[tuple[str, str]] = []
    window = HistoryWindow(
        root, repo, tmp_path / "exports", on_log=lambda lvl, msg: logs.append((lvl, msg))
    )
    window.withdraw()
    try:
        assert window.row_count() == 3
        assert "3" in window.status_text

        window.search_var.set("invoice")
        window.search()
        assert window.row_count() == 2

        first = window.tree.get_children()[0]
        window.tree.selection_set(first)
        assert window.delete_selected(confirm=False) == 1
        assert window.row_count() == 1
        assert repo.count_scans() == 2
        assert any(level == "OK" for level, _ in logs)

        out = window.export("json")
        assert out is not None and out.exists() and out.parent == tmp_path / "exports"

        window.show_all()
        assert window.row_count() == 2
        assert window.delete_selected(confirm=False) == 0
    finally:
        window.destroy()


def test_history_reports_database_errors(root, tmp_path):
    from database.models import DatabaseError
    from gui.history_view import HistoryWindow

    class BrokenRepo:
        backend_name = "Broken"

        def fetch_scans(self, limit=500, offset=0):
            raise DatabaseError("connection lost")

        def search_scans(self, query, limit=500):
            raise DatabaseError("connection lost")

    logs: list[tuple[str, str]] = []
    window = HistoryWindow(
        root, BrokenRepo(), tmp_path, on_log=lambda lvl, msg: logs.append((lvl, msg))
    )
    window.withdraw()
    try:
        assert window.row_count() == 0
        assert logs and logs[-1][0] == "ERROR" and "connection lost" in logs[-1][1]
    finally:
        window.destroy()


def test_stats_window_renders_with_and_without_data(root, repo, tmp_path):
    from gui.stats_view import StatsWindow

    logs: list[tuple[str, str]] = []
    window = StatsWindow(root, repo, on_log=lambda lvl, msg: logs.append((lvl, msg)))
    window.withdraw()
    try:
        assert window.total_scans == 3
        assert window.average_confidence == pytest.approx((0.91 + 0.55 + 0.78) / 3, abs=1e-6)
        assert len(window.figure.axes) == 2
        assert len(window.figure.axes[0].patches) == 3  # one bar per active day
    finally:
        window.destroy()

    empty = SQLiteScanRepository(tmp_path / "empty.sqlite3")
    window = StatsWindow(root, empty, on_log=lambda lvl, msg: logs.append((lvl, msg)))
    window.withdraw()
    try:
        assert window.total_scans == 0
        assert window.average_confidence is None
        assert any("No scans" in t.get_text() for t in window.figure.axes[0].texts)
    finally:
        window.destroy()
        empty.close()
