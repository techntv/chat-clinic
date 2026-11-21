# Clinic chatbot (Messenger + Claude)

A multi-tenant AI sales assistant for clinics in Vietnam. Customers message the clinic's
Facebook Page; the bot answers in Vietnamese using the clinic's own Google Sheet (FAQ, prices,
info), never invents prices, never gives medical advice, and invites the customer to book.

Stack: Python 3.12, Django 5 + Django Ninja, Postgres 16, Claude Haiku (`anthropic` SDK),
Google Sheets (`gspread`), Docker Compose with Caddy for HTTPS.

## How it works

```
Meta ──POST /webhooks/messenger──▶ webhook (verify signature, parse, return 200 fast)
                                       │ run_in_background()
                                       ▼
                               ConversationService   (one flow for every channel)
                                 1. find tenant by Page id   (unknown page → ignore)
                                 2. save message, dedupe by mid
                                 3. paused? → stop
                                 4. typing_on → ReplyEngine → send reply → save reply
                                       │
                                       ▼
                               ReplyEngine           (knows nothing about Messenger)
                                 system prompt = prompts/clinic_base.md + Info tab + tenant extra
                                 Claude tool loop (≤ 4 tool rounds, then a forced text answer)
                                 tools: search_faq, get_price  ──▶ GoogleSheetSource (15-min cache)
```

| Path | What |
|---|---|
| `clinic/channels/` | `ChannelAdapter` (abstract), `MessengerAdapter`, `GraphApiClient`, webhook router |
| `clinic/services/conversation.py` | `ConversationService`: dedupe, pause, save, reply, send |
| `clinic/services/background.py` | `run_in_background()`: thread pool now, swap for a queue later |
| `clinic/ai/` | `PromptBuilder`, `ReplyEngine` (Claude loop, fallback, logging) |
| `clinic/tools/` | `Tool` (abstract), `SearchFaqTool`, `GetPriceTool`, `ToolRegistry` |
| `clinic/knowledge/` | `KnowledgeSource` (abstract), `GoogleSheetSource`, `CsvKnowledgeSource` |
| `clinic/text_utils.py` | Vietnamese fuzzy matching (`normalize_vi`, `best_matches`), message splitting |
| `clinic/wiring.py` | Builds the objects above once per process |
| `prompts/clinic_base.md` | Base system prompt (edit to change the bot's behavior) |
| `scripts/` | `simulate_message.py`, `eval_questions.py`, `eval_sample.csv`, `sample_sheet/*.csv` |

## Run locally

```bash
cp .env.example .env
```

In `.env`, set `DOMAIN=localhost`, `DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1`, and your
`ANTHROPIC_API_KEY`. Put the Google service account key at `secrets/google-service-account.json`
(see below). Then:

```bash
docker compose up -d --build
```

```bash
docker compose exec web python manage.py createsuperuser
```

Open https://localhost/admin (Caddy uses its own local certificate, so the browser will warn
once), create a tenant (see "Create a tenant"), then send a fake message:

```bash
uv run python scripts/simulate_message.py "tẩy trắng răng bao nhiêu" --page-id <PAGE_ID> --url https://localhost/webhooks/messenger --insecure
```

Watch what happens:

```bash
docker compose logs -f web
```

With a fake page token the reply cannot be delivered: the Claude call and its tool calls are
logged, then a Graph API error. Replies are saved to the conversation (admin) only once they
have been sent.

### Tests and lint

Locally (needs Postgres on localhost:5432, user/password `clinic`, with CREATEDB):

```bash
uv sync
```

```bash
uv run pytest
```

```bash
uv run ruff check . && uv run ruff format --check .
```

Or inside Docker, against the compose database:

```bash
docker compose run --rm web pytest
```

Claude, the Graph API and Google Sheets are always faked in tests; no keys are needed.

## Environment variables (`.env`)

