# Arrearo — Devpost submission

Paste the sections below into the matching Devpost fields. Upload the images in this folder.

## Links (Devpost "Try it out" + repo)
- GitHub repo: https://github.com/jo2980958-hub/arrearo
- Live dashboard: https://d9gwfmvszoiw2.cloudfront.net
- Live API: https://hppo19gaaf.execute-api.us-east-1.amazonaws.com
- Demo video: ADD YOUR LINK (YouTube or Vimeo, public or unlisted)

## Images to upload (in this folder)
- `images/cover.png` — thumbnail
- `architecture.png` — architecture (AWS icons)
- `images/how-it-works.png`, `images/features.png` — gallery

## Elevator pitch (tagline, keep under ~200 chars)
Run your credit control from WhatsApp. An agent reads your invoices, computes the statutory interest you are legally owed in a tested engine, and chases late payers with messages you approve before they send.

## Inspiration
Late payment is a quiet killer for UK small businesses. The Department for Business and Trade puts the cost at about £11bn a year. Owners rarely chase properly, and almost none add the interest the Late Payment of Commercial Debts (Interest) Act 1998 already gives them, because the process is awkward and done at night. We wanted that whole job to run as an agent where the owner already is: a WhatsApp chat, with the money and the law handled by code that can be audited to the penny.

## What it does
The owner sends a photo or PDF of an invoice on WhatsApp. Claude extracts it into structured fields under a forced tool call and flags anything it is unsure about rather than guessing. A deterministic legal engine computes when the debt becomes legally late and the statutory interest and fixed recovery sum it carries. When the debt is late, the agent drafts a chase that cites the exact figures and the 1998 Act; the owner approves before it sends on WhatsApp or email. Debtor replies are classified into six intents. Aged debts get a Letter Before Action, checked against the Pre-Action Protocol for Debt Claims and rendered to a branded PDF. The same account is fully operable as an app inside WhatsApp and from a web dashboard.

## How we built it

**Serverless topology (one SAM stack).** Three Python 3.12 Lambdas share a single Lambda layer, defined in one `template.yaml`. Nothing runs between requests.
- `arrearo-webhook` is subscribed to an Amazon SNS topic that AWS End User Messaging Social publishes WhatsApp events to. The inbound event is triple-wrapped (SNS record → AWS envelope → Meta webhook entry JSON string), which the handler parses defensively so one malformed record never drops the batch. It idempotently claims each `wamid` with a conditional DynamoDB put so SNS redelivery is safe, then routes the sender to the extraction flow, the debtor-reply flow, or the in-WhatsApp app. This is the only function with media and session IAM.
- `arrearo-api` sits behind an Amazon API Gateway HTTP API with a Cognito JWT authorizer. It resolves the signed-in user to a business by the email claim and scopes every read to that business. The CORS preflight is a separate unauthenticated `OPTIONS` route, because an `OPTIONS` carries no token and would otherwise 401 and break every fetch.
- `arrearo-scheduler` is driven by Amazon EventBridge Scheduler: an hourly `due_sweep` that advances invoices and a 08:00 Europe/London digest.
- The dashboard is a React and Vite build served from a private S3 bucket through Amazon CloudFront with Origin Access Control, signing in to an Amazon Cognito user pool.

**CDS services called at runtime** (made by the deployed Lambdas, not a script; `common/cds.py` is the only module that builds the `socialmessaging` and `sesv2` clients, `agent/llm.py` the only one that builds `bedrock-runtime`, so every call is auditable):
- AWS End User Messaging Social — `SendWhatsAppMessage` (text, interactive buttons and lists), `GetWhatsAppMessageMedia` (pull an inbound invoice photo/PDF into S3), `PostWhatsAppMessageMedia` (stage a PDF in S3, register it for a media id, send it as a `document`).
- Amazon SES v2 — `SendEmail` for the login codes, the email chases, and the Letter Before Action as a base64 attachment.
- Amazon Bedrock — `Converse` with tool use.

