# Arrearo technical deep dive

This is the engineering account of Arrearo: what it is, how it is built, and what every
AWS service and every Claude model actually does. It is written against the deployed code,
not a plan. Where the older docs (`README.md`, `docs/ARCHITECTURE.md`, `docs/SPEC.md`) have
fallen behind the code, this document follows the code and says so.

Account 854924711083 (Brownshift), region us-east-1, one SAM stack named `arrearo`.

## What Arrearo is

Arrearo is a late-payment recovery tool for UK small businesses that runs on WhatsApp and a
web dashboard. The owner sends a photo or PDF of an invoice; Claude reads it into structured
fields; a deterministic legal engine works out when the debt becomes legally late and how
much statutory interest it is owed under the Late Payment of Commercial Debts (Interest) Act
1998; and when the debt is late the agent drafts a compliance-checked chase, the owner
approves it, and it goes out over WhatsApp or email. Debtor replies are classified. Aged
debts get a Letter Before Action rendered to PDF. The whole product is also operable as a
full app inside WhatsApp, with an emailed one-time-code login, menu navigation, and
natural-language commands that Claude maps to the same actions the dashboard exposes. Every
figure a debtor or a court could see is computed in tested Python. The model phrases; it
never decides what is owed.

## Architecture overview

Serverless, event-driven, in one `template.yaml`. Nothing runs between requests.

There are three Lambda functions (Python 3.12), all sharing one Lambda layer:

- **`arrearo-webhook`** handles WhatsApp inbound. It is subscribed to the SNS topic
  `brownshift-whatsapp-events`. Timeout 90s. It is the only function with media and session
  permissions, because the in-WhatsApp app runs inside it.
- **`arrearo-api`** is the dashboard's HTTP backend behind API Gateway. Timeout 29s.
- **`arrearo-scheduler`** is driven by EventBridge Scheduler. Timeout 300s.

Two entry paths reach this backend.

**WhatsApp inbound path.** A message to the Arrearo number is received by AWS End User
Messaging Social, which publishes a webhook event to the SNS topic. SNS invokes
`arrearo-webhook`. The function decides whether the sender is a registered business owner, a
debtor on an open invoice, or neither (in which case the sender is talking to the in-WhatsApp
app). It extracts, classifies, stores, and replies, and fetches any image or PDF via
`GetWhatsAppMessageMedia` into the media S3 bucket.

**Dashboard path.** The React and Vite app is built to static files, held in a private S3
bucket, and served by CloudFront with Origin Access Control. The browser signs in to a
Cognito user pool with `USER_PASSWORD_AUTH` and calls the API Gateway HTTP API with the
resulting JWT. API Gateway validates the token with a Cognito JWT authorizer, then proxies
every route to `arrearo-api`.

**Scheduled path.** EventBridge Scheduler invokes `arrearo-scheduler` two ways: `rate(1 hour)`
with `{"task":"due_sweep"}`, and `cron(0 8 * * ? *)` in Europe/London with `{"task":"digest"}`.

**The shared layer** (`services/layer/python`) carries everything the three functions have in
common, so the handlers stay thin:

- `common/`: `config.py` (one place for model IDs, ARNs, table names, the brand), `db.py`
  (all DynamoDB access), `cds.py` (the only place that talks to WhatsApp and SES),
  `flows.py` (the shared business flows), `documents.py` and `pdf.py` (PDF rendering).
- `agent/`: `llm.py` (the Bedrock Converse helper), `extract.py`, `classify.py`, `draft.py`.
- `legal/engine.py`: the deterministic legal engine, with its own test suite.
- `wa/`: the in-WhatsApp app (session, auth, router, intent, menus, views, actions,
  messages, inbound).

The layer build copies `python/` as-is. There is no `requirements.txt` and no pip step, which
is why the PDF renderer is hand-written rather than using a library (more on that below).

## Request and data flows

### (a) A WhatsApp invoice photo becomes a tracked invoice

1. The owner sends a photo of an invoice. End User Messaging Social publishes an event to SNS,
   which invokes `arrearo-webhook`.
