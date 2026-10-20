"""Prompts shared by every backend (kept stable so Claude's prompt cache stays warm)."""

from __future__ import annotations

import json

from core.prescription import RawPrescription

SYSTEM_PROMPT = """You read Indian medical prescriptions (printed or handwritten, in English with Indian brand names) and return the medications as JSON for a medicine-reminder app.

Rules:
- Copy every value exactly as written on the page. Do not translate, expand or guess. If a value is absent or not legible, use null.
- Frequency notation: "1-0-1" lists morning-afternoon-night counts (1-0-1 = morning and night). OD = once daily, BD = twice daily, TDS or TID = three times daily, QID = four times daily, HS = at bedtime, SOS = when required, q8h = every 8 hours.
- Timing notation: A/F or AF = after food, B/F or BF = before food, AC = before meals, PC = after meals, HS = bedtime.
- Dosage forms: Tab. or T. = tablet, Cap. = capsule, Syp. or Syr. = syrup, Inj. = injection, Oint. = cream, Drops or gtt = drops, Inh. or MDI = inhaler, Pwd. or Sachet = powder. Keep the form prefix inside `name` when it is written there.
- Put the raw frequency text in frequency_text, the raw timing text in timing_text and the raw duration text in duration_text. Do not convert them to numbers.
- One entry per medicine line, in the order written. Never invent a medicine, dose, frequency or duration that is not on the page.
- confidence is your 0-1 estimate of how legible that medicine line was.
"""

_INSTRUCTION = (
    "Extract every medication from this prescription image. Return only the JSON object with the "
    "keys patient_name, patient_age, doctor_name, prescribed_on, medications and notes."
)


def build_instruction(ocr_hint: str | None, include_schema: bool) -> str:
    """User-turn text: the task, an optional OCR transcript, and optionally the JSON schema."""
    parts = [_INSTRUCTION]
    if ocr_hint:
        parts.append(
            "A separate OCR pass read the following text. It may contain mistakes; use it only to "
            "confirm spellings of names and numbers:\n" + ocr_hint
        )
    if include_schema:
        parts.append(
            "The JSON must match this schema exactly:\n"
            + json.dumps(RawPrescription.model_json_schema())
        )
    return "\n\n".join(parts)
