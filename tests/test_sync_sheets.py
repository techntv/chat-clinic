import pytest
from django.core.management import CommandError, call_command

from clinic.models import SheetCache
from tests.fakes import FakeFetcher


@pytest.fixture
def fake_fetcher(monkeypatch) -> FakeFetcher:
    fetcher = FakeFetcher([{"key": "Hotline", "value": "0909"}])
    monkeypatch.setattr("clinic.knowledge.google_sheet.GspreadFetcher", lambda: fetcher)
    return fetcher


@pytest.mark.django_db
def test_sync_sheets_refreshes_all_tabs(tenant, fake_fetcher, capsys):
    call_command("sync_sheets", "--tenant", str(tenant.pk))

    assert [tab for _, tab in fake_fetcher.calls] == ["FAQ", "Services", "Info"]
    assert SheetCache.objects.filter(tenant=tenant).count() == 3
    assert "Info: 1 rows" in capsys.readouterr().out


@pytest.mark.django_db
def test_sync_sheets_unknown_tenant(fake_fetcher):
    with pytest.raises(CommandError, match="not found"):
        call_command("sync_sheets", "--tenant", "999")


@pytest.mark.django_db
def test_sync_sheets_reports_failures(tenant, fake_fetcher):
    fake_fetcher.error = RuntimeError("permission denied")
    with pytest.raises(CommandError, match="failed"):
        call_command("sync_sheets", "--tenant", str(tenant.pk))
