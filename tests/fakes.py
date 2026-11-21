"""Hand-written fakes shared by the tests."""

from pathlib import Path
from typing import Any

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
