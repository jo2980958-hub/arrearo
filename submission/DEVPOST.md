# Arrearo — Devpost submission

Paste-ready copy for the Devpost form. Fill the three links once the repo is public, the video is up, and the ACE opportunity exists.

| Field | Value |
|---|---|
| Public repo | _(GitHub URL once pushed)_ |
| Demo video (~3 min) | _(YouTube/Vimeo URL)_ |
| Live app | https://d9gwfmvszoiw2.cloudfront.net |
| WhatsApp | +233 55 906 2312 |
| Web dashboard login | `owner@arrearo.com` / `Arrearo-Demo-7391!Kq` |
| WhatsApp login (demo) | message the number, tap Log in, use `devpost-demo@brownshift.com` |
| AWS account | 854924711083 (Brownshift), us-east-1 |
| Entrant email | devpost-demo@brownshift.com |

## Name

Arrearo

## Elevator pitch (one line)

Run your whole credit control from WhatsApp: an agent that reads your invoices, chases late payers, and adds the interest you are legally owed.

## Inspiration

Late payment is a tax on small businesses that nobody votes for. The UK government says it costs the economy £11bn a year and shuts 38 businesses a day. The average affected firm is owed about £17,000 and loses about 86 hours a year chasing it, usually the owner, at night. Two things stood out. Owners chase on email, where debtors ignore them. And almost none of them know the law already lets them add interest and a fixed sum to a late commercial debt. So we built the credit controller that lives on the channel people actually read, and that knows the law they are not using.

## What it does

Arrearo is a full app that lives inside WhatsApp. You log in once with a code emailed to you, and your number is linked to your account. After that, you run everything from the chat.

- **See your position.** "What am I owed" gives the total outstanding and the interest building each day.
- **Work your invoices.** List them, open one, and see the amount, days late, the statutory interest, the fixed recovery sum, the total owed, and the legal basis.
- **Add an invoice.** Send a photo or a PDF, or just type the details. Claude reads it and you confirm.
- **Chase.** The agent drafts a chase that cites the exact figures and the 1998 Act, you approve, and it sends on WhatsApp or email.
- **Escalate.** Old debts get a Letter Before Action, checked against the Pre-Action Protocol and emailed as a designed PDF.
- **Edit anything.** Change your business details or any invoice field by saying so.
- **Get documents.** "Send me the Mercer invoice as a PDF" or "send me a statement" and a designed, branded PDF arrives as a WhatsApp document.
- **Check a debtor.** Ask about any company and get its payment risk from UK government data.

You talk to it in plain language. Claude works out what you meant and takes you there, and falls back to a menu when it is unsure. There is a web dashboard too, with the same data.

## How we built it

Serverless on AWS, one SAM stack, three Lambda functions sharing one layer, and no servers between requests.

**The shape.** Three functions do the work. `webhook` is subscribed to the WhatsApp SNS topic and handles everything inbound. `api` sits behind the API Gateway HTTP API and serves the dashboard. `scheduler` is driven by EventBridge Scheduler. A single Lambda layer holds the parts they share: the DynamoDB access, the CDS wrappers, the shared business flows, the legal engine, the agent code, and the WhatsApp app. The layer is copied as-is with no pip step, which is why even the PDF renderer is hand-written.

**WhatsApp inbound.** A message hits AWS End User Messaging Social, which publishes a webhook event to the SNS topic, which invokes `webhook`. The payload is JSON inside JSON (the Meta entry is a string inside the SNS message), so it is decoded twice. A conditional write to the events table keyed by the WhatsApp message id makes SNS redelivery idempotent. The sender is then resolved: a registered WhatsApp number is the owner (send an invoice, confirm with YES, mark paid), a number on an open invoice is a debtor (the reply is classified and the timeline updates), and anyone else enters the WhatsApp app.

