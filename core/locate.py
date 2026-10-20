"""Map extracted values back to OCR fragments so the UI can highlight them."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from rapidfuzz import fuzz

MIN_SCORE = 80
MIN_LENGTH = 3
LINE_OVERLAP = 0.5


@dataclass(frozen=True)
class Fragment:
    """One OCR fragment: text plus its 4-point box."""

    text: str
    bbox: list[list[int]]


def _y_range(bbox: list[list[int]]) -> tuple[int, int]:
    ys = [point[1] for point in bbox]
    return min(ys), max(ys)


def _vertical_overlap(a: Fragment, b: Fragment) -> float:
    a_min, a_max = _y_range(a.bbox)
    b_min, b_max = _y_range(b.bbox)
    inter = max(0, min(a_max, b_max) - max(a_min, b_min))
    shortest = max(1, min(a_max - a_min, b_max - b_min))
    return inter / shortest


def line_union(anchor: Fragment, fragments: Sequence[Fragment]) -> list[list[int]]:
    """Axis-aligned box covering every fragment on the same text line as `anchor`."""
    members = [f for f in fragments if _vertical_overlap(anchor, f) >= LINE_OVERLAP] or [anchor]
    xs = [p[0] for f in members for p in f.bbox]
    ys = [p[1] for f in members for p in f.bbox]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def locate(
    value: str | None,
    fragments: Sequence[Fragment],
    min_score: int = MIN_SCORE,
    min_length: int = MIN_LENGTH,
) -> tuple[list[list[int]] | None, float]:
    """Find the text line containing `value`; returns `(line_bbox, score)` or `(None, score)`."""
    if not value or len(value.strip()) < min_length or not fragments:
        return None, 0.0
    query = value.strip().lower()
    best: Fragment | None = None
    best_score = 0.0
    for fragment in fragments:
        score = float(fuzz.partial_ratio(query, fragment.text.lower()))
        if score > best_score:
            best, best_score = fragment, score
    if best is None or best_score < min_score:
        return None, best_score
    return line_union(best, fragments), best_score