2. `parse_sns_event` unwraps the payload. The Meta webhook entry is JSON encoded inside the
   SNS message JSON, so `whatsAppWebhookEntry` is parsed a second time. The handler yields a
   normalised message dict per inbound message and per status event.
3. `handle_message` calls `db.claim_message(wamid)`, which does a conditional `put_item` into
   the events table keyed `dedupe#<wamid>` with a 7-day TTL. If the item already exists the
   message is a redelivery and is skipped. This makes SNS retries idempotent.
4. The sender number is normalised to `+E.164`. `db.get_business_by_whatsapp` looks it up. A
   match means this is the owner, so `handle_owner` runs.
5. For an image or a document, `handle_owner` checks the MIME type against `extract.FMT`
   (JPEG and PNG), calls `GetWhatsAppMessageMedia` to write the file to
   `s3://<media>/inbound/<businessId>/<mediaId>`, reads the bytes back from S3, and calls
   `extract.extract_from_image`.
6. Claude Haiku 4.5 on Bedrock reads the image under a forced tool call and returns the
   fields. `extract.normalise` converts money to integer pence, derives an agreed due date
   from printed terms if one is not shown, and flags low confidence or missing fields. A
   missing amount stays `None` and forces confirmation; the model is never allowed to invent
   one.
7. `db.create_invoice` writes the invoice with status `extracted`. The legally-late date is
   computed by the engine at write time, never supplied by the caller. Two timeline events are
   written: `created` and `extracted`.
8. The reply to the owner states what Arrearo read, the amount formatted as pounds, and the
   date the debt becomes legally late, and asks for `YES`. A later `YES` (matched by regex
   against the newest `extracted` invoice) calls `flows.confirm_invoice`, which sets status
   `confirmed`, writes a `confirmed` event, and scores the debtor against the
   payment-practices table.

### (b) WhatsApp app login and a navigation action

This path runs when the sender is neither a registered owner nor a debtor on an open invoice.
`handle_message` falls through to `handle_app`, which hands the message to `wa.router.handle`.

1. `wa.router` loads the per-number session from the `arrearo-wa-sessions` table. A fresh
   number is `logged_out`.
2. The first interaction returns `welcome_logged_out`, an interactive button that carries the
   id `login`. Tapping it moves the session to `awaiting_email` and asks for the account email.
3. The owner types their email. `wa.auth.submit_email` resolves it with
   `db.get_business_by_email` (case-insensitive across `email`, `contactEmail`, `ownerEmail`).
   A business record exists only for an account created on the web, so this also proves the
   account is real. On a hit it generates a 6-digit code from `secrets`, stores a salted
   SHA-256 hash of it (never the code), sets a 10-minute expiry, and emails the code through
   SES. The session moves to `awaiting_otp`. Throttles: 60 seconds between resends, 5 requests
   per hour.
4. The owner types the code. `wa.auth.submit_otp` hashes it with the stored salt and compares
   with `hmac.compare_digest`. On a match, `session.link` persists the number-to-business link,
   sets state `authed`, and clears the OTP working fields. Three wrong attempts, or an expired
   code, resets to `awaiting_email`.
5. Once `authed`, every message is routed. A global command (`menu`, `summary`, `logout`,
   `help`) is handled first. An interactive tap wins over loose text: its id is a stable screen
   key, optionally `key:arg` (for example `inv:<id>`, `more:2`, `chasego:<id>`), dispatched by
   `_dispatch` to the matching function in `wa.views` or `wa.actions`.
6. A number only ever acts on its own linked business. Every view and action re-checks
   ownership by comparing the invoice's `businessId` against the session's `businessId`, so a
   guessed or stale invoice id returns "I couldn't find that invoice."

### (c) A chase is drafted, compliance-checked, and sent

This is one path in `common/flows.py`, used by the dashboard, the WhatsApp app, and the
scheduler.

1. `draft_chase_for` loads the invoice (with derived figures), the business, and any debtor
   record. `choose_stage` picks the stage from how many chases have already been sent
   (`reminder`, `first_chase`, `second_chase`, `final_notice`). `pick_channel` chooses WhatsApp
   only if the 24-hour window is open, otherwise email.
