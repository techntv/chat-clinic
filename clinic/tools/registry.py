import logging
from typing import Any

from clinic.dto import ToolResult
from clinic.knowledge.base import KnowledgeSource, KnowledgeSourceError
from clinic.models import Tenant
from clinic.tools.base import Tool
from clinic.tools.get_price import GetPriceTool
from clinic.tools.search_faq import SearchFaqTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Builds the Claude `tools` list and dispatches tool calls by name."""

    def __init__(self, tools: list[Tool]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    def definitions(self) -> list[dict[str, Any]]:
        return [tool.definition() for tool in self._tools.values()]

    def run(self, tenant: Tenant, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Run one tool call.

        Bad calls (unknown tool, wrong arguments) come back as is_error results so Claude can
        recover. KnowledgeSourceError propagates: the Sheet is down and the caller sends the
        fallback reply.
        """
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(name, arguments, f"Unknown tool: {name}", is_error=True)
        try:
            output = tool.run(tenant, **arguments)
        except KnowledgeSourceError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("bad tool call tool=%s input=%r error=%r", name, arguments, exc)
            return ToolResult(name, arguments, f"Invalid arguments: {exc}", is_error=True)
        return ToolResult(name, arguments, output)


def default_registry(knowledge: KnowledgeSource) -> ToolRegistry:
    """The tools every clinic gets. Booking and handoff tools will be added here."""
    return ToolRegistry([SearchFaqTool(knowledge), GetPriceTool(knowledge)])
