"""Tests for core.prescription (pydantic models shared by both vision backends)."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from core.prescription import (
    Frequency,
    Medication,
    PrescriptionExtraction,
    RawMedication,
    RawPrescription,
)


def _raw_med(**overrides) -> dict:
    data = {
        "name": "Dolo 650",
        "strength": "650 mg",
        "form": "tablet",
        "dose": "1",
        "frequency_text": "1-0-1",
        "timing_text": "A/F",
        "duration_text": "5 days",
        "instructions": None,
        "confidence": 0.9,
    }
    data.update(overrides)
    return data


def test_raw_prescription_parses_minimal_payload():
    raw = RawPrescription.model_validate(
        {
            "patient_name": None,
            "patient_age": None,
            "doctor_name": None,
            "prescribed_on": None,
            "medications": [_raw_med()],
            "notes": None,
        }
    )
    assert raw.medications[0].name == "Dolo 650"
    assert raw.medications[0].form == "tablet"


def test_raw_prescription_defaults_allow_sparse_model_output():
    raw = RawPrescription.model_validate({"medications": [{"name": "Azithral", "confidence": 0.5}]})
    med = raw.medications[0]
    assert med.strength is None and med.frequency_text is None and med.dose is None
    assert raw.patient_name is None and raw.notes is None


def test_confidence_is_clamped_to_unit_interval():
    assert RawMedication.model_validate(_raw_med(confidence=1.7)).confidence == 1.0
    assert RawMedication.model_validate(_raw_med(confidence=-0.2)).confidence == 0.0
    assert RawMedication.model_validate(_raw_med(confidence=None)).confidence == 0.0


def test_invalid_form_and_status_are_rejected():
    with pytest.raises(ValidationError):
        RawMedication.model_validate(_raw_med(form="pill"))
    with pytest.raises(ValidationError):
        Medication.model_validate({**_raw_med(), "status": "maybe", "frequency": {}})


def test_json_schema_is_generated_for_model_backends():
    schema = RawPrescription.model_json_schema()
    assert schema["type"] == "object"
    assert "medications" in schema["properties"]
    assert "RawMedication" in schema["$defs"]


def test_frequency_defaults():
    freq = Frequency()
    assert freq.pattern is None and freq.times_per_day is None
    assert freq.slots == [] and freq.interval_hours is None and freq.as_needed is False


def test_extraction_roundtrips_through_json():
    med = Medication.model_validate(
        {
            **_raw_med(),
            "brand_matched": "Dolo",
            "composition": "Paracetamol",
            "frequency": {"pattern": "1-0-1", "times_per_day": 2, "slots": ["morning", "night"]},
            "timing": "after_food",
            "duration_days": 5,
            "status": "ok",
            "bbox": [[0, 0], [10, 0], [10, 5], [0, 5]],
            "field_status": {"name": "ok", "frequency": "ok"},
        }
    )
    extraction = PrescriptionExtraction(
        document_id=1,
        patient_name="Suman",
        patient_age="32",
        doctor_name="Dr Rao",
        prescribed_on="2026-10-20",
        medications=[med],
        notes=None,
        warnings=[],
        backend="claude",
        model="claude-opus-5-5",
        handwritten=False,
        processing_ms=1234,
    )
    data = json.loads(extraction.model_dump_json())
    assert data["medications"][0]["frequency"]["slots"] == ["morning", "night"]
    assert PrescriptionExtraction.model_validate(data) == extraction