2. `agent.draft.draft_chase` builds a facts dict from the engine's figures
   (`facts_for`) and asks Claude Sonnet 4.5 to phrase a message around them. The system prompt
   forbids using any figure not in the facts and forbids any wording that implies criminal
   proceedings or official authority.
3. The draft is scanned twice before it can leave: `engine.compliance_scan` for prohibited
   wording, and `_must_cite` to confirm the draft actually quotes the total owed and the
   original amount. If either fails, the prompt is rewritten once with the specific problem and
   the model is asked again. A second failure raises `ComplianceBlock`, which the caller logs
   as a `compliance_block` event and surfaces to the owner. Nothing is sent.
4. On send, `flows.send_chase` re-runs `engine.compliance_scan` on the final text (the owner
   may have edited it), then checks `engine.can_contact_now` for the minimum gap for this
   stage. If too soon, it returns `too_soon` and sends nothing.
5. The channel wrapper fires: `cds.send_whatsapp_text` or `cds.send_email`. In dry mode the
   wrapper logs the payload and returns a `dry-run-...` id, so nothing leaves AWS. On a real
   send the invoice moves to `chasing` and a `chased` event records the stage, the message id,
   the text, and the total owed.

### (d) A PDF document rendered and sent as a WhatsApp document

Triggered from the WhatsApp app by "send me the invoice as a PDF" or "send me a statement".

1. `wa.actions.send_invoice_pdf` (or `send_statement_pdf`) checks ownership, then calls
   `common/documents.py` to render a designed A4 PDF from the invoice and business data. The
   renderer is pure Python (see below) and computes no figures; it only lays out numbers the
   engine already produced.
2. `cds.send_whatsapp_document` stages the bytes in `s3://<media>/outbound/<uuid>/<file>`,
   registers them with `PostWhatsAppMessageMedia` to get a media id, then sends a `document`
   message by that id via `send_whatsapp_raw`.
3. In dry mode steps 2 is skipped and the function returns "Live sending is off in this demo,
   so it stayed on AWS." The document path is valid only inside the 24-hour window.

## What each AWS and CDS service does, and why

| Service | What Arrearo uses it for | Exact calls and where |
|---|---|---|
| AWS End User Messaging Social | The WhatsApp channel: inbound events, outbound text, interactive buttons and lists, and documents; pulling inbound media; pushing a PDF up to send as a document | `send_whatsapp_message` in `cds.send_whatsapp_text` and `cds.send_whatsapp_raw`; `get_whatsapp_message_media` in `cds.fetch_whatsapp_media`; `post_whatsapp_message_media` in `cds.send_whatsapp_document`. All in `common/cds.py` on `boto3.client("socialmessaging")` |
| Amazon SNS | Carries inbound WhatsApp webhook events to the webhook Lambda | Topic `brownshift-whatsapp-events` is the event source for `arrearo-webhook` (template `WhatsAppTopicArn`) |
| Amazon SES v2 | Sends the OTP login code, email chases, and the Letter Before Action with its PDF attachment | `send_email` in `cds.send_email` on `boto3.client("sesv2")`, using the `Content.Simple` shape with `Attachments` for the PDF |
| Amazon Bedrock | Runs Claude for extraction, classification, intent routing, and drafting | `converse` in `agent/llm.py` on `boto3.client("bedrock-runtime")`, against two inference profiles |
| Amazon DynamoDB | All state: businesses, invoices, debtors, conversations, events, WhatsApp sessions | Six on-demand tables, accessed only through `common/db.py` and `wa/session.py` |
| AWS Lambda | The three handlers plus the shared layer | `webhook`, `api`, `scheduler`; layer `arrearo-common` |
| Amazon API Gateway (HTTP API) | The dashboard's REST surface, with a Cognito JWT authorizer and a CORS preflight that bypasses it | `HttpApi` with `DefaultAuthorizer: CognitoJwt`; an unauthorized `OPTIONS /{proxy+}` route |
| Amazon Cognito | Dashboard identity; the WhatsApp OTP login resolves to the same business account | User pool `arrearo-owners`, client with `USER_PASSWORD_AUTH` |
| Amazon S3 | Inbound invoice media (90-day lifecycle), outbound PDFs staged for WhatsApp, and the dashboard build | `MediaBucket` and `WebBucket` |
| Amazon CloudFront | Serves the dashboard from the private web bucket over HTTPS, with SPA fallbacks | `WebDistribution` with Origin Access Control |
| Amazon EventBridge Scheduler | The hourly due sweep and the 08:00 London digest | Two `ScheduleV2` events on `arrearo-scheduler` |
| AWS SAM | The whole stack as one template and one deploy | `infra/template.yaml`, `infra/deploy.sh` |

