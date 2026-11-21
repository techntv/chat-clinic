import re
from typing import Any

from clinic.knowledge.base import Tab
from clinic.models import Tenant
from clinic.text_utils import best_matches
from clinic.tools.base import NOT_FOUND, KnowledgeTool, to_json

_NUMBER = re.compile(r"\d{4,}")


def format_vnd(price: str) -> str:
    """'2500000' -> '2.500.000đ'; '1500000 - 3000000' -> '1.500.000đ - 3.000.000đ'.

    Text that is not a plain number ("Liên hệ") is returned unchanged.
    """
    if price.strip() == "0":
        return "Miễn phí"
    if not _NUMBER.search(price):
        return price
    return _NUMBER.sub(lambda m: f"{int(m.group()):,}".replace(",", ".") + "đ", price)


class GetPriceTool(KnowledgeTool):
    name = "get_price"
    description = (
        "Look up a service in the clinic's price list. Returns the best matching services "
        "with price, duration and notes as JSON, or 'not found'. "
        "This is the ONLY source of prices: call it before mentioning any price."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "service": {
                "type": "string",
                "description": "Service name in Vietnamese, e.g. 'tẩy trắng răng'.",
            }
        },
        "required": ["service"],
        "additionalProperties": False,
    }

    def run(self, tenant: Tenant, **kwargs: Any) -> str:
        service = str(kwargs["service"])
        rows = self.knowledge.get_tab(tenant, Tab.SERVICES)
        matches = best_matches(service, rows, key=lambda row: row.get("service", ""), limit=5)
        if not matches:
            return NOT_FOUND
        return to_json([self._row_view(m.item) for m in matches])

    @staticmethod
    def _row_view(row: dict[str, str]) -> dict[str, str]:
        price = row.get("price_vnd", "")
        return {
            "service": row.get("service", ""),
            "price_vnd": price,
            "price_display": format_vnd(price) if price else "",
            "duration": row.get("duration", ""),
            "notes": row.get("notes", ""),
        }
