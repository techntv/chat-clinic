import json
from abc import ABC, abstractmethod
from typing import Any, ClassVar

from clinic.knowledge.base import KnowledgeSource
from clinic.models import Tenant

NOT_FOUND = "not found"


class Tool(ABC):
    """A function Claude can call. Add a tool = add one subclass and register it."""

    name: ClassVar[str]
    description: ClassVar[str]
    input_schema: ClassVar[dict[str, Any]]

    @abstractmethod
    def run(self, tenant: Tenant, **kwargs: Any) -> str:
        """Do the work and return text for Claude to read."""

    def definition(self) -> dict[str, Any]:
        """The entry for the Claude `tools` list."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


class KnowledgeTool(Tool, ABC):
    """A tool that reads the clinic's knowledge source."""

    def __init__(self, knowledge: KnowledgeSource) -> None:
        self.knowledge = knowledge


def to_json(data: Any) -> str:
    """Compact JSON that keeps Vietnamese readable (fewer tokens than \\u escapes)."""
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
