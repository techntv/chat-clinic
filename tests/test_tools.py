import json

import pytest

from clinic.knowledge.base import KnowledgeSourceError
from clinic.models import Tenant
from clinic.tools.base import NOT_FOUND
from clinic.tools.get_price import GetPriceTool, format_vnd
from clinic.tools.registry import ToolRegistry, default_registry
from clinic.tools.search_faq import SearchFaqTool
from tests.fakes import FailingKnowledgeSource, sample_knowledge

TENANT = Tenant(name="Demo")  # tools never touch the database themselves


@pytest.fixture
def faq_tool() -> SearchFaqTool:
    return SearchFaqTool(sample_knowledge())


@pytest.fixture
def price_tool() -> GetPriceTool:
    return GetPriceTool(sample_knowledge())


# --- search_faq --------------------------------------------------------------------------------


def test_search_faq_returns_top_matches(faq_tool):
    rows = json.loads(faq_tool.run(TENANT, query="có trả góp không"))
    assert rows[0]["question"] == "Có hỗ trợ trả góp không?"
    assert "0%" in rows[0]["answer"]
    assert len(rows) <= 3


def test_search_faq_without_accents(faq_tool):
    rows = json.loads(faq_tool.run(TENANT, query="tay trang rang co dau khong"))
    assert rows[0]["question"] == "Tẩy trắng răng có đau không?"


def test_search_faq_not_found(faq_tool):
    assert faq_tool.run(TENANT, query="giá vé máy bay đi Đà Nẵng") == NOT_FOUND


# --- get_price ---------------------------------------------------------------------------------


def test_get_price_without_accents(price_tool):
    rows = json.loads(price_tool.run(TENANT, service="tay trang rang"))
    services = [r["service"] for r in rows]
    assert services == ["Tẩy trắng răng tại phòng khám", "Tẩy trắng răng tại nhà"]
    assert rows[0]["price_vnd"] == "2500000"
    assert rows[0]["price_display"] == "2.500.000đ"
    assert rows[0]["duration"] == "60 phút"


def test_get_price_returns_all_columns(price_tool):
    rows = json.loads(price_tool.run(TENANT, service="Implant"))
    assert rows == [
        {
            "service": "Cấy ghép Implant",
            "price_vnd": "18000000",
            "price_display": "18.000.000đ",
            "duration": "3 - 6 tháng",
            "notes": "Giá cho 1 trụ; chưa gồm mão sứ",
        }
    ]


def test_get_price_with_filler_words(price_tool):
    rows = json.loads(price_tool.run(TENANT, service="cho em hỏi giá cạo vôi bao nhiêu ạ"))
    assert rows[0]["service"] == "Cạo vôi răng"


def test_get_price_not_found(price_tool):
    assert price_tool.run(TENANT, service="phẫu thuật thẩm mỹ mũi") == NOT_FOUND


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("300000", "300.000đ"),
        ("1500000 - 3000000", "1.500.000đ - 3.000.000đ"),
        ("0", "Miễn phí"),
        ("Liên hệ", "Liên hệ"),
    ],
)
def test_format_vnd(raw, expected):
    assert format_vnd(raw) == expected


# --- registry ----------------------------------------------------------------------------------


def test_registry_definitions_match_tools():
    registry = default_registry(sample_knowledge())
    definitions = registry.definitions()
    assert [d["name"] for d in definitions] == ["search_faq", "get_price"]
    assert all({"name", "description", "input_schema"} == set(d) for d in definitions)


def test_registry_dispatches_by_name():
    result = default_registry(sample_knowledge()).run(TENANT, "get_price", {"service": "veneer"})
    assert not result.is_error
    assert json.loads(result.output)[0]["service"] == "Dán sứ Veneer"


def test_registry_unknown_tool_is_error():
    result = ToolRegistry([]).run(TENANT, "book_appointment", {})
    assert result.is_error


def test_registry_bad_arguments_is_error():
    result = default_registry(sample_knowledge()).run(TENANT, "get_price", {"name": "x"})
    assert result.is_error
    assert "Invalid arguments" in result.output


def test_registry_lets_knowledge_errors_through():
    registry = default_registry(FailingKnowledgeSource())
    with pytest.raises(KnowledgeSourceError):
        registry.run(TENANT, "search_faq", {"query": "giờ mở cửa"})
