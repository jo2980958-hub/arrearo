# Recoup market research: WhatsApp-native late-payment recovery for UK SMEs

Compiled 2026-10-08. Evidence labels used throughout:
- **[FETCHED]** pulled live with curl on 2026-10-08 (URL given)
- **[TRAINING]** from model knowledge, not verified tonight. Treat as a lead, not a fact.
- **[UNVERIFIED]** could not confirm; do not put in a pitch deck without checking

---

## 1. Market size and pain (UK late payment)

### 1.1 Government figures, verified
| Claim | Source | Status |
|---|---|---|
| Late payment costs the UK economy **£11bn a year** and shuts down **38 businesses every day** | DBT/Business Secretary press release "Time to pay up: Toughest crackdown on late payments in a generation unveiled...", published 30 Jul 2025. https://www.gov.uk/government/news/time-to-pay-up-toughest-crackdown-on-late-payments-in-a-generation-unveiled-in-plan-to-back-small-businesses | **[FETCHED]** exact wording confirmed via gov.uk content API |
| Same figures repeated: "£11 billion every year", "38 businesses shut their doors every single day... 266 a week" | Press release 24 Mar 2026 "Time to Pay Up: Government unveils toughest crackdown on late payments in over 25 years". https://www.gov.uk/government/news/time-to-pay-up-government-unveils-toughest-crackdown-on-late-payments-in-over-25-years | **[FETCHED]** |
| £11bn a year, shown as headline stat | Small Business Commissioner homepage, https://www.smallbusinesscommissioner.gov.uk/ | **[FETCHED]** |
| SMEs employ 60% of the workforce and generate £2.8 trillion turnover | Same 30 Jul 2025 release | **[FETCHED]** |

Caveat: the "38 a day" figure is a government headline. The release does not cite a methodology in the text I read. Quote it as "the UK government says", not as our own finding.

### 1.2 The law is moving in our favour (this is the product's regulatory tailwind)
All **[FETCHED]** from the 24 Mar 2026 release unless noted.
- Largest late-payment reforms in 25+ years, building on the Late Payment of Commercial Debt (Interest) Act 1998.
- **Mandatory statutory interest**: all commercial contracts must include statutory interest at **8% above Bank of England base rate**. Today, interest is a right most firms never claim; the reform makes it a default.
- **60-day cap** on payment terms when large firms pay smaller suppliers. The Jul 2025 release said the cap would later reduce to 45 days.
- Small Business Commissioner gets powers to investigate, adjudicate disputes and fine; fines "tens of millions" for persistent offenders.
- Worked example from the government: £10,000 owed, paid 60 days late = **£10,293.15** (£10,000 + **£193.15 interest** + **£100 compensation**). That £100 is the fixed-sum compensation for a debt of £10,000 or more.
- Boards/audit committees of persistently late large payers must publish explanations.
- Existing rules **[FETCHED]** https://www.gov.uk/late-commercial-payments-interest-debt-recovery/charging-interest-commercial-debt : statutory interest is 8% plus base rate for B2B.
- Fixed compensation tiers (£40 under £1,000; £70 for £1,000 to £9,999.99; £100 for £10,000+) are **[TRAINING]**, consistent with the £100 in the government example. The fetched gov.uk page did not return them through my text extraction.
- Exact commencement date of the new law: **[UNVERIFIED]**. Check the bill's status before claiming "in force".

Product implication: the interest calculation becomes a compliance-grade feature, not a nice-to-have. Most owners do not know they can claim, so "we add what you are legally owed" is a concrete money-back hook.

### 1.3 Per-SME amounts and % paid late, VERIFIED from the DBT primary research
Source: DBT / London Economics, "Late payments research: estimating the economic cost of late payments and their impact on the UK economy", July 2025 (YouGov/IFF survey, roughly 1,450 businesses; plus DBT Business Population Estimates 2024). PDF: https://assets.publishing.service.gov.uk/media/688a089a6478525675738ff9/late_payments_research_impact_on_uk_economy.pdf and infographic https://assets.publishing.service.gov.uk/media/68652e8f6569be0acf74db3e/late-payments-infographic.pdf . **[FETCHED and read via pdftotext]**

