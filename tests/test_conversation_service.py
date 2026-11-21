import pytest

from clinic.ai.prompt_builder import PromptBuilder
from clinic.ai.reply_engine import ReplyEngine
from clinic.dto import IncomingMessage
from clinic.models import Conversation, Message
from clinic.services.conversation import ATTACHMENT_REPLY, ConversationService
from clinic.tools.registry import default_registry
from tests.fakes import FakeChannel, FakeClaude, claude_response, sample_knowledge, text_block


def incoming(
    text: str = "Xin chào", mid: str = "m_1", page: str = "PAGE_1", **kw
) -> IncomingMessage:
    return IncomingMessage(
        channel="messenger", account_id=page, sender_id="PSID_1", message_id=mid, text=text, **kw
    )


def make_service(claude: FakeClaude, channel: FakeChannel, history_size: int = 12):
    knowledge = sample_knowledge()
    engine = ReplyEngine(claude, default_registry(knowledge), PromptBuilder(knowledge))
    return ConversationService(engine, {"messenger": channel}, history_size=history_size)


@pytest.fixture
def channel() -> FakeChannel:
    return FakeChannel()


@pytest.mark.django_db
def test_reply_is_sent_and_both_messages_saved(tenant, channel):
    claude = FakeClaude(claude_response(text_block("Dạ em chào chị ạ"), output_tokens=7))

    make_service(claude, channel).handle(incoming())

    assert channel.typing == ["PSID_1"]
    assert channel.sent == [("PSID_1", "Dạ em chào chị ạ")]
    user_msg, bot_msg = Message.objects.order_by("id")
    assert (user_msg.role, user_msg.text, user_msg.external_message_id) == (
        "user",
        "Xin chào",
        "m_1",
    )
    assert (bot_msg.role, bot_msg.text, bot_msg.external_message_id) == (
        "assistant",
        "Dạ em chào chị ạ",
        "out_1",
    )
    assert bot_msg.output_tokens == 7
    assert bot_msg.input_tokens == 100
    assert bot_msg.latency_ms is not None
    assert bot_msg.tenant == tenant


@pytest.mark.django_db
def test_duplicate_mid_is_processed_once(tenant, channel):
    claude = FakeClaude(claude_response(text_block("Dạ")))
    service = make_service(claude, channel)

    service.handle(incoming(mid="m_dup"))
    service.handle(incoming(mid="m_dup"))  # Meta retried the webhook

    assert len(channel.sent) == 1
    assert len(claude.requests) == 1
    assert Message.objects.filter(role="user").count() == 1


@pytest.mark.django_db
def test_paused_conversation_stores_but_does_not_reply(conversation, channel):
    conversation.is_bot_paused = True
    conversation.save()
    claude = FakeClaude()

    make_service(claude, channel).handle(incoming("Cho em gặp nhân viên"))

    assert channel.sent == [] and channel.typing == []
    assert claude.requests == []
    assert list(conversation.messages.values_list("text", flat=True)) == ["Cho em gặp nhân viên"]


@pytest.mark.django_db
def test_unknown_page_is_ignored(tenant, channel):
    claude = FakeClaude()

    make_service(claude, channel).handle(incoming(page="SOME_OTHER_PAGE"))

    assert channel.sent == []
    assert not Conversation.objects.exists()
    assert not Message.objects.exists()


@pytest.mark.django_db
def test_inactive_tenant_is_ignored(tenant, channel):
    tenant.is_active = False
    tenant.save()

    make_service(FakeClaude(), channel).handle(incoming())

    assert channel.sent == []
    assert not Message.objects.exists()


@pytest.mark.django_db
def test_attachment_only_gets_text_only_note_without_claude(tenant, channel):
    claude = FakeClaude()

    make_service(claude, channel).handle(incoming(text="", has_attachment=True))

    assert claude.requests == []
    assert channel.sent == [("PSID_1", ATTACHMENT_REPLY)]
    assert Message.objects.filter(role="user").get().text.startswith("[Khách gửi")


@pytest.mark.django_db
def test_history_is_limited_and_includes_previous_turns(conversation, channel):
    for i in range(5):
        Message.objects.create(
            tenant=conversation.tenant, conversation=conversation, role="user", text=f"q{i}"
        )
        Message.objects.create(
            tenant=conversation.tenant, conversation=conversation, role="assistant", text=f"a{i}"
        )
    claude = FakeClaude(claude_response(text_block("ok")))

    make_service(claude, channel, history_size=4).handle(incoming("q5"))

    assert claude.requests[0]["messages"] == [
        {"role": "user", "content": "q4"},
        {"role": "assistant", "content": "a4"},
        {"role": "user", "content": "q5"},
    ]  # 4 newest: a3 (dropped: leading assistant), q4, a4, q5


@pytest.mark.django_db
def test_send_failure_is_logged_and_reply_not_saved(tenant, channel, caplog):
    channel.fail_send = True

    make_service(FakeClaude(claude_response(text_block("Dạ"))), channel).handle(incoming())

    assert "sending reply failed" in caplog.text
    assert not Message.objects.filter(role="assistant").exists()


@pytest.mark.django_db
def test_typing_failure_does_not_block_reply(tenant, channel):
    def broken_typing(conversation):
        raise RuntimeError("graph hiccup")

    channel.send_typing = broken_typing

    make_service(FakeClaude(claude_response(text_block("Dạ"))), channel).handle(incoming())

    assert channel.sent == [("PSID_1", "Dạ")]
