"""Thin data models. Business logic lives in services, tools and adapters."""

from django.db import models


class Tenant(models.Model):
    """One clinic: one Facebook Page and one Google Sheet."""

    name = models.CharField(max_length=200)
    fb_page_id = models.CharField(max_length=64, unique=True)
    fb_page_access_token = models.TextField()
    google_sheet_id = models.CharField(max_length=200)
    system_prompt_extra = models.TextField(
        blank=True, help_text="Extra instructions for this clinic, added to the system prompt."
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name


class Conversation(models.Model):
    class Channel(models.TextChoices):
        MESSENGER = "messenger", "Messenger"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="conversations")
    channel = models.CharField(max_length=20, choices=Channel.choices)
    external_user_id = models.CharField(max_length=128, help_text="Messenger PSID")
    is_bot_paused = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "channel", "external_user_id"], name="uniq_conversation_user"
            )
        ]

    def __str__(self) -> str:
        return f"{self.channel}:{self.external_user_id}"


class Message(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="messages")
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    text = models.TextField()
    # Channel message id (Messenger "mid"). Unique, so a retried webhook is stored once.
    external_message_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    input_tokens = models.PositiveIntegerField(null=True, blank=True)
    output_tokens = models.PositiveIntegerField(null=True, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        return f"{self.role}: {self.text[:50]}"


class SheetCache(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="sheet_caches")
    tab_name = models.CharField(max_length=100)
    data = models.JSONField(default=list)
    fetched_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "tab_name"], name="uniq_sheet_cache_tab")
        ]

    def __str__(self) -> str:
        return f"{self.tenant} / {self.tab_name}"
