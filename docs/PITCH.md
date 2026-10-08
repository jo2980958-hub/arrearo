# Arrearo: the business case

Labels: **[sourced]** means fetched from a primary source on 2026-10-08 and recorded in `research/market.md`. **[estimate]** means our arithmetic or judgement, not a fetched fact.

## One line

The credit controller that chases your late invoices on WhatsApp and adds the interest you are legally owed.

## The market

- Late payment costs the UK economy £11bn a year, and the UK government says it shuts down 38 businesses every day. **[sourced]** DBT press release, 30 July 2025. The 38 a day is a modelled estimate of about 14,000 extra closures a year.
- Over 1.5m businesses, 28% of all UK businesses, are affected each year. About £26bn is owed late at any time. The average affected business is owed about £17,000, and spends about 86 hours a year chasing. **[sourced]** DBT and London Economics research, July 2025.
- Micro firms (0 to 9 staff) have about £9,214 overdue on average, which is 4.61% of turnover. Small firms (10 to 49) have about £52,081. **[sourced]** same research.
- The law is moving our way. On 24 March 2026 the government announced its largest late-payment reforms in over 25 years: mandatory statutory interest of 8% over base rate in commercial contracts, and a 60 day cap on payment terms for large payers. **[sourced]** gov.uk. The commencement date is not confirmed, so we do not claim it is in force.
- Addressable base: roughly 1m UK B2B-invoicing SMEs. **[estimate]** If each paid £600 a year, that is a £600m annual pool. Treat it as an illustrative ceiling.

## The gap

Chaser, Satago, Kolleno and Upflow sell email, SMS, phone and letters. A text search of their home, pricing and feature pages found no mention of WhatsApp. **[sourced]** Search covered marketing pages only, so they may have it in beta.

None of them applies statutory interest inside the chase. Satago has a late payment calculator, which is a calculator, not an action. **[sourced]**

WhatsApp collection tools do exist elsewhere (Seenn, Peakflo, AblyWorks), mostly built for India, Southeast Asia and the Middle East. None we found is UK-statute aware. **[sourced, shallow search]** So we do not claim to be the first WhatsApp tool. We claim to be the UK one that knows the law.

Price is a second gap. Chaser starts at £199 a month, Kolleno at £545 to £650 per user. A micro firm with £9k overdue is priced out of both. Satago (£45 to £200) is the only incumbent at that price, and it is email and SMS. **[sourced]**

## What we built that is hard to copy

1. **WhatsApp native.** Debtors reply in the thread. Replies become structured promises and disputes.
2. **A deterministic legal engine.** Interest, late dates, fixed sums and compliance checks are tested code. The model phrases, it never decides what is owed.
3. **A debtor data asset.** Scoring from government payment-practices data now. Cross-customer payment behaviour later, with consent. **[roadmap]**

Each is copyable alone. Together they are a wedge.

## Pricing

Subscription tiers by invoice volume, GBP, excluding VAT. **[estimate, to be tested]**

| Tier | Price | For |
|---|---|---|
| Starter | £29 a month | Sole traders and micro firms. Up to 25 active overdue invoices, WhatsApp and email chasing, statutory interest |
| Growth | £79 a month | Small firms. 150 active invoices, debtor-risk scoring, promise tracking |
| Scale | £199 a month | Larger SMEs and accountants. Unlimited invoices, multi-client, Letter Before Action pack |

Why subscription: acquirers value predictable ARR. A percentage of recovered debt invites debt-collector regulation and lumpy revenue. A success fee on recovered interest only could come later, after legal advice.

The ROI line: at £20 an hour, 86 hours of chasing is £1,720 a year. Starter costs £348 a year. **[sourced hours, estimate rate]**

WhatsApp message costs are not yet modelled. Meta's UK rate card was not fetched. **[unverified]**

## The $1M+ thesis

- $1M of ARR needs about 1,400 firms at £50 a month, or 700 at £100. In a base of about 1m firms, that is 0.07% to 0.14%. **[estimate]**
- Strategic buyers have paid roughly 3x to 8x ARR for B2B SaaS. **[estimate, a heuristic and not a quote]** That puts $1M of ARR at roughly $3M to $8M.
- A $1M+ outcome is plausible at modest scale. A $10M+ outcome needs the data and network effect, or a distribution partner. Features alone will not get there.

## The exit thesis

Likely buyers, none contacted, all **[estimate]**:

- **Accounting platforms**: Xero, Sage, Intuit QuickBooks, FreeAgent. They own the SME base and the invoices. WhatsApp chasing with interest is a natural bolt-on.
- **Money movers**: GoCardless, Stripe, Tide, Starling, and invoice lenders such as iwoca and Funding Circle. "Your overdue invoices, chased and paid" is a retention feature, and the chase is a funnel into an advance on the invoice.
- **AR specialists**: Chaser, Kolleno, Upflow. A WhatsApp-native agent is a feature they could buy.
- **Credit bureaux**: Creditsafe, Experian, Equifax. Debtor behaviour data is the thing they sell.

## The path

1. UK micro and small firms, with accounting connectors and an accountant referral channel.
2. Pay-by-link in the chat, with a fee per payment collected, through a regulated payment provider. We never hold funds.
3. Invoice advance referrals, for a second revenue line without balance-sheet risk.
4. An escalation pack: Letter Before Action and a small claims bundle, sold per use.
5. A debtor-risk network across customers, designed for consent from the start.
6. Ireland and the other markets that share the law.

## Risks, plainly

- **WhatsApp opt-in and templates.** A first message to a debtor needs a Meta-approved template, and the debtor's number in the owner's contacts is not opt-in. We build around it with a click-to-WhatsApp link on every invoice. Approval is pending. **[sourced limitation]**
- **Meta policy on AI on WhatsApp.** A task-specific collections agent should fit, but the current policy text needs checking before launch. **[unverified]**
- **Regulation.** Debts owed by sole traders and consumers touch other rules, and PECR treats sole traders like individuals. Legal advice is needed before launch. **[unverified]**
- **Incumbents copy.** The answer is speed, the legal engine and the data.
