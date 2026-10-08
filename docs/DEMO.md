# Arrearo demo: a three minute walkthrough

For judges. Everything below runs on the deployed stack in AWS account 854924711083, us-east-1.

- Dashboard: https://d9gwfmvszoiw2.cloudfront.net
- Login: `owner@arrearo.com` / `Arrearo-Demo-7391!Kq`
- WhatsApp: +233 55 906 2312

## The story

Sam Hartley runs Hartley & Finch Joinery. Customers pay late. Sam does not have time to chase, and does not know the law adds interest. Arrearo does it from WhatsApp.

## Script

### 0:00 Open on the problem (15 seconds)

Say: "The UK government says late payment costs the economy £11bn a year. The average affected business is owed about £17,000, and spends about 86 hours a year chasing it."

### 0:15 Sam WhatsApps an invoice photo (30 seconds)

1. From the owner's phone, send a photo of an invoice to +233 55 906 2312.
2. Arrearo replies within seconds. Expected shape: "I read an invoice to Northfield Catering Ltd for £480.00 (ref HF-2291), dated ... It becomes legally late on ... Reply YES to confirm."
3. Reply YES. Arrearo confirms it is tracking the invoice and says when it will start chasing.

What is happening: the SNS event reaches the webhook Lambda. It calls `GetWhatsAppMessageMedia`, sends the image to Claude Haiku 4.5 on Bedrock, and the legal engine works out the late date.

### 0:45 The dashboard (45 seconds)

1. Open the dashboard and sign in.
2. Overview: outstanding total, interest accruing, overdue count.
3. Invoices: the table shows status, amount, days late, total owed and debtor risk.
4. Open **Mercer Plant Hire Ltd**, invoice HF-2177.
   - Amount: £8,600.00
   - 80 days late
   - Statutory rate: 11.75% a year (8% over the 3.75% base rate)
   - Interest accrued: £221.48
   - Fixed recovery sum: £70.00
   - **Total owed: £8,891.48**
5. Point at the legal basis on the page and the timeline: created, extracted, confirmed, scored, chased, chased, chased.
6. Open **Biffa Waste Services Limited**. Show the debtor risk panel, drawn from the government payment-practices data. Say that an unknown debtor shows as unknown.

### 1:30 The chase cites the law (30 seconds)

1. On the Mercer invoice, choose to chase. Pick "draft".
2. The message appears for approval. It states the original amount, the interest per day, the running total of £8,891.48, and the legal basis: the Late Payment of Commercial Debts (Interest) Act 1998.
3. Say: "Claude wrote the words. The numbers came from the legal engine. If the draft implied court or criminal action, the compliance scan would block it."
4. Send it. Say what happens in this deployment: it is in dry mode, so the response shows `dryRun: true` and nothing leaves AWS.

### 2:00 A reply is classified (25 seconds)

1. From the debtor's number, with an open invoice against it, reply: "Sorry, will pay Friday."
2. Arrearo answers the debtor and records the intent as `promise_to_pay` with the promised date.
3. Refresh the dashboard. The timeline shows the reply and the promise. Status is now promised.

This path needs the debtor's number to be on an invoice and the 24 hour window to be open, which the inbound message does.

### 2:25 The Letter Before Action (25 seconds)

1. Back on Mercer, choose Letter Before Action, draft.
2. Show the letter text and the Pre-Action Protocol checklist alongside it.
3. Say: "Approving sends this by email with a PDF attached, through SES."

### 2:50 The digest (10 seconds)

Say: "Every morning at 08:00 London time, EventBridge triggers the scheduler and Sam gets a summary of who owes what and what Arrearo did." Close on the positioning: get paid on WhatsApp, with the statutory interest already added.

## What is live and what is disclosed as pending

| Step | Status |
|---|---|
| WhatsApp in: invoice photo, YES, PAID | Live |
| Bedrock extraction and classification | Live |
| Legal engine, interest, fixed sum, compliance scan | Live |
| Dashboard, Cognito login, API | Live |
| Debtor risk from payment-practices subset | Live, 400 companies |
| WhatsApp replies inside the 24 hour window | Live |
| Chase and LBA drafts | Live |
| Chase sending | Dry by default (`SendMode=dry`). Flip with `infra/deploy.sh SendMode=live` |
| WhatsApp first contact to a debtor | Pending: needs a Meta-approved template |
| SES email delivery | Built and called at runtime. Pending sender identity verification, and the account is in the SES sandbox |
| Custom domain `arrearo.com` | Pending: blocked by an AWS account hold on Route 53 Domains |

Seeded invoices (Northfield, Biffa, Redcliffe, Mercer) come from `infra/seed.py`. The Mercer figures above are the engine's output for that seed on the day it was written. The day count rises each day, and so does the interest.
