"""Storage for prescription documents, model extractions and user corrections."""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from config.settings import Settings
from database.models import DatabaseError
from database.mysql_repository import MySQLConnectionBase
from utils.logger import get_logger

log = get_logger("database.prescriptions")

_DT_FORMAT = "%Y-%m-%d %H:%M:%S"
_DOC_COLUMNS = (
    "id, created_at, source, image_path, backend, model, handwritten, processing_ms, usage_json"
)


@dataclass
class DocumentRecord:
    """One uploaded prescription image and how it was processed."""

    id: int | None
    created_at: datetime
    source: str
    image_path: str
    backend: str
    model: str
    handwritten: bool
    processing_ms: int
    usage_json: str | None


class PrescriptionRepository(Protocol):
    """Contract implemented by the SQLite and MySQL repositories below."""

    backend_name: str

    def create_document(self, record: DocumentRecord) -> int:
        """Insert a document row and return its id."""

    def set_image_path(self, document_id: int, image_path: str) -> None:
        """Record where the image was stored."""

    def save_extraction(self, document_id: int, raw_json: str, result_json: str) -> int:
        """Store the model output and the validated result."""

    def save_correction(self, document_id: int, corrected_json: str) -> int:
        """Store a user-corrected result."""

    def get_document(
        self, document_id: int
    ) -> tuple[DocumentRecord, str | None, str | None] | None:
        """Return `(document, latest result_json, latest corrected_json)` or None."""

    def delete_document(self, document_id: int) -> bool:
        """Delete a document and everything attached to it."""

    def count_documents(self) -> int:
        """Number of stored documents."""

    def close(self) -> None:
        """Release connections."""


def _decode_json_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes | bytearray):
        return value.decode("utf-8")
    return str(value)


