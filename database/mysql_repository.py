"""MySQL implementation of `ScanRepository` with a connection pool and auto-created schema."""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from config.settings import Settings
from database.models import (
    DatabaseError,
    ScanRecord,
    SessionRecord,
    decode_bbox,
    encode_bbox,
    like_pattern,
)
from utils.logger import get_logger

log = get_logger("database.mysql")

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_]+$")
_SCAN_COLUMNS = "id, session_id, detected_text, confidence, bbox, image_path, language, created_at"

# MySQL error numbers we translate into plain language.
_ERR_ACCESS_DENIED = 1045
_ERR_DB_ACCESS_DENIED = 1044
_ERR_CANT_CONNECT = {2002, 2003, 2005, 2006, 2013, 2055}
_ERR_UNKNOWN_DB = 1049
_ERR_NO_TABLE = 1146
_ERR_PRIVILEGE = 1227
_ERR_TOO_MANY_CONNECTIONS = 1040


def load_schema_statements(path: Path = SCHEMA_PATH) -> list[str]:
    """Return the `CREATE TABLE` statements from schema.sql (skipping CREATE DATABASE)."""
    lines = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if not line.strip().startswith("--")
    ]
    statements = [chunk.strip() for chunk in "\n".join(lines).split(";")]
    return [s for s in statements if s and not s.upper().startswith("CREATE DATABASE")]


