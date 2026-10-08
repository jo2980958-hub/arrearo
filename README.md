# Arrearo

**Run your whole credit control from WhatsApp. An agent reads your invoices, chases late payers, and adds the interest you are legally owed.**

Arrearo is a deployed AWS product for UK small businesses. The owner sends a photo or a PDF of an invoice on WhatsApp. Claude reads it into structured fields, a deterministic legal engine works out when the debt becomes legally late and how much statutory interest it carries, and when the debt is late the agent drafts a compliance-checked chase that the owner approves before it goes out. Debtor replies are classified. Aged debts get a Letter Before Action rendered to PDF. The same account is operable as a full app inside WhatsApp and from a web dashboard.

Built for the AWS CDS Agentic AI hackathon. Live on AWS account 854924711083, region us-east-1, as one SAM stack named `arrearo`.

| | |
|---|---|
| Dashboard | https://d9gwfmvszoiw2.cloudfront.net |
| API | https://hppo19gaaf.execute-api.us-east-1.amazonaws.com |
| WhatsApp | +233 55 906 2312 |
| Stack | `arrearo`, us-east-1 |
| Dashboard login | `owner@arrearo.com` / `Arrearo-Demo-7391!Kq` |
| WhatsApp login | message the number, tap **Log in**, use `devpost-demo@brownshift.com` |

## The problem

Late payment hurts UK small businesses, and most owners do nothing about it.

- The Department for Business and Trade says late payment costs the UK economy £11bn a year and shuts 38 businesses a day (press release, 30 July 2025). The 38-a-day figure is a modelled estimate from DBT and London Economics research, about 14,000 additional closures a year.
- The same research finds over 1.5m businesses, 28% of all UK businesses, are affected each year, with about £26bn owed late at any time.
- The average affected business is owed about £17,000 and spends about 86 hours a year chasing it.

Chasing is awkward, slow, and usually done by the owner at night. Most owners also do not know the law already lets them add interest and a fixed sum to a late commercial debt, so they almost never do.

## What it does

You run everything from the chat. Log in once with a code emailed to you, and your WhatsApp number is linked to your account.

- **See your position.** "What am I owed" returns the total outstanding and the interest building each day.
- **Work your invoices.** List them, open one, and read the amount, days late, the statutory interest, the fixed recovery sum, the total owed, and the legal basis.
- **Add an invoice.** Send a photo or a PDF, or type the details. Claude reads it and you confirm.
- **Chase.** The agent drafts a chase that cites the exact figures and the 1998 Act, you approve, and it sends on WhatsApp or email.
- **Escalate.** Old debts get a Letter Before Action, checked against the Pre-Action Protocol and emailed as a designed PDF.
- **Edit anything.** Change a business detail or any invoice field by saying so.
- **Get documents.** "Send me the Mercer invoice as a PDF" or "send me a statement" and a branded PDF arrives as a WhatsApp document.
- **Check a debtor.** Ask about a company and get its payment risk from UK government data.

You talk to it in plain language. Claude works out what you meant and takes you there, falling back to a menu when it is unsure. A web dashboard shows the same data.

## How it works

1. **Capture.** The owner WhatsApps a photo of an invoice.
2. **Extract.** Claude Haiku 4.5 on Amazon Bedrock reads it into structured fields under a forced tool call. It never invents an amount; unsure fields are flagged for confirmation.
3. **Confirm.** Arrearo replies with what it read and the date the debt becomes legally late. The owner replies `YES`.
4. **Track.** The invoice appears in the dashboard with interest accruing daily and the legal basis shown. The debtor is scored from payment-practices data. Unknown debtors stay unknown.
5. **Chase.** When the debt is late, the legal engine produces the figures. Claude Sonnet 4.5 phrases the message around them, a compliance scan checks it, and it goes out by WhatsApp or email.
6. **Reply.** The debtor's answer is classified into promise to pay, dispute, not received, paid, question, or other. The invoice status and timeline update, and any promised date is tracked.
7. **Escalate.** Old debts get a Letter Before Action: drafted, checked against the Pre-Action Protocol fields, rendered to PDF, and emailed.
8. **Digest.** Every morning at 08:00 London time the owner gets a summary.

## Architecture

Serverless and event-driven, in one SAM template. Nothing runs between requests.

