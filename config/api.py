from django.db import connection
from ninja import NinjaAPI

from clinic.channels.webhooks import router as webhooks_router

api = NinjaAPI(title="Clinic chatbot", version="0.1.0")
api.add_router("/webhooks", webhooks_router)


@api.get("/health")
def health(request) -> dict[str, str]:
    """Liveness + database check, used by Docker and uptime monitors."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return {"status": "ok"}