- This is where "38 a day" comes from: **about 14,000 additional business closures a year** attributable to late payment (against about 330,000 total closures in 2023), "equivalent to 38 every day". It is a modelled (econometric) estimate, not a count of insolvencies filed.
- **Over 1.5m businesses, 28% of all UK businesses, are affected by late payment each year.**
- **About £26bn** is owed in late payments at any given time: an interest-free loan to customers.
- **Average £17,085 per affected business** (about £17k).

By size class (average value currently overdue, among affected businesses):
| Size | Avg overdue, affected firms | As % of annual turnover |
|---|---|---|
| Micro (0-9 staff) | **£9,214** | **4.61%** |
| Small (10-49) | **£52,081** | 1.47% |
| Medium (50-249) | £193,635 | 0.79% |
| Large (250+) | £703,479 | 0.23% |

Share of businesses with a current late-payment problem (overdue invoices and/or terms over 60 days, YouGov/IFF Table 1): **20% of micro, 42% of small, 51% of medium, 67% of large** ("no issues": 80% / 58% / 49% / 33%).
- Share of outstanding invoices that are late, by value: about 10.9% (micro), 16.5% (small), 12.0% (medium), 12.2% (large). Read from chart text, approximate.
- **Staff time chasing**: 22% of surveyed firms spent staff time chasing; **about 86 hours a year per affected business, about 133m hours economy-wide.**
- 15% of surveyed firms said they avoided doing business with specific customers because of payment behaviour.
- Only about 47.6% of micro firms offer trade credit at all (LSBS, cited in the report), so the addressable base is B2B invoicers, not all micro firms.

**FSB "% of small businesses paid late"**: FSB page is JS-rendered and returned nothing. **[UNVERIFIED]**. Use the DBT numbers above; they are a government primary source with a methodology.

Product implication: the sweet spot is the **micro firm with about £9k overdue that is 4.6% of turnover** and the **small (10-49) firm with about £52k overdue**. For a micro firm, 4.6% of turnover stuck in late invoices is existential, so a £30 to £100/mo tool has an obvious ROI case.

### 1.4 Sizing sketch (our arithmetic, flagged as assumption)
- UK private sector business count is about 5.5 to 5.6m, of which about 99% are small (<50 staff) **[TRAINING]**; roughly 1.4m are employers **[TRAINING]**. Check against the DBT "Business population estimates" release.
- B2B-invoicing SMEs with accounting software: I estimate 1 to 1.5m. Xero alone reports 1m+ UK subscribers **[TRAINING]**.
- If a serviceable 1m firms paid an average £600/yr, that would be a £600m annual revenue pool. Treat this as an illustrative ceiling, not a forecast.

---

## 2. Competitors

Evidence key as above. Pricing and channel claims marked **[FETCHED]** come from the vendors' own live pricing/product pages on 2026-10-08. Funding and valuation figures are **[TRAINING]/[UNVERIFIED]** because Crunchbase blocks curl (Cloudflare 403) and search engines were rate-limited; check before use.

### 2.1 The incumbents the brief listed