# ----------------------------------------------------------------------------- SQLite
_SQLITE_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        source TEXT NOT NULL,
        image_path TEXT NOT NULL,
        backend TEXT NOT NULL,
        model TEXT NOT NULL,
        handwritten INTEGER NOT NULL DEFAULT 0,
        processing_ms INTEGER NOT NULL DEFAULT 0,
        usage_json TEXT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS extractions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        created_at TEXT NOT NULL,
        raw_json TEXT NOT NULL,
        result_json TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS corrections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        created_at TEXT NOT NULL,
        corrected_json TEXT NOT NULL
    )
    """,
)


class SQLitePrescriptionRepository:
    """SQLite implementation (offline mode and tests)."""

    backend_name = "SQLite"

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.RLock()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(path), check_same_thread=False, timeout=5)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
            with self._tx() as cur:
                for statement in _SQLITE_SCHEMA:
                    cur.execute(statement)
        except (sqlite3.Error, OSError) as exc:
            raise DatabaseError(f"Could not open the SQLite database at {path}: {exc}") from exc

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

    def create_document(self, record: DocumentRecord) -> int:
        """Insert a document row and return its id."""
        with self._tx() as cur:
            cur.execute(
                "INSERT INTO documents (created_at, source, image_path, backend, model, "
                "handwritten, processing_ms, usage_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.created_at.strftime(_DT_FORMAT),
                    record.source,
                    record.image_path,
                    record.backend,
                    record.model,
                    int(record.handwritten),
                    int(record.processing_ms),
                    record.usage_json,
                ),
            )
            return int(cur.lastrowid or 0)

    def set_image_path(self, document_id: int, image_path: str) -> None:
        """Record where the image was stored."""
        with self._tx() as cur:
            cur.execute(
                "UPDATE documents SET image_path = ? WHERE id = ?", (image_path, document_id)
            )

    def save_extraction(self, document_id: int, raw_json: str, result_json: str) -> int:
        """Store the model output and the validated result."""
        with self._tx() as cur:
            cur.execute(
                "INSERT INTO extractions (document_id, created_at, raw_json, result_json) "
                "VALUES (?, ?, ?, ?)",
                (document_id, datetime.now().strftime(_DT_FORMAT), raw_json, result_json),
            )
            return int(cur.lastrowid or 0)

    def save_correction(self, document_id: int, corrected_json: str) -> int:
        """Store a user-corrected result."""
        with self._tx() as cur:
            cur.execute(
                "INSERT INTO corrections (document_id, created_at, corrected_json) "
                "VALUES (?, ?, ?)",
                (document_id, datetime.now().strftime(_DT_FORMAT), corrected_json),
            )
            return int(cur.lastrowid or 0)

    def get_document(
        self, document_id: int
    ) -> tuple[DocumentRecord, str | None, str | None] | None:
        """Return `(document, latest result_json, latest corrected_json)` or None."""
        with self._tx() as cur:
            cur.execute(f"SELECT {_DOC_COLUMNS} FROM documents WHERE id = ?", (document_id,))
            row = cur.fetchone()
            if row is None:
                return None
            cur.execute(
                "SELECT result_json FROM extractions WHERE document_id = ? "
                "ORDER BY id DESC LIMIT 1",
                (document_id,),
            )
            result = cur.fetchone()
            cur.execute(
                "SELECT corrected_json FROM corrections WHERE document_id = ? "
                "ORDER BY id DESC LIMIT 1",
                (document_id,),
            )
            correction = cur.fetchone()
        document = DocumentRecord(
            id=int(row["id"]),
            created_at=datetime.strptime(row["created_at"], _DT_FORMAT),
            source=row["source"],
            image_path=row["image_path"],
            backend=row["backend"],
            model=row["model"],
            handwritten=bool(row["handwritten"]),
            processing_ms=int(row["processing_ms"]),
            usage_json=row["usage_json"],
        )
        return document, (result[0] if result else None), (correction[0] if correction else None)

    def delete_document(self, document_id: int) -> bool:
        """Delete a document; extractions and corrections cascade."""
        with self._tx() as cur:
            cur.execute("DELETE FROM documents WHERE id = ?", (document_id,))
            return cur.rowcount > 0

    def count_documents(self) -> int:
        """Number of stored documents."""
        with self._tx() as cur:
            cur.execute("SELECT COUNT(*) FROM documents")
            return int(cur.fetchone()[0])

    def close(self) -> None:
        """Close the connection; safe to call twice."""
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None  # type: ignore[assignment]


# ------------------------------------------------------------------------------ MySQL
class MySQLPrescriptionRepository(MySQLConnectionBase):
    """MySQL implementation; tables come from `schema.sql` via the shared bootstrap."""

    def __init__(
        self, settings: Settings, connector_module: Any | None = None, pool_size: int = 2
    ) -> None:
        super().__init__(settings, connector_module=connector_module, pool_size=pool_size)

    def create_document(self, record: DocumentRecord) -> int:
        """Insert a document row and return its id."""
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO documents (created_at, source, image_path, backend, model, "
                "handwritten, processing_ms, usage_json) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    record.created_at,
                    record.source,
                    record.image_path,
                    record.backend,
                    record.model,
                    int(record.handwritten),
                    int(record.processing_ms),
                    record.usage_json,
                ),
            )
            return int(cur.lastrowid)

    def set_image_path(self, document_id: int, image_path: str) -> None:
        """Record where the image was stored."""
        with self._cursor() as cur:
            cur.execute(
                "UPDATE documents SET image_path = %s WHERE id = %s", (image_path, document_id)
            )

    def save_extraction(self, document_id: int, raw_json: str, result_json: str) -> int:
        """Store the model output and the validated result."""
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO extractions (document_id, created_at, raw_json, result_json) "
                "VALUES (%s, %s, %s, %s)",
                (document_id, datetime.now().replace(microsecond=0), raw_json, result_json),
            )
            return int(cur.lastrowid)

    def save_correction(self, document_id: int, corrected_json: str) -> int:
        """Store a user-corrected result."""
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO corrections (document_id, created_at, corrected_json) "
                "VALUES (%s, %s, %s)",
                (document_id, datetime.now().replace(microsecond=0), corrected_json),
            )
            return int(cur.lastrowid)

    def get_document(
        self, document_id: int
    ) -> tuple[DocumentRecord, str | None, str | None] | None:
        """Return `(document, latest result_json, latest corrected_json)` or None."""
        with self._cursor() as cur:
            cur.execute(f"SELECT {_DOC_COLUMNS} FROM documents WHERE id = %s", (document_id,))
            row = cur.fetchone()
            if row is None:
                return None
            cur.execute(
                "SELECT result_json FROM extractions WHERE document_id = %s "
                "ORDER BY id DESC LIMIT 1",
                (document_id,),
            )
            result = cur.fetchone()
            cur.execute(
                "SELECT corrected_json FROM corrections WHERE document_id = %s "
                "ORDER BY id DESC LIMIT 1",
                (document_id,),
            )
            correction = cur.fetchone()
        document = DocumentRecord(
            id=int(row[0]),
            created_at=row[1],
            source=row[2],
            image_path=row[3],
            backend=row[4],
            model=row[5],
            handwritten=bool(row[6]),
            processing_ms=int(row[7]),
            usage_json=_decode_json_text(row[8]),
        )
        return (
            document,
            _decode_json_text(result[0]) if result else None,
            _decode_json_text(correction[0]) if correction else None,
        )

    def delete_document(self, document_id: int) -> bool:
        """Delete a document; extractions and corrections cascade via foreign keys."""
        with self._cursor() as cur:
            cur.execute("DELETE FROM documents WHERE id = %s", (document_id,))
            return cur.rowcount > 0

    def count_documents(self) -> int:
        """Number of stored documents."""
        with self._cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM documents")
            return int(cur.fetchone()[0])
