import json

import pytest

from clinic import wiring
from clinic.channels.messenger import compute_signature
from tests.fakes import messenger_payload, messenger_text_event

URL = "/webhooks/messenger"


@pytest.fixture
def handled(monkeypatch) -> list:
    calls: list = []
    monkeypatch.setattr(wiring, "handle_incoming", calls.append)
    return calls


def signed_post(client, payload: dict | bytes, secret: str = "app-secret"):
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    return client.post(
        URL,
        data=body,
        content_type="application/json",
        HTTP_X_HUB_SIGNATURE_256=compute_signature(body, secret),
    )


# --- GET verification ----------------------------------------------------------------------------


def test_verification_good_token_returns_challenge(client):
    response = client.get(
        URL, {"hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "8812"}
    )
    assert response.status_code == 200
    assert response.content == b"8812"
    assert response["Content-Type"].startswith("text/plain")


def test_verification_bad_token_is_forbidden(client):
    response = client.get(
        URL, {"hub.mode": "subscribe", "hub.verify_token": "nope", "hub.challenge": "8812"}
    )
    assert response.status_code == 403
    assert b"8812" not in response.content


# --- POST ----------------------------------------------------------------------------------------


def test_valid_signature_accepts_and_dispatches(client, handled):
    response = signed_post(client, messenger_text_event("Giá cạo vôi?", mid="m_1"))

    assert response.status_code == 200
    assert [m.message_id for m in handled] == ["m_1"]
    assert handled[0].text == "Giá cạo vôi?"


def test_invalid_signature_is_rejected(client, handled):
    response = signed_post(client, messenger_text_event(), secret="wrong-secret")

    assert response.status_code == 403
    assert handled == []


def test_missing_signature_is_rejected(client, handled):
    response = client.post(URL, data=messenger_text_event(), content_type="application/json")

    assert response.status_code == 403
    assert handled == []


def test_malformed_json_is_bad_request(client, handled):
    assert signed_post(client, b"not json").status_code == 400


def test_status_events_return_200_without_work(client, handled):
    payload = messenger_payload("PAGE_1", {"sender": {"id": "U"}, "read": {"watermark": 1}})
    assert signed_post(client, payload).status_code == 200
    assert handled == []
