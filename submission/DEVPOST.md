# Arrearo — Devpost submission

Paste-ready copy for the Devpost form. Fill the three links at the top once the repo is public, the video is up, and the ACE opportunity exists.

| Field | Value |
|---|---|
| Public repo | _(GitHub URL once pushed)_ |
| Demo video (~3 min) | _(YouTube/Vimeo URL)_ |
| Live app | https://d9gwfmvszoiw2.cloudfront.net |
| Try it | Login `owner@arrearo.com` / `Arrearo-Demo-7391!Kq` · WhatsApp +233 55 906 2312 |
| AWS account | 854924711083 (Brownshift), us-east-1 |

## Name

Arrearo

## Elevator pitch (one line)

The credit controller that chases your late invoices on WhatsApp and adds the interest you are legally owed.

## Inspiration

Late payment is a tax on small businesses that nobody votes for. The UK government says it costs the economy £11bn a year and shuts 38 businesses a day. The average affected firm is owed about £17,000 and loses about 86 hours a year chasing it, usually the owner, at night. Two things stood out to us. Owners chase on email, where debtors ignore them. And almost none of them know the law already lets them add interest and a fixed sum to a late commercial debt. So we built the thing that chases on the channel people actually read, and that knows the law they are not using.

## What it does

The owner sends a photo of an invoice to Arrearo on WhatsApp. An agent reads it, confirms what it read, and tracks it. When the debt goes late, Arrearo works out the statutory interest and the fixed recovery sum, and chases the debtor with the exact figures and the legal basis. Replies are understood: a promise to pay is tracked, a dispute stops the chasing and escalates, "never got it" triggers a resend. Debts that age get a Letter Before Action, drafted against the Pre-Action Protocol and emailed. Every morning the owner gets a digest. A dashboard shows every invoice, the interest ticking up, and a risk score for each debtor drawn from public payment data.

## How we built it

Serverless on AWS, one SAM stack. WhatsApp comes in through AWS End User Messaging Social to an SNS topic, which triggers a Lambda. That Lambda reads the invoice photo with Claude Haiku 4.5 on Amazon Bedrock, runs a deterministic legal engine, and writes to DynamoDB. A second Lambda serves the dashboard API behind an Amazon API Gateway HTTP API with a Cognito JWT authorizer. A third runs on Amazon EventBridge Scheduler for the due sweep and the morning digest. Claude Sonnet 4.5 drafts the messages. Amazon SES sends email and the Letter Before Action PDF. The dashboard is React and Vite on S3 and CloudFront.

The part we care about most is the legal engine. It is plain, tested Python. It computes interest at 8% over the Bank of England base rate in whole pence, the fixed sum of £40, £70 or £100, and the date a debt becomes legally late. It also scans every draft and blocks anything that implies criminal proceedings, false authority or an official document, which the Administration of Justice Act 1970 section 40 makes an offence. The language model phrases the facts. It never decides what is owed.

## Challenges we ran into

Cold outbound on WhatsApp needs a Meta-approved template, and approval is a long-lead step outside the AWS API, so first contact to a debtor is not something we could switch on in the build window. Replies inside the 24 hour window work, so the demo is driven by inbound messages. Registering our domain failed on an account-level hold at Route 53, so the app runs on its CloudFront and API Gateway URLs and SES sends from a verified sender on another domain we control. A CORS preflight was hitting the JWT authorizer and failing until we added an unauthorized OPTIONS route. We disclose all of this in the README rather than hide it.

## Accomplishments we are proud of

It is a real, deployed product, not a slide. Three CDS and AWS services are called at runtime by the Lambdas, not by a script: WhatsApp send and media fetch, SES send, and Bedrock. SES has been proven with a live send and a returned MessageId. The legal engine has 26 tests and the backend 88. The debtor data is real, built from the UK government payment-practices dataset.

## What we learned

The agent is only trustworthy because the money and the law are not left to it. Pulling every number and every compliance rule out of the model and into tested code is what makes a collections agent safe to point at a real debtor.

## What's next

A Meta-approved template for first contact. Pay-by-link in the chat through a regulated provider, so we never hold funds. Accounting connectors for Xero and Sage. A debtor-risk network across customers, designed for consent from the start.

## Built with

aws, aws-lambda, amazon-bedrock, claude, anthropic, aws-end-user-messaging, whatsapp, amazon-ses, amazon-dynamodb, amazon-sns, amazon-eventbridge, amazon-cognito, amazon-api-gateway, amazon-s3, amazon-cloudfront, aws-sam, python, react, vite, typescript

## CDS services called at runtime

| Service | Call | Where |
|---|---|---|
| AWS End User Messaging Social | `SendWhatsAppMessage` | `send_whatsapp_text()` in `services/layer/python/common/cds.py` |
| AWS End User Messaging Social | `GetWhatsAppMessageMedia` | `fetch_whatsapp_media()` in the same file |
| Amazon SES v2 | `SendEmail` | `send_email()` in the same file |
| Amazon Bedrock | `Converse` | `services/layer/python/agent/llm.py` |

## AI disclosure

At runtime, Arrearo reasons with Anthropic Claude on Amazon Bedrock. Claude Haiku 4.5 reads invoices and classifies replies. Claude Sonnet 4.5 drafts chases, Letters Before Action and digests. Amounts, dates and interest are never produced by the model. They come from the deterministic legal engine. At build time, this codebase was written with AI assistance (Claude Code) under human direction. A person set the product, made the decisions, and reviewed and deployed the result.

## ACE opportunity

Net-new opportunity tagged `AWS CDS Agentic AI Hackathon -Sept. 2026` (exact string). Opportunity ID: _(record the O-prefixed id here once created or confirmed)_.
