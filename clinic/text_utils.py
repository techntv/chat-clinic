"""Vietnamese-aware fuzzy matching, shared by every tool that searches the Sheet."""

import re
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from rapidfuzz import fuzz

_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)
_SPACES = re.compile(r"\s+")

# Filler words in customer messages ("cho em hỏi giá ... bao nhiêu ạ"). Dropping them keeps
# the match on the words that matter. Only general Vietnamese, nothing clinic-specific.
_STOPWORDS = frozenset(
    """
    ạ à ơi nhé nha nhá hả hở nhỉ vậy thế đi
    em anh chị mình bạn shop ad admin bác
    cho hỏi xin muốn cần biết
    có không ko k hông hok được là của và với thì mà ở tại bên các những một
    giá bao nhiêu tiền nhiu bn chi phí phi
    gì nào sao làm như
    dịch vụ
    """.split()  # noqa: SIM905 - a word list reads better as text
)

DEFAULT_MIN_SCORE = 60.0
# Drop matches this far below the best one ("răng sứ" should not also return "tẩy trắng răng").
DEFAULT_MARGIN = 15.0


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


_PLAIN_STOPWORDS = frozenset(strip_accents(w) for w in _STOPWORDS)


def has_accents(text: str) -> bool:
    return strip_accents(text) != normalize_vi(text)


def _content_words(text: str, plain: bool) -> str:
    """Text without filler words; falls back to all words if nothing is left."""
    words = (strip_accents(text) if plain else normalize_vi(text)).split()
    stop = _PLAIN_STOPWORDS if plain else _STOPWORDS
    kept = [w for w in words if w not in stop]
    return " ".join(kept or words)


def similarity(query: str, candidate: str) -> float:
    """0-100 score of how well `candidate` covers `query`.

    Typed without accents ("tay trang rang"): compare accent-free forms.
    Typed with accents: compare accented forms, so "bảo hiểm" does not match "bao lâu".
    """
    plain = not has_accents(query)
    return fuzz.token_set_ratio(_content_words(query, plain), _content_words(candidate, plain))


@dataclass(frozen=True)
class Match[T]:
    item: T
    score: float


def best_matches[T](
    query: str,
    items: Iterable[T],
    key: Callable[[T], str],
    limit: int = 3,
    min_score: float = DEFAULT_MIN_SCORE,
    margin: float = DEFAULT_MARGIN,
) -> list[Match[T]]:
    """Up to `limit` items whose `key(item)` best matches `query`, best first.

    Keeps items scoring at least `min_score` and within `margin` points of the best item.
    """
    if not normalize_vi(query):
        return []
    scored = sorted(
        (Match(item, similarity(query, key(item))) for item in items),
        key=lambda m: m.score,
        reverse=True,
    )
    if not scored:
        return []
    cutoff = max(min_score, scored[0].score - margin)
    return [m for m in scored if m.score >= cutoff][:limit]