class MySQLConnectionBase:
    """Connection pool plus schema bootstrap shared by every MySQL repository."""

    backend_name = "MySQL"

    def __init__(
        self, settings: Settings, connector_module: Any | None = None, pool_size: int = 3
    ) -> None:
        if connector_module is None:
            import mysql.connector as connector_module  # noqa: N813 - keep the module name
        self._connector = connector_module
        self._settings = settings
        self._pool: Any | None = None
        if not _IDENTIFIER.match(settings.db_name):
            raise DatabaseError(
                f"DB_NAME {settings.db_name!r} is not a valid MySQL identifier "
                "(use letters, digits and underscores only)."
            )
        self._bootstrap(pool_size)

    # -------------------------------------------------------------- bootstrap
    def _translate(self, exc: Exception) -> str:
        errno = getattr(exc, "errno", None)
        msg = getattr(exc, "msg", None) or str(exc)
        s = self._settings
        if errno == _ERR_ACCESS_DENIED:
            return (
                f"MySQL rejected the credentials for user '{s.db_user}'. "
                "Check DB_USER and DB_PASSWORD in your .env file."
            )
        if errno in _ERR_CANT_CONNECT:
            return (
                f"MySQL server is not reachable at {s.db_host}:{s.db_port}. "
                "Make sure the MySQL service is running and DB_HOST/DB_PORT are correct."
            )
        if errno in {_ERR_DB_ACCESS_DENIED, _ERR_PRIVILEGE}:
            return (
                f"User '{s.db_user}' lacks permission on database '{s.db_name}'. "
                f"Grant it with: GRANT ALL PRIVILEGES ON {s.db_name}.* TO '{s.db_user}'@'%';"
            )
        if errno == _ERR_UNKNOWN_DB:
            return f"Database '{s.db_name}' does not exist and could not be created."
        if errno == _ERR_NO_TABLE:
            return "A required table is missing. Restart the app to recreate the schema."
        if errno == _ERR_TOO_MANY_CONNECTIONS:
            return "MySQL has too many open connections; close other clients and retry."
        return f"MySQL error {errno or ''}: {msg}".replace("error :", "error:")

    def _server_kwargs(self) -> dict[str, Any]:
        s = self._settings
        return {
            "host": s.db_host,
            "port": s.db_port,
            "user": s.db_user,
            "password": s.db_password,
            "connection_timeout": 5,
            "charset": "utf8mb4",
        }

    def _ensure_database(self) -> None:
        name = self._settings.db_name
        connection = self._connector.connect(**self._server_kwargs())
        try:
            cursor = connection.cursor()
            try:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{name}` CHARACTER SET utf8mb4")
                connection.commit()
            except self._connector.Error as exc:
                # A user may be allowed to use the database without being allowed to create it.
                cursor.execute("SHOW DATABASES LIKE %s", (name,))
                if cursor.fetchone() is None:
                    raise exc
            finally:
                cursor.close()
        finally:
            connection.close()

    def _bootstrap(self, pool_size: int) -> None:
        try:
            self._ensure_database()
            self._pool = self._connector.pooling.MySQLConnectionPool(
                pool_name=f"ocr_scanner_{id(self)}",
                pool_size=pool_size,
                pool_reset_session=True,
                database=self._settings.db_name,
                **self._server_kwargs(),
            )
            with self._connection() as connection:
                cursor = connection.cursor()
                try:
                    for statement in load_schema_statements():
                        cursor.execute(statement)
                finally:
                    cursor.close()
        except DatabaseError:
            raise
        except self._connector.Error as exc:
            log.warning("MySQL bootstrap failed: %s", exc)
            raise DatabaseError(self._translate(exc)) from exc
        except OSError as exc:
            raise DatabaseError(f"Could not read schema.sql: {exc}") from exc
        log.info(
            "MySQL repository ready: %s@%s:%s/%s",
            self._settings.db_user,
            self._settings.db_host,
            self._settings.db_port,
            self._settings.db_name,
        )

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        if self._pool is None:
            raise DatabaseError("MySQL connection pool is closed.")
        try:
            connection = self._pool.get_connection()
        except self._connector.Error as exc:
            raise DatabaseError(self._translate(exc)) from exc
        try:
            yield connection
            connection.commit()
        except self._connector.Error as exc:
            with suppress(Exception):
                connection.rollback()
            raise DatabaseError(self._translate(exc)) from exc
        finally:
            with suppress(Exception):
                connection.close()

    @contextmanager
    def _cursor(self) -> Iterator[Any]:
        with self._connection() as connection:
            cursor = connection.cursor()
            try:
                yield cursor
            finally:
                cursor.close()

    def close(self) -> None:
        """Drop the pool reference; pooled connections close when garbage-collected."""
        pool, self._pool = self._pool, None
        if pool is not None:
            with suppress(Exception):
                pool._remove_connections()  # noqa: SLF001 - connector has no public drain API


class MySQLScanRepository(MySQLConnectionBase):
    """Store scans in MySQL. Creates the database and tables on first use."""

    # --------------------------------------------------------------- sessions
    def create_session(self, started_at: datetime) -> int:
        """Insert a session row and return its id."""
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO scan_sessions (started_at, ended_at, total_detections) "
                "VALUES (%s, NULL, 0)",
                (started_at,),
            )
            return int(cur.lastrowid)

    def end_session(self, session_id: int, ended_at: datetime, total_detections: int) -> None:
        """Mark a session as finished."""
        with self._cursor() as cur:
            cur.execute(
                "UPDATE scan_sessions SET ended_at = %s, total_detections = %s WHERE id = %s",
                (ended_at, total_detections, session_id),
            )

    def get_session(self, session_id: int) -> SessionRecord | None:
        """Return a session or None."""
        with self._cursor() as cur:
            cur.execute(
                "SELECT id, started_at, ended_at, total_detections FROM scan_sessions "
                "WHERE id = %s",
                (session_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return SessionRecord(
            id=int(row[0]), started_at=row[1], ended_at=row[2], total_detections=int(row[3] or 0)
        )

    def delete_session(self, session_id: int) -> bool:
        """Delete a session; scans keep existing with a NULL session (FK ON DELETE SET NULL)."""
        with self._cursor() as cur:
            cur.execute("DELETE FROM scan_sessions WHERE id = %s", (session_id,))
            return cur.rowcount > 0

    # ------------------------------------------------------------------ scans
    @staticmethod
    def _row_to_scan(row: tuple[Any, ...]) -> ScanRecord:
        return ScanRecord(
            id=int(row[0]),
            session_id=int(row[1]) if row[1] is not None else None,
            detected_text=row[2],
            confidence=float(row[3]),
            bbox=decode_bbox(row[4]),
            image_path=row[5],
            language=row[6],
            created_at=row[7],
        )

    def insert_scan(self, record: ScanRecord) -> int:
        """Insert one scan and return its id."""
        return self.insert_scans([record])[0]

    def insert_scans(self, records: list[ScanRecord]) -> list[int]:
        """Insert many scans in one transaction and return their ids."""
        if not records:
            return []
        ids: list[int] = []
        with self._cursor() as cur:
            for record in records:
                cur.execute(
                    "INSERT INTO scans (session_id, detected_text, confidence, bbox, image_path, "
                    "language, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (
                        record.session_id,
                        record.detected_text,
                        float(record.confidence),
                        encode_bbox(record.bbox),
                        record.image_path,
                        record.language,
                        record.created_at,
                    ),
                )
                ids.append(int(cur.lastrowid))
        return ids

    def fetch_scans(self, limit: int = 500, offset: int = 0) -> list[ScanRecord]:
        """Return scans newest first."""
        with self._cursor() as cur:
            cur.execute(
                f"SELECT {_SCAN_COLUMNS} FROM scans ORDER BY created_at DESC, id DESC "
                "LIMIT %s OFFSET %s",
                (int(limit), int(offset)),
            )
            return [self._row_to_scan(row) for row in cur.fetchall()]

    def search_scans(self, query: str, limit: int = 500) -> list[ScanRecord]:
        """Case-insensitive substring search, newest first."""
        if not query.strip():
            return self.fetch_scans(limit=limit)
        with self._cursor() as cur:
            cur.execute(
                f"SELECT {_SCAN_COLUMNS} FROM scans WHERE detected_text LIKE %s "
                "ORDER BY created_at DESC, id DESC LIMIT %s",
                (like_pattern(query), int(limit)),
            )
            return [self._row_to_scan(row) for row in cur.fetchall()]

    def delete_scan(self, scan_id: int) -> bool:
        """Delete a scan; True if a row was removed."""
        with self._cursor() as cur:
            cur.execute("DELETE FROM scans WHERE id = %s", (scan_id,))
            return cur.rowcount > 0

    def count_scans(self) -> int:
        """Return the number of stored scans."""
        with self._cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM scans")
            return int(cur.fetchone()[0])

    def scans_per_day(self, days: int = 30) -> list[tuple[date, int]]:
        """Return `(day, count)` for the last `days` days, oldest first."""
        if days <= 0:
            return []
        since = datetime.combine(date.today() - timedelta(days=days - 1), datetime.min.time())
        with self._cursor() as cur:
            cur.execute(
                "SELECT DATE(created_at) AS day, COUNT(*) FROM scans WHERE created_at >= %s "
                "GROUP BY day ORDER BY day",
                (since,),
            )
            return [(row[0], int(row[1])) for row in cur.fetchall()]

    def confidence_values(self, limit: int = 5000) -> list[float]:
        """Return recent confidence values."""
        with self._cursor() as cur:
            cur.execute("SELECT confidence FROM scans ORDER BY id DESC LIMIT %s", (int(limit),))
            return [float(row[0]) for row in cur.fetchall()]