**Claude on Amazon Bedrock.** Every model call goes through a thin `Converse` wrapper against the two `us.` inference profiles (direct model ids are rejected on this account). Claude Haiku 4.5 does the structured, high-volume work under a forced single-tool call at temperature 0, so it must return JSON matching a strict schema: reading an invoice from a photo, a PDF or text; classifying a debtor reply into one of six intents; and routing free text in the WhatsApp app to exactly one action plus, where relevant, an invoice id copied from a list of the caller's own invoices. Claude Sonnet 4.5 does the writing: chases, Letters Before Action, and the digest. The drafter injects the engine's figures as facts, then runs two guards before a draft can send: one scan for prohibited wording and one that confirms the required figures appear verbatim. A failing draft is rewritten once, then blocked and shown to the owner.

**The deterministic legal engine (the moat).** `legal/engine.py` is pure Python, no I/O, with its own test suite. Everything a debtor or a court could rely on is computed here in integer pence, with interest in `Decimal` rounded half up. Statutory interest is 8% over the Bank of England base rate, and the base rate is selected by when the debt went overdue (the reference-date rule, SI 2002/1675 art. 4) from a dated table. The fixed recovery sum is £40 / £70 / £100 by band. The legally-late date is the day after the due date, honouring an agreed term or falling back to the statutory 30 days from the later of invoice and delivery. A compliance scan blocks drafts that imply criminal proceedings or look like an official document, in line with the Administration of Justice Act 1970 s.40. A contact-cadence rule enforces a minimum gap between chases. Claude never produces a figure; it only phrases messages around figures the engine produced.

**Data model.** Six Amazon DynamoDB tables, on-demand, money as integer pence. Derived money is never stored: `with_derived` recomputes days late, interest, the fixed sum and the total on every read, so a value can never go stale, and a paid invoice stops accruing at its paid date. GSIs resolve a Cognito user and an inbound WhatsApp number to a business, and a message id back to its conversation row for delivery callbacks.

**The in-WhatsApp app and auth.** The `wa/` package turns WhatsApp into a full client. Login is an emailed one-time code: six digits from `secrets`, stored only as a salted SHA-256 hash with a 10-minute expiry, verified with `hmac.compare_digest`, limited to three attempts, a 60-second resend throttle and five requests an hour. No password ever travels over WhatsApp. Every view and action re-checks the invoice's `businessId` against the session link, and the intent resolver rejects any invoice id that is not the caller's before dispatching.

**PDFs without a dependency.** The Lambda layer is copied as-is with no pip step, so the invoice, statement and Letter Before Action PDFs are rendered by hand-written byte-level PDF code that only lays out figures the engine produced.

**Testing.** 165 tests. `moto` mocks DynamoDB, `botocore`'s `Stubber` asserts the exact WhatsApp and SES request shapes (and that dry mode never calls AWS), and a small fake Bedrock returns queued tool inputs so the agent logic is tested without the model. A full-surface audit drives every screen and action through the router as a logged-in user.

## Challenges we ran into
WhatsApp only allows free-form messages inside a 24-hour window, so cold outreach needs a Meta-approved template; the demo is driven by inbound messages where the owner's photo opens the window. Keeping the money correct and auditable meant computing every figure in a deterministic engine and recomputing derived values on read. Getting strict extraction out of a vision model meant forced tool use at temperature 0 with unsure fields flagged. The SNS payload is triple-wrapped and arrives out of order, so parsing and the delivery ladder both had to be defensive and idempotent.

## Accomplishments that we're proud of
A deployed product, not a demo script, with the money owned by a tested engine and the model boxed into reading and phrasing. Every outbound chase is scanned twice before it can send. The whole thing is one SAM stack with per-function least-privilege IAM, live WhatsApp and SES sends confirmed, and 165 tests.

## What we learned
The agent is only trustworthy because a deterministic core owns the numbers, the dates and the compliance rules, and because the model's output is validated and re-scoped to the caller before anything happens. The model reads and phrases; the engine decides.

## What's next for Arrearo
WhatsApp message templates for cold outreach, a live Bank of England base rate rather than a dated constant, a cross-customer debtor score built from the chase-and-pay history (consent and data-protection design first), and SES production access.

## Built with
AWS Lambda, Amazon DynamoDB, Amazon API Gateway (HTTP API), Amazon Cognito, Amazon SNS, Amazon EventBridge Scheduler, Amazon S3, Amazon CloudFront, AWS SAM, Amazon Bedrock, Anthropic Claude (Haiku 4.5, Sonnet 4.5), AWS End User Messaging Social (WhatsApp), Amazon SES v2, Python 3.12, React, Vite, TypeScript