The three CDS services that are exercised by the deployed Lambdas at runtime (not by a script)
are End User Messaging Social, SES v2, and Bedrock. `common/cds.py` is the only module that
constructs the `socialmessaging` and `sesv2` clients, and `agent/llm.py` is the only module
that constructs the `bedrock-runtime` client. Everything funnels through those two files, so
the runtime calls are easy to find and audit.

IAM is scoped per function in the template:

- `arrearo-webhook` holds `social-messaging:SendWhatsAppMessage`,
  `GetWhatsAppMessageMedia`, and `PostWhatsAppMessageMedia` (scoped to the phone-number-id
  resource), `bedrock:InvokeModel` on the two inference profiles and their backing foundation
  models, `ses:SendEmail`/`SendRawEmail`, CRUD on all six tables, and S3 CRUD on the media
  bucket. It is the only function with media and session access, because the in-WhatsApp app
  lives inside it.
- `arrearo-api` holds only `SendWhatsAppMessage` (not the media calls), Bedrock, SES, CRUD on
  the five business tables, and S3 read.
- `arrearo-scheduler` holds `SendWhatsAppMessage`, Bedrock, SES, and CRUD on the five business
  tables.

## The Claude layer

All model calls go through `agent/llm.py`, which wraps Bedrock `Converse`. Two inference
profiles are used (direct model ids are rejected on this account, so the `us.` profiles are
mandatory):

- **Claude Haiku 4.5** (`us.anthropic.claude-haiku-4-5-20251001-v1:0`) does the structured,
  high-volume work:
  - **Invoice extraction** (`agent/extract.py`): vision on a photo, or a PDF document block, or
    plain text. It reads fields into the `record_invoice` tool.
  - **Reply classification** (`agent/classify.py`): a debtor's WhatsApp reply becomes one of
    `promise_to_pay`, `dispute`, `not_received`, `paid`, `question`, `other`, plus an optional
    promised date and an opt-out flag.
  - **Intent routing** (`wa/intent.py`): free text in the WhatsApp app becomes one of a fixed
    set of actions, with the invoice id copied from the context the function supplies.
- **Claude Sonnet 4.5** (`us.anthropic.claude-sonnet-4-5-20250929-v1:0`) does the writing:
  chases, Letters Before Action, and the morning digest (`agent/draft.py`).

**The forced-tool-use pattern.** `converse_tool` sets `toolConfig` to a single tool and
`toolChoice` to that tool by name, with temperature 0. The model is therefore required to
return a `toolUse` block whose input matches the tool's JSON schema. The helper pulls that
input dict out and returns it; if the model somehow returns no tool call it raises. This is how
extraction, classification, and intent routing all stay structured. The schemas are strict
(`record_invoice`, `classify_reply`, `route`), and the tool output is then post-processed by
deterministic code in `normalise`, `classify_reply`, and `intent.resolve`.

**Why amounts, dates, and interest are never the model's.** The extraction tool is told to
return `null` for anything not clearly visible and never to estimate or calculate. `normalise`
converts the model's gross figure to integer pence itself and refuses to fill a missing amount.
For drafting, the facts dict is built entirely from the engine's figures, and the drafter
enforces two things on the output: `compliance_scan` for wording, and `_must_cite` to confirm
the required figures appear verbatim. A draft that invents or omits a figure is rewritten once
and then blocked. The model chooses words and, in the app, where to navigate. It does not
choose numbers.

