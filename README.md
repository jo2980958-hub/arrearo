# Arrearo

Run your credit control from WhatsApp. The owner sends an invoice photo; Claude reads it
into fields, a deterministic legal engine works out when the debt is legally late and the
statutory interest it carries, and the agent drafts a compliance-checked chase the owner
approves before it sends. Built for the AWS CDS Agentic AI Hackathon on AWS serverless,
one SAM stack, Claude on Amazon Bedrock.

| | |
|---|---|
| Dashboard | https://d9gwfmvszoiw2.cloudfront.net |
| API | https://hppo19gaaf.execute-api.us-east-1.amazonaws.com |

## What it does

- Add an invoice by sending a photo, a PDF, or typing it; Claude reads it and you confirm.
- See what you are owed and the statutory interest building each day.
- Chase late payers with a message that cites the exact figures and the 1998 Act, after you approve it.
- Escalate aged debts with a Letter Before Action, checked against the Pre-Action Protocol and emailed as a PDF.
- Run all of it by natural language in WhatsApp, or from the web dashboard.

## Architecture

![Arrearo architecture](submission/architecture.png)

Three Python 3.12 Lambdas share one layer: `arrearo-webhook` (WhatsApp inbound via SNS, and
the in-WhatsApp app), `arrearo-api` (the dashboard HTTP API behind API Gateway + Cognito),
and `arrearo-scheduler` (EventBridge: an hourly sweep and the 08:00 digest). The shared
layer holds the **deterministic legal engine** — it computes money, statutory interest and
compliance in tested Python. Claude only reads invoices/replies and phrases messages; it
never decides a figure, and any invoice it touches is re-checked against the caller's own
account. Six DynamoDB tables (money as integer pence, derived figures recomputed on read);
the dashboard is a React + Vite build on S3 + CloudFront.

**CDS services at runtime** (made by the deployed Lambdas; all in `services/layer/python/common/cds.py` and `agent/llm.py`):

| Service | Call |
|---|---|
| End User Messaging Social | `SendWhatsAppMessage`, `GetWhatsAppMessageMedia`, `PostWhatsAppMessageMedia` |
| Amazon SES v2 | `SendEmail` (OTP codes, email chases, the LBA attachment) |
| Amazon Bedrock | `Converse` — Claude Haiku (read/classify/route), Claude Sonnet (draft) |

## Run it

```bash
infra/deploy.sh                      # build + deploy (sends stay dry)
infra/deploy.sh SendMode=live        # turn real WhatsApp + SES sends on
python infra/seed.py --sub <cognito-user-sub> --email owner@arrearo.com
cd web && npm install && npm run build
aws s3 sync dist/ s3://<WebBucket>/ --delete
aws cloudfront create-invalidation --distribution-id <WebDistributionId> --paths '/*'
```

## Tests

```bash
pytest          # 165 tests: pytest + moto (DynamoDB), botocore Stubber (exact CDS request shapes), a fake Bedrock
```

## Repository layout

```
infra/       SAM template, deploy script, seed
services/    functions (webhook, api, scheduler), layer (legal, agent, common, wa), debtors, tests
web/         React + Vite dashboard
submission/  architecture diagram and images
```

## Licence

MIT. See [LICENSE](LICENSE).
