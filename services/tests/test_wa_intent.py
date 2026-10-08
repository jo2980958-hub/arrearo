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


# ── web parity: edit, create, timeline, name search ─────────────────────────

def test_router_edit_business_name(business):
    num = _login(business)
    llm.set_client(FakeBedrock([{"action": "edit_business", "field": "business name",
                                 "value": "Brownshift Technologies UK"}]))
    [r] = router.handle(num, {"text": "update business name to Brownshift Technologies UK"})
    assert "Brownshift Technologies UK" in body(r)
    assert db.get_business(business["businessId"])["name"] == "Brownshift Technologies UK"


def test_router_edit_invoice_amount(business, invoice):
    num = _login(business)
    llm.set_client(FakeBedrock([{"action": "edit_invoice", "invoiceId": invoice["invoiceId"],
                                 "field": "amount", "value": "9000"}]))
    [r] = router.handle(num, {"text": "set the amount on that invoice to 9000"})
    assert "£9,000" in body(r)
    assert db.get_invoice(invoice["invoiceId"])["amountPence"] == 900000


def test_router_timeline(business, invoice):
    num = _login(business)
    db.add_event(invoice["invoiceId"], "confirmed", "whatsapp", "owner", {})
    llm.set_client(FakeBedrock([{"action": "timeline", "invoiceId": invoice["invoiceId"]}]))
    [r] = router.handle(num, {"text": "show me the history of that invoice"})
    assert "History" in body(r)


def test_debtor_name_search_finds_by_name(business):
    # the risk dataset is keyed by company number; lookup must be by name
    db.put_debtor({"debtorKey": "00946107", "name": "BIFFA WASTE SERVICES LIMITED",
                   "riskBand": "medium", "avgDaysToPay": 41})
    num = _login(business)
    llm.set_client(FakeBedrock([{"action": "debtors", "query": "biffa waste"}]))
    [r] = router.handle(num, {"text": "check biffa waste"})
    assert "BIFFA WASTE SERVICES LIMITED" in body(r) and "medium" in body(r)
