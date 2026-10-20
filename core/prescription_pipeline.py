"""Image -> OCR pass -> vision backend -> validation -> `PrescriptionExtraction`."""

from __future__ import annotations

import json
import re
import statistics
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from time import perf_counter
from typing import Any

import numpy as np

from config.settings import Settings
from core.drug_lexicon import DrugLexicon
from core.imaging import encode_jpeg, load_image, prepare_for_ocr
from core.locate import Fragment, locate
from core.prescription import Medication, PrescriptionExtraction, RawMedication, Status
from core.sig_grammar import (
    normalise_strength,
    parse_duration,
    parse_frequency,
    parse_timing,
    strip_form_prefix,
    validate_dose,
)
from database.prescription_repository import DocumentRecord
from utils.helpers import ensure_dir
from utils.logger import get_logger

log = get_logger("core.prescription_pipeline")

HANDWRITTEN_CONFIDENCE = 0.45
MIN_PRINTED_FRAGMENTS = 4
NO_MEDICATIONS_WARNING = "No medications found on this image"
_WEIGHTS = {"model": 0.4, "lexicon": 0.3, "sig": 0.2, "locate": 0.1}


@dataclass
class OCRPass:
    """What EasyOCR found before the vision model runs."""

    fragments: list[Fragment] = field(default_factory=list)
    mean_confidence: float = 0.0
    handwritten: bool = True
    hint: str | None = None


def _reading_order(results: Sequence[Any]) -> list[list[Any]]:
    """Group OCR results into lines (by vertical position) and sort each line left to right."""
    if not results:
        return []
    heights = [max(p[1] for p in r.bbox) - min(p[1] for p in r.bbox) for r in results]
    bucket = max(1.0, statistics.median(heights) * 0.8)
    keyed = sorted(
        results,
        key=lambda r: (
            round(sum(p[1] for p in r.bbox) / len(r.bbox) / bucket),
            min(p[0] for p in r.bbox),
        ),
    )
    lines: list[list[Any]] = []
    last_bucket: int | None = None
    for result in keyed:
        current = round(sum(p[1] for p in result.bbox) / len(result.bbox) / bucket)
        if last_bucket is None or current != last_bucket:
            lines.append([])
            last_bucket = current
        lines[-1].append(result)
    return lines


def run_ocr_pass(
    frame: np.ndarray,
    engine: Any,
    *,
    min_conf: float = HANDWRITTEN_CONFIDENCE,
    min_fragments: int = MIN_PRINTED_FRAGMENTS,
    hint_for_printed: bool = True,
) -> OCRPass:
    """Run EasyOCR once; decide printed vs handwritten; build the optional text hint."""
    try:
        results = list(engine.detect(frame, min_confidence=0.0))
    except Exception:
        log.exception("OCR pass failed; continuing without fragments")
        results = []
    lines = _reading_order(results)
    fragments = [
        Fragment(r.text, [[int(x), int(y)] for x, y in r.bbox]) for line in lines for r in line
    ]
    mean_confidence = float(sum(r.confidence for r in results) / len(results)) if results else 0.0
    handwritten = len(results) < min_fragments or mean_confidence < min_conf
    hint = None
    if not handwritten and hint_for_printed:
        hint = "\n".join(" ".join(r.text for r in line) for line in lines)
    return OCRPass(
        fragments=fragments, mean_confidence=mean_confidence, handwritten=handwritten, hint=hint
    )


def _infer_strength(clean_name: str, strengths: Sequence[str]) -> str | None:
    number = re.search(r"(?<![\d.])(\d+(?:\.\d+)?)(?![\d.])", clean_name)
    if not number:
        return None
    candidates = [s for s in strengths if s.split(" ")[0] == number.group(1)]
    return candidates[0] if len(candidates) == 1 else None


