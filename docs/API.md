# Arrearo API (deployed contract)

Base URL: `https://hppo19gaaf.execute-api.us-east-1.amazonaws.com`. JSON. Money is integer pence.
Auth: Cognito ID token (or access token) in `Authorization: Bearer <token>`. Pool `us-east-1_msvFwkml2`, client `27i88lcsa2upc3pg821o7bo9ag` (no secret; flows USER_PASSWORD_AUTH, USER_SRP_AUTH). CORS is open (`*`). `GET /health` needs no token.
Errors: `{"error": "..."}` with 400/401/404/405/409/422/500; a compliance block is 422 with `violations[]` and `draft`.

Derived fields on every invoice (computed by the legal engine at read time): `daysLate, statutoryRatePct, baseRatePct, dailyInterestPence, interestAccruedPence, fixedRecoverySumPence, totalOwedPence, legallyLateDate`.

| Route | Body / notes | Returns |
|---|---|---|
| `GET /me` | | `{user, business \| null, brand, statutoryRatePct, baseRatePct}` |
| `PUT /me` | onboarding: `name` (required on create), `ownerName, email, whatsappNumber, sector, defaultTermsDays, bankName, bankSortCode, bankAccount` | `{business}` |
| `GET /invoices?status=` | newest first | `{invoices[], summary{outstandingPence, interestAccruedPence, fixedRecoverySumPence, totalOwedPence, dailyInterestPence, openCount, overdueCount, paidCount}}` |
| `POST /invoices` | `debtorName, amountPence (int), invoiceDate` required; `debtorType` (company\|sole_trader\|individual\|public_authority), `debtorCompanyNumber, debtorEmail, debtorWhatsapp, deliveryDate, agreedDueDate, reference, description` | 201 `{invoice}` (status `confirmed`) |
| `GET /invoices/{id}` | | `{invoice, debtor \| null, events[], messages[]}` |
| `PATCH /invoices/{id}` | any invoice field above and/or `status` (`confirmed` and `paid` also write timeline events), `promisedDate` | `{invoice}` |
| `POST /invoices/{id}/chase` | `{mode: "draft"\|"send", message?, stage?, channel?}`. `draft` returns the agent text to approve/edit; `send` sends `message` (or a fresh draft) after the compliance scan | `{draft{stage,channel,message}, sent, dryRun?, messageId?}` |
| `POST /invoices/{id}/lba` | `{mode: "draft"\|"send", text?}` | `{text, protocol{...Pre-Action checklist}, sent, dryRun?}`; send emails the text plus a PDF |
| `GET /invoices/{id}/events` | audit timeline | `{events[]}` |
| `GET /debtors/{key}` | companyNumber or lower-cased name | `{debtor}`; unknown companies return `riskBand: "unknown"`, never a guess |

Send mode: the stack parameter `SendMode` is `dry` by default. In dry mode `send` returns `sent:false, dryRun:true` and nothing leaves AWS or is recorded as sent. Deploy with `infra/deploy.sh SendMode=live` to turn real WhatsApp/SES sends on.
