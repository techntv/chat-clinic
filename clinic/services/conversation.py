"""The message flow shared by every channel: dedupe -> pause check -> save -> reply -> send."""

import logging
from collections.abc import Iterator, Mapping
from contextlib import contextmanager

from django.conf import settings
from django.db import IntegrityError, connection, transaction

from clinic.ai.reply_engine import ReplyEngine
from clinic.channels.base import ChannelAdapter
from clinic.dto import IncomingMessage
from clinic.models import Conversation, Message, Tenant

logger = logging.getLogger(__name__)

ATTACHMENT_PLACEHOLDER = "[Khách gửi hình ảnh hoặc tệp đính kèm]"
ATTACHMENT_REPLY = (
    "Dạ hiện tại em chỉ đọc được tin nhắn chữ ạ. "
    "Anh/chị nhắn giúp em câu hỏi để em hỗ trợ nhé, hoặc nhân viên sẽ xem hình và phản hồi sau ạ."
)

# Which Tenant field identifies the business account on each channel.
_TENANT_KEY = {Conversation.Channel.MESSENGER: "fb_page_id"}


class ConversationService:
    def __init__(
        self,
        engine: ReplyEngine,
        adapters: Mapping[str, ChannelAdapter],
        history_size: int | None = None,
    ) -> None:
        self._engine = engine
        self._adapters = adapters
        self._history_size = history_size or settings.CLAUDE_HISTORY_MESSAGES

    def handle(self, incoming: IncomingMessage) -> None:
        tenant = self._find_tenant(incoming)
        if tenant is None:
            logger.info("ignored message for unknown page account_id=%s", incoming.account_id)
            return
        stored = self._store_incoming(tenant, incoming)
        if stored is None:
            logger.info("duplicate message ignored mid=%s", incoming.message_id)
            return
        conversation, _ = stored
        if conversation.is_bot_paused:
            logger.info("bot paused, not replying conversation=%s", conversation.pk)
            return
        with _conversation_lock(conversation.pk):
            self._reply(tenant, conversation, incoming)

    # --- steps ---------------------------------------------------------------------------------

    @staticmethod
    def _find_tenant(incoming: IncomingMessage) -> Tenant | None:
        key = _TENANT_KEY.get(incoming.channel)
        if key is None:
            return None
        return Tenant.objects.filter(is_active=True, **{key: incoming.account_id}).first()

    @staticmethod
    def _store_incoming(
        tenant: Tenant, incoming: IncomingMessage
    ) -> tuple[Conversation, Message] | None:
        """Save the customer's message. None if this message id was already stored."""
        conversation, _ = Conversation.objects.get_or_create(
            tenant=tenant, channel=incoming.channel, external_user_id=incoming.sender_id
        )
        text = incoming.text or (ATTACHMENT_PLACEHOLDER if incoming.has_attachment else "")
        try:
            with transaction.atomic():
                message = Message.objects.create(
                    tenant=tenant,
                    conversation=conversation,
                    role=Message.Role.USER,
                    text=text,
                    external_message_id=incoming.message_id or None,
                )
        except IntegrityError:
            return None
        conversation.save(update_fields=["updated_at"])
        return conversation, message

    def _reply(self, tenant: Tenant, conversation: Conversation, incoming: IncomingMessage) -> None:
        adapter = self._adapters[conversation.channel]
        if incoming.has_attachment and not incoming.text:
            self._send(adapter, tenant, conversation, ATTACHMENT_REPLY)
            return
        try:
            adapter.send_typing(conversation)
        except Exception as exc:
            logger.warning("typing indicator failed conversation=%s error=%r", conversation.pk, exc)
        result = self._engine.reply(tenant, self._history(conversation))
        self._send(
            adapter,
            tenant,
            conversation,
            result.text,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=result.latency_ms,
        )

    def _history(self, conversation: Conversation) -> list[Message]:
        recent = conversation.messages.order_by("-created_at", "-id")[: self._history_size]
        return list(reversed(recent))

    @staticmethod
    def _send(
        adapter: ChannelAdapter,
        tenant: Tenant,
        conversation: Conversation,
        text: str,
        **usage: int,
    ) -> None:
        try:
            message_ids = adapter.send_text(conversation, text)
        except Exception:
            logger.exception("sending reply failed conversation=%s", conversation.pk)
            return
        Message.objects.create(
            tenant=tenant,
            conversation=conversation,
            role=Message.Role.ASSISTANT,
            text=text,
            external_message_id=(message_ids[0] if message_ids and message_ids[0] else None),
            **usage,
        )


@contextmanager
def _conversation_lock(conversation_id: int) -> Iterator[None]:
    """Postgres advisory lock: one reply at a time per conversation, across all workers."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_lock(%s)", [conversation_id])
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [conversation_id])
