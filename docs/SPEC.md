# Recoup — technical spec (the build contract)

Build target: **AWS serverless, us-east-1, account 854924711083 (profile `default`)**. Python 3.12 Lambdas, boto3. React (Vite) dashboard. AWS SAM for IaC. Product name read from one config constant (`BRAND`) so a rename is one edit.

Priorities: **P0 = demo spine + the product's core (must be 9/10)**, P1 = important, P2 = if time. Agents build P0 first and solid.

## 1. Data model — DynamoDB, per-entity tables (on-demand billing)
All tables prefixed `recoup-`. ISO-8601 UTC timestamps. Money as integer **pence** (avoid float); render as £.

- **businesses** — PK `businessId` (uuid). `name, ownerName, email, whatsappNumber`(E.164), `sector, defaultTermsDays`(int, e.g. 30), `bankName, bankSortCode, bankAccount`(for invoice/LBA), `cognitoSub, createdAt`.
- **invoices** — PK `invoiceId` (uuid). GSI `byBusiness` (businessId, createdAt). Fields: `businessId, debtorName, debtorCompanyNumber`(nullable), `debtorType`(company|sole_trader|individual|public_authority), `debtorEmail, debtorWhatsapp`(nullable), `amountPence, currency`(GBP), `invoiceDate, deliveryDate`(nullable), `agreedDueDate`(nullable), `reference, description`, `status`(extracted|confirmed|due|chasing|promised|disputed|paid|lba|escalated), `sourceChannel`(whatsapp|dashboard), `extractionConfidence`(0-1), `legallyLateDate`(computed), `createdAt, confirmedAt, paidAt`. Derived at read time (not stored stale): `daysLate, interestAccruedPence, fixedRecoverySumPence, totalOwedPence`.
- **debtors** — PK `debtorKey` (companyNumber if present else normalized name). Payment-practices cache: `name, companyNumber, avgDaysToPay, pctPaidWithin30, pct31to60, pct60plus, pctPaidLate, pctInvoicesDisputed, reportPeriodEnd, riskBand`(low|medium|high), `source`(payment-practices|unknown), `fetchedAt`.
- **conversations** — PK `whatsappNumber`, SK `createdAt#messageId`. `direction`(in|out), `messageId, body, mediaId`(nullable), `intent`(nullable: promise_to_pay|dispute|not_received|paid|question|other), `invoiceId`(nullable), `windowExpiresAt`(24h ISO, from delivery events), `raw`(trimmed).
- **events** — PK `invoiceId`, SK `createdAt#seq`. The audit timeline (Govern): `type`(created|extracted|confirmed|debtor_scored|due|chased|replied|promised|disputed|lba_drafted|lba_sent|paid|digest|compliance_block), `channel`(whatsapp|email|system), `actor`(agent|owner|debtor|system), `detail`(map), `createdAt`.

## 2. Legal engine — `services/legal/engine.py` (PURE, fully unit-tested, P0)
Deterministic. Verdicts/amounts NEVER from an LLM. All money in pence (int), interest via `decimal.Decimal`, round half-up to the penny.
```
boe_base_rate() -> (rate_pct: float, as_of: str, source: str)      # live BoE IUDBEDR; fallback to a dated constant
statutory_rate(base_pct: float) -> float                            # base + 8.0
legally_late_date(invoice_date, delivery_date, agreed_due_date, debtor_type) -> date
    # agreed date wins; else 30d (public_authority) / 60d (business) from later of invoice/delivery;
    # 30d default when no terms. Return the date the debt becomes legally late.
days_late(legally_late_date, today) -> int                          # 0 if not yet late
daily_interest_pence(amount_pence, statutory_rate_pct) -> Decimal   # amount * rate/100 / 365
interest_accrued_pence(amount_pence, statutory_rate_pct, days_late) -> int
fixed_recovery_sum_pence(amount_pence) -> int                       # 4000 (<100000) / 7000 (<1000000) / 10000 (>=1000000)
total_owed_pence(amount_pence, interest_pence, fixed_sum_pence) -> int
can_contact_now(last_contact_at, now, stage) -> bool                # AJA 1970 s.40 cadence guard (min gap per stage)
compliance_scan(text) -> list[violation]                            # flag: implies criminal proceedings / false authority / official-doc styling
lba_required_fields(invoice, business, debtor) -> dict              # Pre-Action Protocol for Debt Claims checklist (sole trader/individual)
```
Tests (`services/legal/test_engine.py`): tier boundaries for fixed sum (£999.99→£40, £1000→£70, £9999.99→£70, £10000→£100); late-date for each debtor_type incl. no-terms; interest accrual (a worked example checked by hand); compliance_scan flags a message implying court/criminal action; can_contact_now rejects same-day re-chase. Target ≥95% coverage on engine.py.