**The WhatsApp app.** It lives inside the `webhook` function. Login is an emailed one-time code, never a password in chat: a 6-digit code from a cryptographic source, stored only as a salted SHA-256 hash with a ten-minute expiry, three attempts, and request throttles. Once the number is linked to an account, a router maps interactive taps, global commands, and free text to the same screens and actions the dashboard has. Free text goes to Claude Haiku 4.5 on Amazon Bedrock with a routing tool and a compact list of the caller's own invoices; Claude returns one action and, where relevant, an invoice id copied from that list. The resolver then validates that the id really belongs to the caller before dispatching, maps field names to canonical keys, and falls back to the menu when it is unsure. Claude picks where to go; it cannot reach another account's data and it cannot produce a figure.

**Claude, used in two roles.** Every model call is a Bedrock `Converse` through one helper, against the two `us.` inference profiles. Claude Haiku 4.5 does the structured work under a forced single-tool call at temperature 0, so it must return JSON matching a strict schema: reading an invoice from a photo, PDF, or text; classifying a debtor's reply into one of six intents; and routing what you type in the app. Claude Sonnet 4.5 does the writing: chases, Letters Before Action, and the morning digest. The drafter injects the engine's figures as facts, then checks every draft twice before it can be sent, once for prohibited wording and once to confirm the required figures appear verbatim; a bad draft is rewritten once and then blocked.

