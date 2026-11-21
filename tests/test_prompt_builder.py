from datetime import datetime
from types import SimpleNamespace

import pytest

from clinic.ai.prompt_builder import PromptBuilder
from tests.fakes import sample_knowledge

FIXED_NOW = datetime(2026, 11, 21, 9, 30)  # a Saturday


@pytest.fixture
def builder() -> PromptBuilder:
    return PromptBuilder(sample_knowledge(), clock=lambda: FIXED_NOW)


def turn(role: str, text: str) -> SimpleNamespace:
    return SimpleNamespace(role=role, text=text)


@pytest.mark.django_db
def test_system_prompt_has_base_info_and_extra(builder, tenant):
    stable, clock_block = builder.system(tenant)

    assert "sales assistant" in stable["text"]
    assert "- Hotline: 0909 000 000" in stable["text"]
    assert "Clinic: Nha khoa Demo" in stable["text"]
    assert "chỗ đậu xe ô tô miễn phí" in stable["text"]  # tenant.system_prompt_extra
    assert stable["cache_control"] == {"type": "ephemeral"}
    assert clock_block["text"] == "Current time at the clinic: Thứ Bảy, 21/11/2026 09:30"
    assert "cache_control" not in clock_block


@pytest.mark.django_db
def test_system_prompt_without_extra(builder, tenant):
    tenant.system_prompt_extra = ""
    assert "Extra instructions" not in builder.system(tenant)[0]["text"]


def test_messages_merge_consecutive_roles_and_start_with_user(builder):
    history = [
        turn("assistant", "Dạ em chào chị"),
        turn("user", "chị ơi"),
        turn("user", "tẩy trắng bao nhiêu"),
        turn("assistant", "Dạ 2.500.000đ ạ"),
        turn("user", "  "),
        turn("user", "ok"),
    ]
    assert builder.messages(history) == [
        {"role": "user", "content": "chị ơi\ntẩy trắng bao nhiêu"},
        {"role": "assistant", "content": "Dạ 2.500.000đ ạ"},
        {"role": "user", "content": "ok"},
    ]
