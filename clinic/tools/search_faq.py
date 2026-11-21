from typing import Any

from clinic.knowledge.base import Tab
from clinic.models import Tenant
from clinic.text_utils import best_matches
from clinic.tools.base import NOT_FOUND, KnowledgeTool, to_json


class SearchFaqTool(KnowledgeTool):
    name = "search_faq"
    description = (
        "Search the clinic's FAQ (policies, payment, insurance, aftercare, parking, ...). "
        "Returns up to 3 matching question/answer pairs as JSON, or 'not found'. "
        "Use it for any question about the clinic that is not a price."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The customer's question, in Vietnamese, as short keywords.",
            }
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    def run(self, tenant: Tenant, **kwargs: Any) -> str:
        query = str(kwargs["query"])
        rows = self.knowledge.get_tab(tenant, Tab.FAQ)
        matches = best_matches(query, rows, key=lambda row: row.get("question", ""), limit=3)
        if not matches:
            return NOT_FOUND
        return to_json(
            [
                {"question": m.item.get("question", ""), "answer": m.item.get("answer", "")}
                for m in matches
            ]
        )
