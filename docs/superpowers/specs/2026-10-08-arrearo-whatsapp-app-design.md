# Arrearo on WhatsApp — design spec

Date: 2026-10-08. Status: approved to build (Roger: "yeah lets go, build now prioritize quality").

## Goal

Turn Arrearo into a WhatsApp-native app. A user logs in once with an emailed code, their number is linked to their Arrearo business, and from then on `START` opens a menu that mirrors the web dashboard: summary, invoices, invoice detail, debtor risk, and the actions (confirm, chase, mark paid, Letter Before Action, add an invoice). Logged out shows only `Log in`. Logged in shows the whole app.

This is additive. The web dashboard and its Cognito password login are untouched.

## Non-goals (v1)

- No password typed in chat, ever. Login is an emailed one-time code only.
- No account signup from WhatsApp. v1 links to an account that already exists on the web. Signup is roadmap.
- Settings is view-only in WhatsApp. Editing stays on the web.
- No cross-customer data. A number sees only its linked business.

## Login flow

1. Unlinked number sends anything → welcome + one button `Log in`.
2. Tap `Log in` → state `AWAITING_EMAIL`, prompt for the account email.
3. User types email → `db.get_business_by_email` resolves it. If found: generate a 6-digit code, store its hash with a 10-minute expiry, email it via SES, state `AWAITING_OTP`. If not found: say so, stay `AWAITING_EMAIL`.
4. User types the code → verify against the hash. Success: write the number→businessId link, state `AUTHED`, show the main menu. Failure: decrement attempts (max 3), then force a restart.
5. Linked number: `START` goes straight to the menu. `LOGOUT` unlinks.

OTP rules: 6 digits; stored as a salted SHA-256 hash, never plaintext; 10-minute expiry; 3 verify attempts; 60-second resend throttle; at most 5 requests per number per hour.

## Menu map

Logged out: any message → `welcome_logged_out()` (text + `Log in` button).

Logged in main menu (a WhatsApp list message): Summary, Invoices, Add an invoice, Debtors, Settings, Help, Log out.

Global commands anywhere (case-insensitive, with or without a leading slash): `START`/`MENU`, `SUMMARY`, `BACK`, `HELP`, `LOGOUT`.

Screens:
- Summary → `flows.portfolio_summary` rendered: outstanding total, interest/day, counts open/overdue/promised. Buttons to Invoices and Menu.
- Invoices → list of open invoices (10 per page, `MORE` to page). Each row opens an invoice.
- Invoice detail → debtor, ref, amount, days late, statutory rate, interest, fixed sum, total owed, status, legal basis, latest timeline event. Action buttons by status: `extracted`→Confirm; chaseable→Send chase / Mark paid / Letter Before Action. Each action shows a draft and asks Approve/Cancel.
- Add an invoice → "send a photo or PDF" → extract → short summary + Confirm/Discard.
- Debtors → type a company name → risk band, avg days to pay, share paid late; unknown stays unknown.
- Settings → business details, bank account masked to last two digits. View-only.
- Help / Log out.

## Architecture

New isolated layer package `services/layer/python/wa/`. Each module is small, single-purpose and unit-tested with a stubbed boto3 (`db.set_resource`, `cds.set_client`).

### Module contracts (fixed — agents build to these)

`wa/session.py` — per-number state in DynamoDB table `config.TBL_WA_SESSIONS` (PK `waNumber`). Owns its own table access; does not touch `common/db.py`.
- `STATES`: `"logged_out" | "awaiting_email" | "awaiting_otp" | "authed"`.
- `get(wa_number: str) -> dict` — returns the record, or a fresh `{"waNumber","state":"logged_out"}` default.
- `save(session: dict) -> None`.
- `set_state(wa_number, state, **fields) -> dict`.
- `set_context(wa_number, screen: str, params: dict | None = None) -> dict`.
- `clear_context(wa_number) -> None`.
- `link(wa_number, business_id) -> dict` — persists link + `state="authed"`.
- `unlink(wa_number) -> dict` — `state="logged_out"`, clears link + context.
- Link fields persist; `context` is treated as stale after 30 minutes (store `contextAt`).

`wa/auth.py` — depends on `wa.session`, `common.db.get_business_by_email`, `common.cds.send_email`, `common.config`.
- `start_login(wa_number) -> dict` — set `awaiting_email`; return a Reply (see Reply shape).
- `submit_email(wa_number, email) -> dict` — resolve account, issue+email OTP or report not found; return a Reply.
- `submit_otp(wa_number, code) -> dict` — verify; on success `session.link` and return the main menu Reply; else return a retry Reply.
- `logout(wa_number) -> dict`.
- Helpers: `_gen_code() -> str`, `_hash(code, salt) -> str`.

`wa/messages.py` — pure builders returning a Meta WhatsApp message dict WITHOUT the `to` field (the send layer adds it).
- `text(body: str) -> dict`.
- `buttons(body: str, buttons: list[tuple[str, str]], header: str | None = None) -> dict` — up to 3 `(id, title)`.
- `list_message(body: str, button_label: str, sections: list[dict], header: str | None = None) -> dict` — `sections=[{"title","rows":[{"id","title","description"?}]}]`, up to 10 rows total.
- `document(media_id_or_link: str, filename: str, caption: str | None = None, by_id=True) -> dict`.

