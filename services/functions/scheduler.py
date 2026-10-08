"""EventBridge Scheduler targets: hourly due-sweep and the daily owner digest."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from agent import draft as drafter
from common import cds, db, flows
from legal import engine

log = logging.getLogger()
log.setLevel(logging.INFO)


def due_sweep() -> dict:
    """confirmed -> due on the due date; chase anything late whose cadence allows.
    In dry mode nothing is written or sent: the report says what would happen."""
    live = cds.live()
    report = {"live": live, "due": [], "chased": [], "skipped": [], "blocked": []}
    for biz in db.list_businesses():
        for inv in db.list_invoices_by_business(biz["businessId"]):
            if inv["status"] not in ("confirmed", "due", "chasing"):
                continue
            iid = inv["invoiceId"]
            due_on = date.fromisoformat(inv["legallyLateDate"]) - timedelta(days=1)
            if datetime.now(timezone.utc).date() < due_on or inv.get("debtorOptOut"):
                continue
            if inv["status"] == "confirmed":
                report["due"].append(iid)
                if live:
                    db.update_invoice(iid, {"status": "due"})
                    db.add_event(iid, "due", "system", "system", {})
            if not live:
                report["skipped"].append({"invoiceId": iid, "reason": "dry-run", "stage": flows.choose_stage(inv)})
                continue
            try:
                r = flows.chase_invoice(iid)
                (report["chased"] if r.get("sent") else report["skipped"]).append({"invoiceId": iid, **{k: r.get(k) for k in ("reason", "stage", "channel")}})
            except drafter.ComplianceBlock:
                report["blocked"].append(iid)
            except Exception:   # noqa: BLE001
                log.exception("chase failed for %s", iid)
                report["skipped"].append({"invoiceId": iid, "reason": "error"})
    return report


def daily_digest() -> dict:
    sent = []
    for biz in db.list_businesses():
        invoices = db.list_invoices_by_business(biz["businessId"])
        if not any(i["status"] in flows.OPEN_STATUSES for i in invoices):
            continue
        try:
            text = drafter.draft_digest(biz, invoices)
        except drafter.ComplianceBlock:
            log.warning("digest blocked for %s", biz["businessId"])
            continue
        via = "whatsapp" if biz.get("whatsappNumber") and db.window_open(biz["whatsappNumber"]) else "email"
        if via == "whatsapp":
            cds.send_whatsapp_text(biz["whatsappNumber"], text)
        elif biz.get("email"):
            cds.send_email(biz["email"], f"Your {datetime.now(timezone.utc):%d %b} payments digest", text)
        else:
            continue
        db.add_event(f"business#{biz['businessId']}", "digest", via, "agent", {"sent": cds.live(), "text": text})
        sent.append({"businessId": biz["businessId"], "via": via, "sent": cds.live()})
    return {"digests": sent}


def selfcheck() -> dict:
    """Diagnostic: does this runtime's boto3 know the CDS operations we call?"""
    import boto3
    sm = boto3.client("socialmessaging", region_name="us-east-1")
    ses = boto3.client("sesv2", region_name="us-east-1")
    attach = "Attachments" in ses.meta.service_model.shape_for("SimpleEmailContent").members \
        if "SimpleEmailContent" in ses.meta.service_model.shape_names else \
        "Attachments" in ses.meta.service_model.shape_for("Message").members
    return {"boto3": boto3.__version__,
            "send_whatsapp_message": hasattr(sm, "send_whatsapp_message"),
            "get_whatsapp_message_media": hasattr(sm, "get_whatsapp_message_media"),
            "ses_simple_attachments": attach, "send_mode": "live" if cds.live() else "dry"}


def handler(event, context=None):
    task = (event or {}).get("task", "due_sweep")
    if task == "selfcheck":
        return selfcheck()
    out = daily_digest() if task == "digest" else due_sweep()
    log.info("scheduler %s: %s", task, out)
    return out
