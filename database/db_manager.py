"""Pick the storage backend: MySQL when reachable, otherwise an offline SQLite file."""

from __future__ import annotations

from typing import Any

from config.settings import Settings
from database.models import DatabaseError, ScanRepository
from database.mysql_repository import MySQLScanRepository
from database.prescription_repository import (
    MySQLPrescriptionRepository,
    PrescriptionRepository,
    SQLitePrescriptionRepository,
)
from database.sqlite_repository import SQLiteScanRepository
from utils.logger import get_logger

log = get_logger("database.manager")


class DatabaseManager:
    """Own the active `ScanRepository` and remember whether we are in offline mode."""

    def __init__(self, settings: Settings, connector_module: Any | None = None) -> None:
        self._settings = settings
        self._connector_module = connector_module
        self.repo: ScanRepository | None = None
        self.prescriptions: PrescriptionRepository | None = None
        self.offline: bool = False
        self.warning: str | None = None

    @property
    def backend_name(self) -> str:
        """`"MySQL"`, `"SQLite"` or `"none"` before `connect()`."""
        return self.repo.backend_name if self.repo is not None else "none"

    def connect(self) -> None:
        """Try MySQL, fall back to SQLite. Never raises; inspect `offline` and `warning`."""
        if self.repo is not None:
            return
        try:
            self.repo = MySQLScanRepository(self._settings, connector_module=self._connector_module)
            self.prescriptions = MySQLPrescriptionRepository(
                self._settings, connector_module=self._connector_module
            )
            self.offline = False
            self.warning = None
            return
        except DatabaseError as exc:
            mysql_problem = str(exc)
        except Exception as exc:  # pragma: no cover - defensive: unexpected connector failure
            log.exception("Unexpected error while connecting to MySQL")
            mysql_problem = f"unexpected error: {exc}"

        self.offline = True
        try:
            self.repo = SQLiteScanRepository(self._settings.offline_db_path)
            self.prescriptions = SQLitePrescriptionRepository(self._settings.offline_db_path)
            self.warning = (
                f"MySQL unavailable: {mysql_problem} Running in OFFLINE mode - scans are "
                f"saved to the local SQLite file {self._settings.offline_db_path}."
            )
        except DatabaseError as exc:
            self.repo = None
            self.prescriptions = None
            self.warning = (
                f"MySQL unavailable: {mysql_problem} The offline SQLite fallback also failed: "
                f"{exc} Scans will not be saved."
            )
        log.warning(self.warning)

    def close(self) -> None:
        """Close the active repository; safe to call twice."""
        repo, self.repo = self.repo, None
        prescriptions, self.prescriptions = self.prescriptions, None
        if repo is not None:
            repo.close()
        if prescriptions is not None:
            prescriptions.close()