`wa/inbound.py` — `extract_interactive(message: dict) -> dict | None`: given a raw Meta message object, if it is an interactive button/list reply return `{"kind":"button"|"list","id","title"}`, else None.

`wa/menus.py` — `parse_command(text: str) -> str | None`; `welcome_logged_out() -> dict`; `main_menu() -> dict`; `help_text() -> dict`. Returns Replies built via `wa.messages`.

`wa/views.py` — read formatters, each returns a Reply. Depend on `common.db`, `common.flows`, `common.config`, `wa.messages`.
- `summary(business_id) -> dict`; `invoice_list(business_id, page=0) -> dict`; `invoice_detail(business_id, invoice_id) -> dict`; `debtor(business_id, query) -> dict`; `settings(business_id) -> dict`.

`wa/actions.py` — write actions, each returns a Reply. Depend on `common.flows`, `common.db`, `agent.extract`, `wa.messages`.
- `confirm(business_id, invoice_id) -> dict`.
- `chase_draft(business_id, invoice_id) -> dict`; `chase_send(business_id, invoice_id) -> dict`.
- `mark_paid(business_id, invoice_id) -> dict`.
- `lba_draft(business_id, invoice_id) -> dict`; `lba_send(business_id, invoice_id) -> dict`.
- `ingest_media(business_id, media: dict) -> dict` — media `{"media_id","mime","bucket","key"}`; fetch, extract (image or PDF), store as an `extracted` invoice, return a short summary + Confirm/Discard.

`wa/router.py` — the state machine. `handle(wa_number: str, inbound: dict) -> list[dict]` where `inbound={"text":str|None,"tap_id":str|None,"tap_title":str|None,"media":dict|None}` and the return is a list of Replies. Loads session; if not `authed`, routes to `wa.auth` (except global `HELP`); else dispatches commands, taps and screen context to `wa.menus`/`wa.views`/`wa.actions`. Owns every ownership-scope check (a number only ever acts on its linked business).

### Reply shape

Every screen returns a Reply dict: a message built by `wa.messages` plus a target hint. Concretely a Reply is exactly what `wa.messages.*` returns (a Meta message dict without `to`). A screen that needs several bubbles returns a `list[dict]`. The send layer calls `common.cds.send_whatsapp_raw(to, reply)` for each.

### Shared infra (owned by the lead, provided before agents start)

- `common/config.py`: `TBL_WA_SESSIONS`, `COGNITO_USER_POOL_ID`.
- `common/db.py`: `get_business_by_email(email) -> dict | None` (Cognito `list_users` by email → sub → `get_business_by_sub`).
- `common/cds.py`: `send_whatsapp_raw(to, message: dict) -> str` (adds `to`, dry/live aware, returns wamid). Existing `send_whatsapp_text` unchanged.
- `agent/extract.py`: extended by the PDF agent to accept `application/pdf` and add a `summary` field.
- `services/functions/webhook.py`: integrated by the lead to parse interactive taps and route through `wa.router` instead of the current unknown-sender drop.
- `infra/template.yaml`: the new table + IAM for Cognito `list_users` and SES; wired by the lead at deploy.

## Security

- No passwords in chat. OTP only, hashed, expiring, attempt- and rate-limited.
- One number ↔ one business. Re-linking requires `LOGOUT` first.
- Bank details masked in WhatsApp (last two digits). Full details only on the web.
- Every send honours `SEND_MODE` and the 24-hour window. Navigation is user-initiated so the window is open.
- Disclose in the README that WhatsApp content reaches Meta.

## Testing

Each module ships with its own `test_wa_<module>.py` under `services/tests/`, using stubbed boto3 (`db.set_resource`, `cds.set_client`) — no live AWS in tests. Target: the auth state machine, the OTP rules (expiry, attempts, wrong code), the router transitions (logged out vs authed, each command, each tap), the message builders (button and list JSON shape), and PDF extraction. Keep the existing 46 tests green.

## Build split (about 6 Opus agents, isolated files)

1. Auth + session: `wa/session.py`, `wa/auth.py` + tests.
2. CDS interactive: `wa/messages.py`, `wa/inbound.py` + tests.
3. Router + menus: `wa/router.py`, `wa/menus.py` + tests.
4. Read views: `wa/views.py` + tests.
5. Write actions: `wa/actions.py` + tests.
6. PDF: `agent/extract.py` (+ `common/pdf` reuse) + tests.

Lead owns `config.py`, `db.py`, `cds.py`, `webhook.py`, `template.yaml`, integration, deploy, live verification. Agents commit incrementally and never touch files outside their list.

## Demo

Log in from Roger's phone (+233547738808) with a verified demo email (SES sandbox), navigate Summary → Invoices → an invoice → Send chase (live, in-window), add a PDF invoice, check a debtor. Flip `SEND_MODE=live` for the session, then back to dry.

## Constraints (disclosed)

SES sandbox delivers only to verified emails, so the demo login uses a verified address. WhatsApp content reaches Meta. WhatsApp allows 3 buttons / 10 list rows, so long lists paginate. Cold re-engagement needs a Meta template; navigation is user-initiated so this does not arise.
