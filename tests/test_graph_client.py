import json

import pytest
import responses

from clinic.channels.graph_client import GraphApiClient, GraphApiError
from clinic.channels.messenger import MessengerAdapter
from clinic.models import Conversation

URL = "https://graph.facebook.com/v24.0/me/messages"


@responses.activate
def test_send_message_payload():
    responses.post(URL, json={"recipient_id": "PSID", "message_id": "m_out"})

    message_id = GraphApiClient(version="v24.0").send_message("tok", "PSID", "Dạ em chào chị")

    assert message_id == "m_out"
    request = responses.calls[0].request
    assert "access_token=tok" in request.url
    assert json.loads(request.body) == {
        "recipient": {"id": "PSID"},
        "messaging_type": "RESPONSE",
        "message": {"text": "Dạ em chào chị"},
    }


@responses.activate
def test_sender_action_payload():
    responses.post(URL, json={"recipient_id": "PSID"})

    GraphApiClient(version="v24.0").send_sender_action("tok", "PSID", "typing_on")

    assert json.loads(responses.calls[0].request.body) == {
        "recipient": {"id": "PSID"},
        "sender_action": "typing_on",
    }


@responses.activate
def test_graph_error_raises():
    responses.post(URL, status=400, json={"error": {"message": "Invalid OAuth access token"}})

    with pytest.raises(GraphApiError) as excinfo:
        GraphApiClient(version="v24.0").send_message("bad", "PSID", "hi")
    assert excinfo.value.status == 400


@responses.activate
@pytest.mark.django_db
def test_adapter_splits_long_replies(conversation):
    responses.post(URL, json={"message_id": "m"})
    text = ("Câu dài. " * 300).strip()  # ~2700 chars

    ids = MessengerAdapter(graph=GraphApiClient(version="v24.0")).send_text(conversation, text)

    sent = [json.loads(c.request.body)["message"]["text"] for c in responses.calls]
    assert len(ids) == len(sent) == 2
    assert all(len(part) <= 2000 for part in sent)
    assert " ".join(sent) == text
    assert "access_token=page-token" in responses.calls[0].request.url


@responses.activate
@pytest.mark.django_db
def test_adapter_typing_uses_tenant_token(conversation: Conversation):
    responses.post(URL, json={})

    MessengerAdapter(graph=GraphApiClient(version="v24.0")).send_typing(conversation)

    assert "access_token=page-token" in responses.calls[0].request.url
    assert json.loads(responses.calls[0].request.body)["sender_action"] == "typing_on"
