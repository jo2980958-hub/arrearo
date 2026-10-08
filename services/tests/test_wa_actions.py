"""Unit tests for wa.actions — the WhatsApp write actions.

Every test runs in dry mode (SEND_MODE unset, cleared by conftest), with the
Bedrock client stubbed by FakeBedrock. DynamoDB is moto via the autouse `aws`
fixture. No live AWS, no real sends.
"""
from fakes import FakeBedrock

from agent import extract, llm
from common import config, db
from wa import actions


# ── helpers ───────────────────────────────────────────────────────────────
def _body(reply):
    return reply["text"]["body"]


def _btn_ids(reply):
    return [b["reply"]["id"] for b in reply["interactive"]["action"]["buttons"]]


def _btn_titles(reply):
    return [b["reply"]["title"] for b in reply["interactive"]["action"]["buttons"]]


def _clean_draft(invoice):
    """A compliant draft that cites both figures the drafter requires."""
    inv = db.get_invoice(invoice["invoiceId"])
    total = config.gbp(inv["totalOwedPence"])
    return (f"Hello, we are chasing an overdue invoice. The original amount is "
            f"{config.gbp(inv['amountPence'])} and the total now owed is {total}. "
            "Please reply with a payment date.")


# ── confirm ───────────────────────────────────────────────────────────────
def test_confirm_tracks_and_reports_late_date(invoice):
    reply = actions.confirm(invoice["businessId"], invoice["invoiceId"])
    inv = db.get_invoice(invoice["invoiceId"])
    assert reply["type"] == "text"
    assert "confirmed" in _body(reply).lower()
    assert inv["legallyLateDate"] in _body(reply)
    assert inv["status"] == "confirmed"
    assert "confirmed" in [e["type"] for e in db.list_events(invoice["invoiceId"])]


def test_confirm_guard_rejects_other_business(invoice):
    reply = actions.confirm("not-this-business", invoice["invoiceId"])
    assert _body(reply) == actions.NOT_FOUND
    # nothing changed
    assert db.list_events(invoice["invoiceId"]) == []


def test_action_guard_rejects_missing_invoice(business):
    reply = actions.mark_paid(business["businessId"], "no-such-invoice")
    assert _body(reply) == actions.NOT_FOUND


# ── chase ─────────────────────────────────────────────────────────────────
def test_chase_draft_shows_message_and_approve_cancel(invoice):
    draft = _clean_draft(invoice)
    llm.set_client(FakeBedrock(texts=[draft, draft]))
    out = actions.chase_draft(invoice["businessId"], invoice["invoiceId"])
    assert isinstance(out, list) and len(out) == 2
    assert out[0]["type"] == "text" and _body(out[0]) == draft
    iid = invoice["invoiceId"]
    assert _btn_ids(out[1]) == [f"chasego:{iid}", f"inv:{iid}"]
    assert _btn_titles(out[1]) == ["Approve & send", "Cancel"]


def test_chase_send_dry_reports_draft_ready(invoice):
    draft = _clean_draft(invoice)
    llm.set_client(FakeBedrock(texts=[draft, draft]))
    reply = actions.chase_send(invoice["businessId"], invoice["invoiceId"])
    assert reply["type"] == "text"
    assert "nothing left AWS" in _body(reply)
    # dry run never flips status or writes a chased event
    assert db.get_invoice(invoice["invoiceId"])["status"] == "confirmed"
    assert "chased" not in [e["type"] for e in db.list_events(invoice["invoiceId"])]


def test_chase_guard_rejects_other_business(invoice):
    reply = actions.chase_draft("not-this-business", invoice["invoiceId"])
    assert _body(reply) == actions.NOT_FOUND


# ── mark paid ─────────────────────────────────────────────────────────────
def test_mark_paid(invoice):
    reply = actions.mark_paid(invoice["businessId"], invoice["invoiceId"])
    assert reply["type"] == "text" and "paid" in _body(reply).lower()
    assert db.get_invoice(invoice["invoiceId"])["status"] == "paid"
    assert "paid" in [e["type"] for e in db.list_events(invoice["invoiceId"])]


# ── Letter Before Action ──────────────────────────────────────────────────
def test_lba_draft_shows_letter_and_does_not_send(invoice):
    draft = _clean_draft(invoice)
    llm.set_client(FakeBedrock(texts=[draft, draft]))
    out = actions.lba_draft(invoice["businessId"], invoice["invoiceId"])
    assert isinstance(out, list) and len(out) == 2
    assert out[0]["type"] == "text" and _body(out[0]) == draft
    iid = invoice["invoiceId"]
    assert _btn_ids(out[1]) == [f"lbago:{iid}", f"inv:{iid}"]
    # drafting is non-sending: no lba events, status untouched
    types = [e["type"] for e in db.list_events(iid)]
    assert "lba_drafted" not in types and "lba_sent" not in types
    assert db.get_invoice(iid)["status"] == "confirmed"


