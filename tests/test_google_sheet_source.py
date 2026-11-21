from datetime import UTC, datetime, timedelta

import pytest

from clinic.knowledge.base import KnowledgeSourceError
from clinic.knowledge.google_sheet import GoogleSheetSource, clean_rows
from clinic.models import SheetCache, Tenant
from tests.fakes import FakeFetcher

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
ROWS = [{"Question ": "Có trả góp không?", "answer": "Có ạ"}]


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def fetcher() -> FakeFetcher:
    return FakeFetcher(ROWS)


@pytest.fixture
def source(fetcher, clock) -> GoogleSheetSource:
    return GoogleSheetSource(fetcher=fetcher, ttl=timedelta(minutes=15), clock=clock)


def test_clean_rows_normalizes_headers_values_and_drops_empty_rows():
    raw = [{" Price_VND ": 300000, "Service": " Cạo vôi "}, {"Service": "", "Price_VND": ""}]
    assert clean_rows(raw) == [{"price_vnd": "300000", "service": "Cạo vôi"}]


@pytest.mark.django_db
def test_first_read_fetches_and_caches(source, fetcher, tenant):
    rows = source.get_tab(tenant, "FAQ")

    assert rows == [{"question": "Có trả góp không?", "answer": "Có ạ"}]
    assert fetcher.calls == [("sheet-1", "FAQ")]
    assert SheetCache.objects.get(tenant=tenant, tab_name="FAQ").data == rows


@pytest.mark.django_db
def test_fresh_cache_is_served_without_fetching(source, fetcher, clock, tenant):
    source.get_tab(tenant, "FAQ")
    clock.now = NOW + timedelta(minutes=14)
    source.get_tab(tenant, "FAQ")

    assert len(fetcher.calls) == 1


@pytest.mark.django_db
def test_stale_cache_is_refetched(source, fetcher, clock, tenant):
    source.get_tab(tenant, "FAQ")
    clock.now = NOW + timedelta(minutes=16)
    fetcher.rows = [{"question": "Mới", "answer": "Mới"}]

    assert source.get_tab(tenant, "FAQ") == [{"question": "Mới", "answer": "Mới"}]
    assert len(fetcher.calls) == 2


@pytest.mark.django_db
def test_google_error_serves_stale_cache(source, fetcher, clock, tenant):
    source.get_tab(tenant, "FAQ")
    clock.now = NOW + timedelta(hours=2)
    fetcher.error = RuntimeError("quota")

    assert source.get_tab(tenant, "FAQ")[0]["answer"] == "Có ạ"


@pytest.mark.django_db
def test_google_error_without_cache_raises(source, fetcher, tenant):
    fetcher.error = RuntimeError("quota")
    with pytest.raises(KnowledgeSourceError):
        source.get_tab(tenant, "FAQ")


@pytest.mark.django_db
def test_cache_is_per_tenant(source, fetcher, tenant):
    other = Tenant.objects.create(
        name="Other", fb_page_id="PAGE_2", fb_page_access_token="t", google_sheet_id="sheet-2"
    )
    source.get_tab(tenant, "FAQ")
    source.get_tab(other, "FAQ")

    assert fetcher.calls == [("sheet-1", "FAQ"), ("sheet-2", "FAQ")]
