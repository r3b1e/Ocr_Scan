"""Tests for the database layer: SQLite always, MySQL when reachable, plus mocked failures."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from config.settings import Settings
from database.db_manager import DatabaseManager
from database.models import DatabaseError, ScanRecord
from database.mysql_repository import MySQLScanRepository
from database.sqlite_repository import SQLiteScanRepository

ROOT = Path(__file__).resolve().parents[1]
MYSQL_TEST_DB = "ocr_scanner_test"


def _mysql_settings(tmp_path: Path) -> Settings:
    """Build settings for the MySQL test database from env vars or the repo .env."""
    settings = Settings.load(env_path=ROOT / ".env", base_dir=tmp_path)
    settings.db_host = os.environ.get("OCR_TEST_MYSQL_HOST", settings.db_host)
    settings.db_port = int(os.environ.get("OCR_TEST_MYSQL_PORT", settings.db_port))
    settings.db_user = os.environ.get("OCR_TEST_MYSQL_USER", settings.db_user)
    settings.db_password = os.environ.get("OCR_TEST_MYSQL_PASSWORD", settings.db_password)
    settings.db_name = MYSQL_TEST_DB
    return settings


def _drop_mysql_test_database(settings: Settings) -> None:
    """Start every MySQL test from an empty database (also exercises auto-creation)."""
    import mysql.connector

    try:
        connection = mysql.connector.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            connection_timeout=3,
        )
    except mysql.connector.Error as exc:
        pytest.skip(f"MySQL not reachable for tests: {exc}")
    try:
        cursor = connection.cursor()
        cursor.execute(f"DROP DATABASE IF EXISTS `{MYSQL_TEST_DB}`")
        connection.commit()
        cursor.close()
    finally:
        connection.close()


def _record(text: str = "HELLO", confidence: float = 0.9, **overrides) -> ScanRecord:
    values = dict(
        id=None,
        session_id=None,
        detected_text=text,
        confidence=confidence,
        bbox=[[0, 0], [10, 0], [10, 5], [0, 5]],
        image_path="captures/x.png",
        language="en",
        created_at=datetime(2026, 9, 20, 10, 0, 0),
    )
    values.update(overrides)
    return ScanRecord(**values)


@pytest.fixture(params=["sqlite", pytest.param("mysql", marks=pytest.mark.mysql)])
def repo(request, tmp_path: Path):
    if request.param == "sqlite":
        repository = SQLiteScanRepository(tmp_path / "test.sqlite3")
    else:
        settings = _mysql_settings(tmp_path)
        _drop_mysql_test_database(settings)
        try:
            repository = MySQLScanRepository(settings)
        except DatabaseError as exc:
            pytest.skip(f"MySQL not reachable for tests: {exc}")
    yield repository
    repository.close()


def test_backend_name(repo):
    assert repo.backend_name in {"SQLite", "MySQL"}


def test_create_and_end_session(repo):
    started = datetime(2026, 9, 20, 9, 0, 0)
    session_id = repo.create_session(started)
    assert isinstance(session_id, int) and session_id >= 1
    session = repo.get_session(session_id)
    assert session is not None
    assert session.started_at == started
    assert session.ended_at is None
    assert session.total_detections == 0

    ended = datetime(2026, 9, 20, 9, 5, 0)
    repo.end_session(session_id, ended, total_detections=7)
    session = repo.get_session(session_id)
    assert session.ended_at == ended
    assert session.total_detections == 7


def test_get_missing_session_returns_none(repo):
    assert repo.get_session(999_999) is None


def test_insert_and_fetch_roundtrip(repo):
    session_id = repo.create_session(datetime(2026, 9, 20, 9, 0, 0))
    scan_id = repo.insert_scan(_record(session_id=session_id))
    assert isinstance(scan_id, int) and scan_id >= 1

    rows = repo.fetch_scans()
    assert len(rows) == 1
    row = rows[0]
    assert row.id == scan_id
    assert row.session_id == session_id
    assert row.detected_text == "HELLO"
    assert row.confidence == pytest.approx(0.9, abs=1e-6)
    assert row.bbox == [[0, 0], [10, 0], [10, 5], [0, 5]]
    assert row.image_path == "captures/x.png"
    assert row.language == "en"
    assert row.created_at == datetime(2026, 9, 20, 10, 0, 0)


def test_insert_scans_bulk_and_order_newest_first(repo):
    base = datetime(2026, 9, 20, 10, 0, 0)
    ids = repo.insert_scans(
        [
            _record("first", created_at=base),
            _record("second", created_at=base + timedelta(seconds=1)),
            _record("third", created_at=base + timedelta(seconds=2)),
        ]
    )
    assert len(ids) == 3 and len(set(ids)) == 3
    assert repo.insert_scans([]) == []
    texts = [r.detected_text for r in repo.fetch_scans()]
    assert texts == ["third", "second", "first"]
    assert [r.detected_text for r in repo.fetch_scans(limit=1)] == ["third"]
    assert [r.detected_text for r in repo.fetch_scans(limit=1, offset=1)] == ["second"]


def test_null_bbox_and_image_roundtrip(repo):
    repo.insert_scan(_record(bbox=None, image_path=None, session_id=None))
    row = repo.fetch_scans()[0]
    assert row.bbox is None and row.image_path is None and row.session_id is None


def test_search_is_case_insensitive_substring(repo):
    repo.insert_scans([_record("Invoice 123"), _record("total invoice"), _record("Receipt")])
    found = repo.search_scans("INVOICE")
    assert sorted(r.detected_text for r in found) == ["Invoice 123", "total invoice"]
    assert repo.search_scans("nothing-here") == []
    assert len(repo.search_scans("")) == 3


def test_search_escapes_like_wildcards(repo):
    repo.insert_scans([_record("100%"), _record("100 percent"), _record("a_b"), _record("aXb")])
    assert [r.detected_text for r in repo.search_scans("100%")] == ["100%"]
    assert [r.detected_text for r in repo.search_scans("a_b")] == ["a_b"]


def test_delete_scan_and_count(repo):
    ids = repo.insert_scans([_record("a"), _record("b")])
    assert repo.count_scans() == 2
    assert repo.delete_scan(ids[0]) is True
    assert repo.delete_scan(ids[0]) is False
    assert repo.count_scans() == 1


def test_scans_per_day_and_confidence_values(repo):
    today = datetime.now().replace(microsecond=0)
    yesterday = today - timedelta(days=1)
    repo.insert_scans(
        [
            _record("a", 0.5, created_at=today),
            _record("b", 0.7, created_at=today),
            _record("c", 0.9, created_at=yesterday),
        ]
    )
    per_day = repo.scans_per_day(days=7)
    assert per_day == [(yesterday.date(), 1), (today.date(), 2)]
    assert all(isinstance(d, date) for d, _ in per_day)
    assert sorted(repo.confidence_values()) == pytest.approx([0.5, 0.7, 0.9], abs=1e-6)
    assert repo.scans_per_day(days=0) == []


def test_deleting_session_keeps_scans(repo):
    session_id = repo.create_session(datetime(2026, 9, 20, 9, 0, 0))
    repo.insert_scan(_record(session_id=session_id))
    repo.delete_session(session_id)
    assert repo.get_session(session_id) is None
    rows = repo.fetch_scans()
    assert len(rows) == 1 and rows[0].session_id is None


def test_sqlite_creates_parent_directory(tmp_path: Path):
    path = tmp_path / "deep" / "nested" / "scans.sqlite3"
    repository = SQLiteScanRepository(path)
    try:
        assert path.exists()
        assert repository.count_scans() == 0
    finally:
        repository.close()


# ---------------------------------------------------------------------------
# Mocked MySQL connector: error mapping and offline fallback
# ---------------------------------------------------------------------------


class FakeMySQLError(Exception):
    def __init__(self, msg: str, errno: int):
        super().__init__(msg)
        self.msg = msg
        self.errno = errno


class FailingConnector:
    """Mimics the mysql.connector module surface used by MySQLScanRepository."""

    Error = FakeMySQLError

    def __init__(self, errno: int, msg: str):
        self.errno = errno
        self.msg = msg
        self.calls = 0

    def connect(self, **kwargs):
        self.calls += 1
        raise FakeMySQLError(self.msg, self.errno)


@pytest.mark.parametrize(
    ("errno", "msg", "expected"),
    [
        (1045, "Access denied for user 'x'@'localhost'", "credentials"),
        (2003, "Can't connect to MySQL server on 'localhost:3306'", "localhost:3306"),
        (1044, "Access denied to database", "permission"),
    ],
)
def test_mysql_errors_are_translated(tmp_settings, errno, msg, expected):
    connector = FailingConnector(errno, msg)
    with pytest.raises(DatabaseError) as excinfo:
        MySQLScanRepository(tmp_settings, connector_module=connector)
    text = str(excinfo.value)
    assert expected in text
    assert "Traceback" not in text
    assert connector.calls == 1


def test_database_manager_falls_back_to_sqlite(tmp_settings):
    connector = FailingConnector(2003, "Can't connect to MySQL server")
    manager = DatabaseManager(tmp_settings, connector_module=connector)
    manager.connect()
    try:
        assert manager.offline is True
        assert manager.backend_name == "SQLite"
        assert manager.warning and "offline" in manager.warning.lower()
        assert tmp_settings.offline_db_path.exists()
        manager.repo.insert_scan(_record("offline row"))
        assert manager.repo.count_scans() == 1
    finally:
        manager.close()


def test_database_manager_connect_is_idempotent(tmp_settings):
    connector = FailingConnector(2003, "down")
    manager = DatabaseManager(tmp_settings, connector_module=connector)
    manager.connect()
    first_repo = manager.repo
    manager.connect()
    assert manager.repo is first_repo
    manager.close()
    manager.close()


@pytest.mark.mysql
def test_database_manager_uses_mysql_when_available(tmp_path: Path):
    settings = _mysql_settings(tmp_path)
    settings.ensure_directories()
    manager = DatabaseManager(settings)
    manager.connect()
    try:
        if manager.offline:
            pytest.skip(f"MySQL not reachable: {manager.warning}")
        assert manager.backend_name == "MySQL"
        assert manager.warning is None
        assert manager.repo.count_scans() >= 0
    finally:
        manager.close()