**The legal engine.** `legal/engine.py` is pure Python with its own tests. It computes statutory interest at 8% over the Bank of England base rate, choosing the base rate by when the debt went overdue (the Late Payment Order's reference-date rule), in whole pence with `Decimal`. It computes the fixed recovery sum (£40 / £70 / £100 by debt size), the legally-late date (an agreed date wins, otherwise 30 days from the later of invoice or delivery), the compliance scan against the Administration of Justice Act 1970 s.40, the contact-cadence guard, and the Pre-Action Protocol checklist for a Letter Before Action. Derived figures are never stored; `with_derived` recomputes days late, interest, and the total on every read, so nothing goes stale.

**Documents.** The invoice, statement, and Letter Before Action are rendered to A4 PDF by a hand-written content-stream builder (no third-party library), which lays out figures the engine already produced and computes nothing itself. A PDF is sent over WhatsApp by staging it in S3, registering it with End User Messaging media upload for a media id, and sending a document message by that id; the LBA also rides out as an SES attachment.

**The dashboard.** React and Vite, built to a private S3 bucket and served by CloudFront with Origin Access Control. It signs in to a Cognito user pool and calls the HTTP API with the JWT; API Gateway validates the token with a Cognito authorizer. The CORS preflight is a separate unauthorized `OPTIONS` route, because an `OPTIONS` request carries no token and would otherwise be rejected with a 401 and break every fetch. Data is in six DynamoDB tables (businesses, invoices, debtors, conversations, events, WhatsApp sessions), money stored as integer pence. EventBridge Scheduler runs the hourly due sweep and the 08:00 London digest.

### What each service does

- **AWS End User Messaging Social** is the WhatsApp channel. `SendWhatsAppMessage` sends text, interactive buttons and lists, and documents; `GetWhatsAppMessageMedia` pulls inbound invoice photos and PDFs into S3; `PostWhatsAppMessageMedia` uploads an outbound PDF so it can be sent as a document. All in `services/layer/python/common/cds.py`.
- **Amazon SNS** carries inbound WhatsApp webhook events to the `webhook` Lambda via the `brownshift-whatsapp-events` topic.
- **Amazon SES v2** sends the OTP login code, email chases, and the Letter Before Action with its PDF attached (`SendEmail`, same file).
- **Amazon Bedrock** runs Claude: Haiku 4.5 for extraction, classification, and intent routing; Sonnet 4.5 for drafting (`Converse` in `services/layer/python/agent/llm.py`).
- **Amazon DynamoDB** holds all state across six on-demand tables; derived money is computed at read time by the engine.
- **AWS Lambda** runs the three handlers (`webhook`, `api`, `scheduler`) and the shared layer.
- **Amazon API Gateway (HTTP API)** is the dashboard's REST surface, with a Cognito JWT authorizer and the unauthorized CORS preflight route.
- **Amazon Cognito** is dashboard identity; the WhatsApp OTP login resolves to the same business account.
- **Amazon S3** holds inbound media (90-day lifecycle), staged outbound PDFs, and the dashboard build.
- **Amazon CloudFront** serves the dashboard from the private bucket over HTTPS with SPA fallbacks.
- **Amazon EventBridge Scheduler** fires the hourly due sweep and the daily digest.
- **AWS SAM** is the whole stack in one template with one deploy script.

The part we care about most is that the money and the law are not left to the model. Interest at 8% over the Bank of England base rate, the fixed sum, the late dates and the compliance checks are plain tested code. Claude decides where you want to go and phrases the messages. It never decides what you owe. There is a deeper write-up in `submission/TECHNICAL.md`.

## Challenges we ran into

WhatsApp first contact to a debtor needs a Meta-approved template, which is a long-lead step, so cold outbound is disclosed as pending while in-window messaging works. Collecting a login over WhatsApp safely meant no passwords in chat, so we built an emailed one-time code instead. Sending a designed document over WhatsApp meant rendering a real PDF with no third-party library (the Lambda layer has no build step) and uploading it as media. A redeploy resets the send mode to dry, which is a safe default but something to remember before a live demo.

## Accomplishments we are proud of

It is a real, deployed product you operate entirely from WhatsApp, not a slide. Several AWS and CDS services are called at runtime by the Lambdas, not by a script. The legal engine has its own test suite and the whole backend has over 130 tests, including a full-surface audit that walks every screen and action. The debtor data is real, from the UK government payment-practices dataset. We proved the whole thing on a real phone: login, navigation, a live chase, and a designed invoice PDF delivered as a WhatsApp document.

## What we learned

A chat agent is only trustworthy because the consequential parts are not the model's to decide. Pulling every number and every compliance rule out of Claude and into tested code is what makes an agent safe to point at a real debtor and a real bank balance.

## What's next

A Meta-approved template for first contact. Pay-by-link in the chat through a regulated provider, so we never hold funds. Accounting connectors for Xero and Sage. A debtor-risk network across customers, designed for consent from the start.

## Built with

aws, aws-lambda, amazon-bedrock, claude, anthropic, aws-end-user-messaging, whatsapp, whatsapp-interactive-messages, amazon-ses, amazon-dynamodb, amazon-sns, amazon-eventbridge, amazon-cognito, amazon-api-gateway, amazon-s3, amazon-cloudfront, aws-sam, python, react, vite, typescript

## CDS services called at runtime

These calls are made by the deployed Lambdas.

| Service | Call | Where |
|---|---|---|
| AWS End User Messaging Social | `SendWhatsAppMessage` (text, interactive buttons/lists, documents) | `services/layer/python/common/cds.py` |
| AWS End User Messaging Social | `GetWhatsAppMessageMedia` (inbound invoice photos/PDFs) | same file |
| AWS End User Messaging Social | `PostWhatsAppMessageMedia` (upload a PDF to send as a document) | same file |
| Amazon SES v2 | `SendEmail` (login codes, chases, the LBA PDF) | same file |
| Amazon Bedrock | `Converse` (Haiku for reading/classifying/intent, Sonnet for drafting) | `services/layer/python/agent/llm.py` |

## AI disclosure

At runtime, Arrearo reasons with Anthropic Claude on Amazon Bedrock. Claude Haiku 4.5 reads invoices, classifies replies, and routes what you type to the right action. Claude Sonnet 4.5 drafts chases, Letters Before Action and digests. Amounts, dates and interest are never produced by the model. They come from the deterministic legal engine, and any invoice the agent acts on is checked against your own account. At build time, this codebase was written with AI assistance (Claude Code) under human direction. A person set the product, made the decisions, and reviewed and deployed the result.

## ACE opportunity

Net-new opportunity tagged `AWS CDS Agentic AI Hackathon -Sept. 2026` (exact string). Opportunity ID: _(record the O-prefixed id here once created or confirmed)_.
