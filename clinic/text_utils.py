"""Vietnamese-aware fuzzy matching, shared by every tool that searches the Sheet."""

import re
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TypeVar

from rapidfuzz import fuzz

T = TypeVar("T")

_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)
_SPACES = re.compile(r"\s+")

DEFAULT_MIN_SCORE = 60.0


def normalize_vi(text: str) -> str:
    """Lowercase, NFC-normalize, drop punctuation and collapse whitespace. Keeps accents."""
    text = unicodedata.normalize("NFC", text).lower()
    text = _PUNCTUATION.sub(" ", text)
    return _SPACES.sub(" ", text).strip()


def strip_accents(text: str) -> str:
    """'Tẩy trắng răng' -> 'tay trang rang'. Also maps đ -> d."""
    decomposed = unicodedata.normalize("NFD", normalize_vi(text))
    without_marks = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return without_marks.replace("đ", "d")


def similarity(query: str, candidate: str) -> float:
    """0-100 score. Compares both the accented and the accent-free forms, keeps the best."""
    accented = fuzz.WRatio(normalize_vi(query), normalize_vi(candidate))
    plain = fuzz.WRatio(strip_accents(query), strip_accents(candidate))
    return max(accented, plain)


@dataclass(frozen=True)
class Match[T]:
    item: T
    score: float


def best_matches(
    query: str,
    items: Iterable[T],
    key: Callable[[T], str],
    limit: int = 3,
    min_score: float = DEFAULT_MIN_SCORE,
) -> list[Match[T]]:
    """Return up to `limit` items whose `key(item)` best matches `query`, best first."""
    if not normalize_vi(query):
        return []
    scored = [Match(item, similarity(query, key(item))) for item in items]
    good = [m for m in scored if m.score >= min_score]
    good.sort(key=lambda m: m.score, reverse=True)
    return good[:limit]
