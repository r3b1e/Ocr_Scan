"""Shared pytest fixtures for the OCR scanner test-suite."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture()
def tmp_settings(tmp_path: Path):
    """Return a Settings object whose output directories live under tmp_path."""
    from config.settings import Settings

    settings = Settings.load(env_path=tmp_path / "missing.env", base_dir=tmp_path)
    settings.ensure_directories()
    return settings


MYSQL_TEST_DB = "ocr_scanner_test"


@pytest.fixture()
def mysql_settings(tmp_path: Path):
    """Settings for a throwaway MySQL test database; skips when MySQL is unreachable."""
    import os

    from config.settings import Settings

    settings = Settings.load(env_path=ROOT / ".env", base_dir=tmp_path)
    settings.db_host = os.environ.get("OCR_TEST_MYSQL_HOST", settings.db_host)
    settings.db_port = int(os.environ.get("OCR_TEST_MYSQL_PORT", settings.db_port))
    settings.db_user = os.environ.get("OCR_TEST_MYSQL_USER", settings.db_user)
    settings.db_password = os.environ.get("OCR_TEST_MYSQL_PASSWORD", settings.db_password)
    settings.db_name = MYSQL_TEST_DB
    settings.ensure_directories()

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
    return settings
