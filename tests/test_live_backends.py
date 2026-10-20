"""Opt-in live checks against the real backends: `pytest -m live -s tests/test_live_backends.py`.

Each backend is skipped when it is not configured (no API key / Ollama not running).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from config.settings import Settings
from core.drug_lexicon import DrugLexicon
from core.extractors import build_extractor
from core.ocr_engine import OCREngine
from core.prescription_pipeline import run_extraction

pytestmark = pytest.mark.live

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).with_name("fixtures")
LEXICON = DrugLexicon.load(ROOT / "data" / "drug_lexicon_in.csv")


@pytest.fixture(scope="module")
def engine() -> OCREngine:
    ocr = OCREngine(["en"], gpu="false")
    ocr.warm_up()
    return ocr


@pytest.mark.parametrize("backend", ["claude", "ollama"])
@pytest.mark.parametrize("image_name", ["sample_rx.jpg", "sample_rx_handwritten.jpg"])
def test_live_extraction(backend: str, image_name: str, engine: OCREngine, tmp_path: Path):
    settings = Settings.load(env_path=ROOT / ".env", base_dir=tmp_path)
    settings.extractor_backend = backend
    settings.ensure_directories()
    extractor = build_extractor(settings)
    ready, message = extractor.health()
    if not ready:
        pytest.skip(message)

    result = run_extraction(
        (FIXTURES / image_name).read_bytes(),
        engine=engine,
        extractor=extractor,
        lexicon=LEXICON,
        settings=settings,
    )
    summary = {
        "backend": result.backend,
        "model": result.model,
        "image": image_name,
        "handwritten": result.handwritten,
        "processing_ms": result.processing_ms,
        "medications": [
            {
                "name": m.name,
                "brand": m.brand_matched,
                "composition": m.composition,
                "strength": m.strength,
                "dose": m.dose,
                "pattern": m.frequency.pattern,
                "times_per_day": m.frequency.times_per_day,
                "timing": m.timing,
                "duration_days": m.duration_days,
                "status": m.status,
                "confidence": m.confidence,
            }
            for m in result.medications
        ],
        "warnings": result.warnings,
    }
    print("\nLIVE RESULT " + json.dumps(summary, indent=2))
    assert result.medications, result.warnings
    brands = {m.brand_matched for m in result.medications}
    assert "Dolo" in brands and "Omez" in brands
    dolo = next(m for m in result.medications if m.brand_matched == "Dolo")
    assert (
        dolo.frequency.times_per_day == 2
        and dolo.timing == "after_food"
        and dolo.duration_days == 5
    )
