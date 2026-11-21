import hashlib
import hmac
import json
import logging
from collections.abc import Mapping
from typing import Any

from django.conf import settings
from django.http import HttpRequest

from clinic.channels.base import ChannelAdapter
from clinic.channels.graph_client import GraphApiClient
from clinic.dto import IncomingMessage
from clinic.models import Conversation
from clinic.text_utils import split_message

logger = logging.getLogger(__name__)

MAX_MESSAGE_CHARS = 2000
SIGNATURE_HEADER = "X-Hub-Signature-256"


def compute_signature(body: bytes, app_secret: str) -> str:
    """The X-Hub-Signature-256 value Meta sends for `body`."""
    return "sha256=" + hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()


class MessengerAdapter(ChannelAdapter):
    channel = Conversation.Channel.MESSENGER

    def __init__(
        self,
        graph: GraphApiClient | None = None,
        app_secret: str | None = None,
        verify_token: str | None = None,
    ) -> None:
        self._graph = graph or GraphApiClient()
        self._app_secret = settings.FB_APP_SECRET if app_secret is None else app_secret
        self._verify_token = settings.FB_VERIFY_TOKEN if verify_token is None else verify_token

    # --- incoming ------------------------------------------------------------------------------

    def subscription_challenge(self, params: Mapping[str, str]) -> str | None:
        """Meta's GET verification. Returns hub.challenge when the token matches, else None."""
        if not self._verify_token:
            return None
        token_ok = hmac.compare_digest(params.get("hub.verify_token", ""), self._verify_token)
        if params.get("hub.mode") == "subscribe" and token_ok:
            return params.get("hub.challenge", "")
        return None

    def verify(self, request: HttpRequest) -> bool:
        header = request.headers.get(SIGNATURE_HEADER, "")
        if not self._app_secret or not header:
            return False
        return hmac.compare_digest(header, compute_signature(request.body, self._app_secret))

    def parse_events(self, request: HttpRequest) -> list[IncomingMessage]:
        payload = json.loads(request.body)
        if payload.get("object") != "page":
            return []
        messages: list[IncomingMessage] = []
        for entry in payload.get("entry", []):
            page_id = str(entry.get("id", ""))
            for event in entry.get("messaging", []):
                message = self._parse_event(page_id, event)
                if message:
                    messages.append(message)
        return messages

    def _parse_event(self, page_id: str, event: dict[str, Any]) -> IncomingMessage | None:
        message = event.get("message")
        if not message or message.get("is_echo"):
            return None  # delivery, read, postback, reaction, or our own echo
        if message.get("sticker_id"):
            return None  # stickers and the "like" thumb
        text = str(message.get("text", "")).strip()
        has_attachment = bool(message.get("attachments"))
        if not text and not has_attachment:
            return None
        return IncomingMessage(
            channel=self.channel,
            account_id=page_id,
            sender_id=str(event.get("sender", {}).get("id", "")),
            message_id=str(message.get("mid", "")),
            text=text,
            has_attachment=has_attachment,
        )

    # --- outgoing ------------------------------------------------------------------------------

    def send_text(self, conversation: Conversation, text: str) -> list[str]:
        token = conversation.tenant.fb_page_access_token
        return [
            self._graph.send_message(token, conversation.external_user_id, part)
            for part in split_message(text, MAX_MESSAGE_CHARS)
        ]

    def send_typing(self, conversation: Conversation) -> None:
        self._graph.send_sender_action(
            conversation.tenant.fb_page_access_token, conversation.external_user_id, "typing_on"
        )
