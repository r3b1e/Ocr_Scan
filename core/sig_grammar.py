"""Parser for Indian prescription shorthand ("sig" = signa, the dosing instruction).

Pure functions, no I/O. Everything unparseable returns `None` / `parsed=False` so the caller
can mark the field `unverified` instead of guessing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.prescription import Form, Frequency, Slot, Timing

SLOTS_3: tuple[Slot, ...] = ("morning", "afternoon", "night")
SLOTS_4: tuple[Slot, ...] = ("morning", "afternoon", "evening", "night")
_DASHES = str.maketrans({"–": "-", "—": "-", "‐": "-", "‑": "-", "½": "1/2"})
_NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "twelve": 12,
    "fifteen": 15,
    "thirty": 30,
}


@dataclass(frozen=True)
class SigParse:
    """Result of parsing a frequency string."""

    frequency: Frequency = field(default_factory=Frequency)
    timing: Timing | None = None
    dose_fraction: str | None = None
    parsed: bool = False


def _clean(text: str | None) -> str:
    if not text:
        return ""
    value = text.strip().lower().translate(_DASHES)
    value = re.sub(r"(?<=[a-z])\.", "", value)  # b.d. -> bd, t.d.s -> tds
    value = re.sub(r"\s*-\s*", "-", value)
    return re.sub(r"\s+", " ", value).strip()


# --------------------------------------------------------------------------- frequency
_PATTERN_RE = re.compile(r"(?<![\d/])((?:\d+(?:/\d+)?)(?:-(?:\d+(?:/\d+)?)){2,3})(?![\d/])")
_AS_NEEDED_RE = re.compile(
    r"\b(sos|prn|when required|if needed|as needed|as required|when needed)\b"
)
_INTERVAL_RES = (
    re.compile(r"\bq\s*(\d{1,2})\s*h\b"),
    re.compile(r"\bevery\s+(\d{1,2})\s*(?:hours|hrs|hr|h)\b"),
    re.compile(r"\b(\d{1,2})\s*(?:hourly|hrly)\b"),
)
_WEEKLY_RE = re.compile(r"\b(once weekly|weekly|once a week|every week)\b")
_KEYWORD_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("QID", re.compile(r"\b(qid|four times|4 times|4x)\b")),
    ("TDS", re.compile(r"\b(tds|tid|thrice|three times|3 times|3x)\b")),
    (
        "BD",
        re.compile(r"\b(bd|bid|twice|two times|2 times|2x|morning (?:and|&) (?:night|evening))\b"),
    ),
    ("HS", re.compile(r"\b(hs|bedtime|nocte|at night)\b")),
    (
        "OD",
        re.compile(
            r"\b(od|once daily|once a day|daily|every day|everyday|once|every morning|morning)\b"
        ),
    ),
)
_KEYWORD_SCHEDULE: dict[str, tuple[int, list[Slot]]] = {
    "OD": (1, ["morning"]),
    "BD": (2, ["morning", "night"]),
    "TDS": (3, ["morning", "afternoon", "night"]),
    "QID": (4, ["morning", "afternoon", "evening", "night"]),
    "HS": (1, ["night"]),
}


def _slot_value(token: str) -> float:
    if "/" in token:
        numerator, denominator = token.split("/", 1)
        try:
            return int(numerator) / int(denominator)
        except (ValueError, ZeroDivisionError):
            return 0.0
    try:
        return float(token)
    except ValueError:
        return 0.0


def _parse_numeric_pattern(cleaned: str) -> tuple[Frequency, str | None] | None:
    match = _PATTERN_RE.search(cleaned)
    if not match:
        return None
    tokens = match.group(1).split("-")
    slots_map = SLOTS_3 if len(tokens) == 3 else SLOTS_4
    values = [_slot_value(token) for token in tokens]
    active = [slots_map[i] for i, value in enumerate(values) if value > 0]
    if not active:
        return None
    nonzero_tokens = {token for token, value in zip(tokens, values, strict=True) if value > 0}
    dose_fraction = (
        nonzero_tokens.pop() if len(nonzero_tokens) == 1 and nonzero_tokens != {"1"} else None
    )
    frequency = Frequency(pattern="-".join(tokens), times_per_day=len(active), slots=list(active))
    return frequency, dose_fraction


def parse_frequency(text: str | None) -> SigParse:
    """Parse "1-0-1", "BD", "TDS", "q8h", "SOS", "twice daily" ... into a `Frequency`."""
    cleaned = _clean(text)
    if not cleaned:
        return SigParse()
    timing = parse_timing(text)
    as_needed = bool(_AS_NEEDED_RE.search(cleaned))

    numeric = _parse_numeric_pattern(cleaned)
    if numeric is not None:
        frequency, dose_fraction = numeric
        frequency.as_needed = as_needed
        return SigParse(
            frequency=frequency, timing=timing, dose_fraction=dose_fraction, parsed=True
        )

    for pattern in _INTERVAL_RES:
        match = pattern.search(cleaned)
        if match:
            hours = int(match.group(1))
            if 1 <= hours <= 24:
                frequency = Frequency(
                    pattern=f"q{hours}h",
                    times_per_day=max(1, 24 // hours),
                    interval_hours=hours,
                    as_needed=as_needed,
                )
                return SigParse(frequency=frequency, timing=timing, parsed=True)

    if _WEEKLY_RE.search(cleaned):
        frequency = Frequency(pattern="weekly", interval_hours=168, as_needed=as_needed)
        return SigParse(frequency=frequency, timing=timing, parsed=True)

    for code, pattern in _KEYWORD_PATTERNS:
        if pattern.search(cleaned):
            times, slots = _KEYWORD_SCHEDULE[code]
            frequency = Frequency(
                pattern=code, times_per_day=times, slots=list(slots), as_needed=as_needed
            )
            if code == "HS" and timing is None:
                timing = "bedtime"
            return SigParse(frequency=frequency, timing=timing, parsed=True)

    if as_needed:
        return SigParse(frequency=Frequency(as_needed=True), timing=timing, parsed=True)
    return SigParse(timing=timing)


# ------------------------------------------------------------------------------ timing
_TIMING_PATTERNS: tuple[tuple[Timing, re.Pattern[str]], ...] = (
    ("empty_stomach", re.compile(r"empty\s*stomach")),
    (
        "after_food",
        re.compile(
            r"\b(a/?f|after\s*(?:food|meals?|eating|lunch|dinner|breakfast)|pc|post\s*(?:meal|food))\b"
        ),
    ),
    ("before_food", re.compile(r"\b(b/?f|before\s*(?:food|meals?|eating|breakfast)|ac)\b")),
    ("with_food", re.compile(r"\bwith\s*(?:food|meals?|milk)\b")),
    ("bedtime", re.compile(r"\b(hs|bedtime|at night|nocte)\b")),
    ("any", re.compile(r"\b(any ?time)\b")),
)


def parse_timing(text: str | None) -> Timing | None:
    """Map "A/F", "before food", "HS" ... to a `Timing` value."""
    cleaned = _clean(text)
    if not cleaned:
        return None
    for timing, pattern in _TIMING_PATTERNS:
        if pattern.search(cleaned):
            return timing
    return None


# ---------------------------------------------------------------------------- duration
_NUMBER = r"(?:(?<!\d)\d+|(?<![a-z])(?:" + "|".join(_NUMBER_WORDS) + r"))"
_DURATION_RES: tuple[tuple[re.Pattern[str], int], ...] = (
    (re.compile(r"\b(\d+)\s*/\s*7\b"), 1),
    (re.compile(r"\b(\d+)\s*/\s*52\b"), 7),
    (re.compile(r"\b(\d+)\s*/\s*12\b"), 30),
    (re.compile(rf"({_NUMBER})\s*(?:days?|d)\b"), 1),
    (re.compile(rf"({_NUMBER})\s*(?:weeks?|wks?|w)\b"), 7),
    (re.compile(rf"({_NUMBER})\s*(?:months?|mo|m)\b"), 30),
)


def _to_number(token: str) -> int | None:
    if token.isdigit():
        return int(token)
    return _NUMBER_WORDS.get(token)


def parse_duration(text: str | None) -> int | None:
    """Return the course length in days for "x 5 days", "2 weeks", "1 month", "5/7" ..."""
    cleaned = _clean(text)
    if not cleaned:
        return None
    for pattern, multiplier in _DURATION_RES:
        match = pattern.search(cleaned)
        if match:
            number = _to_number(match.group(1))
            if number is None:
                continue
            days = number * multiplier
            return days if 1 <= days <= 365 else None
    return None


# -------------------------------------------------------------------------------- form
_FORM_WORDS: dict[str, Form] = {
    "tab": "tablet",
    "tabs": "tablet",
    "tablet": "tablet",
    "tablets": "tablet",
    "t": "tablet",
    "cap": "capsule",
    "caps": "capsule",
    "capsule": "capsule",
    "capsules": "capsule",
    "c": "capsule",
    "syp": "syrup",
    "syr": "syrup",
    "syrup": "syrup",
    "susp": "syrup",
    "suspension": "syrup",
    "soln": "syrup",
    "solution": "syrup",
    "liquid": "syrup",
    "inj": "injection",
    "injection": "injection",
    "iv": "injection",
    "im": "injection",
    "oint": "cream",
    "ointment": "cream",
    "cream": "cream",
    "crm": "cream",
    "gel": "cream",
    "drops": "drops",
    "drop": "drops",
    "gtt": "drops",
    "eye drops": "drops",
    "ear drops": "drops",
    "nasal drops": "drops",
    "e/d": "drops",
    "inh": "inhaler",
    "inhaler": "inhaler",
    "mdi": "inhaler",
    "rotacap": "inhaler",
    "rotacaps": "inhaler",
    "rotahaler": "inhaler",
    "dpi": "inhaler",
    "neb": "inhaler",
    "nebulizer": "inhaler",
    "pwd": "powder",
    "powder": "powder",
    "sachet": "powder",
    "sachets": "powder",
    "granules": "powder",
}
_FORM_PREFIX_RE = re.compile(
    r"^\s*(tabs?|tablet|caps?|capsule|syp|syr|syrup|susp|inj|injection|oint|ointment|cream|gel|drops|gtt|"
    r"inh|inhaler|mdi|pwd|powder|sachet|t|c)\.?\s+(\S.*)$",
    re.IGNORECASE,
)


def parse_form(text: str | None) -> Form | None:
    """Map "Tab.", "Syp", "gtt" ... to a dosage `Form`; unknown words give None."""
    cleaned = _clean(text)
    return _FORM_WORDS.get(cleaned) if cleaned else None


def strip_form_prefix(name: str | None) -> tuple[Form | None, str]:
    """Split "Tab. Dolo 650" into ("tablet", "Dolo 650"); names without a prefix are unchanged."""
    if not name:
        return None, ""
    match = _FORM_PREFIX_RE.match(name)
    if not match:
        return None, name.strip()
    return parse_form(match.group(1)), match.group(2).strip()


# ----------------------------------------------------------------------------- strength
_UNIT_ALIASES = {
    "mg": "mg",
    "mcg": "mcg",
    "µg": "mcg",
    "ug": "mcg",
    "g": "g",
    "gm": "g",
    "ml": "ml",
    "%": "%",
    "iu": "IU",
    "units": "units",
    "unit": "units",
    "u": "units",
}
_STRENGTH_RE = re.compile(
    r"^\s*(\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)?)\s*(mg|mcg|µg|ug|gm|g|ml|%|iu|units?|u)"
    r"(?:\s*/\s*(\d+(?:\.\d+)?)\s*(ml|mg|g))?\s*$",
    re.IGNORECASE,
)


def normalise_strength(text: str | None) -> str | None:
    """Return "500 mg", "100 mg/5 ml", "0.5 %" ... or None when no unit is present."""
    if not text:
        return None
    match = _STRENGTH_RE.match(text.strip())
    if not match:
        return None
    amount = re.sub(r"\s*/\s*", "/", match.group(1))
    unit = _UNIT_ALIASES[match.group(2).lower()]
    result = f"{amount} {unit}"
    if match.group(3):
        result += f"/{match.group(3)} {match.group(4).lower()}"
    return result


# --------------------------------------------------------------------------------- dose
_DOSE_RE = re.compile(
    r"^(\d+(?:\.\d+)?|\d+/\d+|half|one|two|three|four|five)"
    r"(?:\s*(tabs?|tablets?|caps?|capsules?|tsp|tbsp|ml|drops?|puffs?|sachets?|units?|iu|spoons?|scoops?))?$"
)


def validate_dose(text: str | None) -> bool:
    """True for plausible single-dose strings: "1", "1/2", "5 ml", "2 puffs", "half"."""
    cleaned = _clean(text)
    if not cleaned:
        return False
    match = _DOSE_RE.match(cleaned)
    if not match:
        return False
    amount = match.group(1)
    if amount.replace(".", "", 1).isdigit() and match.group(2) is None and float(amount) > 20:
        return False
    return True
