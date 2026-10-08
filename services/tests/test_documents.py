from datetime import date

from common import config, db, documents


def _late_invoice(invoice):
    """The fixture invoice, rendered late so interest and the fixed sum populate."""
    return db.get_invoice(invoice["invoiceId"], today=date(2026, 8, 30))


def _is_pdf(blob: bytes) -> str:
    assert isinstance(blob, bytes)
    assert blob.startswith(b"%PDF")
    assert blob.rstrip().endswith(b"%%EOF")
    return blob.decode("latin-1")


def _money(pence: int) -> str:
    # The £ sign is escaped to a byte in the stream, so match the digits only.
    return config.gbp(pence).replace("£", "")


def test_invoice_pdf_is_pdf_with_debtor_ref_and_money(business, invoice):
    inv = _late_invoice(invoice)
    text = _is_pdf(documents.invoice_pdf(business, inv))
    assert inv["debtorName"] in text
    assert inv["reference"] in text
    assert _money(inv["amountPence"]) in text          # "2,500.00"
    assert _money(inv["interestAccruedPence"]) in text  # statutory interest shown
    assert _money(inv["fixedRecoverySumPence"]) in text  # "70.00"
    assert _money(inv["totalOwedPence"]) in text        # bold total due
    # bank details appear in full (creditor's own document)
    assert business["bankAccount"] in text
    assert "Late Payment of Commercial Debts" in text


def test_invoice_pdf_not_late_hides_interest_rows(business, invoice):
    inv = db.get_invoice(invoice["invoiceId"], today=date(2026, 7, 15))
    text = _is_pdf(documents.invoice_pdf(business, inv))
    assert inv["daysLate"] == 0
    assert "Statutory interest" not in text
    assert "Fixed recovery sum" not in text
    assert _money(inv["amountPence"]) in text
    assert _money(inv["totalOwedPence"]) in text


def test_statement_pdf_lists_invoices_and_grand_total(business, invoice):
    inv = _late_invoice(invoice)
    summary = {"totalOwedPence": inv["totalOwedPence"] + 10_000}
    text = _is_pdf(documents.statement_pdf(business, [inv], summary))
    assert inv["debtorName"] in text
    assert inv["reference"] in text
    assert "Total outstanding" in text
    assert _money(summary["totalOwedPence"]) in text


def test_statement_pdf_empty(business):
    summary = {"totalOwedPence": 0}
    text = _is_pdf(documents.statement_pdf(business, [], summary))
    assert "No open invoices." in text
    assert _money(0) in text  # "0.00"


def test_lba_pdf_is_a_formal_letter(business, invoice):
    inv = _late_invoice(invoice)
    letter_text = ("Dear Bluebell Builders Ltd,\n\n"
                   "Our invoice INV-1042 for the kitchen fit-out is now overdue. "
                   "Unless payment is received within 14 days we will commence proceedings "
                   "to recover the debt together with statutory interest and costs.")
    text = _is_pdf(documents.lba_pdf(business, inv, letter_text))
    assert inv["debtorName"] in text
    assert "proceedings" in text        # a word from the body survived wrapping
    assert "Yours faithfully," in text
    assert business["name"] in text


def test_plain_dict_invoice_also_renders(business):
    inv = {"debtorName": "Cobble & Co", "reference": "INV-9",
           "description": "Groundworks", "invoiceDate": "2026-05-01",
           "legallyLateDate": "2026-06-01", "amountPence": 889_148,
           "daysLate": 40, "statutoryRatePct": 11.75, "interestAccruedPence": 11_452,
           "fixedRecoverySumPence": 10_000, "totalOwedPence": 910_600, "status": "confirmed"}
    text = _is_pdf(documents.invoice_pdf(business, inv))
    assert "Cobble & Co" in text
    assert "8,891.48" in text            # amount, pound sign stripped
    assert _money(inv["totalOwedPence"]) in text
