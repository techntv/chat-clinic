"""Webhook endpoints. They only verify, parse and hand off; the reply happens in the background."""

import logging

from django.http import HttpRequest, HttpResponse
from ninja import Router

from clinic import wiring
from clinic.services.background import run_in_background

logger = logging.getLogger(__name__)

router = Router(tags=["webhooks"])


@router.get("/messenger", include_in_schema=False)
def messenger_verify(request: HttpRequest) -> HttpResponse:
    challenge = wiring.messenger_adapter().subscription_challenge(request.GET)
    if challenge is None:
        logger.warning("messenger webhook verification failed")
        return HttpResponse("Forbidden", status=403, content_type="text/plain")
    return HttpResponse(challenge, content_type="text/plain")


@router.post("/messenger", include_in_schema=False)
def messenger_receive(request: HttpRequest) -> HttpResponse:
    adapter = wiring.messenger_adapter()
    if not adapter.verify(request):
        logger.warning("messenger webhook rejected: bad signature")
        return HttpResponse("Forbidden", status=403, content_type="text/plain")
    try:
        messages = adapter.parse_events(request)
    except (ValueError, AttributeError, TypeError):
        logger.warning("messenger webhook rejected: malformed payload")
        return HttpResponse("Bad Request", status=400, content_type="text/plain")
    for message in messages:
        run_in_background(wiring.handle_incoming, message)
    return HttpResponse("EVENT_RECEIVED", content_type="text/plain")