![Arrearo architecture](submission/architecture.png)

Three Python 3.12 Lambda functions share one layer:

- **`arrearo-webhook`** handles everything inbound from WhatsApp. It is subscribed to the SNS topic `brownshift-whatsapp-events`. The in-WhatsApp app runs inside it, so it is the only function with media and session permissions.
- **`arrearo-api`** is the dashboard's HTTP backend behind API Gateway.
- **`arrearo-scheduler`** is driven by EventBridge Scheduler: an hourly `due_sweep` and the 08:00 London `digest`.

The shared layer (`services/layer/python`) keeps the handlers thin:

- `common/` — `config.py` (model ids, ARNs, table names, brand), `db.py` (all DynamoDB access), `cds.py` (the only module that talks to WhatsApp and SES), `flows.py` (shared business flows), `documents.py` and `pdf.py` (PDF rendering).
- `agent/` — `llm.py` (the Bedrock Converse helper), `extract.py`, `classify.py`, `draft.py`.
- `legal/engine.py` — the deterministic legal engine, with its own test suite.
- `wa/` — the in-WhatsApp app (session, auth, router, intent, menus, views, actions, messages, inbound).

The layer build copies `python/` as-is with no pip step, which is why even the PDF renderer is hand-written rather than using a library.

Two entry paths reach the backend. A WhatsApp message is received by AWS End User Messaging Social, which publishes a webhook event to SNS, which invokes `arrearo-webhook`; the function decides whether the sender is a registered owner, a debtor on an open invoice, or someone talking to the in-WhatsApp app. The dashboard is a React and Vite build served from a private S3 bucket through CloudFront with Origin Access Control; it signs in to a Cognito user pool and calls the API Gateway HTTP API with the JWT, which API Gateway validates with a Cognito authorizer. The CORS preflight is a separate unauthorized `OPTIONS` route, because an `OPTIONS` request carries no token and would otherwise be rejected with a 401 and break every fetch.

## CDS services called at runtime

This is the hackathon's hard requirement. These calls are made by the deployed Lambdas, not by a script. `common/cds.py` is the only module that constructs the `socialmessaging` and `sesv2` clients, and `agent/llm.py` is the only module that constructs the `bedrock-runtime` client, so every runtime call is easy to find and audit.

| Service | Call | Where |
|---|---|---|
| AWS End User Messaging Social | `SendWhatsAppMessage` (text, interactive buttons and lists, documents) | `send_whatsapp_text` / `send_whatsapp_raw` in `services/layer/python/common/cds.py` |
| AWS End User Messaging Social | `GetWhatsAppMessageMedia` (inbound invoice photos and PDFs) | `fetch_whatsapp_media`, same file |
| AWS End User Messaging Social | `PostWhatsAppMessageMedia` (upload a PDF to send as a document) | `send_whatsapp_document`, same file |
| Amazon SES v2 | `SendEmail` (OTP login codes, email chases, the LBA PDF attachment) | `send_email`, same file |
| Amazon Bedrock | `Converse` (Haiku for reading, classifying, and intent; Sonnet for drafting) | `services/layer/python/agent/llm.py` |

Inbound WhatsApp arrives through the same service: the SNS topic `brownshift-whatsapp-events` triggers `services/functions/webhook.py`, which fetches invoice photos with `GetWhatsAppMessageMedia`. IAM is scoped per function in `infra/template.yaml`; only `arrearo-webhook` holds the media and session permissions. By default the stack runs with `SendMode=dry` (see Known limitations).

## How Claude is used

Every model call goes through `agent/llm.py`, a thin wrapper over Bedrock `Converse`, against the two `us.` inference profiles (direct model ids are rejected on this account).

- **Claude Haiku 4.5** (`us.anthropic.claude-haiku-4-5-20251001-v1:0`) does the structured, high-volume work under a forced single-tool call at temperature 0, so it must return JSON matching a strict schema: reading an invoice from a photo, a PDF, or text (`extract.py`); classifying a debtor's reply into one of six intents (`classify.py`); and routing what you type in the app to one action (`wa/intent.py`).
- **Claude Sonnet 4.5** (`us.anthropic.claude-sonnet-4-5-20250929-v1:0`) does the writing: chases, Letters Before Action, and the morning digest (`draft.py`).

