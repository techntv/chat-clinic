from django.core.management.base import BaseCommand, CommandError, CommandParser

from clinic.knowledge.base import Tab
from clinic.knowledge.google_sheet import GoogleSheetSource
from clinic.models import Tenant


class Command(BaseCommand):
    help = "Force-refresh the Google Sheet cache (FAQ, Services, Info) for one or all tenants."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--tenant", type=int, help="Tenant id. Omit to sync all active.")

    def handle(self, *args, tenant: int | None = None, **options) -> None:
        if tenant is not None:
            tenants = list(Tenant.objects.filter(pk=tenant))
            if not tenants:
                raise CommandError(f"Tenant {tenant} not found")
        else:
            tenants = list(Tenant.objects.filter(is_active=True))

        source = GoogleSheetSource()
        failed = False
        for t in tenants:
            for tab in Tab.ALL:
                try:
                    rows = source.refresh(t, tab)
                except Exception as exc:
                    failed = True
                    self.stderr.write(f"[{t.pk}] {t.name} / {tab}: FAILED {exc!r}")
                else:
                    self.stdout.write(f"[{t.pk}] {t.name} / {tab}: {len(rows)} rows")
        if failed:
            raise CommandError("Some tabs failed to sync")
