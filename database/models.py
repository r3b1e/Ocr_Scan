"""Data records and the repository interface shared by MySQL and SQLite backends."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any, Protocol


class DatabaseError(RuntimeError):
    """Raised with a plain-language message when a database operation fails."""


@dataclass
class ScanRecord:
    """One recognised text fragment stored in the `scans` table."""

    id: int | None
    session_id: int | None
    detected_text: str
    confidence: float
    bbox: list[list[int]] | None
    image_path: str | None
    language: str
    created_at: datetime

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable mapping (datetime as ISO-8601)."""
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data


@dataclass
class SessionRecord:
    """One camera session stored in the `scan_sessions` table."""

    id: int
    started_at: datetime
    ended_at: datetime | None
    total_detections: int


class ScanRepository(Protocol):
    """Storage contract implemented by `MySQLScanRepository` and `SQLiteScanRepository`."""

    backend_name: str

    def create_session(self, started_at: datetime) -> int:
        """Insert a session row and return its id."""

    def end_session(self, session_id: int, ended_at: datetime, total_detections: int) -> None:
        """Mark a session as finished."""

    def get_session(self, session_id: int) -> SessionRecord | None:
        """Return a session or None when it does not exist."""

    def delete_session(self, session_id: int) -> bool:
        """Delete a session; its scans keep existing with `session_id = NULL`."""

    def insert_scan(self, record: ScanRecord) -> int:
        """Insert one scan and return its id."""

    def insert_scans(self, records: list[ScanRecord]) -> list[int]:
        """Insert many scans in one transaction and return their ids."""

    def fetch_scans(self, limit: int = 500, offset: int = 0) -> list[ScanRecord]:
        """Return scans newest first."""

    def search_scans(self, query: str, limit: int = 500) -> list[ScanRecord]:
        """Case-insensitive substring search on `detected_text`, newest first."""

    def delete_scan(self, scan_id: int) -> bool:
        """Delete a scan; return True if a row was removed."""

    def count_scans(self) -> int:
        """Return the total number of scans."""

    def scans_per_day(self, days: int = 30) -> list[tuple[date, int]]:
        """Return `(day, count)` pairs for the last `days` days, oldest first."""

    def confidence_values(self, limit: int = 5000) -> list[float]:
        """Return recent confidence values for the histogram."""

    def close(self) -> None:
        """Release connections."""


def decode_bbox(value: object) -> list[list[int]] | None:
    """Decode a bbox column that may arrive as JSON text, bytes or an already-parsed list."""
    if value is None:
        return None
    if isinstance(value, list):
        return value
    if isinstance(value, bytes | bytearray):
        value = value.decode("utf-8")
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, list) else None


def encode_bbox(bbox: list[list[int]] | None) -> str | None:
    """Encode a bbox for storage in a JSON/TEXT column."""
    return json.dumps(bbox) if bbox is not None else None


def like_pattern(query: str) -> str:
    """Escape LIKE wildcards in a user query and wrap it for substring matching."""
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"