The drafter injects the engine's figures as facts, then checks every draft twice before it can be sent: once for prohibited wording, and once to confirm the required figures appear verbatim. A bad draft is rewritten once and then blocked, logged, and shown to the owner. Claude decides where you want to go and phrases the messages. It never decides what you owe, and it cannot reach another account's data.

## The legal engine

`services/layer/python/legal/engine.py` is the moat: pure Python with no I/O, tested in `legal/test_engine.py`. Everything a debtor or a court could rely on is computed here, in integer pence, with interest in `Decimal` rounded half up to the penny.

- **Statutory interest** is 8% over the Bank of England base rate. The base rate is chosen by *when the debt went overdue* (the Late Payment Order's reference-date rule, SI 2002/1675 art. 4), from a small table of reference-date rates, with a dated constant as the fallback.
- **Fixed recovery sum** is £40 under £1,000, £70 from £1,000 to £9,999.99, and £100 from £10,000.
- **Legally late date** is the day after the due date. An agreed due date wins; otherwise the statutory default of 30 days runs from the later of the invoice and delivery dates.
- **Compliance scan** blocks drafts that imply criminal proceedings, claim false authority, or look like an official document, in line with the Administration of Justice Act 1970 s.40.
- **Contact cadence** enforces a minimum gap between contacts per stage, so an automated chaser never contacts at an oppressive frequency.
- **LBA fields** are the Pre-Action Protocol for Debt Claims checklist.

Derived figures are never stored. `db.with_derived` recomputes days late, interest, the fixed sum, and the total on every read, so a value can never go stale. A paid invoice stops accruing at its paid date.

## The in-WhatsApp app

The `wa/` package turns WhatsApp into a full client for the same data the dashboard shows. It runs inside `arrearo-webhook` for any number that is not a known owner or debtor.

- **Login is an emailed one-time code.** No password ever travels over WhatsApp. The code is six digits from `secrets`, stored only as a salted SHA-256 hash with a 10-minute expiry, verified with a constant-time compare, limited to three attempts, a 60-second resend throttle, and five requests an hour. On success the number is linked to the business id.
- **A router** maps interactive taps, global commands (`menu`, `summary`, `logout`, `help`), and free text to the same screens and actions the dashboard has. Free text goes to Haiku with a compact list of the caller's own invoices; it returns one action and, where relevant, an invoice id copied from that list.
- **Ownership is re-checked everywhere.** Every view and action compares the invoice's `businessId` against the session's link, and the intent resolver rejects any invoice id that is not the caller's before dispatching. A guessed or stale id returns "I couldn't find that invoice."

## Documents

`common/pdf.py` and `common/documents.py` write PDF bytes directly, with no third-party library, because the layer build has no pip step. The renderer lays out figures the engine already produced and computes nothing itself. It renders a branded invoice, a statement, and a Letter Before Action. A PDF is sent over WhatsApp by staging it in S3, registering it with `PostWhatsAppMessageMedia` for a media id, and sending a `document` message by that id; the LBA also rides out as an SES attachment.

## Data model

Six DynamoDB tables, on-demand billing, money stored as integer pence. Derived money is computed at read time by the engine.

| Table | Role |
|---|---|
| `arrearo-businesses` | The SME account: name, owner, email, WhatsApp number, bank details. GSIs resolve a dashboard user and an inbound WhatsApp number to a business. |
| `arrearo-invoices` | Extracted and confirmed invoices: amount in pence, dates, debtor type, status, the computed legally-late date. |
| `arrearo-debtors` | The payment-practices cache: average days to pay, share paid late, risk band, source. |
| `arrearo-conversations` | Inbound and outbound WhatsApp messages, used to compute the 24-hour free-form window. |
| `arrearo-events` | The audit timeline per invoice, plus the idempotency markers that make SNS redelivery safe. |
| `arrearo-wa-sessions` | The WhatsApp app's per-number login state, the number-to-business link, and the transient navigation context. |

## Debtor intelligence

`services/debtors/` holds a subset of companies from the UK government payment-practices data (Check when large businesses pay their suppliers). For each it keeps average days to pay, share paid within 30 days, share paid late, and a risk band. A lookup returns that record or `unknown`; it never guesses. Longer term, Arrearo records every chase, reply, and payment per debtor on the invoice timeline, which across many creditors becomes a view of who pays and when. Today that record is per invoice; a cross-customer score is on the roadmap and needs consent and data-protection design first.

## Testing

165 tests across the source tree, run with `pytest` from the project root. They use `moto` to mock DynamoDB and `botocore`'s `Stubber` to assert the exact WhatsApp and SES request shapes, and a small fake Bedrock that returns queued tool inputs so the agent logic is tested without calling the model.

- `services/tests/` (131) — the webhook, the HTTP API router and ownership scoping, the CDS wrappers (exact request shapes, and that dry mode never calls AWS), the DynamoDB layer, the agents, the documents, the scheduler, and the whole WhatsApp app. `test_wa_audit.py` is a full-surface walk that drives every screen and action through the router as a logged-in user.
- `legal/test_engine.py` (26) — the fixed-sum boundaries, the late-date rules, a hand-checked interest accrual, the compliance scan, and the cadence guard.
- `services/debtors/test_debtors.py` (8) — the debtor dataset loader and scoring.

## Deploy

Needs the AWS SAM CLI, Python 3.12, Node, and AWS credentials for the target account.

```bash
# backend: build and deploy the stack (sends stay dry)
infra/deploy.sh

# turn real WhatsApp and SES sends on
infra/deploy.sh SendMode=live

# seed a demo business and four invoices
python infra/seed.py --sub <cognito user sub> --email owner@arrearo.com

# dashboard: build, then sync to the web bucket and invalidate CloudFront
cd web && npm install && npm run build
aws s3 sync dist/ s3://<WebBucket output> --delete
aws cloudfront create-invalidation --distribution-id <WebDistributionId output> --paths '/*'
```

`infra/deploy.sh` prints the stack outputs (`ApiUrl`, `WebUrl`, `WebBucket`, `WebDistributionId`, and the Cognito ids). The dashboard env vars are baked in at build time: `VITE_API_URL`, `VITE_COGNITO_REGION`, `VITE_COGNITO_CLIENT_ID`. Use `VITE_DEMO=1 npm run dev` for a seeded local preview with no login.

## Known limitations

We would rather you hear these from us.

- **SendMode is `dry` by default.** In dry mode a send returns `sent:false, dryRun:true` and nothing leaves AWS. Deploy with `SendMode=live` to send for real. A redeploy resets it to dry, which is safe but worth remembering before a live demo.
- **SES is in the sandbox.** Arrearo calls SES `SendEmail` at runtime and a live send has been confirmed (a real message, a MessageId returned, DKIM success). The account is still in the SES sandbox, so live recipients must be verified. The proven live send came from a verified address on `kasamafo.africa`, because `arrearo.com` could not be registered (an account-level hold on Route 53 Domains).
- **No custom domain.** The same Route 53 Domains hold blocks `arrearo.com`, so the app runs on its CloudFront and API Gateway URLs.
- **WhatsApp cold contact needs a Meta template.** WhatsApp only allows free-form messages inside 24 hours of the other party's last message. A first message to a debtor needs a Meta-approved template, which is a long-lead step outside the AWS API and is not yet in place. In-window messaging works, so the demo is driven by inbound messages where the owner's photo opens the window.
- **Base rate is a dated constant.** The engine holds the Bank of England base rate as a constant with an as-of date and a small reference-date table. It does not fetch the rate live.
- **Debtor data is a subset.** A few hundred companies, not the full dataset. Anyone else is `unknown`.
- **Not legal advice.** Arrearo assists with credit control. Whether and when to send a Letter Before Action is the owner's call.

## AI disclosure

- **At runtime,** Arrearo reasons with Anthropic Claude on Amazon Bedrock. Haiku 4.5 reads invoices, classifies replies, and routes what you type. Sonnet 4.5 drafts chases, Letters Before Action, and digests. Amounts, dates, and interest are never produced by the model; they come from the deterministic legal engine, and any invoice the agent acts on is checked against your own account.
- **At build time,** this codebase was written with AI assistance (Claude Code) under human direction. A person set the product, made the decisions, and reviewed and deployed the result.

## Repository layout

```
infra/       SAM template, deploy script, seed
services/    functions (webhook, api, scheduler), layer (legal, agent, common, wa), debtors, tests
web/         React + Vite dashboard
submission/  architecture diagram and images
```

## Licence

MIT. See [LICENSE](LICENSE).