## 3. Agent Lambdas — Bedrock (`services/agent/`, P0 except digest P1)
Models via inference profiles: reasoning/drafting `us.anthropic.claude-sonnet-4-5-20250929-v1:0`; extraction/classification `us.anthropic.claude-haiku-4-5-20251001-v1:0`. Use `bedrock-runtime` `converse`. Every draft passes `legal.compliance_scan` before it can be sent; a violation → re-draft once, else block + log a `compliance_block` event and surface to the owner (never auto-send a non-compliant message).
- `extract.py` — image bytes (invoice photo) or text → `{debtorName, amountPence, invoiceDate, deliveryDate, agreedDueDate, reference, confidence}`. Haiku vision. Never invents an amount; low confidence → ask the owner to confirm.
- `classify.py` — inbound reply text + invoice context → `{intent, confidence, extracted{promisedDate?}}`.
- `draft_chase.py` — invoice+debtor+stage → compliant WhatsApp/email chase citing amount, **daily statutory interest**, running total, and the legal basis. Tone escalates by stage but never threatens criminal action.
- `draft_lba.py` — Letter Before Action text + the Pre-Action-Protocol fields (P1).
- `draft_digest.py` — owner's morning digest (P1).
The numbers in every draft come from the legal engine and are injected into the prompt as facts; the model phrases, it does not compute.

## 4. CDS integration — `services/channels/` (P0)
- `whatsapp_in.py` (Lambda, SNS-subscribed to `brownshift-whatsapp-events`): double-decode the payload; normalize sender to E.164 (+ prefix); if media → `socialmessaging get-whatsapp-message-media` → bytes → `extract`; if text → `classify` against the open invoice for that number; write conversation + events; reply via whatsapp_out within the 24h window. Idempotent on messageId. Track `windowExpiresAt` from delivery events.
- `whatsapp_out.py`: `socialmessaging send_whatsapp_message` (exact shape per research/technical.md). Only send free-form within the window; outside → the owner is notified (templates are a disclosed future item — Meta approval is long-lead).
- `email.py`: `sesv2 send_email` (simple) + raw/MIME for a PDF LBA attachment. Sender = a verified identity (the Route53 product domain if it verifies tonight; else disclosed-pending).
Both import a thin `cds` client wrapper so the "AWS SDK client called at runtime" requirement is unmistakable in the code.

## 5. Debtor intelligence — `services/debtors/` (P1)
Loader pulls a SUBSET of the UK payment-practices CSV (`check-payment-practices.service.gov.uk/export/csv/`) — a few hundred well-known companies — into the `debtors` table (offline/author-time script, committed as a small seed). Runtime `score(debtorName|companyNumber)` returns the cached record + a riskBand, or `unknown` (never guesses). Shown on the invoice + used to set expectations.

## 6. API — API Gateway HTTP API + Lambda (`services/api/`, P0)
JSON. Auth: Cognito JWT (P0 — a hosted-UI or a simple username/password user pool; a dev token path is acceptable for the demo but Cognito is the 9/10 target).
- `GET /me` · `GET /invoices` · `GET /invoices/{id}` · `POST /invoices` (manual add) · `PATCH /invoices/{id}` (confirm/mark paid/dispute) · `POST /invoices/{id}/chase` (manual) · `POST /invoices/{id}/lba` (approve+send) · `GET /invoices/{id}/events` · `GET /debtors/{key}`. Derived money fields computed on read via the legal engine.

## 7. Dashboard — React + Vite (`web/`, P0; must be genuinely polished, distinct, 9/10)
S3 + CloudFront. A real SME-owner console: a portfolio view (outstanding total, interest accruing live, overdue count), an invoice table (status, amount, days late, total owed, debtor risk), an invoice detail (the Detect→Chase→Reply→LBA→Paid timeline, the accruing-interest figure updating, the debtor-risk panel, agent-drafted messages to approve/edit/send), and an onboarding flow. Distinct, trustworthy UK-fintech design — NOT a reuse of any other project's system. Name/brand from `BRAND` config.

## 8. IaC + deploy — `infra/` (AWS SAM, P0)
One `template.yaml`: the 6 tables, the Lambdas (+ a shared layer holding `legal` + `cds` wrappers), the SNS subscription, the HTTP API, Cognito user pool, EventBridge Scheduler (daily digest + due-date sweep), S3+CloudFront, least-privilege IAM (bedrock:InvokeModel on the two profiles, socialmessaging:SendWhatsAppMessage/GetWhatsAppMessageMedia, ses:SendEmail, dynamodb CRUD, scoped). `sam build && sam deploy`. Commit incrementally.

## 9. Demo seed + script (`infra/seed.py`, P0)
A demo business + 4 invoices spanning states: (a) just extracted from WhatsApp, (b) due today → first chase, (c) promised-to-pay, (d) aged → LBA. At least one real UK debtor company (from the dataset) showing a real risk band. The runnable demo: WhatsApp an invoice photo → extract+confirm+risk → dashboard shows it, interest accruing → trigger the chase (WhatsApp+SES) with statutory interest + legal basis → a reply is classified + tracked → LBA drafted+emailed → digest.

## Open items resolved by the two research agents (fold in before building)
- Final product NAME + domain (market agent) → set `BRAND`, register domain.
- Exact `send_whatsapp_message` / `get_whatsapp_message_media` shapes + the inbound SNS schema (technical agent) → whatsapp_in/out.
- Current BoE base rate + total statutory % (technical agent) → engine fallback constant + displayed figure.
- Pre-Action Protocol LBA required fields + s.40 cadence specifics (technical agent) → lba_required_fields + can_contact_now.
