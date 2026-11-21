"""Webhook -> ConversationService -> ReplyEngine (tool call) -> Graph API, with only the
outside world faked: Claude (FakeClaude), the Sheet (sample CSVs) and Graph API (responses)."""

import json

import pytest
import responses

from clinic import wiring
from clinic.ai.prompt_builder import PromptBuilder
from clinic.ai.reply_engine import ReplyEngine
from clinic.channels.graph_client import GraphApiClient
from clinic.channels.messenger import MessengerAdapter, compute_signature
from clinic.models import Message
from clinic.services.conversation import ConversationService
from clinic.tools.registry import default_registry
from tests.fakes import (
    FakeClaude,
    claude_response,
    messenger_text_event,
    sample_knowledge,
    text_block,
    tool_use_block,
)

GRAPH_URL = "https://graph.facebook.com/v24.0/me/messages"


@pytest.fixture
def claude(monkeypatch) -> FakeClaude:
    fake = FakeClaude(
        claude_response(tool_use_block("get_price", {"service": "tay trang rang"})),
        claude_response(
            text_block(
                "Dạ tẩy trắng răng tại phòng khám là 2.500.000đ, tại nhà là 1.200.000đ ạ. "
                "Chị muốn em đặt lịch khám không ạ?"
            ),
            input_tokens=300,
            output_tokens=40,
        ),
    )
    knowledge = sample_knowledge()
    adapter = MessengerAdapter(graph=GraphApiClient(version="v24.0"))
    engine = ReplyEngine(fake, default_registry(knowledge), PromptBuilder(knowledge))
    service = ConversationService(engine, {"messenger": adapter})
    monkeypatch.setattr(wiring, "messenger_adapter", lambda: adapter)
    monkeypatch.setattr(wiring, "conversation_service", lambda: service)
    return fake


@responses.activate
@pytest.mark.django_db
def test_incoming_message_tool_call_reply_sent(client, tenant, claude):
    responses.post(GRAPH_URL, json={"recipient_id": "PSID_1", "message_id": "m_reply"})
    body = json.dumps(messenger_text_event("tay trang rang bao nhieu vay em", mid="m_in")).encode()

    response = client.post(
        "/webhooks/messenger",
        data=body,
        content_type="application/json",
        HTTP_X_HUB_SIGNATURE_256=compute_signature(body, "app-secret"),
    )

    assert response.status_code == 200

    # Claude got the customer's text, then the get_price result from the Sheet.
    assert claude.requests[0]["messages"][0]["content"] == "tay trang rang bao nhieu vay em"
    tool_result = claude.requests[1]["messages"][2]["content"][0]["content"]
    assert "Tẩy trắng răng tại phòng khám" in tool_result
    assert "2.500.000đ" in tool_result

    # Graph API: typing indicator first, then the reply, both with the tenant's page token.
    sent = [json.loads(call.request.body) for call in responses.calls]
    assert sent[0] == {"recipient": {"id": "PSID_1"}, "sender_action": "typing_on"}
    assert sent[1]["messaging_type"] == "RESPONSE"
    assert sent[1]["recipient"] == {"id": "PSID_1"}
    assert "2.500.000đ" in sent[1]["message"]["text"]
    assert all("access_token=page-token" in call.request.url for call in responses.calls)

    # Both turns stored, tokens on the assistant message.
    user_msg, bot_msg = Message.objects.order_by("id")
    assert user_msg.external_message_id == "m_in"
    assert bot_msg.external_message_id == "m_reply"
    assert (bot_msg.input_tokens, bot_msg.output_tokens) == (400, 60)
