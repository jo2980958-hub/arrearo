"""Write actions over WhatsApp, each returning a Reply (or list).

Thin wrappers over common.flows and agent.extract that add the WhatsApp draft ->
Approve/Cancel interaction. Every action re-checks the invoice belongs to business_id.
Depends on common.flows, common.db, common.cds, common.config, agent.draft,
agent.extract, wa.messages.
Contract fixed by the spec — agent fills the bodies.
"""
from __future__ import annotations

import re
from typing import Optional

from agent import draft as drafter
from agent import extract
from common import cds, config, db, flows
from wa import messages

NOT_FOUND = "I couldn't find that invoice."

# Business fields editable from WhatsApp (parity with the web dashboard).
BUSINESS_FIELDS = {"name", "email", "bankName", "bankSortCode", "bankAccount", "ownerName", "address"}
_BUSINESS_LABEL = {"name": "business name", "email": "email", "bankName": "bank name",
                   "bankSortCode": "sort code", "bankAccount": "account number",
                   "ownerName": "owner name", "address": "address"}
INVOICE_FIELDS = {"debtorName", "invoiceDate", "agreedDueDate", "reference", "description",
                  "debtorEmail", "debtorWhatsapp"}


def _pounds_to_pence(value) -> Optional[int]:
    s = re.sub(r"[^0-9.]", "", str(value))
    try:
        return round(float(s) * 100) if s else None
    except ValueError:
        return None


def update_business(business_id: str, field: str, value: str) -> dict:
    """Edit a business detail (name, email, bank, owner, address). Web parity."""
    if field not in BUSINESS_FIELDS or not value:
        return messages.text("I can't change that here. Try, for example, "
                             "'update business name to Brownshift Technologies UK'.")
    if not db.get_business(business_id):
        return messages.text("I couldn't load your business.")
    db.update_business(business_id, {field: str(value).strip()})
    return messages.text(f"Done. Your {_BUSINESS_LABEL.get(field, field)} is now {str(value).strip()}.")


def edit_invoice(business_id: str, invoice_id: str, field: str, value: str) -> dict:
    """Edit a field on an invoice (amount, customer, dates, reference, etc.). Web parity."""
    inv = _owned(business_id, invoice_id)
    if inv is None:
        return messages.text(NOT_FOUND)
    if field == "amountPence":
        pence = _pounds_to_pence(value)
        if pence is None:
            return messages.text("I couldn't read that amount. Try 'set the amount to 9000'.")
        db.update_invoice(invoice_id, {"amountPence": pence})
        up = db.get_invoice(invoice_id)
        return messages.text(f"Updated. {up.get('debtorName')} is now {config.gbp(up['amountPence'])}, "
                             f"total owed {config.gbp(up['totalOwedPence'])}.")
    if field in INVOICE_FIELDS and value:
        db.update_invoice(invoice_id, {field: str(value).strip()})
        up = db.get_invoice(invoice_id)
        return messages.text(f"Updated. {up.get('debtorName')} invoice, {field} is now {str(value).strip()}.")
    return messages.text("I can't change that field. You can edit amount, customer, dates, reference "
                         "or description.")


def create_from_text(business_id: str, text: str) -> dict:
    """Create an invoice from a typed description, e.g. 'add invoice for Acme Ltd, 1200, 2026-09-01'."""
    fields = extract.extract_from_text(text)
    if not fields.get("isInvoice") or not all(fields.get(k) for k in ("debtorName", "amountPence", "invoiceDate")):
        return messages.text("Tell me the customer, the amount and the invoice date, for example "
                             "'add invoice for Acme Ltd, 1200, dated 2026-09-01'. Or send a photo or PDF.")
    created = db.create_invoice(business_id, {
        "debtorName": fields["debtorName"], "debtorType": "company", "amountPence": fields["amountPence"],
        "currency": fields.get("currency") or config.CURRENCY, "invoiceDate": fields["invoiceDate"],
        "deliveryDate": fields.get("deliveryDate"), "agreedDueDate": fields.get("agreedDueDate"),
        "reference": fields.get("reference"), "description": fields.get("description"),
        "status": "extracted", "sourceChannel": "whatsapp",
        "extractionConfidence": fields.get("extractionConfidence")})
    nid = created["invoiceId"]
    db.add_event(nid, "created", "whatsapp", "owner", {})
    db.add_event(nid, "extracted", "whatsapp", "agent", {"reference": fields.get("reference")})
    summary = (f"I've added an invoice to {fields['debtorName']} for "
               f"{config.gbp(fields['amountPence'])} dated {fields['invoiceDate']}.")
    return messages.buttons(summary, [(f"confirm:{nid}", "Confirm"), ("menu", "Discard")])


