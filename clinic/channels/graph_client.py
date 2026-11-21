"""The only code that talks to graph.facebook.com."""

import logging
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

GRAPH_HOST = "https://graph.facebook.com"


class GraphApiError(Exception):
    def __init__(self, status: int, payload: Any) -> None:
        self.status = status
        self.payload = payload
        super().__init__(f"Graph API error {status}: {payload}")


class GraphApiClient:
    def __init__(self, version: str | None = None, timeout: float | None = None) -> None:
        self._version = version or settings.GRAPH_API_VERSION
        self._timeout = timeout or settings.GRAPH_API_TIMEOUT_SECONDS

    def post(self, path: str, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{GRAPH_HOST}/{self._version}/{path.lstrip('/')}"
        response = requests.post(
            url, params={"access_token": access_token}, json=payload, timeout=self._timeout
        )
        try:
            body = response.json()
        except ValueError:
            body = response.text
        if response.status_code >= 400:
            raise GraphApiError(response.status_code, body)
        return body if isinstance(body, dict) else {}

    def send_message(self, access_token: str, recipient_id: str, text: str) -> str:
        """Send a text reply. Returns the Messenger message id."""
        body = self.post(
            "me/messages",
            access_token,
            {
                "recipient": {"id": recipient_id},
                "messaging_type": "RESPONSE",
                "message": {"text": text},
            },
        )
        return str(body.get("message_id", ""))

    def send_sender_action(self, access_token: str, recipient_id: str, action: str) -> None:
        """action: 'typing_on', 'typing_off' or 'mark_seen'."""
        self.post(
            "me/messages",
            access_token,
            {"recipient": {"id": recipient_id}, "sender_action": action},
        )
