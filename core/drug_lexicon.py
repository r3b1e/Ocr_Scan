"""Indian drug lexicon: fuzzy matching of brand and generic names.

The lexicon is a CSV (`brand, composition, strengths, form, source`). Matching strips dosage
forms and strengths from the query, then compares against brand names and against each
component of a composition with RapidFuzz.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from rapidfuzz import fuzz, process

from core.prescription import Status
from core.sig_grammar import strip_form_prefix
from utils.logger import get_logger

log = get_logger("core.drug_lexicon")

OK_SCORE = 90.0
CORRECTED_SCORE = 75.0
MatchedOn = Literal["brand", "composition", "none"]

_STRENGTH_TOKEN = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|µg|ug|gm|g|ml|%|iu|units?)\b|\b\d{2,}(?:\.\d+)?\b", re.IGNORECASE
)
_SEPARATORS = re.compile(r"[-_./\\(),:;]+")
_NON_ALNUM = re.compile(r"[^a-z0-9+ ]+")


@dataclass(frozen=True)
class DrugEntry:
    """One lexicon row."""

    brand: str
    composition: str
    strengths: tuple[str, ...]
    form: str
    source: str


@dataclass(frozen=True)
class LexiconMatch:
    """Outcome of matching a name against the lexicon."""

    entry: DrugEntry | None
    score: float
    status: Status
    matched_on: MatchedOn
    canonical: str | None


NO_MATCH = LexiconMatch(
    entry=None, score=0.0, status="unverified", matched_on="none", canonical=None
)


def normalise_name(name: str | None) -> str:
    """Lower-case, drop dosage-form prefix, strengths and punctuation: "Tab. Dolo-650" -> "dolo"."""
    _, stripped = strip_form_prefix(name)
    value = _SEPARATORS.sub(" ", stripped.lower())
    value = _STRENGTH_TOKEN.sub(" ", value)
    value = _NON_ALNUM.sub(" ", value)
    return re.sub(r"\s+", " ", value).strip()


def _status_for(score: float) -> Status:
    if score >= OK_SCORE:
        return "ok"
    if score >= CORRECTED_SCORE:
        return "corrected"
    return "unverified"


class DrugLexicon:
    """In-memory lexicon with fuzzy brand and composition lookup."""

    def __init__(self, entries: Iterable[DrugEntry]) -> None:
        self._entries: list[DrugEntry] = list(entries)
        self._brand_keys: list[str] = []
        self._brand_entries: list[DrugEntry] = []
        self._component_keys: list[str] = []
        self._component_values: list[tuple[str, DrugEntry]] = []
        for entry in self._entries:
            self._brand_keys.append(normalise_name(entry.brand))
            self._brand_entries.append(entry)
            components = [entry.composition, *[c.strip() for c in entry.composition.split("+")]]
            for component in dict.fromkeys(c for c in components if c):
                key = normalise_name(component)
                if key:
                    self._component_keys.append(key)
                    self._component_values.append((component, entry))

    def __len__(self) -> int:
        """Number of lexicon rows."""
        return len(self._entries)

    @classmethod
    def load(cls, path: Path) -> DrugLexicon:
        """Read the CSV; a missing or unreadable file yields an empty lexicon (logged)."""
        entries: list[DrugEntry] = []
        try:
            with path.open(newline="", encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    brand = (row.get("brand") or "").strip()
                    composition = (row.get("composition") or "").strip()
                    if not brand or not composition:
                        continue
                    strengths = tuple(
                        s.strip() for s in (row.get("strengths") or "").split("|") if s.strip()
                    )
                    entries.append(
                        DrugEntry(
                            brand=brand,
                            composition=composition,
                            strengths=strengths,
                            form=(row.get("form") or "").strip(),
                            source=(row.get("source") or "").strip(),
                        )
                    )
        except OSError as exc:
            log.warning("Drug lexicon not loaded from %s: %s", path, exc)
        log.info("Drug lexicon: %s entries from %s", len(entries), path)
        return cls(entries)

    def match(self, name: str | None) -> LexiconMatch:
        """Match a medicine name; see `LexiconMatch.status` for how trustworthy the hit is."""
        query = normalise_name(name)
        if not query or not re.search(r"[a-z]", query) or not self._entries:
            return NO_MATCH
        brand_hit = process.extractOne(query, self._brand_keys, scorer=fuzz.WRatio)
        component_hit = process.extractOne(query, self._component_keys, scorer=fuzz.WRatio)
        brand_score = float(brand_hit[1]) if brand_hit else 0.0
        component_score = float(component_hit[1]) if component_hit else 0.0
        if brand_hit and brand_score >= component_score and brand_score >= CORRECTED_SCORE:
            entry = self._brand_entries[brand_hit[2]]
            return LexiconMatch(entry, brand_score, _status_for(brand_score), "brand", entry.brand)
        if component_hit and component_score >= CORRECTED_SCORE:
            canonical, entry = self._component_values[component_hit[2]]
            return LexiconMatch(
                entry, component_score, _status_for(component_score), "composition", canonical
            )
        best = max(brand_score, component_score)
        return LexiconMatch(None, best, "unverified", "none", None)