| Key | Meaning |
|---|---|
| `DJANGO_SECRET_KEY` | Long random string. `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DJANGO_DEBUG` | `false` in production |
| `DJANGO_ALLOWED_HOSTS` | Your domain, plus `localhost,127.0.0.1` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://<your domain>` (needed for the admin login) |
| `DOMAIN` | Domain Caddy gets an HTTPS certificate for (`localhost` locally) |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Database; compose builds `DATABASE_URL` from them |
| `FB_VERIFY_TOKEN` | Any random string; type the same one in the Meta webhook settings |
| `FB_APP_SECRET` | Meta app secret, used to check `X-Hub-Signature-256` |
| `GRAPH_API_VERSION` | e.g. `v24.0`. Check the [changelog](https://developers.facebook.com/docs/graph-api/changelog) and use a current version |
| `ANTHROPIC_API_KEY` | Claude API key from https://platform.claude.com |
| `CLAUDE_MODEL` | `claude-haiku-5-5` (current Haiku) |
| `CLAUDE_EFFORT` | `low` (fast, cheap chat). `medium`/`high` think more |
| `CLAUDE_MAX_TOKENS`, `CLAUDE_MAX_TOOL_ROUNDS`, `CLAUDE_HISTORY_MESSAGES` | Defaults 2048, 4, 12 |
| `CLAUDE_INPUT_USD_PER_MTOK`, `CLAUDE_OUTPUT_USD_PER_MTOK` | Prices for cost logs (Haiku 5.5: 0.10 / 0.50) |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Set by compose to `/run/secrets/google-service-account.json` |
| `SHEET_CACHE_MINUTES` | Sheet cache lifetime, default 15 |
| `BACKGROUND_WORKERS`, `GUNICORN_WORKERS`, `GUNICORN_THREADS` | Concurrency (defaults 4, 2, 4) |

## Deploy on a VPS

Any Ubuntu 22.04/24.04 VPS with 1 GB RAM is enough to start.

1. Point a DNS **A record** for your domain (e.g. `bot.example.com`) to the VPS IP.
2. Open ports 80 and 443 (Caddy needs 80 for the Let's Encrypt challenge):

   ```bash
   sudo ufw allow OpenSSH && sudo ufw allow 80 && sudo ufw allow 443 && sudo ufw enable
   ```

3. Install Docker:

   ```bash
   curl -fsSL https://get.docker.com | sudo sh
   ```

4. Get the code and configure it:

   ```bash
   git clone <this repo> chat-clinic && cd chat-clinic
   ```

   ```bash
   cp .env.example .env && nano .env
   ```

   Fill in every value (see the table above) with `DOMAIN=bot.example.com`.
   Copy your Google key to `secrets/google-service-account.json`.

5. Start, then create an admin user:

   ```bash
   docker compose up -d --build
   ```

   ```bash
   docker compose exec web python manage.py createsuperuser
   ```

6. Check https://bot.example.com/health returns `{"status": "ok"}`.

Update later with `git pull && docker compose up -d --build` (migrations run on start).
Postgres data lives in the `pgdata` Docker volume; back it up with
`docker compose exec db pg_dump -U clinic clinic > backup.sql`.

## Google Sheet and service account

**Sheet format** (one Google Sheet per clinic, first row = headers, exact tab names):

| Tab | Columns |
|---|---|
| `FAQ` | `question`, `answer` |
| `Services` | `service`, `price_vnd`, `duration`, `notes` |
| `Info` | `key`, `value` (opening hours, address, phone, booking policy, ...) |

`price_vnd` is a plain number (`2500000`), a range (`1500000 - 3000000`) or text (`Liên hệ`).
`0` is shown as "Miễn phí". To start fast, import the files in `scripts/sample_sheet/` (File →
Import → Upload, "Insert new sheet", then rename each tab to `FAQ`, `Services`, `Info`).

**Service account** (once, shared by all clinics):

1. In https://console.cloud.google.com create a project (or pick one).
2. APIs & Services → Library → enable **Google Sheets API**.
3. IAM & Admin → Service Accounts → Create service account (no roles needed).
4. Open it → Keys → Add key → JSON. Save the file as `secrets/google-service-account.json`.
5. Copy the service account's email (`...@....iam.gserviceaccount.com`).

**For each clinic's sheet:** Share → paste the service account email → **Viewer** → Send.
The sheet id is the long part of the URL: `docs.google.com/spreadsheets/d/<SHEET_ID>/edit`.

Changes in the sheet show up within 15 minutes. To refresh now:

```bash
docker compose exec web python manage.py sync_sheets --tenant <TENANT_ID>
```

Without `--tenant` it refreshes all active tenants. It also reports permission errors, so it is
a good check after sharing a new sheet. If Google is down, the bot keeps using the last cached
copy.

## Meta app, webhook and Page token

1. Go to https://developers.facebook.com/apps → **Create app** → use case "Other" →
   type **Business**. (Meta renames these screens often; look for "Messenger".)
2. App settings → Basic: copy the **App secret** into `FB_APP_SECRET`.
3. Add the **Messenger** product (Messenger API settings).
4. **Webhook**: Callback URL `https://<DOMAIN>/webhooks/messenger`, Verify token = your
   `FB_VERIFY_TOKEN` → Verify and save. (The server must already be running.) Subscribe to the
   **`messages`** field.
5. **Page token**: in the Messenger settings, connect the clinic's Facebook Page, generate an
   access token for it, and subscribe the app to the Page (so its webhooks reach you).
   Copy the Page id and the token for the tenant. For a token that does not expire, create a
   **System User** in Meta Business Settings, give it the Page and the app, and generate the
   token there with `pages_messaging` and `pages_manage_metadata`.
6. **Testing vs. live**: while the app is in development mode, only people with a role on the
   app (admin, developer, tester) get replies. For real customers, submit **App Review** for
   `pages_messaging` (Meta also asks for Business Verification), then switch the app to Live.

Messenger only allows replies (`messaging_type: RESPONSE`) within 24 hours of the customer's
last message, which is how this bot works.

## Create a tenant (one per clinic)

Admin → Clinic chatbot → Tenants → Add:

| Field | Value |
|---|---|
| Name | Clinic name (the bot uses it in the prompt) |
| Fb page id | The Facebook Page id (`entry.id` in webhooks) |
| Fb page access token | The Page token from step 5 above |
| Google sheet id | From the sheet URL |
| System prompt extra | Optional clinic-specific instructions, e.g. "Luôn nhắc khách mang theo CCCD." |
| Is active | Unchecked = the bot ignores this Page |

Then run `sync_sheets --tenant <id>` to check the sheet is readable.

**Pausing the bot for one customer:** Admin → Conversations → tick **Is bot paused**. Messages
are still saved; the bot stops replying until you untick it.

## Eval script

Runs questions through the same reply loop (real Claude API, costs a few cents) and checks the
replies for expected keywords:

```bash
uv run python scripts/eval_questions.py
```

```bash
uv run python scripts/eval_questions.py --tenant 1 --show
```

The first command uses `scripts/eval_sample.csv` (20 questions) against the sample sheet data in
`scripts/sample_sheet/`, so it needs only `ANTHROPIC_API_KEY`. `--tenant` uses that tenant's live
Google Sheet (write your own CSV for its data). In Docker:
`docker compose exec web python scripts/eval_questions.py`.

CSV format: `question,expected_keywords`. Keywords are separated by `;` (all required) and
alternatives by `|` (any one). Matching ignores case and accents. Example:
`"tẩy trắng bao nhiêu","2.500.000;đặt lịch|hẹn"`. The script prints PASS/FAIL per question,
the tools used, average latency, tokens and cost.

## Logs and cost

Every Claude call logs one line:

```
claude reply tenant=1 model=claude-haiku-5-5 latency_ms=2140 rounds=2 input_tokens=4210 cache_read_tokens=3500 output_tokens=95 cost_usd=0.000469 tools=[get_price({'service': 'tẩy trắng răng'})] fallback=False
```

Tokens and latency are also stored on each assistant message (see the admin). On any Claude or
Sheets error the customer gets a polite fallback message and the error is logged with a
traceback.

## Extending

- **New tool** (booking, handoff): subclass `Tool` in `clinic/tools/`, add it in
  `default_registry()`, and mention it in `prompts/clinic_base.md`.
- **New channel** (Zalo): subclass `ChannelAdapter`, add a webhook route that calls
  `run_in_background(wiring.handle_incoming, message)`, register the adapter in
  `wiring.conversation_service()`, and add its tenant id field to `_TENANT_KEY` in
  `clinic/services/conversation.py`.
- **Real queue**: replace the body of `run_in_background()` in `clinic/services/background.py`.

## Known limits (MVP)

- Background work runs in a thread pool inside the web process. Messages being processed when
  the container restarts are lost (Meta does not resend them because we already returned 200).
- Replies for one conversation are serialized with a Postgres advisory lock. A customer who sends
  three quick messages can get up to three replies.
- Images, voice and files are not read: the bot asks the customer to type, and the message is
  saved as a placeholder for staff.
- Page tokens are stored in plain text in the database (admin access only).