## The deterministic legal engine

`legal/engine.py` is pure Python with no I/O. It is the trust boundary: everything a debtor or
a court could rely on is computed here, in integer pence, with interest in `Decimal` rounded
half-up to the penny.

- **Statutory interest.** The rate is 8% plus the Bank of England base rate. `statutory_rate_for`
  picks the base rate by *when the debt went overdue*: the Late Payment Order (SI 2002/1675,
  art. 4) fixes a debt's rate at the Bank Rate on the reference date before it went overdue, so
  a debt overdue in the first half of a year uses the previous 31 December and one overdue in
  the second half uses that 30 June. The engine holds a small table of reference-date base
  rates (for example 3.75% at 31 Dec 2025, giving 11.75% for H1 2026), and falls back to a
  dated constant (`BASE_RATE_PCT = 3.75`, as-of 2026-09-24) for dates not in the table.
  `daily_interest_pence` is `amount * rate / 100 / 365` as an un-rounded Decimal;
  `interest_accrued_pence` multiplies by whole days late and rounds to the penny.
- **Fixed recovery sum.** `fixed_recovery_sum_pence` returns £40 under £1,000, £70 from £1,000
  up to £9,999.99, and £100 from £10,000, in pence.
- **Legally late date.** `legally_late_date` is the day after the due date. An agreed due date
  wins. Otherwise the statutory default of 30 days runs from the later of the invoice date and
  the delivery date. The default is 30 days for every debtor type. (The 60-day figure is held
  only as `MAX_AGREED_TERM_DAYS`, the outer limit before an agreed term is challengeable; it is
  not used to compute lateness. The older README/ARCHITECTURE text that says business debts
  default to 60 days is stale against this code.)
- **Days late.** `days_late` counts inclusively from the late date and is 0 before it.
- **Compliance scan.** `compliance_scan` is a set of regular expressions keyed to the
  Administration of Justice Act 1970 s.40. It flags wording that implies criminal proceedings
  (criminal, prosecute, arrest, police, fraud, jail, prison), that implies action already taken
  rather than possible (bailiff, court order, CCJ unless qualified with "may"), that implies
  official authority (on behalf of the court or government, official notice), or that styles the
  message as an official document (summons, warrant, writ, statutory demand). An empty list is
  clean.
- **Contact cadence.** `can_contact_now` enforces a minimum gap between contacts per stage
  (3 days for a reminder, 7 for the first and second chase, 14 for a final notice or LBA), so an
  automated chaser never contacts at an oppressive frequency.
- **LBA fields.** `lba_required_fields` returns the Pre-Action Protocol for Debt Claims
  checklist. The Protocol applies where the debtor is a sole trader or an individual, not a
  company; the reply period is 30 days when it applies and 14 otherwise, and the Information
  Sheet and Reply Form are flagged as enclosed when it applies.

The separation is the point. If the model drafts a figure, the draft is rejected. If the model
drafts a threat, the scan blocks it. The numbers and the rules are code with tests; the model
only ever sees them as facts to phrase.

Derived figures are never stored. `db.with_derived` recomputes days late, the statutory rate,
daily and accrued interest, the fixed sum, and the total owed on every read, so a value can
never be stale. A paid invoice stops accruing at its `paidAt` date. The fixed sum only applies
once the debt is actually late.

## The WhatsApp app internals

The `wa/` package turns WhatsApp into a full client for the same data the dashboard shows. It
runs inside `arrearo-webhook` for any number that is not a known owner or debtor.

**Session and auth state machine** (`session.py`, `auth.py`). State lives in the
`arrearo-wa-sessions` table, keyed by WhatsApp number. The states are `logged_out`,
`awaiting_email`, `awaiting_otp`, `authed`. Login is an emailed one-time code: no password ever
travels over WhatsApp. The code is 6 digits from `secrets`, stored only as a salted SHA-256
hash with a 10-minute expiry, verified with a constant-time compare, with 3 attempts, a 60-second
resend throttle, and a cap of 5 requests per hour. On success the number is linked to the
business id, and the OTP working fields are cleared. The table also holds a transient navigation
context (the current screen) with a 30-minute staleness window, so a bare company name is read
as a debtor lookup only when the app just asked for one.

