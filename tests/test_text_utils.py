import unicodedata

import pytest

from clinic.text_utils import best_matches, normalize_vi, similarity, split_message, strip_accents


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


def test_best_matches_drops_items_far_below_the_best():
    items = ["Bọc răng sứ Titan", "Tẩy trắng răng tại nhà"]
    assert [m.item for m in best_matches("răng sứ", items, key=str)] == ["Bọc răng sứ Titan"]


def test_accented_query_does_not_match_accent_collisions():
    # "bảo" and "bao" are the same once accents are stripped.
    items = ["Phòng khám có nhận bảo hiểm không?", "Tẩy trắng răng giữ được bao lâu?"]
    matches = best_matches("bảo hiểm", items, key=str)
    assert [m.item for m in matches] == ["Phòng khám có nhận bảo hiểm không?"]


def test_filler_words_are_ignored():
    assert similarity("cho em hỏi giá cạo vôi bao nhiêu ạ", "Cạo vôi răng") == 100


def test_split_message_short_text_is_one_chunk():
    assert split_message("Dạ em chào chị ạ", 2000) == ["Dạ em chào chị ạ"]


def test_split_message_prefers_paragraphs():
    text = "a" * 10 + "\n\n" + "b" * 10
    assert split_message(text, 15) == ["a" * 10, "b" * 10]


def test_split_message_hard_cuts_without_spaces():
    assert split_message("x" * 25, 10) == ["x" * 10, "x" * 10, "x" * 5]


def test_split_message_respects_limit():
    text = " ".join(["Tẩy trắng răng."] * 400)
    chunks = split_message(text, 2000)
    assert all(len(c) <= 2000 for c in chunks)
    assert " ".join(chunks) == text
