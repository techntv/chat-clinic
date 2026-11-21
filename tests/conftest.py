import pytest
from django.test import Client

from clinic.models import Conversation, Tenant


@pytest.fixture
def client() -> Client:
    return Client()


@pytest.fixture
def tenant(db) -> Tenant:
    return Tenant.objects.create(
        name="Nha khoa Demo",
        fb_page_id="PAGE_1",
        fb_page_access_token="page-token",
        google_sheet_id="sheet-1",
        system_prompt_extra="Phòng khám có chỗ đậu xe ô tô miễn phí.",
    )


@pytest.fixture
def conversation(tenant: Tenant) -> Conversation:
    return Conversation.objects.create(
        tenant=tenant, channel=Conversation.Channel.MESSENGER, external_user_id="PSID_1"
    )
