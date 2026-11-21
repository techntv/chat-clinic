from django import forms
from django.contrib import admin

from clinic.models import Conversation, Message, SheetCache, Tenant


class TenantForm(forms.ModelForm):
    class Meta:
        model = Tenant
        fields = "__all__"
        widgets = {"fb_page_access_token": forms.PasswordInput(render_value=True)}


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    form = TenantForm
    list_display = ["id", "name", "fb_page_id", "google_sheet_id", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "fb_page_id"]


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = ["created_at", "role", "text", "input_tokens", "output_tokens", "latency_ms"]
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None) -> bool:
        return False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["id", "tenant", "channel", "external_user_id", "is_bot_paused", "updated_at"]
    list_editable = ["is_bot_paused"]
    list_filter = ["tenant", "channel", "is_bot_paused"]
    search_fields = ["external_user_id"]
    readonly_fields = ["tenant", "channel", "external_user_id", "created_at", "updated_at"]
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "tenant",
        "conversation",
        "role",
        "short_text",
        "output_tokens",
        "created_at",
    ]
    list_filter = ["tenant", "role"]
    search_fields = ["text", "external_message_id"]
    readonly_fields = [f.name for f in Message._meta.fields]

    @admin.display(description="text")
    def short_text(self, obj: Message) -> str:
        return obj.text[:80]


@admin.register(SheetCache)
class SheetCacheAdmin(admin.ModelAdmin):
    list_display = ["tenant", "tab_name", "fetched_at", "row_count"]
    list_filter = ["tenant", "tab_name"]
    readonly_fields = ["tenant", "tab_name", "data", "fetched_at"]

    @admin.display(description="rows")
    def row_count(self, obj: SheetCache) -> int:
        return len(obj.data)