**Router, intent, and safe fallback** (`router.py`, `intent.py`, `menus.py`). The router loads
the session; if not `authed` it routes to the login flow (except global HELP, which works in any
state). Once authed, it handles global commands, then an interactive tap (whose id is the stable
screen key), then media (sent to ingest), then free text. Free text goes to `intent.resolve`,
which gives Claude Haiku a compact context (a portfolio summary and up to 40 open invoices with
their ids) and the `route` tool. Claude returns one action and, where relevant, the exact invoice
id copied from the context, or a field and value for an edit. `intent.resolve` then validates:
an invoice id is accepted only if `db.get_invoice(id).businessId` matches the caller's business,
field names are mapped to canonical keys by `_business_field`/`_invoice_field`, and anything
uncertain returns `{"kind":"menu"}`. If the Bedrock call itself fails, it also falls back to the
menu. So the model picks where to go; it cannot reach another business's data and it cannot
produce a figure.

**Views and actions** (`views.py`, `actions.py`). Views are read-only screens that mirror the
dashboard: the summary, a paged invoice list (9 per page, with a tenth "More results" row so
every invoice stays reachable), an invoice detail with the full figures and the legal basis and
status-appropriate action buttons, a timeline, a debtor risk lookup, and settings with the bank
account masked to its last two digits. Actions are the writes: confirm, chase (draft then an
Approve-and-send button), mark paid, Letter Before Action (draft then approve), edit a business
field, edit an invoice field, create from typed text, and send an invoice or statement PDF.
Every action calls `_owned` first and returns "I couldn't find that invoice" if the id is not
the caller's. The chase and LBA actions go through the same `flows` functions, so the compliance
scan and the dry/live switch apply identically to the app and the dashboard.

**Message builders** (`messages.py`, `inbound.py`). `messages.py` builds raw Meta message JSON
with no I/O and no `to` field (the send layer adds `to`). It enforces WhatsApp's limits by
truncation: body 1024, button title 20, row title 24, row description 72, at most 3 buttons and
10 list rows. `inbound.py` normalises an inbound interactive tap into `{kind, id, title}`. Pure
builders are trivial to unit-test, which is why they are split out.

## The PDF document pipeline

`common/pdf.py` and `common/documents.py` write PDF bytes directly, with no third-party library,
because the layer build has no pip step. `pdf.py` is a minimal single-font text writer.
`documents.py` is the designed renderer: a tiny content-stream builder (`_Canvas`) that emits
filled rectangles, rule lines, and Helvetica/Helvetica-Bold text with optional right-alignment
for money columns, then assembles the PDF objects and cross-reference table by hand. It renders
three documents: a branded invoice (header band, bill-to, line item, a totals box that shows
statutory interest and the fixed sum once the debt is late, bank details, and the 1998 Act
footer), a statement (open invoices in a table with a grand total), and the Letter Before Action
laid out as a formal letter around the drafted text. It renders money only through
`config.gbp`; it computes nothing.

Sending a PDF as a WhatsApp document is a three-step dance in `cds.send_whatsapp_document`: put
the bytes in the media S3 bucket under `outbound/<uuid>/<filename>`, call
`PostWhatsAppMessageMedia` with that S3 location to register the file and get a media id, then
send a `document` message referencing the media id. The LBA PDF instead rides out as an SES
attachment (`cds.send_email` builds the `Attachments` entry with `ContentTransferEncoding:
BASE64`).

## Data model

Six DynamoDB tables, on-demand billing, money as integer pence. DynamoDB returns numbers as
`Decimal`; `db._clean` turns whole Decimals back into `int` and the rest into `float` on every
read.

