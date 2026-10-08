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

Serverless on AWS, one SAM stack. WhatsApp comes in through AWS End User Messaging Social to an SNS topic that triggers a Lambda. A number that is not a registered owner or a known debtor enters the WhatsApp app: a login state machine, then a router that maps taps, commands and free text to the right screen or action. Free text that is not a command goes to Claude Haiku 4.5 on Amazon Bedrock, which picks the action; Claude Haiku also reads invoices and classifies replies, and Claude Sonnet 4.5 drafts chases, letters and digests. A deterministic legal engine computes every figure. Documents are rendered to PDF by a small pure-Python renderer and sent as WhatsApp documents via AWS End User Messaging media upload, or by email through Amazon SES. The dashboard is React and Vite on S3 and CloudFront, behind an API Gateway HTTP API with a Cognito authorizer. Data is in DynamoDB; EventBridge Scheduler runs the due sweep and the morning digest.

The part we care about most is that the money and the law are not left to the model. Interest at 8% over the Bank of England base rate, the fixed sum, the late dates and the compliance checks are plain tested code. Claude decides where you want to go and phrases the messages. It never decides what you owe.

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
