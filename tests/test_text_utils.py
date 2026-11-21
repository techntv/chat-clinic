import unicodedata

import pytest

from clinic.text_utils import best_matches, normalize_vi, similarity, strip_accents


def test_normalize_vi_lowercases_and_strips_punctuation():
    assert normalize_vi("  Tẩy TRẮNG răng??  ") == "tẩy trắng răng"


def test_normalize_vi_unifies_unicode_forms():
    assert normalize_vi(unicodedata.normalize("NFD", "Tẩy")) == "tẩy"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Tẩy trắng răng", "tay trang rang"),
        ("Đặt lịch", "dat lich"),
        ("Niềng răng mắc cài", "nieng rang mac cai"),
    ],
)
def test_strip_accents(text, expected):
    assert strip_accents(text) == expected


def test_similarity_matches_text_without_accents():
    assert similarity("tay trang rang", "Tẩy trắng răng") == 100


def test_best_matches_orders_by_score_and_limits():
    items = ["Tẩy trắng răng tại phòng khám", "Cạo vôi răng", "Tẩy trắng răng tại nhà", "Implant"]
    matches = best_matches("tay trang rang", items, key=str, limit=2)
    assert [m.item for m in matches] == ["Tẩy trắng răng tại phòng khám", "Tẩy trắng răng tại nhà"]


def test_best_matches_drops_unrelated_items():
    assert best_matches("giá vé máy bay", ["Cạo vôi răng", "Bọc răng sứ"], key=str) == []


def test_best_matches_empty_query():
    assert best_matches("  ?? ", ["Cạo vôi răng"], key=str) == []