| Table | Keys | Role |
|---|---|---|
| `arrearo-businesses` | PK `businessId`; GSIs `byCognitoSub`, `byWhatsapp` | The SME account: name, owner, email, WhatsApp number, bank details for documents, `cognitoSub`. The GSIs resolve a dashboard user and an inbound WhatsApp number to a business |
| `arrearo-invoices` | PK `invoiceId`; GSIs `byBusiness` (businessId, createdAt), `byDebtorWhatsapp` (debtorWhatsapp, createdAt) | Extracted and confirmed invoices: amount in pence, dates, debtor type, status, the computed `legallyLateDate`. Derived money is added on read, not stored |
| `arrearo-debtors` | PK `debtorKey` (company number if present, else normalised name) | The payment-practices cache: average days to pay, share paid late, risk band, source |
| `arrearo-conversations` | PK `whatsappNumber`, SK `createdAt#messageId` | Inbound and outbound WhatsApp messages, direction, intent, linked invoice. Used to compute the 24-hour free-form window from the latest inbound message |
| `arrearo-events` | PK `invoiceId`, SK `createdAt#seq`, with TTL | The audit timeline per invoice (created, extracted, confirmed, debtor_scored, due, chased, replied, promised, disputed, lba_drafted, lba_sent, paid, digest, compliance_block). Also holds the `dedupe#<wamid>` idempotency markers under their TTL |
| `arrearo-wa-sessions` | PK `waNumber` | The WhatsApp app's per-number login state, the number-to-business link, the OTP working fields, and the transient navigation context |

The older docs describe five tables. The deployed stack has six; the WhatsApp sessions table was
added with the in-WhatsApp app.

## Testing and infrastructure as code

The suite is run with `pytest` from the project root and uses `moto` to mock DynamoDB and
`botocore`'s `Stubber` to assert exact WhatsApp and SES request shapes. Bedrock is faked with a
small `FakeBedrock` that returns queued tool inputs and texts, so drafting and extraction logic
is tested without calling the model. `conftest.py` builds the same table schemas the SAM template
declares, including the GSIs, so the tests exercise the real query paths.

There are 165 tests across the source tree:

- `services/tests/`, 131 tests: the webhook (owner, debtor, and app dispatch, idempotency,
  double-decoding), the HTTP API router and ownership scoping, the CDS wrappers (exact
  `send_whatsapp_message`, `get_whatsapp_message_media`, and `send_email` shapes, and that dry
  mode never calls AWS), the DynamoDB layer, the agents (pence conversion, never inventing an
  amount, the redraft-once-then-block path, figure citation, markdown stripping), the documents,
  the scheduler and LBA, and the whole WhatsApp app (auth and OTP internals, intent routing,
  router, views, actions, PDF extraction). `test_wa_audit.py` is a full-surface walk: it drives
  every menu screen and every action through the router as a logged-in user, checks web parity
  for the natural-language commands, and checks the guards (a cross-business invoice is never
  touched, an unknown message falls back to the menu, and no action is reachable before login).
- `legal/test_engine.py`, 26 tests on the engine: the fixed-sum tier boundaries, the late-date
  for each debtor type, a hand-checked interest accrual, the compliance scan, and the cadence
  guard.
- `services/debtors/test_debtors.py`, 8 tests on the debtor dataset loader and scoring.

The stack is one `infra/template.yaml` (SAM). `infra/deploy.sh` runs `sam build` locally (no
container) and `sam deploy`, then prints the stack outputs. Sends default to `SendMode=dry`;
`./deploy.sh SendMode=live` turns real sends on. One detail worth calling out: the CORS preflight
is a separate unauthorized `OPTIONS /{proxy+}` route, because an `OPTIONS` request carries no
Authorization header and would otherwise be rejected by the Cognito JWT authorizer with a 401,
which breaks every authenticated fetch from the browser. The Lambda returns 204 for `OPTIONS`.

## Security and honest limitations

- **No passwords in chat.** The WhatsApp login is an emailed one-time code, hashed at rest,
  short-lived, attempt-limited, and rate-limited. The code is never stored or echoed.
- **Ownership is enforced everywhere.** The API scopes every record to the caller's Cognito
  `sub` via the business record. The WhatsApp app re-checks the invoice's `businessId` against
  the session link in every view and action, and the intent resolver rejects any invoice id that
  is not the caller's before it dispatches.
