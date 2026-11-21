import logging
from types import SimpleNamespace

import pytest

from clinic.ai.prompt_builder import PromptBuilder
from clinic.ai.reply_engine import FALLBACK_TEXT, ReplyEngine
from clinic.tools.registry import default_registry
from tests.fakes import (
    FailingKnowledgeSource,
    FakeClaude,
    anthropic_connection_error,
    claude_response,
    sample_knowledge,
    text_block,
    thinking_block,
    tool_use_block,
)

HISTORY = [SimpleNamespace(role="user", text="tay trang rang bao nhieu")]


def make_engine(claude: FakeClaude, knowledge=None, max_tool_rounds: int = 4) -> ReplyEngine:
    knowledge = knowledge or sample_knowledge()
    return ReplyEngine(
        client=claude,
        tools=default_registry(knowledge),
        prompts=PromptBuilder(knowledge),
        model="claude-haiku-5-5",
        max_tool_rounds=max_tool_rounds,
    )


@pytest.mark.django_db
def test_plain_text_answer(tenant):
    claude = FakeClaude(claude_response(text_block("Dạ em chào chị ạ")))

    result = make_engine(claude).reply(tenant, HISTORY)

    assert result.text == "Dạ em chào chị ạ"
    assert not result.is_fallback
    request = claude.requests[0]
    assert request["model"] == "claude-haiku-5-5"
    assert request["messages"] == [{"role": "user", "content": "tay trang rang bao nhieu"}]
    assert [t["name"] for t in request["tools"]] == ["search_faq", "get_price"]
    assert request["tool_choice"] == {"type": "auto"}
    assert request["output_config"] == {"effort": "low"}
    assert "temperature" not in request


@pytest.mark.django_db
def test_tool_call_then_answer(tenant):
    claude = FakeClaude(
        claude_response(
            thinking_block(), tool_use_block("get_price", {"service": "tay trang rang"})
        ),
        claude_response(text_block("Dạ tẩy trắng tại phòng khám là 2.500.000đ ạ")),
    )

    result = make_engine(claude).reply(tenant, HISTORY)

    assert result.text == "Dạ tẩy trắng tại phòng khám là 2.500.000đ ạ"
    assert [(t.name, t.input) for t in result.tool_calls] == [
        ("get_price", {"service": "tay trang rang"})
    ]
    second = claude.requests[1]["messages"]
    assert second[1]["role"] == "assistant"
    assert second[1]["content"][0].type == "thinking"  # passed back unmodified
    tool_result = second[2]["content"][0]
    assert tool_result["type"] == "tool_result"
    assert tool_result["tool_use_id"] == "tu_1"
    assert "2.500.000đ" in tool_result["content"]
    assert result.input_tokens == 200
    assert result.output_tokens == 40


@pytest.mark.django_db
def test_parallel_tool_calls_answered_in_one_message(tenant):
    claude = FakeClaude(
        claude_response(
            tool_use_block("get_price", {"service": "implant"}, "a"),
            tool_use_block("search_faq", {"query": "trả góp"}, "b"),
        ),
        claude_response(text_block("ok")),
    )

    make_engine(claude).reply(tenant, HISTORY)

    results = claude.requests[1]["messages"][2]["content"]
    assert [r["tool_use_id"] for r in results] == ["a", "b"]


@pytest.mark.django_db
def test_tool_rounds_are_capped_then_text_is_forced(tenant):
    looping = [claude_response(tool_use_block("search_faq", {"query": "x"})) for _ in range(2)]
    claude = FakeClaude(*looping, claude_response(text_block("Dạ em kiểm tra lại ạ")))

    result = make_engine(claude, max_tool_rounds=2).reply(tenant, HISTORY)

    assert result.text == "Dạ em kiểm tra lại ạ"
    assert len(claude.requests) == 3
    assert [r["tool_choice"] for r in claude.requests] == [
        {"type": "auto"},
        {"type": "auto"},
        {"type": "none"},
    ]


@pytest.mark.django_db
def test_claude_error_returns_fallback_and_logs(tenant, caplog):
    claude = FakeClaude(anthropic_connection_error())

    with caplog.at_level(logging.ERROR):
        result = make_engine(claude).reply(tenant, HISTORY)

    assert result.is_fallback
    assert result.text == FALLBACK_TEXT
    assert "fallback=True" in caplog.text


@pytest.mark.django_db
def test_sheet_error_returns_fallback(tenant):
    claude = FakeClaude()  # never called: the Info tab fails first

    result = make_engine(claude, knowledge=FailingKnowledgeSource()).reply(tenant, HISTORY)

    assert result.is_fallback
    assert claude.requests == []


@pytest.mark.django_db
def test_refusal_returns_fallback(tenant):
    claude = FakeClaude(claude_response(stop_reason="refusal"))
    assert make_engine(claude).reply(tenant, HISTORY).is_fallback


@pytest.mark.django_db
def test_empty_text_returns_fallback(tenant):
    claude = FakeClaude(claude_response(thinking_block(), stop_reason="end_turn"))
    assert make_engine(claude).reply(tenant, HISTORY).is_fallback


@pytest.mark.django_db
def test_every_call_is_logged(tenant, caplog):
    claude = FakeClaude(
        claude_response(tool_use_block("get_price", {"service": "implant"})),
        claude_response(text_block("ok")),
    )
    with caplog.at_level(logging.INFO, logger="clinic.ai.reply_engine"):
        make_engine(claude).reply(tenant, HISTORY)

    line = caplog.records[-1].getMessage()
    assert f"tenant={tenant.pk}" in line
    assert "latency_ms=" in line
    assert "input_tokens=200" in line
    assert "output_tokens=40" in line
    assert "get_price({'service': 'implant'})" in line
