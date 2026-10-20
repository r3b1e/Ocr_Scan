"""Tests for database.prescription_repository (documents, extractions, corrections)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from database.db_manager import DatabaseManager
from database.prescription_repository import (
    DocumentRecord,
    MySQLPrescriptionRepository,
    SQLitePrescriptionRepository,
)


def _doc(**overrides) -> DocumentRecord:
    values = dict(
        id=None,
        created_at=datetime(2026, 10, 21, 10, 0, 0),
        source="api",
        image_path="data/documents/1.jpg",
        backend="claude",
        model="claude-opus-5-5",
        handwritten=False,
        processing_ms=4321,
        usage_json='{"input_tokens": 10}',
    )
    values.update(overrides)
    return DocumentRecord(**values)


@pytest.fixture(params=["sqlite", pytest.param("mysql", marks=pytest.mark.mysql)])
def repo(request, tmp_path: Path):
    if request.param == "sqlite":
        repository = SQLitePrescriptionRepository(tmp_path / "rx.sqlite3")
    else:
        settings = request.getfixturevalue("mysql_settings")
        repository = MySQLPrescriptionRepository(settings)
    yield repository
    repository.close()


def test_document_lifecycle(repo):
    assert repo.count_documents() == 0
    doc_id = repo.create_document(_doc())
    assert isinstance(doc_id, int) and doc_id >= 1
    assert repo.count_documents() == 1

    extraction_id = repo.save_extraction(
        doc_id, raw_json='{"medications": []}', result_json='{"backend": "claude"}'
    )
    assert extraction_id >= 1

    stored = repo.get_document(doc_id)
    assert stored is not None
    document, result_json, correction_json = stored
    assert document.id == doc_id and document.backend == "claude" and document.handwritten is False
    assert document.processing_ms == 4321 and document.usage_json == '{"input_tokens": 10}'
    assert document.created_at == datetime(2026, 10, 21, 10, 0, 0)
    assert result_json == '{"backend": "claude"}' and correction_json is None

    repo.save_correction(doc_id, '{"v": 1}')
    second = repo.save_correction(doc_id, '{"v": 2}')
    assert second >= 1
    _, _, latest = repo.get_document(doc_id)
    assert latest == '{"v": 2}'


def test_delete_cascades(repo):
    doc_id = repo.create_document(_doc(handwritten=True, usage_json=None))
    repo.save_extraction(doc_id, "{}", "{}")
    repo.save_correction(doc_id, "{}")
    assert repo.delete_document(doc_id) is True
    assert repo.delete_document(doc_id) is False
    assert repo.get_document(doc_id) is None
    assert repo.count_documents() == 0


def test_get_missing_document(repo):
    assert repo.get_document(999_999) is None


def test_database_manager_exposes_prescription_repository(tmp_settings):
    class FakeMySQLError(Exception):
        def __init__(self, msg, errno):
            super().__init__(msg)
            self.msg, self.errno = msg, errno

    class DownConnector:
        Error = FakeMySQLError

        def connect(self, **kwargs):
            raise FakeMySQLError("down", 2003)

    manager = DatabaseManager(tmp_settings, connector_module=DownConnector())
    manager.connect()
    try:
        assert manager.offline is True
        assert isinstance(manager.prescriptions, SQLitePrescriptionRepository)
        assert manager.prescriptions.count_documents() == 0
    finally:
        manager.close()
    assert manager.prescriptions is None
