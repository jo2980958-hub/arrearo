"""Sending designed PDFs (invoice, statement) over WhatsApp as documents."""
from fakes import FakeBedrock

from agent import llm
from common import cds, documents
from wa import actions, router, session


def body(reply):
    if reply.get("type") == "text":
        return reply["text"]["body"]
    if reply.get("type") == "interactive":
        return reply["interactive"]["body"]["text"]
    return ""


def test_send_whatsapp_document_dry_returns_dry_run():
    mid = cds.send_whatsapp_document("+233547738808", b"%PDF-1.4 ...", "invoice.pdf", caption="hi")
    assert mid.startswith("dry-run-")


def test_invoice_pdf_renders_and_action_confirms(business, invoice):
    # the renderer produces a real PDF
    pdf = documents.invoice_pdf(business, __import__("common.db", fromlist=["x"]).get_invoice(invoice["invoiceId"]))
    assert pdf[:4] == b"%PDF"
    r = actions.send_invoice_pdf(business["businessId"], invoice["invoiceId"], "+233547738808")
    assert r["type"] == "text" and "pdf" in body(r).lower()


def test_send_invoice_pdf_guards_other_business(invoice):
    r = actions.send_invoice_pdf("not-this-business", invoice["invoiceId"], "+233547738808")
    assert "couldn't find" in body(r).lower()


def test_router_invoice_pdf_by_language(business, invoice):
    num = "+233555000777"
    session.link(num, business["businessId"])
    llm.set_client(FakeBedrock([{"action": "invoice_pdf", "invoiceId": invoice["invoiceId"]}]))
    [r] = router.handle(num, {"text": "send me that invoice as a pdf"})
    assert "pdf" in body(r).lower()


def test_router_statement_pdf_by_language(business, invoice):
    num = "+233555000888"
    session.link(num, business["businessId"])
    llm.set_client(FakeBedrock([{"action": "statement_pdf"}]))
    [r] = router.handle(num, {"text": "send me a statement"})
    assert "statement" in body(r).lower() or "outstanding" in body(r).lower()
