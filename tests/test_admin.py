import pytest
from django.contrib.auth.models import User

from clinic.models import Message


@pytest.mark.django_db
@pytest.mark.parametrize("model", ["tenant", "conversation", "message", "sheetcache"])
def test_admin_pages_load(client, conversation, model):
    Message.objects.create(
        tenant=conversation.tenant, conversation=conversation, role="user", text="Xin chào"
    )
    User.objects.create_superuser("admin", "admin@example.com", "pw")
    client.login(username="admin", password="pw")

    assert client.get(f"/admin/clinic/{model}/").status_code == 200
    assert client.get(f"/admin/clinic/{model}/add/").status_code in (200, 403)


@pytest.mark.django_db
def test_conversation_change_page_shows_messages(client, conversation):
    Message.objects.create(
        tenant=conversation.tenant, conversation=conversation, role="user", text="Giá bao nhiêu?"
    )
    User.objects.create_superuser("admin", "admin@example.com", "pw")
    client.login(username="admin", password="pw")

    response = client.get(f"/admin/clinic/conversation/{conversation.pk}/change/")
    assert response.status_code == 200
    assert "Giá bao nhiêu?" in response.content.decode()
