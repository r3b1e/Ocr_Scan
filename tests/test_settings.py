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


def test_prescription_extraction_defaults(tmp_path: Path):
    settings = Settings.load(env_path=tmp_path / "nope.env", base_dir=tmp_path)
    assert settings.extractor_backend == "claude"
    assert settings.claude_model == "claude-opus-5-5"
    assert settings.ollama_host == "http://127.0.0.1:11434"
    assert settings.ollama_model == "qwen2.5vl:3b"
    assert settings.extract_max_image_side == 1600
    assert settings.ocr_hint_for_printed is True
    assert settings.confidence_flag_threshold == 0.6
    assert settings.lexicon_path == tmp_path / "data" / "drug_lexicon_in.csv"
    assert settings.api_host == "127.0.0.1" and settings.api_port == 8000


def test_prescription_extraction_overrides_and_fallbacks(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text(
        "EXTRACTOR_BACKEND=ollama\nCLAUDE_MODEL=claude-haiku-5-5\nOLLAMA_HOST=http://box:11434\n"
        "OLLAMA_MODEL=qwen3-vl:2b\nEXTRACT_MAX_IMAGE_SIDE=1200\nOCR_HINT_FOR_PRINTED=false\n"
        "CONFIDENCE_FLAG_THRESHOLD=0.8\nLEXICON_PATH=/tmp/lex.csv\nAPI_HOST=0.0.0.0\nAPI_PORT=9000\n"
    )
    settings = Settings.load(env_path=env, base_dir=tmp_path)
    assert settings.extractor_backend == "ollama"
    assert settings.claude_model == "claude-haiku-5-5"
    assert settings.ollama_host == "http://box:11434"
    assert settings.ollama_model == "qwen3-vl:2b"
    assert settings.extract_max_image_side == 1200
    assert settings.ocr_hint_for_printed is False
    assert settings.confidence_flag_threshold == 0.8
    assert settings.lexicon_path == Path("/tmp/lex.csv")
    assert settings.api_host == "0.0.0.0" and settings.api_port == 9000

    env.write_text("EXTRACTOR_BACKEND=gpt\nAPI_PORT=abc\nEXTRACT_MAX_IMAGE_SIDE=10\n")
    settings = Settings.load(env_path=env, base_dir=tmp_path)
    assert settings.extractor_backend == "claude"
    assert settings.api_port == 8000
    assert settings.extract_max_image_side == 1600
