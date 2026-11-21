"""Google Sheets knowledge source with a database cache (SheetCache)."""

import logging
import threading
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

import gspread
from django.conf import settings
from django.utils import timezone

from clinic.knowledge.base import KnowledgeSource, KnowledgeSourceError
from clinic.models import SheetCache, Tenant

logger = logging.getLogger(__name__)

# (sheet_id, tab_name) -> raw rows from the sheet. Injected in tests.
SheetFetcher = Callable[[str, str], list[dict[str, Any]]]
Row = dict[str, str]


class GspreadFetcher:
    """Reads a worksheet with a Google service account. Thread-safe lazy client."""

    def __init__(self, service_account_file: str | None = None) -> None:
        self._service_account_file = service_account_file or settings.GOOGLE_SERVICE_ACCOUNT_FILE
        self._client: gspread.Client | None = None
        self._lock = threading.Lock()

    def __call__(self, sheet_id: str, tab_name: str) -> list[dict[str, Any]]:
        worksheet = self._get_client().open_by_key(sheet_id).worksheet(tab_name)
        return worksheet.get_all_records(default_blank="")

    def _get_client(self) -> gspread.Client:
        with self._lock:
            if self._client is None:
                if not self._service_account_file:
                    raise KnowledgeSourceError("GOOGLE_SERVICE_ACCOUNT_FILE is not set")
                self._client = gspread.service_account(filename=self._service_account_file)
            return self._client


def clean_rows(raw_rows: list[dict[str, Any]]) -> list[Row]:
    """Lowercase/strip headers, stringify/strip values, drop fully empty rows."""
    rows: list[Row] = []
    for raw in raw_rows:
        row = {str(k).strip().lower(): str(v).strip() for k, v in raw.items() if str(k).strip()}
        if any(row.values()):
            rows.append(row)
    return rows


class GoogleSheetSource(KnowledgeSource):
    """Serves tabs from SheetCache; refetches from Google when older than the TTL.

    If Google fails and a stale copy exists, the stale copy is served (and a warning logged)
    so a short Google outage does not take the bot down.
    """

    def __init__(
        self,
        fetcher: SheetFetcher | None = None,
        ttl: timedelta | None = None,
        clock: Callable[[], datetime] = timezone.now,
    ) -> None:
        self._fetcher = fetcher or GspreadFetcher()
        self._ttl = ttl or timedelta(minutes=settings.SHEET_CACHE_MINUTES)
        self._clock = clock

    def get_tab(self, tenant: Tenant, name: str) -> list[Row]:
        cached = SheetCache.objects.filter(tenant=tenant, tab_name=name).first()
        if cached and self._clock() - cached.fetched_at < self._ttl:
            return cached.data
        try:
            return self.refresh(tenant, name)
        except Exception as exc:
            if cached:
                logger.warning(
                    "sheet refresh failed, serving stale cache tenant=%s tab=%s error=%r",
                    tenant.pk,
                    name,
                    exc,
                )
                return cached.data
            raise KnowledgeSourceError(f"Cannot load tab {name!r}: {exc}") from exc

    def refresh(self, tenant: Tenant, name: str) -> list[Row]:
        """Fetch from Google now and update the cache."""
        rows = clean_rows(self._fetcher(tenant.google_sheet_id, name))
        SheetCache.objects.update_or_create(
            tenant=tenant, tab_name=name, defaults={"data": rows, "fetched_at": self._clock()}
        )
        logger.info("sheet refreshed tenant=%s tab=%s rows=%d", tenant.pk, name, len(rows))
        return rows
