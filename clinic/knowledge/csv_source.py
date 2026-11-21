"""Reads tabs from local CSV files (<dir>/<Tab>.csv). Used by the eval script and tests."""

import csv
from pathlib import Path

from clinic.knowledge.base import KnowledgeSource, KnowledgeSourceError
from clinic.knowledge.google_sheet import Row, clean_rows
from clinic.models import Tenant


class CsvKnowledgeSource(KnowledgeSource):
    def __init__(self, directory: Path | str) -> None:
        self._directory = Path(directory)

    def get_tab(self, tenant: Tenant, name: str) -> list[Row]:
        path = self._directory / f"{name}.csv"
        if not path.exists():
            raise KnowledgeSourceError(f"Missing {path}")
        with path.open(encoding="utf-8", newline="") as f:
            return clean_rows(list(csv.DictReader(f)))
