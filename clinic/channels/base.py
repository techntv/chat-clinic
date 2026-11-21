from abc import ABC, abstractmethod
from typing import ClassVar

from django.http import HttpRequest

from clinic.dto import IncomingMessage
from clinic.models import Conversation


class ChannelAdapter(ABC):
    """One chat channel (Messenger now, Zalo next). Knows the channel's wire format only."""

    channel: ClassVar[str]

    @abstractmethod
    def verify(self, request: HttpRequest) -> bool:
        """True if the webhook request really comes from the channel (signature check)."""

    @abstractmethod
    def parse_events(self, request: HttpRequest) -> list[IncomingMessage]:
        """Customer messages in the webhook payload. Echoes and status events are dropped."""

    @abstractmethod
    def send_text(self, conversation: Conversation, text: str) -> list[str]:
        """Send a reply (split if needed). Returns the channel message ids."""

    @abstractmethod
    def send_typing(self, conversation: Conversation) -> None:
        """Show the typing indicator."""
