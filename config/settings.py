"""Application settings loaded from a `.env` file with safe defaults.

Values are read from the `.env` file first and may be overridden by real
environment variables. Every value is validated; invalid values fall back to
the documented default instead of crashing the application.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

BASE_DIR: Path = Path(__file__).resolve().parents[1]
VALID_GPU_MODES: frozenset[str] = frozenset({"auto", "true", "false"})
VALID_LOG_LEVELS: frozenset[str] = frozenset({"DEBUG", "INFO", "WARNING", "ERROR"})
VALID_BACKENDS: frozenset[str] = frozenset({"claude", "ollama"})
_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def _as_int(value: str | None, default: int, minimum: int | None = None) -> int:
    """Parse an int, returning `default` for missing/invalid/out-of-range values."""
    if value is None or value.strip() == "":
        return default
    try:
        parsed = int(value.strip())
    except ValueError:
        return default
    if minimum is not None and parsed < minimum:
        return default
    return parsed


def _as_float(value: str | None, default: float, low: float, high: float) -> float:
    """Parse a float constrained to `[low, high]`, else return `default`."""
    if value is None or value.strip() == "":
        return default
    try:
        parsed = float(value.strip())
    except ValueError:
        return default
    if not low <= parsed <= high:
        return default
    return parsed


def _as_port(value: str | None, default: int) -> int:
    """Parse a TCP port in 1..65535, else return `default`."""
    port = _as_int(value, default, minimum=1)
    return port if port <= 65535 else default


def _as_bool(value: str | None, default: bool) -> bool:
    """Parse common truthy/falsy spellings, else return `default`."""
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    return default


def _as_languages(value: str | None, default: list[str]) -> list[str]:
    """Parse a comma-separated language list such as `"en, hi"`."""
    if value is None:
        return list(default)
    codes = [code.strip() for code in value.split(",") if code.strip()]
    return codes or list(default)


def _as_choice(value: str | None, default: str, choices: frozenset[str], upper: bool) -> str:
    """Return `value` normalized if it is one of `choices`, else `default`."""
    if value is None:
        return default
    normalized = value.strip().upper() if upper else value.strip().lower()
    return normalized if normalized in choices else default


@dataclass
class Settings:
    """Typed configuration for the whole application."""

    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "ocr_scanner"

    camera_index: int = 0
    camera_width: int = 1280
    camera_height: int = 720

    ocr_languages: list[str] = field(default_factory=lambda: ["en"])
    ocr_gpu: str = "auto"
    ocr_every_n_frames: int = 10
    confidence_threshold: float = 0.4
    preprocess_enabled: bool = True
    model_dir: Path | None = None

    audio_enabled: bool = True
    log_level: str = "INFO"

    extractor_backend: str = "claude"
    claude_model: str = "claude-opus-5-5"
    ollama_host: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5vl:3b"
    extract_max_image_side: int = 1600
    ocr_hint_for_printed: bool = True
    confidence_flag_threshold: float = 0.6
    lexicon_file: Path | None = None
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    base_dir: Path = BASE_DIR

    @property
    def captures_dir(self) -> Path:
        """Directory for annotated scan images."""
        return self.base_dir / "captures"

    @property
    def exports_dir(self) -> Path:
        """Directory for CSV/JSON/TXT exports."""
        return self.base_dir / "exports"

    @property
    def logs_dir(self) -> Path:
        """Directory for rotating log files."""
        return self.base_dir / "logs"

    @property
    def data_dir(self) -> Path:
        """Directory for local data such as the offline SQLite database."""
        return self.base_dir / "data"

    @property
    def offline_db_path(self) -> Path:
        """SQLite file used when MySQL is unreachable."""
        return self.data_dir / "offline_scans.sqlite3"

    @property
    def lexicon_path(self) -> Path:
        """Indian brand/composition CSV (`LEXICON_PATH`, default `data/drug_lexicon_in.csv`)."""
        return self.lexicon_file or self.data_dir / "drug_lexicon_in.csv"

    @property
    def documents_dir(self) -> Path:
        """Directory for uploaded prescription images."""
        return self.data_dir / "documents"

    @property
    def language_label(self) -> str:
        """Compact label such as `"en"` or `"en+hi"` stored with each scan."""
        return "+".join(self.ocr_languages)

    def ensure_directories(self) -> None:
        """Create every output directory the app writes to."""
        for directory in (self.captures_dir, self.exports_dir, self.logs_dir, self.data_dir):
            directory.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_mapping(
        cls, values: Mapping[str, str | None], base_dir: Path | None = None
    ) -> Settings:
        """Build settings from a flat mapping of environment-style keys."""
        defaults = cls()
        model_dir_raw = values.get("OCR_MODEL_DIR")
        lexicon_raw = values.get("LEXICON_PATH")
        return cls(
            db_host=(values.get("DB_HOST") or defaults.db_host).strip(),
            db_port=_as_int(values.get("DB_PORT"), defaults.db_port, minimum=1),
            db_user=(values.get("DB_USER") or defaults.db_user).strip(),
            db_password=values.get("DB_PASSWORD") or defaults.db_password,
            db_name=(values.get("DB_NAME") or defaults.db_name).strip(),
            camera_index=_as_int(values.get("CAMERA_INDEX"), defaults.camera_index, minimum=0),
            camera_width=_as_int(values.get("CAMERA_WIDTH"), defaults.camera_width, minimum=64),
            camera_height=_as_int(values.get("CAMERA_HEIGHT"), defaults.camera_height, minimum=64),
            ocr_languages=_as_languages(values.get("OCR_LANGUAGES"), defaults.ocr_languages),
            ocr_gpu=_as_choice(
                values.get("OCR_GPU"), defaults.ocr_gpu, VALID_GPU_MODES, upper=False
            ),
            ocr_every_n_frames=_as_int(
                values.get("OCR_EVERY_N_FRAMES"), defaults.ocr_every_n_frames, minimum=1
            ),
            confidence_threshold=_as_float(
                values.get("CONFIDENCE_THRESHOLD"), defaults.confidence_threshold, 0.0, 1.0
            ),
            preprocess_enabled=_as_bool(
                values.get("PREPROCESS_ENABLED"), defaults.preprocess_enabled
            ),
            model_dir=Path(model_dir_raw).expanduser() if model_dir_raw else None,
            audio_enabled=_as_bool(values.get("AUDIO_ENABLED"), defaults.audio_enabled),
            log_level=_as_choice(
                values.get("LOG_LEVEL"), defaults.log_level, VALID_LOG_LEVELS, upper=True
            ),
            extractor_backend=_as_choice(
                values.get("EXTRACTOR_BACKEND"),
                defaults.extractor_backend,
                VALID_BACKENDS,
                upper=False,
            ),
            claude_model=(values.get("CLAUDE_MODEL") or defaults.claude_model).strip(),
            ollama_host=(values.get("OLLAMA_HOST") or defaults.ollama_host).strip().rstrip("/"),
            ollama_model=(values.get("OLLAMA_MODEL") or defaults.ollama_model).strip(),
            extract_max_image_side=_as_int(
                values.get("EXTRACT_MAX_IMAGE_SIDE"), defaults.extract_max_image_side, minimum=256
            ),
            ocr_hint_for_printed=_as_bool(
                values.get("OCR_HINT_FOR_PRINTED"), defaults.ocr_hint_for_printed
            ),
            confidence_flag_threshold=_as_float(
                values.get("CONFIDENCE_FLAG_THRESHOLD"),
                defaults.confidence_flag_threshold,
                0.0,
                1.0,
            ),
            lexicon_file=Path(lexicon_raw).expanduser() if lexicon_raw else None,
            api_host=(values.get("API_HOST") or defaults.api_host).strip(),
            api_port=_as_port(values.get("API_PORT"), defaults.api_port),
            base_dir=base_dir or BASE_DIR,
        )

    @classmethod
    def load(cls, env_path: Path | None = None, base_dir: Path | None = None) -> Settings:
        """Load settings from `env_path` (default `<project>/.env`) plus the environment.

        A missing `.env` file is not an error: defaults are used so the app can
        start in offline mode and tell the user what to configure.
        """
        path = env_path or (base_dir or BASE_DIR) / ".env"
        file_values: dict[str, str | None] = {}
        if path.is_file():
            file_values = dict(dotenv_values(path))
        merged: dict[str, str | None] = dict(file_values)
        for key in list(cls().__dataclass_fields__):
            env_key = key.upper()
            if env_key in os.environ:
                merged[env_key] = os.environ[env_key]
        for extra_key in ("OCR_MODEL_DIR", "LEXICON_PATH"):
            if extra_key in os.environ:
                merged[extra_key] = os.environ[extra_key]
        return cls.from_mapping(merged, base_dir=base_dir)