def _owned(business_id: str, invoice_id: str) -> Optional[dict]:
    """Load the invoice only if it belongs to this business, else None."""
    inv = db.get_invoice(invoice_id)
    if not inv or inv.get("businessId") != business_id:
        return None
    return inv


def confirm(business_id: str, invoice_id: str) -> dict:
    inv = _owned(business_id, invoice_id)
    if inv is None:
        return messages.text(NOT_FOUND)
    done = flows.confirm_invoice(invoice_id, "owner", "whatsapp")
    return messages.text(
        f"That invoice is now confirmed and tracked. It becomes legally late on "
        f"{done['legallyLateDate']}, and statutory interest starts to build from that date."
    )


def chase_draft(business_id: str, invoice_id: str) -> dict:
    """Compose a chase via flows.draft_chase_for and present Approve/Cancel."""
    inv = _owned(business_id, invoice_id)
    if inv is None:
        return messages.text(NOT_FOUND)
    try:
        d = flows.draft_chase_for(invoice_id)
    except drafter.ComplianceBlock:
        return messages.text(
            "I couldn't prepare a chase for this one. The wording didn't pass our "
            "compliance check, so there is nothing to send."
        )
    return [
        messages.text(d["message"]),
        messages.buttons("Send this chase?", [
            (f"chasego:{invoice_id}", "Approve & send"),
            (f"inv:{invoice_id}", "Cancel"),
        ]),
    ]


def chase_send(business_id: str, invoice_id: str) -> dict:
    """Send the approved chase via flows.send_chase (honours SEND_MODE + window)."""
    inv = _owned(business_id, invoice_id)
    if inv is None:
        return messages.text(NOT_FOUND)
    try:
        d = flows.draft_chase_for(invoice_id)
        r = flows.send_chase(invoice_id, d["message"], d["stage"], d["channel"], "owner")
    except drafter.ComplianceBlock:
        return messages.text(
            "I couldn't send that chase. The wording didn't pass our compliance "
            "check, so nothing left AWS."
        )
    if r.get("dryRun"):
        return messages.text(
            "Draft is ready. Live sending is off in this demo, so nothing left AWS."
        )
    if r.get("sent"):
        return messages.text("Chase sent.")
    body = "I couldn't send that just now."
    reason = r.get("reason")
    if reason == "too_soon":
        body += " It is too soon after the last chase to send another."
    elif reason:
        body += f" ({reason})"
    return messages.text(body)


def mark_paid(business_id: str, invoice_id: str) -> dict:
    inv = _owned(business_id, invoice_id)
    if inv is None:
        return messages.text(NOT_FOUND)
    flows.mark_paid(invoice_id, "owner", "whatsapp")
    return messages.text("Marked as paid. That invoice is now closed and interest has stopped.")