def test_lba_send_dry_reports_draft_ready(invoice):
    draft = _clean_draft(invoice)
    llm.set_client(FakeBedrock(texts=[draft, draft]))
    reply = actions.lba_send(invoice["businessId"], invoice["invoiceId"])
    assert reply["type"] == "text"
    assert "nothing left AWS" in _body(reply)
    # dry run does not email or flip to lba, but the draft is recorded
    assert db.get_invoice(invoice["invoiceId"])["status"] == "confirmed"
    types = [e["type"] for e in db.list_events(invoice["invoiceId"])]
    assert "lba_drafted" in types and "lba_sent" not in types


def test_lba_guard_rejects_other_business(invoice):
    reply = actions.lba_send("not-this-business", invoice["invoiceId"])
    assert _body(reply) == actions.NOT_FOUND


# ── ingest media ──────────────────────────────────────────────────────────
CANNED = {
    "isInvoice": True,
    "debtorName": "Bluebell Builders Ltd",
    "amountPence": 48000,
    "currency": "GBP",
    "invoiceDate": "2026-09-01",
    "deliveryDate": None,
    "agreedDueDate": "2026-09-30",
    "reference": "INV-7",
    "description": "Scaffolding hire",
    "extractionConfidence": 0.93,
    "unreadableFields": [],
    "missingFields": [],
}


def _stub_media(monkeypatch, cds_mod):
    monkeypatch.setattr(cds_mod, "fetch_whatsapp_media",
                        lambda media_id, bucket, key: {"mimeType": "image/jpeg", "fileSize": 4})
    monkeypatch.setattr(cds_mod, "read_s3", lambda bucket, key: b"\xff\xd8jpeg-bytes")


def test_ingest_image_creates_extracted_invoice(business, monkeypatch):
    from common import cds
    _stub_media(monkeypatch, cds)
    monkeypatch.setattr(extract, "extract_from_image", lambda data, mime: dict(CANNED))
    media = {"media_id": "5303", "mime": "image/jpeg", "bucket": "media-bkt",
             "key": f"inbound/{business['businessId']}/5303"}
    reply = actions.ingest_media(business["businessId"], media)

    assert reply["type"] == "interactive"
    body = reply["interactive"]["body"]["text"]
    assert "Bluebell Builders Ltd" in body and config.gbp(48000) in body and "2026-09-01" in body
    [inv] = db.list_invoices_by_business(business["businessId"])
    assert inv["status"] == "extracted" and inv["amountPence"] == 48000
    assert inv["sourceChannel"] == "whatsapp" and inv["reference"] == "INV-7"
    assert _btn_ids(reply) == [f"confirm:{inv['invoiceId']}", "menu"]
    assert _btn_titles(reply) == ["Confirm", "Discard"]
    assert [e["type"] for e in db.list_events(inv["invoiceId"])] == ["created", "extracted"]


def test_ingest_pdf_uses_extract_from_pdf(business, monkeypatch):
    from common import cds
    _stub_media(monkeypatch, cds)
    monkeypatch.setattr(extract, "extract_from_pdf", lambda data: dict(CANNED), raising=False)
    media = {"media_id": "99", "mime": "application/pdf", "bucket": "media-bkt",
             "key": f"inbound/{business['businessId']}/99"}
    reply = actions.ingest_media(business["businessId"], media)
    assert reply["type"] == "interactive"
    [inv] = db.list_invoices_by_business(business["businessId"])
    assert inv["status"] == "extracted"
    assert _btn_ids(reply)[0] == f"confirm:{inv['invoiceId']}"


def test_ingest_pdf_without_extractor_asks_for_photo(business, monkeypatch):
    from common import cds
    _stub_media(monkeypatch, cds)
    monkeypatch.delattr(extract, "extract_from_pdf", raising=False)
    media = {"media_id": "99", "mime": "application/pdf", "bucket": "b", "key": "k"}
    reply = actions.ingest_media(business["businessId"], media)
    assert reply["type"] == "text" and "photo" in _body(reply).lower()
    assert db.list_invoices_by_business(business["businessId"]) == []


def test_ingest_unsupported_type_asks_for_photo(business, monkeypatch):
    from common import cds
    _stub_media(monkeypatch, cds)
    media = {"media_id": "7", "mime": "audio/ogg", "bucket": "b", "key": "k"}
    reply = actions.ingest_media(business["businessId"], media)
    assert reply["type"] == "text" and "photo" in _body(reply).lower()
    assert db.list_invoices_by_business(business["businessId"]) == []


def test_ingest_unreadable_fields_ask_for_clearer_copy(business, monkeypatch):
    from common import cds
    _stub_media(monkeypatch, cds)
    bad = dict(CANNED, amountPence=None, missingFields=["amountPence"])
    monkeypatch.setattr(extract, "extract_from_image", lambda data, mime: bad)
    media = {"media_id": "5", "mime": "image/png", "bucket": "b", "key": "k"}
    reply = actions.ingest_media(business["businessId"], media)
    assert reply["type"] == "text" and "clearer" in _body(reply).lower()
    assert db.list_invoices_by_business(business["businessId"]) == []
