# Recoup — AWS CDS Agentic AI Hackathon build

**Working name:** Recoup (final name pending market research; centralized in `config`).
**Mandate (Roger, overnight 2026-10-08):** research a market (US/UK), build a 9/10 real product for the AWS CDS Agentic AI hackathon — not a demo toy, something sellable for $1M+. No shortcuts. Up to 10 agents. Deploy on AWS. "No delete." Fully functional by morning, self-graded.

## The decision (made for Roger, who delegated it)
**Product: a WhatsApp-native late-payment recovery agent for UK SMEs**, on **Brownshift (854924711083), us-east-1**.

Why this clears the $1M bar:
- **Validated category** — Chaser, Satago, Kolleno are real companies worth tens of millions. Market + valuation proven, not speculative.
- **Our edge:** (1) **WhatsApp-native** — incumbents are email-only; (2) a **deterministic statutory-interest + letter-before-action legal engine** (a real moat, not an LLM guessing); (3) **debtor risk scoring from the UK payment-practices public dataset** (a genuine data asset).
- CDS-native (WhatsApp + SES + Bedrock) and matches Roger's "Brownshift = UK focus."
- The problem, in the government's words: late payment "costs the UK economy £11bn a year and shuts down 38 businesses every day" (DBT, 30 Jul 2025).

## Feasibility — verified 2026-10-08
- **Bedrock** ✅ invoke works via inference profiles: `us.anthropic.claude-sonnet-4-5-20250929-v1:0` (reasoning/drafting), `us.anthropic.claude-haiku-4-5-20251001-v1:0` (extraction/classification). Direct non-profile IDs fail — always use `us.` profiles.
- **WhatsApp** ✅ WABA `waba-fc7e800db8f4433ab28a07f47089a226` COMPLETE; phone `+233 55 906 2312`, id `phone-number-id-0d66a9b3b8fc463bb9bf999932643060`; SNS topic `arn:aws:sns:us-east-1:854924711083:brownshift-whatsapp-events`.
- **SES** ⚠️ nothing verified; `brownshift.com` is on Cloudflare (no Route 53 zone) so I can't verify it. Account is in **sandbox** (200/day). Plan: register the product's own domain in Route 53 ($16) → control DNS → verify the domain in SES → send from/to addresses at that domain. Fallback if registration validation blocks: build SES fully, disclose "DNS verification pending."
- **Compute** — App Runner capped at 2 in Brownshift us-east-1 → go **serverless** (Lambda + API Gateway + DynamoDB + EventBridge + S3/CloudFront), the correct event-driven shape anyway.
- **AWS profiles:** `default` = Brownshift (854924711083), `ses` = Kasamafo (747452892491). Build on `default`.

## Architecture (AWS serverless, us-east-1)
- **WhatsApp inbound:** existing SNS topic → Lambda webhook handler. Gotchas (from memory, do not rediscover): inbound number has no `+` (normalize to E.164); SNS payload is double-encoded (`whatsAppWebhookEntry` is JSON-in-JSON, parse twice); status events share one `messageId` (idempotent); 24h customer-service window (free-form only within 24h of last inbound, else approved template).
- **Agent Lambdas (Bedrock):** `extract` (Haiku vision → invoice fields), `classify` (reply intent: promise/dispute/not-received/paid), `draft` (Sonnet → chase message, Letter Before Action, digest).
- **Legal engine:** pure, tested Python module in a Lambda layer. Statutory interest = 8% + BoE base rate (live via BoE IUDBEDR); fixed recovery sum £40/£70/£100; lateness 30d (public)/60d (business), or 30d after invoice/goods. Compliance guardrails: Administration of Justice Act 1970 s.40 (never imply criminal proceedings, never false authority, never official-looking docs, cadence regulated); Pre-Action Protocol for Debt Claims (sole traders/individuals).
- **Debtor intelligence:** UK payment-practices dataset (`check-payment-practices.service.gov.uk/export/csv/`, ~99MB) → subset into DynamoDB/S3 → expected pay time + risk per debtor.
- **Data:** DynamoDB (businesses, invoices, debtors, conversations, events, chase-schedule). Single-table or per-entity (decide in spec).
- **Outbound CDS at runtime:** `socialmessaging:SendWhatsAppMessage` + `sesv2:SendEmail` — satisfies the hard "CDS client called at runtime" rule.
- **Scheduling:** EventBridge Scheduler — chase cadence + daily digest.
- **Dashboard:** React (Vite) static → S3 + CloudFront; API → API Gateway (HTTP API) + Lambda; auth → Cognito. Real-time invoice list, chase status, interest accruing live, replies, drafts to approve, debtor risk.
- **IaC:** AWS SAM or CDK — one deployable stack. Commit incrementally (hackathon rule: organisers read commit history).