def validate_medication(
    raw: RawMedication, lexicon: DrugLexicon, fragments: Sequence[Fragment]
) -> tuple[Medication, list[str]]:
    """Apply lexicon, sig grammar, range checks and localisation to one raw medication."""
    warnings: list[str] = []
    field_status: dict[str, Status] = {}

    prefix_form, clean_name = strip_form_prefix(raw.name)
    name = clean_name or raw.name.strip()
    form = raw.form or prefix_form
    match = lexicon.match(raw.name)
    brand_matched: str | None = None
    composition: str | None = None
    if match.matched_on == "brand" and match.entry is not None:
        brand_matched, composition = match.entry.brand, match.entry.composition
        if match.status == "corrected":
            trailing = re.search(r"\d.*$", clean_name)
            corrected = (
                f"{match.entry.brand} {trailing.group(0)}".strip()
                if trailing
                else match.entry.brand
            )
            warnings.append(
                f"Medicine name '{raw.name}' read as '{corrected}' "
                f"(lexicon match {match.score:.0f}%)"
            )
            name = corrected
    elif match.matched_on == "composition":
        composition = match.canonical
        if match.status == "corrected":
            warnings.append(
                f"Medicine '{raw.name}' interpreted as generic '{match.canonical}' "
                f"(match {match.score:.0f}%); please confirm"
            )
    else:
        warnings.append(
            f"Medicine '{raw.name}' was not found in the drug list; please confirm the name"
        )
    field_status["name"] = match.status

    strength = normalise_strength(raw.strength) if raw.strength else None
    if raw.strength and strength is None:
        field_status["strength"] = "unverified"
        warnings.append(f"Strength '{raw.strength}' for {name} is not a recognised amount")
    elif strength:
        field_status["strength"] = "ok"
    elif match.entry is not None:
        strength = _infer_strength(clean_name, match.entry.strengths)
        if strength:
            field_status["strength"] = "ok"

    sig = parse_frequency(raw.frequency_text)
    if raw.frequency_text and raw.frequency_text.strip():
        field_status["frequency"] = "ok" if sig.parsed else "unverified"
        if not sig.parsed:
            warnings.append(f"Could not understand frequency '{raw.frequency_text}' for {name}")

    explicit_timing = parse_timing(raw.timing_text)
    timing = explicit_timing or sig.timing
    if raw.timing_text and raw.timing_text.strip():
        field_status["timing"] = "ok" if explicit_timing else "unverified"
        if not explicit_timing:
            warnings.append(f"Could not understand timing '{raw.timing_text}' for {name}")

    dose = raw.dose or sig.dose_fraction
    if dose and not validate_dose(dose):
        field_status["dose"] = "unverified"
        warnings.append(f"Dose '{dose}' for {name} looks implausible")

    duration_days = parse_duration(raw.duration_text)
    if raw.duration_text and raw.duration_text.strip():
        field_status["duration"] = "ok" if duration_days else "unverified"
        if not duration_days:
            warnings.append(f"Could not understand duration '{raw.duration_text}' for {name}")

    bbox, locate_score = locate(name, fragments)

    sig_component = 1.0 if sig.parsed else (0.0 if (raw.frequency_text or "").strip() else 0.5)
    confidence = (
        _WEIGHTS["model"] * raw.confidence
        + _WEIGHTS["lexicon"] * (match.score / 100.0 if match.matched_on != "none" else 0.0)
        + _WEIGHTS["sig"] * sig_component
        + _WEIGHTS["locate"] * (locate_score / 100.0 if bbox is not None else 0.0)
    )

    if any(value == "unverified" for value in field_status.values()):
        status: Status = "unverified"
    elif any(value == "corrected" for value in field_status.values()):
        status = "corrected"
    else:
        status = "ok"

    medication = Medication(
        name=name,
        strength=strength,
        form=form,
        dose=dose,
        frequency_text=raw.frequency_text,
        timing_text=raw.timing_text,
        duration_text=raw.duration_text,
        instructions=raw.instructions,
        confidence=round(confidence, 4),
        brand_matched=brand_matched,
        composition=composition,
        frequency=sig.frequency,
        timing=timing,
        duration_days=duration_days,
        status=status,
        bbox=bbox,
        field_status=field_status,
    )
    return medication, warnings


def run_extraction(
    image_bytes: bytes,
    *,
    engine: Any,
    extractor: Any,
    lexicon: DrugLexicon,
    settings: Settings,
    repo: Any | None = None,
    source: str = "api",
) -> PrescriptionExtraction:
    """Full pipeline; raises `ImageError` for bad input, `ExtractorError` for backend failures."""
    started = perf_counter()
    frame = load_image(image_bytes, settings.extract_max_image_side)
    prepared = prepare_for_ocr(frame)
    ocr = run_ocr_pass(prepared, engine, hint_for_printed=settings.ocr_hint_for_printed)
    jpeg = encode_jpeg(prepared)
    raw = extractor.extract(jpeg, ocr.hint)

    medications: list[Medication] = []
    warnings: list[str] = []
    for raw_medication in raw.medications:
        medication, medication_warnings = validate_medication(
            raw_medication, lexicon, ocr.fragments
        )
        medications.append(medication)
        warnings.extend(medication_warnings)
    if not medications:
        warnings.append(NO_MEDICATIONS_WARNING)

    processing_ms = int((perf_counter() - started) * 1000)
    result = PrescriptionExtraction(
        patient_name=raw.patient_name,
        patient_age=raw.patient_age,
        doctor_name=raw.doctor_name,
        prescribed_on=raw.prescribed_on,
        medications=medications,
        notes=raw.notes,
        warnings=warnings,
        backend=extractor.name,
        model=extractor.model,
        handwritten=ocr.handwritten,
        processing_ms=processing_ms,
    )
    if repo is not None:
        usage = getattr(extractor, "last_usage", None)
        document_id = repo.create_document(
            DocumentRecord(
                id=None,
                created_at=datetime.now(),
                source=source,
                image_path="",
                backend=extractor.name,
                model=extractor.model,
                handwritten=ocr.handwritten,
                processing_ms=processing_ms,
                usage_json=json.dumps(usage) if usage else None,
            )
        )
        image_path = ensure_dir(settings.documents_dir) / f"{document_id}.jpg"
        image_path.write_bytes(jpeg)
        repo.set_image_path(document_id, str(image_path))
        result.document_id = document_id
        repo.save_extraction(document_id, raw.model_dump_json(), result.model_dump_json())
    log.info(
        "Extraction via %s/%s: %s medication(s), handwritten=%s, %s ms",
        extractor.name,
        extractor.model,
        len(medications),
        ocr.handwritten,
        processing_ms,
    )
    return result