| Vendor | What it does | Price (UK) | Channels | Funding / exit |
|---|---|---|---|---|
| **Chaser** (chaser.io) | Automated credit control and AR for SMB/mid-market. Xero/QuickBooks/Sage/Dynamics integrations, chasing workflows, payment portal, payment plans, a done-for-you "Chaser Care" collections service. Positions on cutting DSO ("75% or more") **[FETCHED]** | **Compact from £199/mo (£179 annual)**; **Core from £599/mo (£539 annual)**; **Complete from £899/mo (£809 annual)**; Compact+Care from £899/mo. Core has 4 users, 30 follow-up templates, 4 automated workflows. **[FETCHED]** https://www.chaser.io/pricing | **Email, SMS, automated phone calls, letters. No WhatsApp mention anywhere on the site.** **[FETCHED]** (JSON-LD: "via email, SMS, phone, and letters") | UK/Australia roots, large Xero-marketplace presence (reviews quoted from Xero). Funding history and any ownership change: **[UNVERIFIED]** |
| **Satago** (satago.com) | Credit-risk insights + credit control + embedded invoice finance, sold direct and via accountants and brokers. Late-payment calculator included **[FETCHED]** | **Basic £45/mo** (25 credit reports, 100 email reminders); **Premium £80/mo** (unlimited email, 100 SMS, card payments, BNPL); **Platinum £200/mo** (1,000 SMS, account manager). Accountant plans £50 and £80/mo. **[FETCHED]** https://www.satago.com/pricing | **Email + SMS.** No WhatsApp on the pricing or product pages **[FETCHED]** | UK; business model is partly invoice finance. Funding/owners: **[UNVERIFIED]** |
| **Kolleno** (kolleno.com) | London-based AR/order-to-cash platform now pitching "AI Agents" that run collections and reconciliation. Credit risk, disputes, e-invoicing, 9+ integrations **[FETCHED]** | **£650 per user/month for >£1M-turnover firms** (promo shown £545); **£1,245 per user/month for >£10M** (promo £995); Enterprise custom. Tiers include 100 to 600 SMS and calls. **[FETCHED]** https://kolleno.com/pricing | Email, **SMS, calls**; payment links. No WhatsApp on pricing/home page **[FETCHED]** | Raised venture funding (amounts **[UNVERIFIED]**) |
| **Chaserpay** | Appears to be **Chaser Pay**, Chaser's payment portal/payment product, not a separate company. chaserpay.com did not resolve (HTTP 000). **[FETCHED]** the "Chaser Pay / Payment portal / Payment plans" nav on chaser.io | Part of Chaser's tiers | n/a | n/a |
| **Quipu Pay** | **Not a competitor.** quipupay.com is a Spanish POS product ("El POS que revoluciona tu negocio"). **[FETCHED]** If the brief meant a different "Quipu", I could not identify it. | n/a | n/a | n/a |
| **Upflow** (upflow.io) | Paris-founded AR platform: collections, payment portal, AI agents, 2-way Gmail/Outlook sync. Aimed at US/EU mid-market **[FETCHED]** | **Quote only**, banded by invoiced revenue: Starter up to $10M, Grow $25M, Scale $50M, Accelerate $100M, Enterprise $100M+. No public £ price. **[FETCHED]** https://www.upflow.io/pricing | "Emails, SMS, calls, letters, tasks." Email unlimited; **SMS and calls on a usage fee**. No WhatsApp mention **[FETCHED]** | VC-backed; round sizes **[UNVERIFIED]** |

**Channel finding (the headline for the gap)**: across Chaser, Satago, Kolleno and Upflow, a text search for "WhatsApp" on home, pricing and feature pages returned **zero hits**. Their channel stack is email, SMS, phone, letter. So "the UK-focused incumbents do not offer WhatsApp" is **[FETCHED]-supported** as of today. Caveat: I searched marketing pages only; they may have it in beta or via integrations.

**Price-point finding**: incumbents are bifurcated. Satago (£45 to £200) is the only one with a genuinely micro-business price, and its credit control is email/SMS-led with a finance upsell. Chaser starts at about £180 to £200/mo and Kolleno at £545 to £650 per user, so a firm with £9k overdue (the DBT micro average) is priced out of everything except Satago. That is an open band at £25 to £99/mo.

