r"""Post a signed fake Messenger message to the webhook, so you can test without Meta.

    uv run python scripts/simulate_message.py "tẩy trắng răng bao nhiêu"
    uv run python scripts/simulate_message.py "giá implant" --page-id 1234567890 --psid TEST_USER
    uv run python scripts/simulate_message.py "hi" --insecure \
        --url https://localhost/webhooks/messenger

The page id must belong to a Tenant (create it in /admin). Signs with FB_APP_SECRET from .env.
The bot's reply goes to the Graph API with that tenant's page token, so with a fake token
you will see the Graph API error in the web logs; the reply is still visible in the logs.
"""

import argparse
import json
import time
import uuid

import django_setup
import requests


def build_payload(page_id: str, psid: str, text: str, mid: str) -> dict:
    now_ms = int(time.time() * 1000)
    return {
        "object": "page",
        "entry": [
            {
                "id": page_id,
                "time": now_ms,
                "messaging": [
                    {
                        "sender": {"id": psid},
                        "recipient": {"id": page_id},
                        "timestamp": now_ms,
                        "message": {"mid": mid, "text": text},
                    }
                ],
            }
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("text", help="Customer message text")
    parser.add_argument("--url", default="http://localhost:8000/webhooks/messenger")
    parser.add_argument("--page-id", help="Facebook Page id (default: first active tenant)")
    parser.add_argument("--psid", default="SIMULATED_USER", help="Fake customer id")
    parser.add_argument("--mid", help="Message id (default: random). Reuse one to test dedupe.")
    parser.add_argument("--secret", help="App secret (default: FB_APP_SECRET from settings)")
    parser.add_argument("--insecure", action="store_true", help="Skip TLS check (local Caddy)")
    args = parser.parse_args()

    django_setup.setup()
    from django.conf import settings

    from clinic.channels.messenger import SIGNATURE_HEADER, compute_signature
    from clinic.models import Tenant

    page_id = args.page_id
    if not page_id:
        tenant = Tenant.objects.filter(is_active=True).order_by("id").first()
        if tenant is None:
            parser.error("no active tenant; create one in /admin or pass --page-id")
        page_id = tenant.fb_page_id

    mid = args.mid or f"m_sim_{uuid.uuid4().hex}"
    body = json.dumps(
        build_payload(page_id, args.psid, args.text, mid), ensure_ascii=False
    ).encode()
    signature = compute_signature(body, args.secret or settings.FB_APP_SECRET)

    response = requests.post(
        args.url,
        data=body,
        headers={"Content-Type": "application/json", SIGNATURE_HEADER: signature},
        timeout=10,
        verify=not args.insecure,
    )
    print(f"POST {args.url} page={page_id} mid={mid} -> {response.status_code} {response.text}")


if __name__ == "__main__":
    main()
