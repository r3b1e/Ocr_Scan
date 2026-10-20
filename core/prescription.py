"""Pydantic models for prescription extraction.

`RawPrescription` is the structure the vision model fills in. `PrescriptionExtraction` is the
validated, enriched response returned by the API and shown in the desktop app.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Form = Literal[
    "tablet", "capsule", "syrup", "injection", "drops", "cream", "inhaler", "powder", "other"
]
Timing = Literal["before_food", "after_food", "with_food", "bedtime", "empty_stomach", "any"]
Slot = Literal["morning", "afternoon", "evening", "night"]
Status = Literal["ok", "corrected", "unverified"]


def _clamp_confidence(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return min(1.0, max(0.0, number))


class RawMedication(BaseModel):
    """One medication line as the vision model reads it (text copied verbatim)."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(description="Brand or generic name exactly as written")
    strength: str | None = Field(default=None, description='e.g. "500 mg", "5 ml"')
    form: Form | None = None
    dose: str | None = Field(default=None, description='e.g. "1", "1/2", "5 ml"')
    frequency_text: str | None = Field(
        default=None, description='e.g. "1-0-1", "BD", "twice daily"'
    )
    timing_text: str | None = Field(default=None, description='e.g. "after food", "A/F", "HS"')
    duration_text: str | None = Field(default=None, description='e.g. "5 days", "x 1 week"')
    instructions: str | None = None
    confidence: float = Field(default=0.0, description="0-1 estimate of how legible this line was")

    @field_validator("confidence", mode="before")
    @classmethod
    def _confidence_in_range(cls, value: Any) -> float:
        return _clamp_confidence(value)


class RawPrescription(BaseModel):
    """Whole prescription as returned by a vision backend."""

    model_config = ConfigDict(extra="ignore")

    patient_name: str | None = None
    patient_age: str | None = None
    doctor_name: str | None = None
    prescribed_on: str | None = Field(default=None, description="ISO date if readable, else null")
    medications: list[RawMedication] = Field(default_factory=list)
    notes: str | None = Field(default=None, description="Diagnosis or advice lines, verbatim")


class Frequency(BaseModel):
    """Normalised dosing schedule."""

    pattern: str | None = None
    times_per_day: int | None = None
    slots: list[Slot] = Field(default_factory=list)
    interval_hours: int | None = None
    as_needed: bool = False


class Medication(RawMedication):
    """A medication after lexicon matching, grammar parsing and image localisation."""

    brand_matched: str | None = None
    composition: str | None = None
    frequency: Frequency = Field(default_factory=Frequency)
    timing: Timing | None = None
    duration_days: int | None = None
    status: Status = "unverified"
    bbox: list[list[int]] | None = None
    field_status: dict[str, Status] = Field(default_factory=dict)


class PrescriptionExtraction(BaseModel):
    """API response: the validated prescription plus provenance."""

    document_id: int | None = None
    patient_name: str | None = None
    patient_age: str | None = None
    doctor_name: str | None = None
    prescribed_on: str | None = None
    medications: list[Medication] = Field(default_factory=list)
    notes: str | None = None
    warnings: list[str] = Field(default_factory=list)
    backend: str
    model: str
    handwritten: bool = False
    processing_ms: int = 0
