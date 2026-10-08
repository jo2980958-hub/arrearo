"""SNS-triggered WhatsApp inbound handler.

Event is triple wrapped (SNS record -> AWS header -> Meta webhook entry string).
Owner messages (a registered business number): an invoice photo or text becomes an
extracted invoice; YES confirms it; PAID marks the latest one paid.
Debtor messages (a number on an open invoice): classified, stored, timeline updated.
"""
from __future__ import annotations

import json
import logging
import os
import re

from agent import classify, extract
from common import cds, config, db, flows
from wa import inbound as wa_inbound
from wa import router as wa_router

log = logging.getLogger()
log.setLevel(logging.INFO)

MEDIA_BUCKET = os.environ.get("MEDIA_BUCKET", "")
STATUS_FOR_INTENT = {"promise_to_pay": "promised", "dispute": "disputed", "not_received": "disputed"}


def parse_sns_event(event):
    for rec in event["Records"]:
        outer = json.loads(rec["Sns"]["Message"])
        entry = outer["whatsAppWebhookEntry"]
        entry = json.loads(entry) if isinstance(entry, str) else entry
        for ch in entry.get("changes", []):
            v = ch.get("value", {})
            for m in v.get("messages", []):
                kind = m.get("type")
                media = m.get(kind) if kind in ("image", "document") else None
                yield {"kind": "message", "from": m["from"], "wamid": m["id"], "type": kind,
                       "text": (m.get("text") or {}).get("body") or (media or {}).get("caption"),
                       "media_id": (media or {}).get("id"), "mime": (media or {}).get("mime_type"),
                       "interactive": wa_inbound.extract_interactive(m),
                       "name": ((v.get("contacts") or [{}])[0].get("profile") or {}).get("name"),
                       "ts": int(m["timestamp"]), "aws_message_id": outer.get("messageId")}
            for s in v.get("statuses", []):
                conv = s.get("conversation") or {}
                yield {"kind": "status", "wamid": s["id"], "status": s["status"], "to": s.get("recipient_id"),
                       "ts": int(s["timestamp"]), "errors": s.get("errors"),
                       "window_expires_at": int(conv["expiration_timestamp"]) if conv.get("expiration_timestamp") else None}


def reply(to: str, body: str, invoice_id=None, reply_to=None):
    mid = cds.send_whatsapp_text(to, body, reply_to_wamid=reply_to)
    if cds.live():
        db.add_message(to, "out", mid, body, invoiceId=invoice_id)
    else:
        log.info("reply (dry-run) to %s: %s", to, body)
    return mid


def money(p):
    return config.gbp(p) if p is not None else "unknown"


def handle_app(m: dict, number: str) -> dict:
    """A number that is neither a registered owner nor a known debtor talks to the
    Arrearo WhatsApp app: OTP login, then menu navigation. wa.router returns a list of
    Replies (Meta message dicts); we send each with cds.send_whatsapp_raw."""
    inter = m.get("interactive") or {}
    inbound = {"text": m.get("text"), "tap_id": inter.get("id"), "tap_title": inter.get("title"),
               "media": None}
    if m.get("type") in ("image", "document") and m.get("media_id"):
        inbound["media"] = {"media_id": m["media_id"], "mime": m.get("mime"),
                            "bucket": MEDIA_BUCKET, "key": f"inbound/app/{number}/{m['media_id']}"}
    replies = wa_router.handle(number, inbound)
    ids = [cds.send_whatsapp_raw(m["from"], r) for r in replies]
    return {"wamid": m["wamid"], "role": "app", "replies": len(replies), "replyIds": ids}


