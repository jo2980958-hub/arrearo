"""PDF invoice extraction and the deterministic summary line."""
from fakes import FakeBedrock

from agent import extract, llm
from common import config


def test_extract_from_pdf_normalises_fields_and_sends_a_document_block():
    fake = FakeBedrock([{"is_invoice": True, "customer_name": "Bluebell Builders Ltd",
                         "invoice_number": "INV-9", "invoice_date": "2026-07-01",
                         "payment_terms_days": 14, "gross_amount": 1234.5, "confidence": 0.95}])
    llm.set_client(fake)
    r = extract.extract_from_pdf(b"%PDF-1.7 fake")
    # Same normalised shape as the image path.
    assert r["amountPence"] == 123450
    assert r["debtorName"] == "Bluebell Builders Ltd"
    assert r["reference"] == "INV-9"
    assert r["agreedDueDate"] == "2026-07-15"
    assert r["needsConfirmation"] is False
    # A document block, not an image block, with the PDF bytes.
    doc = fake.calls[0]["messages"][0]["content"][0]["document"]
    assert doc["format"] == "pdf"
    assert doc["source"]["bytes"] == b"%PDF-1.7 fake"
    # Same tool and the forced tool choice.
    assert fake.calls[0]["toolConfig"]["toolChoice"] == {"tool": {"name": "record_invoice"}}
    assert fake.calls[0]["system"] == [{"text": extract.SYSTEM}]


def test_extract_from_pdf_missing_amount_forces_confirmation():
    llm.set_client(FakeBedrock([{"is_invoice": True, "customer_name": "X Ltd",
                                 "invoice_date": "2026-07-01", "gross_amount": None,
                                 "confidence": 0.99}]))
    r = extract.extract_from_pdf(b"%PDF")
    assert r["amountPence"] is None
    assert r["needsConfirmation"] is True
    assert r["extractionConfidence"] <= 0.5


def test_summary_line_full_fields():
    fields = extract.normalise({"is_invoice": True, "customer_name": "Bluebell Builders Ltd",
                                "invoice_number": "INV-9", "invoice_date": "2026-07-01",
                                "gross_amount": 1234.5, "confidence": 0.95})
    assert extract.summary_line(fields) == (
        "Invoice to Bluebell Builders Ltd for £1,234.50 dated 2026-07-01, ref INV-9")


def test_summary_line_no_reference_omits_ref():
    fields = {"debtorName": "Acme Ltd", "amountPence": 50000, "invoiceDate": "2026-01-02",
              "reference": None}
    assert extract.summary_line(fields) == "Invoice to Acme Ltd for £500.00 dated 2026-01-02"


def test_summary_line_handles_missing_fields_gracefully():
    # Empty input must not raise and must not feed None to gbp.
    assert extract.summary_line({}) == "Invoice to an unknown debtor for an unknown amount"
    partial = {"debtorName": "Acme Ltd", "amountPence": None, "invoiceDate": None,
               "reference": "INV-7"}
    assert extract.summary_line(partial) == (
        "Invoice to Acme Ltd for an unknown amount, ref INV-7")


def test_summary_line_renders_pence_via_config_gbp():
    fields = {"debtorName": "Acme Ltd", "amountPence": 123450, "invoiceDate": "2026-07-01"}
    assert config.gbp(123450) in extract.summary_line(fields)


def test_extract_from_image_still_works_and_keeps_normalise_keys():
    fake = FakeBedrock([{"is_invoice": True, "customer_name": "Bluebell Builders Ltd",
                         "invoice_number": "INV-9", "invoice_date": "2026-07-01",
                         "payment_terms_days": 14, "gross_amount": 1234.5, "confidence": 0.95}])
    llm.set_client(fake)
    r = extract.extract_from_image(b"\xff\xd8", "image/jpeg")
    assert r["amountPence"] == 123450
    assert fake.calls[0]["messages"][0]["content"][0]["image"]["format"] == "jpeg"
    # normalise output keys are unchanged (the shape test_agents.py depends on).
    assert set(r) == {
        "isInvoice", "debtorName", "amountPence", "currency", "invoiceDate",
        "deliveryDate", "agreedDueDate", "reference", "description",
        "extractionConfidence", "unreadableFields", "missingFields", "needsConfirmation",
    }
