"""SQLite implementation of `ScanRepository`, used when MySQL is unreachable."""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

from database.models import (
    DatabaseError,
    ScanRecord,
    SessionRecord,
    decode_bbox,
    encode_bbox,
    like_pattern,
)
from utils.logger import get_logger

log = get_logger("database.sqlite")

_DT_FORMAT = "%Y-%m-%d %H:%M:%S"
_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS scan_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at TEXT NOT NULL,
        ended_at TEXT NULL,
        total_detections INTEGER DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NULL REFERENCES scan_sessions(id) ON DELETE SET NULL,
        detected_text TEXT NOT NULL,
        confidence REAL NOT NULL,
        bbox TEXT NULL,
        image_path TEXT NULL,
        language TEXT DEFAULT 'en',
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_scans_created ON scans(created_at)",
)
_SCAN_COLUMNS = "id, session_id, detected_text, confidence, bbox, image_path, language, created_at"


def _encode_dt(moment: datetime) -> str:
    return moment.strftime(_DT_FORMAT)


def _decode_dt(value: str | None) -> datetime | None:
    return datetime.strptime(value, _DT_FORMAT) if value else None


def _row_to_scan(row: sqlite3.Row) -> ScanRecord:
    return ScanRecord(
        id=int(row["id"]),
        session_id=int(row["session_id"]) if row["session_id"] is not None else None,
        detected_text=row["detected_text"],
        confidence=float(row["confidence"]),
        bbox=decode_bbox(row["bbox"]),
        image_path=row["image_path"],
        language=row["language"],
        created_at=_decode_dt(row["created_at"]) or datetime.min,
    )


class SQLiteScanRepository:
    """Store scans in a local SQLite file. Thread-safe via a single lock."""

    backend_name = "SQLite"

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.RLock()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
            with self._tx() as cur:
                for statement in _SCHEMA:
                    cur.execute(statement)
        except (sqlite3.Error, OSError) as exc:
            raise DatabaseError(
                f"Could not open the offline SQLite database at {path}: {exc}"
            ) from exc
        log.info("SQLite repository ready at %s", path)

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Cursor]:
        with self._lock:
            cursor = self._conn.cursor()
            try:
                yield cursor
                self._conn.commit()
            except sqlite3.Error as exc:
                self._conn.rollback()
                raise DatabaseError(f"SQLite error: {exc}") from exc
            finally:
                cursor.close()

    # --------------------------------------------------------------- sessions
    def create_session(self, started_at: datetime) -> int:
        """Insert a session row and return its id."""
        with self._tx() as cur:
            cur.execute(
                "INSERT INTO scan_sessions (started_at, ended_at, total_detections) "
                "VALUES (?, NULL, 0)",
                (_encode_dt(started_at),),
            )
            return int(cur.lastrowid or 0)

    def end_session(self, session_id: int, ended_at: datetime, total_detections: int) -> None:
        """Mark a session as finished."""
        with self._tx() as cur:
            cur.execute(
                "UPDATE scan_sessions SET ended_at = ?, total_detections = ? WHERE id = ?",
                (_encode_dt(ended_at), total_detections, session_id),
            )

    def get_session(self, session_id: int) -> SessionRecord | None:
        """Return a session or None."""
        with self._tx() as cur:
            cur.execute(
                "SELECT id, started_at, ended_at, total_detections FROM scan_sessions WHERE id = ?",
                (session_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return SessionRecord(
            id=int(row["id"]),
            started_at=_decode_dt(row["started_at"]) or datetime.min,
            ended_at=_decode_dt(row["ended_at"]),
            total_detections=int(row["total_detections"] or 0),
        )

    def delete_session(self, session_id: int) -> bool:
        """Delete a session; scans keep existing with a NULL session."""
        with self._tx() as cur:
            cur.execute("DELETE FROM scan_sessions WHERE id = ?", (session_id,))
            return cur.rowcount > 0

    # ------------------------------------------------------------------ scans
    def insert_scan(self, record: ScanRecord) -> int:
        """Insert one scan and return its id."""
        return self.insert_scans([record])[0]

    def insert_scans(self, records: list[ScanRecord]) -> list[int]:
        """Insert many scans in one transaction and return their ids."""
        if not records:
            return []
        ids: list[int] = []
        with self._tx() as cur:
            for record in records:
                cur.execute(
                    "INSERT INTO scans (session_id, detected_text, confidence, bbox, image_path, "
                    "language, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        record.session_id,
                        record.detected_text,
                        float(record.confidence),
                        encode_bbox(record.bbox),
                        record.image_path,
                        record.language,
                        _encode_dt(record.created_at),
                    ),
                )
                ids.append(int(cur.lastrowid or 0))
        return ids

    def fetch_scans(self, limit: int = 500, offset: int = 0) -> list[ScanRecord]:
        """Return scans newest first."""
        with self._tx() as cur:
            cur.execute(
                f"SELECT {_SCAN_COLUMNS} FROM scans ORDER BY created_at DESC, id DESC "
                "LIMIT ? OFFSET ?",
                (limit, offset),
            )
            return [_row_to_scan(row) for row in cur.fetchall()]

    def search_scans(self, query: str, limit: int = 500) -> list[ScanRecord]:
        """Case-insensitive substring search, newest first."""
        if not query.strip():
            return self.fetch_scans(limit=limit)
        with self._tx() as cur:
            cur.execute(
                f"SELECT {_SCAN_COLUMNS} FROM scans WHERE detected_text LIKE ? ESCAPE '\\' "
                "ORDER BY created_at DESC, id DESC LIMIT ?",
                (like_pattern(query), limit),
            )
            return [_row_to_scan(row) for row in cur.fetchall()]

    def delete_scan(self, scan_id: int) -> bool:
        """Delete a scan; True if a row was removed."""
        with self._tx() as cur:
            cur.execute("DELETE FROM scans WHERE id = ?", (scan_id,))
            return cur.rowcount > 0

    def count_scans(self) -> int:
        """Return the number of stored scans."""
        with self._tx() as cur:
            cur.execute("SELECT COUNT(*) FROM scans")
            return int(cur.fetchone()[0])

    def scans_per_day(self, days: int = 30) -> list[tuple[date, int]]:
        """Return `(day, count)` for the last `days` days, oldest first."""
        if days <= 0:
            return []
        since = datetime.combine(date.today() - timedelta(days=days - 1), datetime.min.time())
        with self._tx() as cur:
            cur.execute(
                "SELECT substr(created_at, 1, 10) AS day, COUNT(*) AS n FROM scans "
                "WHERE created_at >= ? GROUP BY day ORDER BY day",
                (_encode_dt(since),),
            )
            return [(date.fromisoformat(row["day"]), int(row["n"])) for row in cur.fetchall()]

    def confidence_values(self, limit: int = 5000) -> list[float]:
        """Return recent confidence values."""
        with self._tx() as cur:
            cur.execute("SELECT confidence FROM scans ORDER BY id DESC LIMIT ?", (limit,))
            return [float(row[0]) for row in cur.fetchall()]

    def close(self) -> None:
        """Close the connection; safe to call twice."""
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None  # type: ignore[assignment]
