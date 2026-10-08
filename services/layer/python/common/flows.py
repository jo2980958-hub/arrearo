"""Business flows shared by the api, webhook and scheduler Lambdas.

Every outbound message here goes: engine facts -> Sonnet draft -> compliance scan
-> cds wrapper. A blocked draft is logged as a compliance_block event and never sent.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from agent import draft as drafter
from common import cds, config, db
from legal import engine

log = logging.getLogger(__name__)

OPEN_STATUSES = ("confirmed", "due", "chasing", "promised", "disputed", "lba", "escalated")
CHASEABLE = ("confirmed", "due", "chasing", "promised")
STAGE_BY_PRIOR_CHASES = {0: "first_chase", 1: "second_chase"}


def score_debtor(invoice: dict) -> dict:
    """Look the debtor up in the cached payment-practices table. Unknown stays unknown."""
    key = db.debtor_key(invoice["debtorName"], invoice.get("debtorCompanyNumber"))
    debtor = db.get_debtor(key)
    if not debtor and invoice.get("debtorCompanyNumber") is None:
        debtor = None
    detail = ({"riskBand": debtor.get("riskBand"), "avgDaysToPay": debtor.get("avgDaysToPay"),
               "source": debtor.get("source")} if debtor else {"riskBand": "unknown", "source": "unknown"})
    db.add_event(invoice["invoiceId"], "debtor_scored", "system", "agent", detail)
    return debtor or {"riskBand": "unknown", "source": "unknown"}


def confirm_invoice(invoice_id: str, actor: str = "owner", channel: str = "system") -> dict:
    inv = db.update_invoice(invoice_id, {"status": "confirmed", "confirmedAt": db.now_iso()})
    db.add_event(invoice_id, "confirmed", channel, actor, {})
    score_debtor(inv)
    return db.get_invoice(invoice_id)


def mark_paid(invoice_id: str, actor: str = "owner", channel: str = "system") -> dict:
    db.update_invoice(invoice_id, {"status": "paid", "paidAt": db.now_iso()})
    db.add_event(invoice_id, "paid", channel, actor, {})
    return db.get_invoice(invoice_id)


def last_chase_at(invoice_id: str) -> Optional[datetime]:
    sent = [e for e in db.list_events(invoice_id) if e["type"] == "chased" and e["detail"].get("sent")]
    return datetime.fromisoformat(sent[-1]["createdAt"].replace("Z", "+00:00")) if sent else None


def prior_chases(invoice_id: str) -> int:
    return sum(1 for e in db.list_events(invoice_id) if e["type"] == "chased" and e["detail"].get("sent"))


def choose_stage(invoice: dict) -> str:
    if invoice.get("daysLate", 0) <= 0:
        return "reminder"
    return STAGE_BY_PRIOR_CHASES.get(prior_chases(invoice["invoiceId"]), "final_notice")


def pick_channel(invoice: dict) -> Optional[str]:
    """WhatsApp only inside the 24h window (templates are not approved yet); else email."""
    if invoice.get("debtorWhatsapp") and db.window_open(invoice["debtorWhatsapp"]):
        return "whatsapp"
    if invoice.get("debtorEmail"):
        return "email"
    return None


def draft_chase_for(invoice_id: str, stage: Optional[str] = None, channel: Optional[str] = None) -> dict:
    """Draft only (the dashboard shows it for approve/edit/send). Raises ComplianceBlock."""
    inv = db.get_invoice(invoice_id)
    biz = db.get_business(inv["businessId"])
    debtor = db.get_debtor(db.debtor_key(inv["debtorName"], inv.get("debtorCompanyNumber")))
    stage = stage or choose_stage(inv)
    channel = channel or pick_channel(inv) or "email"
    try:
        text = drafter.draft_chase(inv, biz, debtor, stage, channel)
    except drafter.ComplianceBlock as blocked:
        db.add_event(invoice_id, "compliance_block", channel, "agent",
                     {"violations": [{"message": v.message, "span": v.span} for v in blocked.violations],
                      "stage": stage})
        raise
    return {"stage": stage, "channel": channel, "message": text}


def send_chase(invoice_id: str, message: str, stage: str, channel: str, actor: str = "agent") -> dict:
    """Send an (already drafted or owner-edited) chase. Re-scans the text first."""
    violations = engine.compliance_scan(message)
    if violations:
        db.add_event(invoice_id, "compliance_block", channel, actor,
                     {"violations": [{"message": v.message, "span": v.span} for v in violations], "stage": stage})
        raise drafter.ComplianceBlock(violations, message)
    inv = db.get_invoice(invoice_id)
    biz = db.get_business(inv["businessId"])
    if not engine.can_contact_now(last_chase_at(invoice_id), datetime.now(timezone.utc), stage):
        return {"sent": False, "reason": "too_soon", "stage": stage, "channel": channel}
    if channel == "whatsapp":
        mid = cds.send_whatsapp_text(inv["debtorWhatsapp"], message)
        if cds.live():
            db.add_message(inv["debtorWhatsapp"], "out", mid, message, invoiceId=invoice_id)
    else:
        subject = f"Overdue invoice {inv.get('reference') or ''} from {biz['name']}".strip()
        mid = cds.send_email(inv["debtorEmail"], subject, message, reply_to=biz.get("email"))
    sent = cds.live()
    if sent:
        db.update_invoice(invoice_id, {"status": "chasing"})
        db.add_event(invoice_id, "chased", channel, actor,
                     {"sent": True, "stage": stage, "messageId": mid, "message": message,
                      "totalOwedPence": inv["totalOwedPence"]})
    return {"sent": sent, "dryRun": not sent, "messageId": mid, "stage": stage, "channel": channel}


def chase_invoice(invoice_id: str, actor: str = "agent") -> dict:
    inv = db.get_invoice(invoice_id)
    stage = choose_stage(inv)
    if not engine.can_contact_now(last_chase_at(invoice_id), datetime.now(timezone.utc), stage):
        return {"sent": False, "reason": "too_soon"}
    d = draft_chase_for(invoice_id, stage)
    if d["channel"] == "email" and not inv.get("debtorEmail"):
        return {"sent": False, "reason": "no_channel", **d}
    return {**send_chase(invoice_id, d["message"], d["stage"], d["channel"], actor), "message": d["message"]}


def send_lba(invoice_id: str, text: Optional[str] = None, actor: str = "owner") -> dict:
    """Draft (or take the owner's edited) LBA, scan it, email it with the PDF."""
    from common import documents
    inv = db.get_invoice(invoice_id)
    biz = db.get_business(inv["businessId"])
    debtor = db.get_debtor(db.debtor_key(inv["debtorName"], inv.get("debtorCompanyNumber")))
    if text is None:
        try:
            d = drafter.draft_lba(inv, biz, debtor)
        except drafter.ComplianceBlock as blocked:
            db.add_event(invoice_id, "compliance_block", "email", "agent",
                         {"violations": [{"message": v.message, "span": v.span} for v in blocked.violations],
                          "stage": "lba"})
            raise
        text, protocol = d["text"], d["protocol"]
    else:
        violations = engine.compliance_scan(text)
        if violations:
            db.add_event(invoice_id, "compliance_block", "email", actor,
                         {"violations": [{"message": v.message, "span": v.span} for v in violations], "stage": "lba"})
            raise drafter.ComplianceBlock(violations, text)
        protocol = engine.lba_required_fields(inv, biz, debtor or {})
    db.add_event(invoice_id, "lba_drafted", "system", "agent", {"protocol": protocol, "text": text})
    if not inv.get("debtorEmail"):
        return {"sent": False, "reason": "no_email", "text": text, "protocol": protocol}
    pdf_bytes = documents.lba_pdf(biz, inv, text)
    mid = cds.send_email(inv["debtorEmail"], f"Letter Before Action: {biz['name']} / invoice {inv.get('reference') or ''}".strip(),
                         "Please find our Letter Before Action attached. The full text is below.\n\n" + text,
                         attachment={"filename": "Letter-Before-Action.pdf", "content": pdf_bytes,
                                     "content_type": "application/pdf"},
                         reply_to=biz.get("email"))
    sent = cds.live()
    if sent:
        db.update_invoice(invoice_id, {"status": "lba"})
        db.add_event(invoice_id, "lba_sent", "email", actor, {"messageId": mid, "to": inv["debtorEmail"]})
    return {"sent": sent, "dryRun": not sent, "messageId": mid, "text": text, "protocol": protocol}


def portfolio_summary(invoices: list[dict]) -> dict:
    open_ = [i for i in invoices if i.get("status") in OPEN_STATUSES]
    overdue = [i for i in open_ if i.get("daysLate", 0) > 0]
    return {
        "outstandingPence": sum(i["amountPence"] for i in open_),
        "interestAccruedPence": sum(i["interestAccruedPence"] for i in open_),
        "fixedRecoverySumPence": sum(i["fixedRecoverySumPence"] for i in open_),
        "totalOwedPence": sum(i["totalOwedPence"] for i in open_),
        "dailyInterestPence": round(sum(i["dailyInterestPence"] for i in overdue), 4),
        "openCount": len(open_),
        "overdueCount": len(overdue),
        "paidCount": sum(1 for i in invoices if i.get("status") == "paid"),
        "currency": config.CURRENCY,
    }
