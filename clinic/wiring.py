"""Builds the long-lived objects once per process. Tests replace these with fakes."""

from functools import cache

from clinic.ai.prompt_builder import PromptBuilder
from clinic.ai.reply_engine import ReplyEngine, default_claude_client
from clinic.channels.messenger import MessengerAdapter
from clinic.dto import IncomingMessage
from clinic.knowledge.google_sheet import GoogleSheetSource
from clinic.services.conversation import ConversationService
from clinic.tools.registry import default_registry


@cache
def messenger_adapter() -> MessengerAdapter:
    return MessengerAdapter()


@cache
def reply_engine() -> ReplyEngine:
    knowledge = GoogleSheetSource()
    return ReplyEngine(
        client=default_claude_client(),
        tools=default_registry(knowledge),
        prompts=PromptBuilder(knowledge),
    )


@cache
def conversation_service() -> ConversationService:
    return ConversationService(
        engine=reply_engine(), adapters={MessengerAdapter.channel: messenger_adapter()}
    )


def handle_incoming(message: IncomingMessage) -> None:
    """Background entry point for every channel."""
    conversation_service().handle(message)


def reset() -> None:
    """Forget built objects (tests, or after changing settings)."""
    for factory in (messenger_adapter, reply_engine, conversation_service):
        factory.cache_clear()
