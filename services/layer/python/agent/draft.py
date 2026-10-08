"""Sonnet drafting: chase, Letter Before Action, owner digest.

The model phrases; it never computes. Every figure is injected from the legal
engine as a fact, and every draft must (a) quote those figures verbatim and
(b) pass legal.engine.compliance_scan. One re-draft on a violation, then
ComplianceBlock is raised so the caller blocks the send and logs it.
"""
from __future__ import annotations

from typing import Optional

from agent import llm
from common import config
from legal import engine

STAGES = ("reminder", "first_chase", "second_chase", "final_notice")
TONE = {
    "reminder": "friendly and brief; assume an oversight",
    "first_chase": "polite but clear; payment is now overdue and statutory interest is running",
    "second_chase": "firm and professional; reference the earlier message",
    "final_notice": "formal and direct; say that unless payment or a reply arrives within 7 days the business may "
                    "consider recovering the debt through the courts. Do not threaten anything else",
}
RULES = (
    "Hard rules: use ONLY the figures in FACTS, copied exactly, never calculate or round. Never imply criminal "
    "proceedings, the police, fraud, arrest, bailiffs, or any official or government authority. Do not use the words "
    "criminal, police, fraud, prosecution, bailiff, summons, warrant, writ or CCJ. Never style the message as a court "
    "or official document. Write as the business, in the first person plural. British English. No markdown."
)


class ComplianceBlock(Exception):
    def __init__(self, violations, text):
        self.violations, self.text = violations, text
        super().__init__("; ".join(f"{v.message} [{v.span}]" for v in violations))


def facts_for(invoice: dict, business: dict, debtor: Optional[dict] = None) -> dict:
    """The numbers and identities a draft may cite. `invoice` must carry derived fields."""
    interest_applies = invoice.get("debtorType") != "individual"   # the 1998 Act covers commercial debts
    f = {
        "business": business.get("name"),
        "debtor": invoice.get("debtorName"),
        "invoiceReference": invoice.get("reference"),
        "forWhat": invoice.get("description"),
        "invoiceDate": invoice.get("invoiceDate"),
        "dueDate": invoice.get("agreedDueDate") or invoice.get("legallyLateDate"),
        "originalAmount": config.gbp(invoice["amountPence"]),
        "daysLate": invoice.get("daysLate", 0),
    }
    if interest_applies:
        f.update({
            "statutoryRate": f"{invoice['statutoryRatePct']:.2f}% a year (8% plus Bank of England base rate "
                             f"{invoice['baseRatePct']:.2f}%)",
            "interestPerDay": f"£{invoice['dailyInterestPence'] / 100:.4f}".rstrip("0"),
            "interestSoFar": config.gbp(invoice["interestAccruedPence"]),
            "fixedRecoverySum": config.gbp(invoice["fixedRecoverySumPence"]),
            "totalNowOwed": config.gbp(invoice["totalOwedPence"]),
            "legalBasis": "Late Payment of Commercial Debts (Interest) Act 1998",
        })
    else:
        f["totalNowOwed"] = config.gbp(invoice["amountPence"])
    if business.get("bankAccount"):
        f["payTo"] = (f"{business.get('bankName', 'bank')}, sort code {business.get('bankSortCode')}, "
                      f"account {business.get('bankAccount')}")
    if debtor and debtor.get("source") == "payment-practices" and debtor.get("avgDaysToPay"):
        f["debtorPaymentRecord"] = f"reports an average of {debtor['avgDaysToPay']} days to pay suppliers"
    return f


def _must_cite(facts: dict, text: str, keys=("totalNowOwed", "originalAmount")) -> list:
    missing = [facts[k] for k in keys if k in facts and facts[k] not in text]
    return [engine.Violation(code="facts", message="draft omits a required figure", span=m) for m in missing]