## Judge-facing demo (~3 min, all real on AWS)
SME sends an invoice photo on WhatsApp → agent extracts + confirms + shows debtor risk → dashboard shows it, interest accruing → late date reached → agent sends the chase (WhatsApp + SES) citing amount + daily statutory interest + legal basis → a reply "I'll pay Friday" is classified + the promise tracked → debt ages → Letter Before Action drafted + emailed as PDF → morning digest.

## Hackathon hard rules (from memory)
New project in submission window; incremental commits; AWS SDK client imported + called at runtime; public repo + MIT/licence in About (or share private with testing@devpost.com + aws-cds-partner@amazon.com); ~3-min public YouTube demo; architecture diagram; README AI disclosure; each submission needs its own ACE opportunity tagged `AWS CDS Agentic AI Hackathon -Sept. 2026`.

## Agent plan (<=10)
1. Market/competitive/positioning + name+domain shortlist (research)  — RUNNING
2. CDS/AWS technical patterns + UK legal facts refresh (research)      — RUNNING
3-8. Build (after spec): legal engine+dataset · agent/Bedrock · CDS integration · infra/IaC · dashboard · (integration help)
Me: spec, data model, API contract, domain registration, integration, deploy, verify, self-grade, iterate.

## Known constraints (disclose in the README)
- **Domain:** `arrearo.com` registration FAILED — a Brownshift account-level hold on Route 53 Domains ("contact AWS Support"), not fixable tonight. App runs on CloudFront/API-GW URLs. No custom domain tonight.
- **SES:** no DNS-editable verified domain available (brownshift.com on Cloudflare; arrearo.com failed; kasamafo.africa not a Route53 zone). SES is BUILT (calls `ses:SendEmail` at runtime, degrades gracefully, emails rendered in the dashboard) but **live send is pending sender-identity verification** (owner verifies arrearo.com DNS or an email — 2 min). WhatsApp is the live channel; it satisfies the "CDS client called at runtime" requirement on its own.
- **WhatsApp first-contact:** cold outbound to a debtor needs a Meta-approved template (long-lead, not via AWS API). In-window replies are free-form and work. Demo is driven by inbound messages (the SME sends the invoice photo, opening the window).

## Status log
- 2026-10-08 ~04:3x UTC — decision made, feasibility verified, project scaffolded, 2 research agents launched.
- 2026-10-08 ~04:4x UTC — SPEC written (data model, legal-engine interface, API, IaC, demo). **Legal engine built + 23 tests green** (I own this — it's the moat). `common/config.py` written (concrete ARNs/model IDs; internal slug `recoup` stable, BRAND finalised later). Research agents producing high-rigor output (gov.uk-verified figures, botocore-validated CDS shapes). **Key finding:** UK gov announced 24 Mar 2026 the largest late-payment reforms in 25+ yrs — mandatory statutory interest 8%+base on all commercial contracts — a major tailwind. Next: fold research → finalise name → register domain → dispatch build agents (agent/Bedrock, CDS channels, infra, dashboard, debtors).
- 2026-10-08 ~05:30 UTC — **Backend deployed** (stack `arrearo`, us-east-1): 5 tables, layer, webhook/api/scheduler Lambdas, Cognito + JWT HTTP API, SNS subscription, EventBridge schedules, media + web buckets, CloudFront. 88 tests green. Smoke-tested live: auth, /invoices, webhook (Haiku classify), Sonnet chase draft, compliance block, Haiku vision extract, scheduler. Sends are in `SendMode=dry` until the owner flips it. See docs/API.md.
