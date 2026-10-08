"""Natural-language intent: free text maps to actions, answers, or the safe fallback."""
from fakes import FakeBedrock

from agent import llm
from common import db
from wa import intent, router, session


def _login(business):
    """Put a number straight into the AUTHED state linked to this business."""
    num = "+233555000222"
    session.link(num, business["businessId"])
    return num


def body(reply):
    if reply.get("type") == "text":
        return reply["text"]["body"]
    if reply.get("type") == "interactive":
        return reply["interactive"]["body"]["text"]
    return ""


def test_resolve_routes_to_a_named_invoice_by_amount(business, invoice):
    llm.set_client(FakeBedrock([{"action": "open_invoice", "invoiceId": invoice["invoiceId"]}]))
    r = intent.resolve("show me the invoice for 2450 pounds", business["businessId"])
    assert r == {"kind": "route", "tap_id": f"inv:{invoice['invoiceId']}"}


def test_resolve_rejects_a_guessed_invoice_id(business, invoice):
    llm.set_client(FakeBedrock([{"action": "chase", "invoiceId": "not-a-real-id"}]))
    r = intent.resolve("chase that one", business["businessId"])
    assert r == {"kind": "menu"}            # never acts on an id that isn't the caller's


def test_resolve_answers_a_question(business):
    llm.set_client(FakeBedrock([{"action": "answer", "answer": "You have no open invoices."}]))
    r = intent.resolve("what do I owe", business["businessId"])
    assert r == {"kind": "answer", "text": "You have no open invoices."}


def test_resolve_unknown_falls_back_to_menu(business):
    llm.set_client(FakeBedrock([{"action": "unknown"}]))
    assert intent.resolve("asdfghjk", business["businessId"]) == {"kind": "menu"}


def test_router_freetext_takes_the_action(business, invoice):
    num = _login(business)
    llm.set_client(FakeBedrock([{"action": "open_invoice", "invoiceId": invoice["invoiceId"]}]))
    replies = router.handle(num, {"text": "open the Bluebell one"})
    assert any("Late Payment of Commercial Debts" in body(r) for r in replies)


def test_router_freetext_answer(business):
    num = _login(business)
    llm.set_client(FakeBedrock([{"action": "answer", "answer": "You are all caught up."}]))
    [r] = router.handle(num, {"text": "am I owed anything"})
    assert body(r) == "You are all caught up."


def test_router_freetext_marks_paid_via_language(business, invoice):
    num = _login(business)
    llm.set_client(FakeBedrock([{"action": "mark_paid", "invoiceId": invoice["invoiceId"]}]))
    [r] = router.handle(num, {"text": "bluebell has paid me"})
    assert "paid" in body(r).lower()
    assert db.get_invoice(invoice["invoiceId"])["status"] == "paid"


def test_show_menu_phrase_needs_no_llm(business):
    num = _login(business)
    # no FakeBedrock queued: if this reached the LLM it would error, proving the
    # phrase is handled by the fast command parser, not intent.
    llm.set_client(FakeBedrock([]))
    replies = router.handle(num, {"text": "show me menu"})
    assert any(r.get("type") == "interactive" for r in replies)
