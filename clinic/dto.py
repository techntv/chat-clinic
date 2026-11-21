"""Plain dataclasses passed between layers (channel -> service -> engine)."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class IncomingMessage:
    """One customer message, already parsed out of a channel's webhook payload."""

    channel: str  # "messenger"
    account_id: str  # the business account that received it (Facebook Page id)
    sender_id: str  # the customer (Messenger PSID)
    message_id: str  # channel message id (Messenger "mid"), used for dedupe
    text: str  # empty for attachment-only messages
    has_attachment: bool = False


@dataclass(frozen=True)
class ToolResult:
    name: str
    input: dict[str, Any]
    output: str
    is_error: bool = False


@dataclass
class ReplyResult:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    tool_calls: list[ToolResult] = field(default_factory=list)
    is_fallback: bool = False
