from datetime import date

from common import db


def test_late_date_computed_by_engine(invoice):
    assert invoice["legallyLateDate"] == "2026-08-01"   # due 31 Jul (30 days), late from the day after
    assert invoice["debtorWhatsapp"] == "+447700900123"


def test_derived_fields_use_engine(invoice):
    d = db.get_invoice(invoice["invoiceId"], today=date(2026, 8, 30))
    assert d["daysLate"] == 30
    rate = d["statutoryRatePct"]
    assert rate == 11.75                                   # 8 + 3.75 base for H2 2026
    assert d["interestAccruedPence"] == round(250_000 * rate / 100 / 365 * 30)
    assert d["fixedRecoverySumPence"] == 7000              # £2,500 -> £70
    assert d["totalOwedPence"] == 250_000 + d["interestAccruedPence"] + 7000


def test_not_yet_late_has_no_fixed_sum(invoice):
    d = db.get_invoice(invoice["invoiceId"], today=date(2026, 7, 15))
    assert (d["daysLate"], d["interestAccruedPence"], d["fixedRecoverySumPence"]) == (0, 0, 0)
    assert d["totalOwedPence"] == 250_000


def test_paid_invoice_stops_accruing(invoice):
    db.update_invoice(invoice["invoiceId"], {"status": "paid", "paidAt": "2026-08-10T09:00:00Z"})
    d = db.get_invoice(invoice["invoiceId"], today=date(2026, 12, 1))
    assert d["daysLate"] == 10


def test_update_recomputes_late_date(invoice):
    db.update_invoice(invoice["invoiceId"], {"agreedDueDate": "2026-09-01"})
    assert db.get_invoice_raw(invoice["invoiceId"])["legallyLateDate"] == "2026-09-02"


def test_gsi_by_business_and_debtor_whatsapp(business, invoice):
    other = db.create_business({"name": "Other", "cognitoSub": "sub-2", "whatsappNumber": "+447700900002"})
    db.create_invoice(other["businessId"], {"debtorName": "X", "amountPence": 100, "invoiceDate": "2026-07-01"})
    mine = db.list_invoices_by_business(business["businessId"])
    assert [i["invoiceId"] for i in mine] == [invoice["invoiceId"]]
    assert db.list_open_invoices_by_debtor_whatsapp("447700900123")[0]["invoiceId"] == invoice["invoiceId"]
    assert db.get_business_by_sub("sub-1")["businessId"] == business["businessId"]
    assert db.get_business_by_whatsapp("447700900001")["businessId"] == business["businessId"]


def test_money_stays_integer_and_confidence_float(business):
    inv = db.create_invoice(business["businessId"], {"debtorName": "Y", "amountPence": 12345, "invoiceDate": "2026-07-01",
                                                    "extractionConfidence": 0.93})
    got = db.get_invoice_raw(inv["invoiceId"])
    assert got["amountPence"] == 12345 and isinstance(got["amountPence"], int)
    assert got["extractionConfidence"] == 0.93


def test_events_ordered_and_idempotency_claim(invoice):
    for t in ("created", "extracted", "confirmed"):
        db.add_event(invoice["invoiceId"], t, "system", "agent", {"n": 1})
    assert [e["type"] for e in db.list_events(invoice["invoiceId"])] == ["created", "extracted", "confirmed"]
    assert db.claim_message("wamid.A") is True
    assert db.claim_message("wamid.A") is False


def test_conversation_and_window(invoice):
    assert db.window_open("447700900123") is False
    db.add_message("447700900123", "in", "wamid.1", "hello")
    assert db.window_open("+447700900123") is True
    assert db.list_messages("447700900123")[0]["body"] == "hello"
