# Arrearo — Additional information (Devpost)

Paste into the Devpost "Additional info" / eligibility fields as needed.

## AWS CDS services used (the hackathon requirement)
Made by the deployed Lambdas at runtime, not by a script:
- **AWS End User Messaging Social (WhatsApp)** — `SendWhatsAppMessage` (text, interactive buttons and lists), `GetWhatsAppMessageMedia` (inbound invoice photos / PDFs into S3), `PostWhatsAppMessageMedia` (send a PDF as a WhatsApp document).
- **Amazon SES v2** — `SendEmail` for login one-time codes, email chases, and the Letter Before Action PDF attachment.

## Other AWS services
Amazon Bedrock (Anthropic Claude Haiku 4.5 + Sonnet 4.5), AWS Lambda, Amazon DynamoDB, Amazon API Gateway (HTTP API), Amazon Cognito, Amazon SNS, Amazon EventBridge Scheduler, Amazon S3, Amazon CloudFront, AWS SAM. One stack, region us-east-1.

## How to test it (for judges)
- **Live dashboard:** https://d9gwfmvszoiw2.cloudfront.net — sign in with the demo credentials provided on the Devpost submission.
- **Live API:** https://hppo19gaaf.execute-api.us-east-1.amazonaws.com
- **WhatsApp:** message the agent number from the submission, tap **Log in**, use the demo email; a one-time code is emailed, then the full app is available in chat (add an invoice by photo, ask what you are owed, draft a chase, request a PDF).
- **Repo:** https://github.com/jo2980958-hub/arrearo — `pytest` runs 165 tests (moto for DynamoDB, botocore Stubber for the exact WhatsApp/SES request shapes, a fake Bedrock for the agent logic).

## AI tools disclosure
- **At runtime,** Arrearo reasons with Anthropic Claude on Amazon Bedrock: Haiku 4.5 reads invoices, classifies replies and routes the WhatsApp app; Sonnet 4.5 drafts chases, Letters Before Action and digests. Amounts, dates and statutory interest are never produced by the model; they come from a deterministic, tested legal engine, and any invoice the agent acts on is re-scoped to the signed-in business.
- **At build time,** the codebase was written with AI assistance (Claude Code) under human direction. A person set the product, made the decisions, and reviewed and deployed the result.

## Notes for judges
- Money is computed in integer pence; statutory interest is 8% over the Bank of England base rate selected by the debt's overdue reference date (SI 2002/1675), with the fixed recovery sum on top. Every draft is scanned for prohibited wording (Administration of Justice Act 1970 s.40) and checked that the required figures appear before it can send.
- `SendMode` defaults to dry; the deployed stack runs live (real WhatsApp and SES sends confirmed). SES is in sandbox, so live email recipients are verified addresses.

## Licence
MIT (see LICENSE in the repo).
