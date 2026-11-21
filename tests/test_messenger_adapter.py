import json

import pytest
from django.test import RequestFactory

from clinic.channels.messenger import MessengerAdapter, compute_signature
from tests.fakes import messenger_payload, messenger_text_event

SECRET = "app-secret"


@pytest.fixture
def adapter() -> MessengerAdapter:
    return MessengerAdapter(graph=None, app_secret=SECRET, verify_token="verify-me")


def post(body: dict | bytes, signature: str | None = None):
    raw = body if isinstance(body, bytes) else json.dumps(body).encode()
    headers = {}
    if signature is not None:
        headers["HTTP_X_HUB_SIGNATURE_256"] = signature
    return RequestFactory().post(
        "/webhooks/messenger", data=raw, content_type="application/json", **headers
    )


# --- GET verification ----------------------------------------------------------------------------


def test_subscription_challenge_good_token(adapter):
    params = {"hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "123"}
    assert adapter.subscription_challenge(params) == "123"


@pytest.mark.parametrize(
    "params",
    [
        {"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "123"},
        {"hub.mode": "unsubscribe", "hub.verify_token": "verify-me", "hub.challenge": "123"},
        {},
    ],
)
def test_subscription_challenge_rejected(adapter, params):
    assert adapter.subscription_challenge(params) is None


def test_subscription_challenge_rejected_when_token_not_configured():
    adapter = MessengerAdapter(app_secret=SECRET, verify_token="")
    params = {"hub.mode": "subscribe", "hub.verify_token": "", "hub.challenge": "1"}
    assert adapter.subscription_challenge(params) is None


# --- signature -----------------------------------------------------------------------------------


def test_valid_signature(adapter):
    body = json.dumps(messenger_text_event()).encode()
    assert adapter.verify(post(body, compute_signature(body, SECRET)))


@pytest.mark.parametrize(
    "signature",
    [None, "", "sha256=deadbeef", compute_signature(b"other body", SECRET), "sha1=abc"],
)
def test_invalid_signature(adapter, signature):
    body = json.dumps(messenger_text_event()).encode()
    assert not adapter.verify(post(body, signature))


def test_signature_with_wrong_secret(adapter):
    body = json.dumps(messenger_text_event()).encode()
    assert not adapter.verify(post(body, compute_signature(body, "not-the-secret")))


def test_no_app_secret_rejects_everything():
    adapter = MessengerAdapter(app_secret="", verify_token="x")
    body = b"{}"
    assert not adapter.verify(post(body, compute_signature(body, "")))


# --- parsing -------------------------------------------------------------------------------------


def test_parse_text_message(adapter):
    [message] = adapter.parse_events(post(messenger_text_event("  Giá tẩy trắng?  ", mid="m_9")))
    assert message.channel == "messenger"
    assert message.account_id == "PAGE_1"
    assert message.sender_id == "PSID_1"
    assert message.message_id == "m_9"
    assert message.text == "Giá tẩy trắng?"
    assert not message.has_attachment


def test_parse_skips_echo_delivery_read_and_stickers(adapter):
    page = "PAGE_1"
    payload = messenger_payload(
        page,
        {"sender": {"id": page}, "message": {"mid": "e", "text": "hi", "is_echo": True}},
        {"sender": {"id": "U"}, "delivery": {"mids": ["x"], "watermark": 1}},
        {"sender": {"id": "U"}, "read": {"watermark": 1}},
        {"sender": {"id": "U"}, "message": {"mid": "s", "sticker_id": 369239263222822}},
        {"sender": {"id": "U"}, "postback": {"title": "Get Started", "payload": "GET_STARTED"}},
        {"sender": {"id": "U"}, "message": {"mid": "t", "text": "real"}},
    )
    messages = adapter.parse_events(post(payload))
    assert [m.message_id for m in messages] == ["t"]


def test_parse_attachment_message(adapter):
    payload = messenger_payload(
        "PAGE_1",
        {
            "sender": {"id": "U"},
            "message": {"mid": "img", "attachments": [{"type": "image", "payload": {"url": "u"}}]},
        },
    )
    [message] = adapter.parse_events(post(payload))
    assert message.has_attachment
    assert message.text == ""


def test_parse_ignores_non_page_objects(adapter):
    assert adapter.parse_events(post({"object": "instagram", "entry": []})) == []


def test_parse_multiple_entries(adapter):
    payload = {
        "object": "page",
        "entry": [
            messenger_text_event(mid="a", page_id="P1")["entry"][0],
            messenger_text_event(mid="b", page_id="P2")["entry"][0],
        ],
    }
    assert [(m.account_id, m.message_id) for m in adapter.parse_events(post(payload))] == [
        ("P1", "a"),
        ("P2", "b"),
    ]
