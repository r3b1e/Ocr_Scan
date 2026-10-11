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
