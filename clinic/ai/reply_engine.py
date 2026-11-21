"""Runs the Claude tool-use loop for one customer turn. Knows nothing about Messenger."""

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import anthropic
from django.conf import settings

from clinic.ai.prompt_builder import PromptBuilder, Turn
from clinic.dto import ReplyResult, ToolResult
from clinic.models import Tenant
from clinic.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

FALLBACK_TEXT = (
    "Dạ em xin lỗi, hệ thống đang bận một chút ạ. "
    "Nhân viên phòng khám sẽ phản hồi anh/chị trong thời gian sớm nhất ạ."
)


class ClaudeClient(Protocol):
    """The part of anthropic.Anthropic we use (so tests can pass a fake)."""

    messages: Any


@dataclass
class _Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    rounds: int = 0

    def add(self, usage: Any) -> None:
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
        self.input_tokens += (usage.input_tokens or 0) + cache_read + cache_write
        self.output_tokens += usage.output_tokens or 0
        self.cache_read_tokens += cache_read
        self.rounds += 1


def estimate_cost_usd(input_tokens: int, output_tokens: int) -> float:
    """Upper-bound estimate: treats cached input tokens at the full input price."""
    return (
        input_tokens * settings.CLAUDE_INPUT_USD_PER_MTOK
        + output_tokens * settings.CLAUDE_OUTPUT_USD_PER_MTOK
    ) / 1_000_000


def default_claude_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(timeout=settings.CLAUDE_TIMEOUT_SECONDS, max_retries=2)


class ReplyEngine:
    def __init__(
        self,
        client: ClaudeClient,
        tools: ToolRegistry,
        prompts: PromptBuilder,
        model: str | None = None,
        max_tokens: int | None = None,
        effort: str | None = None,
        max_tool_rounds: int | None = None,
    ) -> None:
        self._client = client
        self._tools = tools
        self._prompts = prompts
        self._model = model or settings.CLAUDE_MODEL
        self._max_tokens = max_tokens or settings.CLAUDE_MAX_TOKENS
        self._effort = effort or settings.CLAUDE_EFFORT
        self._max_tool_rounds = (
            settings.CLAUDE_MAX_TOOL_ROUNDS if max_tool_rounds is None else max_tool_rounds
        )

    def reply(self, tenant: Tenant, history: Sequence[Turn]) -> ReplyResult:
        """Answer the last user turn in `history`. Never raises for Claude/Sheet errors."""
        started = time.monotonic()
        usage = _Usage()
        tool_calls: list[ToolResult] = []
        error: Exception | None = None
        try:
            text = self._run_loop(tenant, history, usage, tool_calls)
        except Exception as exc:  # API, Sheet, config or bug: the customer still gets a reply
            error = exc
            text = None
        result = ReplyResult(
            text=text or FALLBACK_TEXT,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            latency_ms=int((time.monotonic() - started) * 1000),
            tool_calls=tool_calls,
            is_fallback=text is None,
        )
        self._log(tenant, result, usage, error)
        return result

    def _run_loop(
        self,
        tenant: Tenant,
        history: Sequence[Turn],
        usage: _Usage,
        tool_calls: list[ToolResult],
    ) -> str | None:
        system = self._prompts.system(tenant)
        messages = self._prompts.messages(history)
        if not messages:
            return None
        for round_no in range(self._max_tool_rounds + 1):
            force_text = round_no == self._max_tool_rounds
            response = self._create(system, messages, force_text)
            usage.add(response.usage)
            tool_uses = [b for b in response.content if b.type == "tool_use"]
            if response.stop_reason != "tool_use" or not tool_uses or force_text:
                return self._final_text(response)
            # Pass the whole assistant turn back (thinking blocks included, unmodified).
            messages.append({"role": "assistant", "content": response.content})
            results = [self._run_tool(tenant, block) for block in tool_uses]
            tool_calls.extend(results)
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result.output,
                            "is_error": result.is_error,
                        }
                        for block, result in zip(tool_uses, results, strict=True)
                    ],
                }
            )
        return None  # unreachable: the last round forces a text answer

    def _create(
        self, system: list[dict[str, Any]], messages: list[dict[str, Any]], force_text: bool
    ):
        # On the last round tools stay listed (keeps the cached prefix) but cannot be called.
        return self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            messages=messages,
            tools=self._tools.definitions(),
            tool_choice={"type": "none"} if force_text else {"type": "auto"},
            output_config={"effort": self._effort},
        )

    def _run_tool(self, tenant: Tenant, block: Any) -> ToolResult:
        arguments = block.input if isinstance(block.input, dict) else {}
        return self._tools.run(tenant, block.name, arguments)

    @staticmethod
    def _final_text(response: Any) -> str | None:
        if response.stop_reason == "refusal":
            logger.warning(
                "claude refusal stop_details=%r", getattr(response, "stop_details", None)
            )
            return None
        text = "\n".join(b.text for b in response.content if b.type == "text").strip()
        return text or None

    def _log(
        self, tenant: Tenant, result: ReplyResult, usage: _Usage, error: Exception | None
    ) -> None:
        tools = ", ".join(f"{t.name}({t.input})" for t in result.tool_calls) or "-"
        line = (
            "claude reply tenant=%s model=%s latency_ms=%d rounds=%d input_tokens=%d "
            "cache_read_tokens=%d output_tokens=%d cost_usd=%.6f tools=[%s] fallback=%s"
        )
        args = (
            tenant.pk,
            self._model,
            result.latency_ms,
            usage.rounds,
            result.input_tokens,
            usage.cache_read_tokens,
            result.output_tokens,
            estimate_cost_usd(result.input_tokens, result.output_tokens),
            tools,
            result.is_fallback,
        )
        if error is not None:
            logger.error(line + " error=%r", *args, error, exc_info=error)
        else:
            logger.info(line, *args)