- **SES sandbox.** SES `SendEmail` is wired and a live send has been confirmed (a real message,
  a MessageId returned, DKIM success). The account is still in the SES sandbox, so live
  recipients must be verified. The code's default sender constant is `billing@brownshift.com`
  (overridable by the `SesSender` stack parameter); the proven live send was made from a verified
  address on `kasamafo.africa`, because `arrearo.com` could not be registered (an account-level
  hold on Route 53 Domains).
- **WhatsApp cold contact.** WhatsApp only allows free-form messages inside 24 hours of the other
  party's last message. A first message to a debtor needs a Meta-approved template, which is a
  long-lead step outside the AWS API and is not yet in place. In-window messaging works, so the
  demo is driven by inbound messages, where the owner's photo opens the window. `pick_channel`
  reflects this: it chooses WhatsApp only if the window is open, otherwise email.
- **Dry by default.** `SendMode=dry` is the deployed default. In dry mode `cds` logs the payload
  and returns a `dry-run-...` id, and `flows` reports `sent:false, dryRun:true`. A redeploy resets
  the mode to dry, which is a safe default but something to flip before a live demo.
- **Base rate is a dated constant.** The engine holds the Bank of England base rate as a constant
  with an as-of date and a small reference-date table. It does not fetch the rate live; a
  scheduled updater is a roadmap item, and the constant is the safe fallback so a chase is never
  blocked on a live fetch.
- **Debtor data is a subset.** The payment-practices cache is a few hundred companies, not the
  full dataset. Anyone not in it is `unknown`, and the lookup never guesses. Cross-customer
  behavioural scoring is logged per invoice today but is not yet a cross-customer score; that
  needs consent and data-protection design first.
- **Not legal advice.** Arrearo assists with credit control. Whether and when to send a Letter
  Before Action is the owner's call.

## How the AI was used to build it

At runtime, Arrearo reasons with Anthropic Claude on Amazon Bedrock as described above: Haiku
4.5 for extraction, classification, and intent routing, Sonnet 4.5 for drafting. Amounts, dates,
and interest are never produced by the model.

At build time, this codebase was written with AI assistance (Claude Code) under human direction.
A person set the product, made the decisions, and reviewed and deployed the result.

## Notes on stale text in the older docs

While writing this against the code, a few claims in the earlier docs were out of date and have
been corrected above:

- **Table count.** `README.md` and `docs/ARCHITECTURE.md` say five DynamoDB tables; the stack
  has six (the `arrearo-wa-sessions` table was added with the WhatsApp app).
- **Default payment term.** `README.md` and `docs/ARCHITECTURE.md` say business debts default to
  60 days; the engine uses a 30-day statutory default for every debtor type, with 60 days held
  only as the maximum-agreed-term constant that does not drive the lateness calculation.
- **CDS call list.** The `README.md` runtime table lists only `SendWhatsAppMessage`,
  `GetWhatsAppMessageMedia`, SES `SendEmail`, and Bedrock `Converse`. The code also calls
  `PostWhatsAppMessageMedia` (to send PDFs as documents) and uses `SendWhatsAppMessage` for
  interactive buttons, lists, and documents, not only text. `submission/DEVPOST.md` has the
  complete table.
- **The WhatsApp app.** `README.md` and `docs/ARCHITECTURE.md` describe the owner and debtor
  inbound flows and the dashboard, but predate the full in-WhatsApp app (OTP login, menu
  navigation, natural-language intent, and PDF documents). That app is in `services/layer/python/wa/`
  and runs inside `arrearo-webhook`.
- **Test count.** `docs/BUILD-LOG.md` records 88 backend tests from the overnight build; the
  current source tree has 165.
- **Working name.** `docs/SPEC.md` and the `legal/engine.py` docstring still say "Recoup", the
  working name. The shipped brand and internal slug are both Arrearo (`config.APP_SLUG = "arrearo"`,
  tables prefixed `arrearo-`).