def _guarded(system: str, prompt: str, facts: dict, cite_keys, max_tokens=900) -> str:
    text = llm.converse_text(config.BEDROCK_REASONING_MODEL, system, prompt, max_tokens)
    problems = engine.compliance_scan(text) + _must_cite(facts, text, cite_keys)
    if problems:
        retry = (prompt + "\n\nYour previous draft was rejected for: "
                 + "; ".join(f"{p.message} ({p.span})" for p in problems)
                 + ". Rewrite it fixing exactly that, quoting the figures from FACTS exactly.")
        text = llm.converse_text(config.BEDROCK_REASONING_MODEL, system, retry, max_tokens)
        problems = engine.compliance_scan(text) + _must_cite(facts, text, cite_keys)
        if problems:
            raise ComplianceBlock(problems, text)
    return text


def draft_chase(invoice: dict, business: dict, debtor: Optional[dict] = None, stage: str = "first_chase",
                channel: str = "whatsapp") -> str:
    facts = facts_for(invoice, business, debtor)
    system = (f"You write payment chasers for a UK small business. {RULES}")
    length = "under 120 words, plain text suitable for WhatsApp" if channel == "whatsapp" else "under 200 words"
    prompt = (f"Write a {channel} message to {facts['debtor']} chasing an overdue invoice. Stage: {stage}. "
              f"Tone: {TONE.get(stage, TONE['first_chase'])}. Length: {length}. "
              "State the original amount, the daily statutory interest, the interest so far, the fixed recovery sum, "
              "the total now owed and the legal basis, then how to pay and ask for a reply with a payment date.\n"
              f"FACTS: {facts}")
    return _guarded(system, prompt, facts, ("totalNowOwed", "originalAmount"))


def draft_lba(invoice: dict, business: dict, debtor: Optional[dict] = None) -> dict:
    """Letter Before Action text plus the Pre-Action Protocol checklist."""
    facts = facts_for(invoice, business, debtor)
    fields = engine.lba_required_fields(invoice, business, debtor or {})
    system = f"You write Letters Before Action for a UK small business. {RULES}"
    prompt = (f"Write a formal Letter Before Action to {facts['debtor']}. Include: the creditor and debtor names, "
              "the invoice reference and what it was for, the original amount, interest accrued and the daily rate, "
              "the fixed recovery sum, the total owed, how to pay, and a final payment deadline of "
              f"{fields['reply_period_days']} days from the date of the letter. State that if payment is not made "
              "the business may start a county court claim. "
              + ("Say the debtor can ask for a statement of account and that an Information Sheet and Reply Form "
                 "are enclosed. " if fields["protocol_applies"] else "")
              + "Plain text, letter format with 'Dear ...' and 'Yours sincerely'.\n"
              f"FACTS: {facts}")
    return {"text": _guarded(system, prompt, facts, ("totalNowOwed", "originalAmount"), 1400), "protocol": fields}


def draft_digest(business: dict, invoices: list[dict]) -> str:
    """Owner's morning digest. Totals are summed here, in code."""
    open_ = [i for i in invoices if i.get("status") not in ("paid", "extracted")]
    late = [i for i in open_ if i.get("daysLate", 0) > 0]
    facts = {
        "business": business.get("name"),
        "openInvoices": len(open_),
        "overdueInvoices": len(late),
        "totalOutstanding": config.gbp(sum(i["amountPence"] for i in open_)),
        "interestAccruedSoFar": config.gbp(sum(i["interestAccruedPence"] for i in late)),
        "totalIncludingInterest": config.gbp(sum(i["totalOwedPence"] for i in open_)),
        "needsAttention": [
            {"debtor": i["debtorName"], "reference": i.get("reference"), "status": i["status"],
             "daysLate": i["daysLate"], "totalOwed": config.gbp(i["totalOwedPence"])}
            for i in sorted(late, key=lambda x: -x["totalOwedPence"])[:5]],
    }
    system = f"You write a short morning summary for a small-business owner about their unpaid invoices. {RULES}"
    prompt = ("Write the morning digest for the owner: friendly, under 120 words, plain text for WhatsApp. "
              "Lead with the total outstanding and interest accrued, then the invoices needing attention, "
              f"then one suggested next step.\nFACTS: {facts}")
    return _guarded(system, prompt, facts, ("totalOutstanding",), 600)
