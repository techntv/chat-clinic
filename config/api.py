from django.db import connection
from ninja import NinjaAPI

api = NinjaAPI(title="Clinic chatbot", version="0.1.0")


@api.get("/health")
def health(request) -> dict[str, str]:
    """Liveness + database check, used by Docker and uptime monitors."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return {"status": "ok"}
