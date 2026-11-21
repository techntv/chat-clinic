import pytest
from django.test import Client

from clinic import wiring
from clinic.models import Conversation, Tenant


@pytest.fixture(autouse=True)
def _hermetic_settings(settings) -> None:
    """Tests must not depend on the developer's shell or .env."""
    settings.CLAUDE_MODEL = "claude-haiku-5-5"
    settings.CLAUDE_EFFORT = "low"
    settings.CLAUDE_MAX_TOKENS = 2048
    settings.CLAUDE_MAX_TOOL_ROUNDS = 4
    settings.CLAUDE_HISTORY_MESSAGES = 12
    settings.FB_VERIFY_TOKEN = "verify-me"
    settings.FB_APP_SECRET = "app-secret"
    settings.GRAPH_API_VERSION = "v24.0"
    settings.BACKGROUND_SYNC = True
    wiring.reset()


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