### 2.2 WhatsApp-based AR tools that DO exist (important: the gap is not "nobody does WhatsApp")
All **[FETCHED]** (vendor marketing pages, fetched 2026-10-08; claims are the vendors' own):
- **Seenn** (seenn.ai): "AI accounts-receivable agent that collects overdue invoices on WhatsApp"; its agent "Jess" also phones debtors in a human-sounding voice and sends invoices/ledger cards from the accounting system. Hebrew UI toggle, so Israel-origin. Closest to our concept; not UK-statute aware as far as the page shows.
- **Peakflo** (blog.peakflo.co): automated WhatsApp messages in an AR platform; Asia-Pacific/India-origin **[TRAINING]**.
- **AblyWorks Remind**: email + WhatsApp reminders, AI follow-ups that record payment promises; integrates Tally, Zoho Books, QuickBooks. India-origin.
- **Zoye** and **AutoInvoiced**: generic small-business WhatsApp automation and billing tools; Zoye's blog is a content play (WhatsApp reminder cadence). AutoInvoiced's "top 5" blog is self-ranked marketing.
- Others in results: WaBulkSend (bulk messaging), an open-source GitHub "billing-ai" WhatsApp-first AR project.

Reading: WhatsApp for payment chasing is a known tactic, mostly sold in India, SE Asia, Middle East, LatAm. **None found is UK-statute-aware or UK-accounting-stack-first**, but my search was shallow (one search engine, one pass). Do not claim "first WhatsApp AR product"; claim "first UK-compliant, statute-aware one" and verify it more before pitching.

### 2.3 Other UK-relevant players **[TRAINING], unverified tonight**
- Accounting-suite built-ins: Xero, QuickBooks, FreeAgent, Sage send email invoice reminders. They are the real "free" competitor; none does WhatsApp natively as far as I know.
- Credit data and collections: Creditsafe, Experian, Equifax, Dun & Bradstreet (data, not chasing); debt-collection agencies and solicitors (letters before action, % fees).
- Invoice finance: Satago (above), Funding Circle, iwoca, MarketFinance, high-street banks. Stenn (invoice finance) went into administration in late 2024, a reminder that financing-led models carry balance-sheet risk. Check details before citing.
- Payments rails: GoCardless (UK, Direct Debit), Stripe, TrueLayer/Yapily (open banking pay-by-bank). These are partners, not competitors.

### 2.4 The precise gap we exploit
Three things bundled; each alone is copyable, together they are a wedge:
1. **WhatsApp-native conversation, not email/SMS.** Debtors reply in-thread ("paid yesterday", "send the invoice again", "can I pay half Friday"). The agent turns replies into structured promise-to-pay dates and disputes, and writes them back to the ledger. Seenn-like tools show demand but are not UK/Xero-first.
2. **Automatic statutory interest and compensation.** The law is 8% over base rate plus fixed-sum compensation, and the new regime makes it mandatory in contracts **[FETCHED]**. No competitor page surfaced it except Satago's "late payment calculator" (a calculator, not an applied-in-message feature). We compute and add it to the chase automatically ("You owe £10,293.15, which includes £193.15 interest and £100 compensation"), the government's own worked example.
3. **Debtor risk from the public dataset.** The government "Check when large businesses pay their suppliers" service publishes payment-practices reports (https://check-payment-practices.service.gov.uk/ **[FETCHED]**, page returns 200; the bulk download URL guessed did not exist, so the data access route is **[UNVERIFIED]**: confirm whether there is a CSV/API before building on it). Also available: Companies House API (needs a free API key; returned 401 without one **[FETCHED]**) for status, filing lateness, insolvency flags. That lets the agent triage who to push, who to escalate, and who is likely insolvent (stop chasing, file a proof of debt).

What it is not: not a credit-control suite for finance teams; no ERP breadth; no phone dialler.

Price-and-size wedge: serve the **micro and small (under 50 staff)** firm that Chaser/Kolleno/Upflow price out and Satago under-serves on channel.

### 2.5 Risks to the gap
- **Meta policy and cost.** **[FETCHED]** from business.whatsapp.com pricing page: pricing is per message by category and market; service messages are free; utility messages sent in reply to a user are free. Business-initiated payment reminders are templated and billed. UK rates vary: look up the published rate card before setting margins. Whether a chase counts as "utility" or "marketing" is Meta's call on template review, **[UNVERIFIED]**.
- **Opt-in.** WhatsApp requires opt-in before business-initiated messages **[TRAINING]**. The debtor's number is in the creditor's contacts, not an opt-in. Workaround to build into the product: a click-to-WhatsApp link/QR on every invoice and a one-time email "get reminders and pay by WhatsApp". Once the debtor messages first, a 24-hour free service window opens.
- **Meta's AI-on-WhatsApp rules.** Meta changed the Business API terms in 2025 to restrict general-purpose AI chatbots on the platform, effective early 2026 **[TRAINING]**. A task-specific collections agent should be inside the rules, but confirm the current policy text before launch.
- **PECR/UK GDPR.** B2B messages to companies are lightly restricted; to sole traders and partnerships they are treated like individuals **[TRAINING]**. Get legal advice before launch.
- **Regulation of collection.** Chasing commercial debt in the creditor's name is generally not a regulated activity, but debts owed by sole traders and consumers touch FCA/CCA-style rules, and holding client money is regulated **[TRAINING]**. Route payments through a regulated PSP (GoCardless, Stripe, open banking); never hold funds.

---

## 3. Positioning and exit thesis

### 3.1 One-line positioning (pick one)
- **Sharpest:** "The credit controller that chases your late invoices on WhatsApp and adds the interest you're legally owed."
- Alternative: "Get paid on WhatsApp, with the statutory interest already added."
- Pitch-to-acquirer version: "UK SME receivables conversations, captured at the point customers actually reply."

Why this works: it names the channel (what competitors lack), the outcome (cash), and a legal hook (interest) that makes the product feel like an agent with authority, not a nagging bot. The 24 Mar 2026 release's worked example makes a clean demo: "owed £10,000, 60 days late, claim £10,293.15".

### 3.2 Who realistically buys it (all **[TRAINING]**, verify specifics)
Tier A, accounting platforms (distribution + a gap in their roadmap):
- **Xero**: acquisitive (Planday, Waddle for invoice finance, Hubdoc, Syft, Lapsed, and the Melio deal announced 2025 at about $2.5bn). It has the SME base and a payments push; WhatsApp reminders on top of Xero invoices is a natural bolt-on.
- **Sage**: UK-based, SME-focused, buys small fintech add-ons.
- **Intuit/QuickBooks**: strong in payments and invoicing; UK is secondary but material.
- **FreeAgent** (NatWest-owned) and **Zoho**: smaller, but the buy-vs-build math favours buying.

Tier B, money movers (collect and finance on the back of the chase):
- **GoCardless**, **Stripe**, **Tide**, **Starling**, **Allica**, **Mettle/NatWest**: all need SME engagement surfaces; "your overdue invoices, chased and paid" is a retention feature.
- **Invoice-finance and lenders** (iwoca, Funding Circle, MarketFinance, Lloyds/Barclays commercial finance, Satago): a chasing agent gives data and a conversion funnel into "advance on this invoice".
- **Credit bureaux** (Creditsafe, Experian, Equifax, D&B): data-led chasing as a product layer.

Tier C, AR specialists (consolidation): Chaser, Kolleno, Upflow, Billtrust/HighRadius/Esker. A WhatsApp-native agent is a feature they would pay to add. These would likely be acqui-hire-priced.

### 3.3 Why it is worth $1M+, honestly
- Mechanical: at B2B SaaS multiples, **$1M ARR is worth roughly $3M to $8M** to a strategic **[TRAINING heuristic, not a quote]**. Hitting $1M ARR needs about 1,400 paying firms at £50/mo (£840k/yr) or 700 at £100/mo. In an addressable group of about 1m UK B2B-invoicing SMEs **[our estimate]**, that is 0.07% to 0.14% penetration.
- The 2026 reform wave is the forcing event: mandatory interest and 60-day caps make "apply the law automatically" a product category, not a feature. Competitors have a calculator; we make it the default action.
- Data asset: the longer it runs, the more it knows about who pays and when, per debtor and sector, from the payments of many creditors (network effect on debtor risk). That is what makes an acquirer pay above ARR multiples.
- **A $1M+ sale is plausible at modest scale. A $10M+ outcome needs the data/network effect or a distribution partner, not features.**

### 3.4 Path beyond
1. UK micro/small via Xero/QuickBooks/Sage connectors, accountant referral channel (Satago and Chaser both run partner programs, which proves the route).
2. Add pay-by-bank/Direct Debit link in the chat (GoCardless/TrueLayer): take a fee per payment collected.
3. Add invoice-advance referral (lender pays a bounty): second revenue line without balance-sheet risk.
4. Escalation module: auto-generated Letter Before Action and small-claims (MCOL) pack; sell as a per-use upsell.
5. Debtor-risk network: a score derived from payment behaviour across tenants plus Companies House and payment-practices data (consent and data-protection design needed up front).
6. Markets with the same law and WhatsApp habits: Ireland, then the EU Late Payment Directive countries; WhatsApp-heavy markets (India, UAE, Brazil) are a separate play where Peakflo/Seenn-type rivals already exist.

---

## 4. Pricing model recommendation

### 4.1 Recommendation: SaaS tiers by invoice volume, plus pay-per-use pass-through for WhatsApp and a small success fee only on collected-by-us payments
Why subscription as the base:
- Predictable ARR is what acquirers value; usage-only revenue is discounted.
- Competitors anchor monthly: Satago £45/£80/£200, Chaser from £179 to £809, Kolleno £545 to £995 per user **[FETCHED]**. A flat tier slots into the market's mental model.
- A pure **% of recovered** model is attractive to SMEs but (a) invites "debt collector" regulation and reputation risk, (b) makes revenue lumpy and attributable disputes (did we recover it or did they pay anyway?), (c) cuts against acquirers' ARR math.
- Pure **per-invoice** pricing penalises the heavy chaser and is hard to forecast for the buyer.

### 4.2 Proposed tiers (GBP, ex-VAT; rough, to be tested)
| Tier | Price | Who | Includes |
|---|---|---|---|
| **Starter** | **£29/mo** | Sole traders, micro (under 10 staff) | 1 accounting connection, up to 25 active overdue invoices, WhatsApp + email chasing, statutory-interest calculation, 100 WhatsApp template sends included |
| **Growth** | **£79/mo** | Small firms (10-49) | 150 active invoices, debtor-risk scoring (Companies House + payment-practices data), promise-to-pay tracking, 500 sends, pay-by-link |
| **Scale** | **£199/mo** | Larger SMEs, accountants (multi-client) | Unlimited active invoices, multi-entity/client, letter-before-action pack, 2,000 sends, priority support |
| Add-ons | usage | all | WhatsApp sends beyond bundle at cost plus margin; payment collection fee (e.g. 0.5% to 1% plus PSP fee) on payments taken in-thread |

Rationale for the numbers:
- ROI line: micro firm with about £9.2k overdue (DBT) and 86 hours/yr wasted chasing across affected firms **[FETCHED]**. At even £20/hr, 86 hours is £1,720/yr of time, versus £348/yr for Starter.
- Underprices Chaser's entry plan (about £179 to £199) by roughly 60% to 85% across Starter and Growth. Against Satago (£45 / £80 / £200) it is near parity (Starter below Basic, Growth about equal to Premium); our differentiation there is WhatsApp plus applied statutory interest, not price.
- Margin check: WhatsApp utility/marketing rates per message vary; assume a few pence per UK template send **[UNVERIFIED, look up the rate card]**. 100 included sends would cost on the order of £2 to £8; compute the real figure before shipping.
- Accountant channel: wholesale price (e.g. 30% off for 10+ clients) gets distribution at low CAC.

### 4.3 Success fee: optional, later
A "we get paid when you do" plan (e.g. 3% to 5% of statutory interest and compensation we recovered, never on principal) is aligned and a good headline for sceptical SMEs, but test after the subscription base exists. Take legal advice on whether it changes the regulatory character of the service.

---

## 5. Product name shortlist

Method: for every candidate I ran a live registry lookup tonight. **.com** via Verisign RDAP (HTTP 404 = not registered), **.co.uk** via Nominet RDAP (404 = not registered). Both are **[FETCHED]**, but an unregistered status can still hide a premium-priced or reserved name: confirm at a registrar. Trademark: I could not search UKIPO/EUIPO (JS-only), so every "TM clash" note is **[TRAINING]**/judgement and must be checked in UKIPO, EUIPO, and USPTO class 36 (financial) and 9/42 (software) before spending on a brand.

**Working name "Recoup"**: recoup.com and recoup.co.uk are both registered **[FETCHED]**, getrecoup.com, recoupai.com, recouped.com, recoupr.com also taken. The word is generic and heavily used; assume a crowded mark and no clean domain. Keep it as a codename, not the brand.

| # | Name | Rationale | .com / .co.uk (tonight) | Trademark note |
|---|---|---|---|---|
| 1 | **Dunmate** | "Dun" is the old verb for demanding payment (dunning); "mate" is warm British shorthand. Right tone for a WhatsApp chaser that stays friendly | .com free, .co.uk free | Check "Dun*" marks; Dun & Bradstreet owns "Dun"-prefixed marks in credit information, so class 36 clash risk with D&B is real. Moderate |
| 2 | **Arrearo** | Coined from "arrears"; short, brandable, no meaning in other languages that I know of | .com free, .co.uk free | "Arrears" is descriptive, but "Arrearo" is distinctive; check for existing "Arrow*" marks in finance (phonetic similarity to Arrow). Low-moderate |
| 3 | **Recoupwise** | Keeps the "Recoup" meaning with a competence suffix; clean domains | .com free, .co.uk free | Exposed to prior "Recoup" marks in class 36; moderate |
| 4 | **Quidback** | "Quid" is UK slang for pound; says exactly what you get ("your quid back") | .com free, **.co.uk taken** | Quid-prefixed financial marks (e.g. Quidco, Quid*) are common; plain-English, may be weak for enterprise buyers. Moderate-high |
| 5 | **Sterlr** | "Sterling" shortened; pound-coded, modern | .com free, .co.uk free | "Sterling" marks are crowded in finance; weak spelling is easy to mistype. High |
| 6 | **Acquitpay** | "Acquit" is the legal sense of discharging a debt | .com free, .co.uk free | Sounds legal/courtroom to some; low clash I know of |
| 7 | **Owedwise** | Plain: knows what you are owed | .com free, .co.uk free | Descriptive and bland; moderate |
| 8 | **Paidbell** | Notification-style: the bell that rings when you're paid | .com free, .co.uk free | Low clash; weakest on "professional" |
| 9 | **Quidhound** | A hound that tracks down the money | .com free, .co.uk free | Playful, memorable; poor for enterprise credibility; "Quid*" risk |
| 10 | **Squarely** (use squarelyhq.com) | "Settling up squarely"; clean word | squarely.com not checked, squarelyhq.com free | A dictionary word, so the plain .com is likely taken; "Squarely" is probably used elsewhere. High |

Taken (do not pursue, checked tonight, `.com` registered): recoup, duely, paidup, paidwell, settld, settlr, remitt, dunning, dunly, dunnit, dunwell, owed, owedly, owedhq, paidly, paidnow, promptly, prompt-pay, payprompt, repaid, repayd, reclaimed, ledgerly, tallyup, evenly, evenup, squared, squareup, clearpay, cleary, chasr, chasely, nudgepay, quittance (quittanceai.com is free).

### Ranking, top 3
1. **Dunmate**: friendliest and most on-message for a WhatsApp-native chaser; distinctive; both domains free. Biggest risk is a Dun & Bradstreet trademark objection in class 36, so run the search first.
2. **Arrearo**: the most "ownable" coined word, reads like a fintech, and both domains are free; best fit if the exit target is a bank or accounting platform.
3. **Recoupwise**: lowest-effort rename from the working title, descriptive for SEO; trade-off is a weaker, more crowded mark.

If trademark search kills #1 and #2, the memorable fallback is **Quidback** (accept the .co.uk gap, or use quidback.co or similar).

---

## Appendix: what I fetched vs. what is training knowledge

**Fetched live (2026-10-08):** gov.uk press releases of 30 Jul 2025 and 24 Mar 2026 via the gov.uk content API; DBT/London Economics research PDF (Jul 2025) and infographic; SBC homepage (£11bn); gov.uk statutory interest page (8% + base); Chaser, Satago, Kolleno, Upflow pricing and feature pages; chaser.io/about nav; quipupay.com; Meta WhatsApp Business pricing page (partial); Seenn, AblyWorks, Zoye, AutoInvoiced pages; Verisign and Nominet RDAP.

**Not obtainable / unverified:** competitor funding and valuation (Crunchbase 403, search rate-limited); FSB "% paid late"; FSB page; payment-practices bulk data URL; UK WhatsApp usage statistics (Ofcom page returned nothing); UKIPO/EUIPO trademarks; Meta UK rate card; commencement date of the new late payment law; exact Meta AI-chatbot policy text.

**Training-knowledge items to verify before external use:** acquirer deal history (Xero/Melio and others), invoice-finance market events (Stenn), fixed compensation tiers (£40/£70/£100), PECR sole-trader treatment, FCA scope of commercial debt chasing, Meta opt-in and AI-chatbot rules, SaaS valuation multiples.