def handle_owner(biz: dict, m: dict) -> str:
    if m["type"] in ("image", "document"):
        if not m.get("media_id"):
            return "I couldn't read that file. Please send a clear photo of the invoice."
        if (m.get("mime") or "") not in extract.FMT:
            return "I can read photos of invoices (JPEG or PNG). Please send one as a picture."
        key = f"inbound/{biz['businessId']}/{m['media_id']}"
        meta = cds.fetch_whatsapp_media(m["media_id"], MEDIA_BUCKET, key)
        image = cds.read_s3(MEDIA_BUCKET, key)
        fields = extract.extract_from_image(image, meta.get("mimeType") or m["mime"])
        source = {"mediaKey": key}
    elif m.get("text"):
        text = m["text"].strip()
        low = text.lower()
        pending = [i for i in db.list_invoices_by_business(biz["businessId"]) if i["status"] == "extracted"]
        if re.fullmatch(r"(yes|y|confirm|ok|correct)[.! ]*", low) and pending:
            inv = flows.confirm_invoice(pending[0]["invoiceId"], "owner", "whatsapp")
            return (f"Confirmed. I'm tracking {inv['debtorName']} for {money(inv['amountPence'])}. "
                    f"It becomes late on {inv['legallyLateDate']} and I'll chase from then.")
        if low.startswith("paid"):
            open_ = [i for i in db.list_invoices_by_business(biz["businessId"]) if i["status"] in flows.OPEN_STATUSES]
            ref = low[4:].strip()
            hit = next((i for i in open_ if ref and ref in (i.get("reference") or "").lower()), open_[0] if open_ and not ref else None)
            if hit:
                flows.mark_paid(hit["invoiceId"], "owner", "whatsapp")
                return f"Marked {hit['debtorName']} ({money(hit['amountPence'])}) as paid."
            return "Which invoice? Reply PAID followed by the invoice number."
        fields = extract.extract_from_text(text)
        if not fields["isInvoice"] or fields["amountPence"] is None:
            return ("Send me a photo of an invoice and I'll start tracking it. "
                    "Reply YES to confirm what I read, or PAID <invoice number> when you get paid.")
        source = {}
    else:
        return "Send me a photo of an invoice and I'll start tracking it."

    if not fields["debtorName"] or fields["amountPence"] is None or not fields["invoiceDate"]:
        return ("I couldn't read the "
                + ", ".join(x.replace("Pence", "").replace("debtorName", "customer name").replace("invoiceDate", "invoice date")
                            for x in fields["missingFields"])
                + ". Please send a clearer photo or type the details.")
    inv = db.create_invoice(biz["businessId"], {
        "debtorName": fields["debtorName"], "debtorType": "company", "amountPence": fields["amountPence"],
        "currency": fields["currency"], "invoiceDate": fields["invoiceDate"], "deliveryDate": fields["deliveryDate"],
        "agreedDueDate": fields["agreedDueDate"], "reference": fields["reference"],
        "description": fields["description"], "status": "extracted", "sourceChannel": "whatsapp",
        "extractionConfidence": fields["extractionConfidence"], **source})
    db.add_event(inv["invoiceId"], "created", "whatsapp", "owner", {})
    db.add_event(inv["invoiceId"], "extracted", "whatsapp", "agent",
                 {"confidence": fields["extractionConfidence"], "needsConfirmation": fields["needsConfirmation"]})
    full = db.get_invoice(inv["invoiceId"])
    warn = " I'm not fully sure about some fields, so please check them." if fields["needsConfirmation"] else ""
    return (f"I read an invoice to {full['debtorName']} for {money(full['amountPence'])}"
            f"{' (ref ' + full['reference'] + ')' if full.get('reference') else ''}, dated {full['invoiceDate']}. "
            f"It becomes legally late on {full['legallyLateDate']}.{warn} Reply YES to confirm.")


def handle_debtor(inv: dict, m: dict) -> str:
    number = m["from"]
    text = m.get("text") or ""
    biz = db.get_business(inv["businessId"])
    if not text:
        db.add_message(number, "in", m["wamid"], None, mediaId=m.get("media_id"), invoiceId=inv["invoiceId"])
        return f"Thanks. Please reply in text so {biz['name']} can read it."
    result = classify.classify_reply(text, inv)
    intent = result["intent"]
    db.add_message(number, "in", m["wamid"], text, intent=intent, invoiceId=inv["invoiceId"])
    detail = {"intent": intent, "confidence": result["confidence"], "body": text, **result["extracted"]}
    db.add_event(inv["invoiceId"], "replied", "whatsapp", "debtor", detail)
    new_status = STATUS_FOR_INTENT.get(intent)
    if new_status:
        fields = {"status": new_status}
        if result["extracted"].get("promisedDate"):
            fields["promisedDate"] = result["extracted"]["promisedDate"]
        db.update_invoice(inv["invoiceId"], fields)
        db.add_event(inv["invoiceId"], "promised" if new_status == "promised" else "disputed",
                     "whatsapp", "debtor", detail)
    if result["optOut"]:
        db.update_invoice(inv["invoiceId"], {"debtorOptOut": True})
    if result["optOut"]:
        return "Understood, we won't message you again on WhatsApp."
    if intent == "promise_to_pay":
        when = result["extracted"].get("promisedDate")
        return f"Thank you. I've noted that you'll pay{' by ' + when if when else ''}. We'll check in then."
    if intent in ("dispute", "not_received"):
        return f"Thanks for telling us. I've passed this to {biz['name']} and they'll be in touch."
    if intent == "paid":
        return f"Thanks. I've told {biz['name']} so they can check their account."
    return f"Thanks for your message. I've passed it to {biz['name']}."


def handle_message(m: dict) -> dict:
    if not db.claim_message(m["wamid"]):
        return {"wamid": m["wamid"], "skipped": "duplicate"}
    number = db.normalise_e164(m["from"])
    biz = db.get_business_by_whatsapp(number)
    if biz:
        db.add_message(number, "in", m["wamid"], m.get("text"), mediaId=m.get("media_id"))
        role, answer = "owner", handle_owner(biz, m)
        inv_id = None
    else:
        open_ = db.list_open_invoices_by_debtor_whatsapp(number)
        if not open_:
            return handle_app(m, number)   # not an owner or debtor: the WhatsApp app (login + menu)
        role, answer, inv_id = "debtor", handle_debtor(open_[0], m), open_[0]["invoiceId"]
    mid = reply(m["from"], answer, inv_id, reply_to=m["wamid"])
    return {"wamid": m["wamid"], "role": role, "reply": answer, "replyId": mid}


def handler(event, context=None):
    results = []
    for item in parse_sns_event(event):
        try:
            if item["kind"] == "message":
                results.append(handle_message(item))
            else:
                log.info("status %s %s", item["status"], item["wamid"])
                if item["status"] == "failed":
                    log.warning("delivery failed: %s", item.get("errors"))
        except Exception:   # noqa: BLE001 - one bad message must not poison the batch, nor trigger SNS retries
            log.exception("failed handling %s", item.get("wamid"))
            results.append({"wamid": item.get("wamid"), "error": True})
    log.info("webhook results: %s", json.dumps(results))
    return {"results": results}
