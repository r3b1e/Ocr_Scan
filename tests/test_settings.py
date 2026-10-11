"""Tests for config.settings."""

from __future__ import annotations

from pathlib import Path

from config.settings import Settings


def test_defaults_when_env_missing(tmp_path: Path):
    settings = Settings.load(env_path=tmp_path / "nope.env", base_dir=tmp_path)
    assert settings.db_host == "localhost"
    assert settings.db_port == 3306
    assert settings.db_name == "ocr_scanner"
    assert settings.camera_index == 0
    assert settings.ocr_languages == ["en"]
    assert settings.ocr_gpu == "auto"
    assert settings.ocr_every_n_frames == 10
    assert settings.confidence_threshold == 0.4
    assert settings.preprocess_enabled is True
    assert settings.audio_enabled is True
    assert settings.captures_dir == tmp_path / "captures"
    assert settings.exports_dir == tmp_path / "exports"
    assert settings.logs_dir == tmp_path / "logs"
    assert settings.offline_db_path == tmp_path / "data" / "offline_scans.sqlite3"


def test_env_file_overrides_defaults(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text(
        "DB_HOST=db.example.com\nDB_PORT=3307\nDB_USER=alice\nDB_PASSWORD=s3cret\n"
        "DB_NAME=mydb\nCAMERA_INDEX=2\nOCR_LANGUAGES=en, hi ,fr\nOCR_GPU=false\n"
        "OCR_EVERY_N_FRAMES=5\nCONFIDENCE_THRESHOLD=0.65\nPREPROCESS_ENABLED=false\n"
        "AUDIO_ENABLED=0\nLOG_LEVEL=debug\n"
    )
    settings = Settings.load(env_path=env, base_dir=tmp_path)
    assert settings.db_host == "db.example.com"
    assert settings.db_port == 3307
    assert settings.db_user == "alice"
    assert settings.db_password == "s3cret"
    assert settings.db_name == "mydb"
    assert settings.camera_index == 2
    assert settings.ocr_languages == ["en", "hi", "fr"]
    assert settings.ocr_gpu == "false"
    assert settings.ocr_every_n_frames == 5
    assert settings.confidence_threshold == 0.65
    assert settings.preprocess_enabled is False
    assert settings.audio_enabled is False
    assert settings.log_level == "DEBUG"


def test_invalid_values_fall_back_to_defaults(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text(
        "DB_PORT=not-a-number\nCAMERA_INDEX=-3\nOCR_EVERY_N_FRAMES=0\n"
        "CONFIDENCE_THRESHOLD=7\nOCR_GPU=maybe\nOCR_LANGUAGES=\n"
    )
    settings = Settings.load(env_path=env, base_dir=tmp_path)
    assert settings.db_port == 3306
    assert settings.camera_index == 0
    assert settings.ocr_every_n_frames == 10
    assert settings.confidence_threshold == 0.4
    assert settings.ocr_gpu == "auto"
    assert settings.ocr_languages == ["en"]


def test_ensure_directories_creates_output_dirs(tmp_path: Path):
    settings = Settings.load(env_path=tmp_path / "nope.env", base_dir=tmp_path)
    settings.ensure_directories()
    for directory in (
        settings.captures_dir,
        settings.exports_dir,
        settings.logs_dir,
        settings.data_dir,
    ):
        assert directory.is_dir()


def test_language_label_joins_codes(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text("OCR_LANGUAGES=en,hi\n")
    settings = Settings.load(env_path=env, base_dir=tmp_path)
    assert settings.language_label == "en+hi"