def lba_draft(business_id: str, invoice_id: str) -> dict:
    inv = _owned(business_id, invoice_id)
    if inv is None:
        return messages.text(NOT_FOUND)
    # flows.send_lba drafts AND sends (and writes an lba_drafted event), so to show a
    # draft only we build the text directly with agent.draft.draft_lba.
    biz = db.get_business(inv["businessId"])
    debtor = db.get_debtor(db.debtor_key(inv["debtorName"], inv.get("debtorCompanyNumber")))
    try:
        d = drafter.draft_lba(inv, biz, debtor)
    except drafter.ComplianceBlock:
        return messages.text(
            "I couldn't prepare a Letter Before Action for this one. The wording "
            "didn't pass our compliance check."
        )
    return [
        messages.text(d["text"]),
        messages.buttons("Send this Letter Before Action?", [
            (f"lbago:{invoice_id}", "Approve & send"),
            (f"inv:{invoice_id}", "Cancel"),
        ]),
    ]


def lba_send(business_id: str, invoice_id: str) -> dict:
    inv = _owned(business_id, invoice_id)
    if inv is None:
        return messages.text(NOT_FOUND)
    try:
        r = flows.send_lba(invoice_id, None, "owner")
    except drafter.ComplianceBlock:
        return messages.text(
            "I couldn't send that Letter Before Action. The wording didn't pass our "
            "compliance check, so nothing left AWS."
        )
    if r.get("dryRun"):
        return messages.text(
            "Draft is ready. Live sending is off in this demo, so nothing left AWS."
        )
    if r.get("sent"):
        return messages.text("Letter Before Action sent.")
    body = "I couldn't send that just now."
    reason = r.get("reason")
    if reason == "no_email":
        body += " There is no email address on file for this debtor yet."
    elif reason:
        body += f" ({reason})"
    return messages.text(body)


def ingest_media(business_id: str, media: dict) -> dict:
    """media = {media_id, mime, bucket, key}. Fetch, extract (image or PDF), store as an
    `extracted` invoice, return a short summary + Confirm/Discard."""
    media_id, mime = media["media_id"], (media.get("mime") or "")
    bucket, key = media["bucket"], media["key"]
    not_a_photo = messages.text("Please send the invoice as a photo (JPEG or PNG).")

    cds.fetch_whatsapp_media(media_id, bucket, key)
    data = cds.read_s3(bucket, key)

    if mime.lower() in extract.FMT:
        fields = extract.extract_from_image(data, mime)
    elif mime.lower() == "application/pdf":
        extract_from_pdf = getattr(extract, "extract_from_pdf", None)
        if not extract_from_pdf:
            return not_a_photo
        fields = extract_from_pdf(data)
    else:
        return not_a_photo

    if not all(fields.get(k) for k in ("debtorName", "amountPence", "invoiceDate")):
        return messages.text(
            "I couldn't read the key details off that invoice. Please send a clearer "
            "photo or PDF showing the customer, the amount and the invoice date."
        )

    created = db.create_invoice(business_id, {
        "debtorName": fields["debtorName"],
        "debtorType": "company",
        "amountPence": fields["amountPence"],
        "currency": fields.get("currency") or config.CURRENCY,
        "invoiceDate": fields["invoiceDate"],
        "deliveryDate": fields.get("deliveryDate"),
        "agreedDueDate": fields.get("agreedDueDate"),
        "reference": fields.get("reference"),
        "description": fields.get("description"),
        "status": "extracted",
        "sourceChannel": "whatsapp",
        "extractionConfidence": fields.get("extractionConfidence"),
    })
    new_id = created["invoiceId"]
    db.add_event(new_id, "created", "whatsapp", "owner", {})
    db.add_event(new_id, "extracted", "whatsapp", "agent", {
        "confidence": fields.get("extractionConfidence"),
        "reference": fields.get("reference"),
        "unreadableFields": fields.get("unreadableFields") or [],
    })

    summary = (f"I read an invoice to {fields['debtorName']} for "
               f"{config.gbp(fields['amountPence'])} dated {fields['invoiceDate']}.")
    if fields.get("reference"):
        summary += f" Reference {fields['reference']}."
    summary += " Confirm it to start tracking, or discard it."
    return messages.buttons(summary, [
        (f"confirm:{new_id}", "Confirm"),
        ("menu", "Discard"),
    ])
