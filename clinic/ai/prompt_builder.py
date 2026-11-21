"""The one place that turns a tenant + chat history into Claude's system prompt and messages."""

from collections.abc import Callable, Sequence
from datetime import datetime
from functools import cached_property
from pathlib import Path
from typing import Any, Protocol

from django.conf import settings
from django.utils import timezone

from clinic.knowledge.base import KnowledgeSource, Tab
from clinic.models import Tenant

BASE_PROMPT_PATH = settings.BASE_DIR / "prompts" / "clinic_base.md"
_WEEKDAYS_VI = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]


class Turn(Protocol):
    """Anything with a role and text, e.g. clinic.models.Message."""

    role: str
    text: str


class PromptBuilder:
    def __init__(
        self,
        knowledge: KnowledgeSource,
        base_prompt_path: Path = BASE_PROMPT_PATH,
        clock: Callable[[], datetime] = timezone.localtime,
    ) -> None:
        self._knowledge = knowledge
        self._base_prompt_path = base_prompt_path
        self._clock = clock

    @cached_property
    def base_prompt(self) -> str:
        return self._base_prompt_path.read_text(encoding="utf-8").strip()

    def system(self, tenant: Tenant) -> list[dict[str, Any]]:
        """System blocks. The first block is stable per tenant and cached; the clock is not."""
        stable = "\n\n".join(
            part
            for part in [
                self.base_prompt,
                f"# Clinic info\nClinic: {tenant.name}\n{self._info_lines(tenant)}",
                self._extra(tenant),
            ]
            if part
        )
        return [
            {"type": "text", "text": stable, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": f"Current time at the clinic: {self._now_text()}"},
        ]

    def messages(self, history: Sequence[Turn]) -> list[dict[str, Any]]:
        """Claude messages from saved chat turns.

        Consecutive turns with the same role are merged (a customer often sends several short
        messages in a row), and the list always starts with a user turn.
        """
        merged: list[dict[str, Any]] = []
        for turn in history:
            text = turn.text.strip()
            if not text:
                continue
            if merged and merged[-1]["role"] == turn.role:
                merged[-1]["content"] += "\n" + text
            else:
                merged.append({"role": turn.role, "content": text})
        while merged and merged[0]["role"] != "user":
            merged.pop(0)
        return merged

    def _info_lines(self, tenant: Tenant) -> str:
        rows = self._knowledge.get_tab(tenant, Tab.INFO)
        lines = [f"- {row['key']}: {row.get('value', '')}" for row in rows if row.get("key")]
        return "\n".join(lines) or "(no info provided)"

    @staticmethod
    def _extra(tenant: Tenant) -> str:
        extra = tenant.system_prompt_extra.strip()
        return f"# Extra instructions from this clinic\n{extra}" if extra else ""

    def _now_text(self) -> str:
        now = self._clock()
        return f"{_WEEKDAYS_VI[now.weekday()]}, {now:%d/%m/%Y %H:%M}"
