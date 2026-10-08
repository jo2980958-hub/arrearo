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
