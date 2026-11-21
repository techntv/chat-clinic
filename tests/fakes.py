"""Hand-written fakes shared by the tests."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2

from clinic.knowledge.base import KnowledgeSource, KnowledgeSourceError
from clinic.knowledge.csv_source import CsvKnowledgeSource
from clinic.models import Tenant

SAMPLE_SHEET_DIR = Path(__file__).resolve().parent.parent / "scripts" / "sample_sheet"


def sample_knowledge() -> CsvKnowledgeSource:
    return CsvKnowledgeSource(SAMPLE_SHEET_DIR)


class InMemoryKnowledgeSource(KnowledgeSource):
    def __init__(self, tabs: dict[str, list[dict[str, str]]]) -> None:
        self.tabs = tabs

    def get_tab(self, tenant: Tenant, name: str) -> list[dict[str, str]]:
        if name not in self.tabs:
            raise KnowledgeSourceError(f"no tab {name}")
        return self.tabs[name]


class FailingKnowledgeSource(KnowledgeSource):
    def get_tab(self, tenant: Tenant, name: str) -> list[dict[str, str]]:
        raise KnowledgeSourceError("Google is down")


class FakeFetcher:
    """Stands in for gspread: records calls, returns canned rows or raises."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = rows or []
        self.calls: list[tuple[str, str]] = []
        self.error: Exception | None = None

    def __call__(self, sheet_id: str, tab_name: str) -> list[dict[str, Any]]:
        self.calls.append((sheet_id, tab_name))
        if self.error:
            raise self.error
        return self.rows


# --- Claude ----------------------------------------------------------------------------------


def text_block(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def thinking_block() -> SimpleNamespace:
    return SimpleNamespace(type="thinking", thinking="", signature="sig")


def tool_use_block(
    name: str, tool_input: dict[str, Any], block_id: str = "tu_1"
) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id=block_id, name=name, input=tool_input)


def claude_response(
    *blocks: SimpleNamespace,
    stop_reason: str | None = None,
    input_tokens: int = 100,
    output_tokens: int = 20,
) -> SimpleNamespace:
    if stop_reason is None:
        stop_reason = "tool_use" if any(b.type == "tool_use" for b in blocks) else "end_turn"
    return SimpleNamespace(
        content=list(blocks),
        stop_reason=stop_reason,
        stop_details=None,
        usage=SimpleNamespace(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
        ),
    )


class FakeClaude:
    """Returns scripted responses in order and records each request."""

    def __init__(self, *responses: SimpleNamespace | Exception) -> None:
        self._responses = list(responses)
        self.requests: list[dict[str, Any]] = []
        self.messages = self  # so the engine can call client.messages.create(...)

    def create(self, **kwargs: Any) -> SimpleNamespace:
        kwargs["messages"] = list(kwargs["messages"])  # snapshot: the engine keeps appending
        self.requests.append(kwargs)
        if not self._responses:
            raise AssertionError("FakeClaude ran out of scripted responses")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def anthropic_connection_error() -> anthropic.APIConnectionError:
    return anthropic.APIConnectionError(
        request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    )
