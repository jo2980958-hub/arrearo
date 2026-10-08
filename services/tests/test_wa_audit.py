"""Full app audit: walk every screen and every action end to end through the router,
exactly as a logged-in user would, and confirm each produces the right reply.

Prints a readable trace (run with -s). Deep content (compliance wording, extraction,
OTP internals) is covered by the per-module tests; this walks the whole surface so we
know nothing is unwired and web parity holds.
"""
import pytest

from agent import draft as drafter
from agent import extract as extractor
from common import db
from fakes import FakeBedrock
from wa import intent, menus, router, session

NUM = "+233555009999"


def _say(reply):
    if reply.get("type") == "text":
        return reply["text"]["body"]
    if reply.get("type") == "interactive":
        i = reply["interactive"]
        return i["body"]["text"]
    return str(reply)


def _row_ids(reply):
    i = reply["interactive"]
    if i["type"] == "button":
        return [b["reply"]["id"] for b in i["action"]["buttons"]]
    return [r["id"] for s in i["action"]["sections"] for r in s["rows"]]


def _intent(action, **kw):
    """Force the next intent.resolve to return this action."""
    from agent import llm
    llm.set_client(FakeBedrock([{"action": action, **kw}]))


@pytest.fixture
def ready(business, monkeypatch):
    """Logged-in number, a debtor in the dataset, and stubbed drafters/extractor."""
    session.link(NUM, business["businessId"])
    db.put_debtor({"debtorKey": "00946107", "name": "BIFFA WASTE SERVICES LIMITED",
                   "riskBand": "medium", "avgDaysToPay": 41, "pctPaidLate": 22})
    monkeypatch.setattr(drafter, "draft_chase",
                        lambda *a, **k: "Reminder: the total now owed is the amount plus interest. Please pay.")
    monkeypatch.setattr(drafter, "draft_lba",
                        lambda *a, **k: {"text": "Letter before action. Please pay the total owed.",
                                         "protocol": {}})
    monkeypatch.setattr(extractor, "extract_from_text",
                        lambda t: {"isInvoice": True, "debtorName": "Acme Ltd", "amountPence": 120000,
                                   "currency": "GBP", "invoiceDate": "2026-09-01", "deliveryDate": None,
                                   "agreedDueDate": None, "reference": "A-1", "description": "Work",
                                   "extractionConfidence": 0.9})
    return business


def _invoice(business, status="confirmed", **kw):
    data = {"debtorName": "Mercer Plant Hire Ltd", "debtorType": "company", "amountPence": 860000,
            "invoiceDate": "2026-06-20", "reference": "HF-2177", "description": "Hire",
            "status": status, "debtorWhatsapp": "447700900500", "debtorEmail": "ap@mercer.test"}
    data.update(kw)
    return db.create_invoice(business["businessId"], data)


def test_menu_covers_every_screen_and_each_one_renders(ready):
    menu = menus.main_menu()
    ids = _row_ids(menu)
    assert set(ids) == {"summary", "invoices", "add_invoice", "debtors", "settings", "help", "logout"}
    _invoice(ready)
    trace = []
    for key in ["summary", "invoices", "settings", "help"]:
        [r] = router.handle(NUM, {"tap_id": key})
        assert _say(r) and not _say(r).lower().startswith("i didn't catch")
        trace.append(f"menu:{key} -> {_say(r)[:60]!r}")
    # add_invoice and debtors set a context and prompt
    [r] = router.handle(NUM, {"tap_id": "add_invoice"})
    assert "photo" in _say(r).lower() or "pdf" in _say(r).lower()
    [r] = router.handle(NUM, {"tap_id": "debtors"})
    assert "company name" in _say(r).lower()
    print("\n".join(trace))


def test_invoice_actions_full_cycle(ready):
    inv = _invoice(ready, status="extracted")
    iid = inv["invoiceId"]
    # open -> detail shows the law + a Confirm action for an extracted invoice
    detail = router.handle(NUM, {"tap_id": f"inv:{iid}"})
    assert any("Late Payment of Commercial Debts" in _say(r) for r in detail)
    # confirm
    [r] = router.handle(NUM, {"tap_id": f"confirm:{iid}"})
    assert "confirm" in _say(r).lower() or "tracking" in _say(r).lower()
    # chase draft -> approve/cancel
    replies = router.handle(NUM, {"tap_id": f"chase:{iid}"})
    assert any(rp.get("type") == "interactive" for rp in replies)
    # chase send (dry) -> a reply, no crash
    [r] = router.handle(NUM, {"tap_id": f"chasego:{iid}"})
    assert _say(r)
    # LBA draft + send
    assert router.handle(NUM, {"tap_id": f"lba:{iid}"})
    assert router.handle(NUM, {"tap_id": f"lbago:{iid}"})
    # mark paid
    [r] = router.handle(NUM, {"tap_id": f"paid:{iid}"})
    assert "paid" in _say(r).lower()
    assert db.get_invoice(iid)["status"] == "paid"


def test_natural_language_covers_web_parity(ready):
    inv = _invoice(ready)
    iid = inv["invoiceId"]
    checks = []

    _intent("answer", answer="You are owed money across your open invoices.")
    checks.append(("what am I owed", _say(router.handle(NUM, {"text": "what am I owed"})[0])))

    _intent("open_invoice", invoiceId=iid)
    assert any("Late Payment" in _say(r) for r in router.handle(NUM, {"text": "open the Mercer invoice"}))

    _intent("edit_business", field="business name", value="Brownshift Technologies UK")
    router.handle(NUM, {"text": "rename my business to Brownshift Technologies UK"})
    assert db.get_business(ready["businessId"])["name"] == "Brownshift Technologies UK"

    _intent("edit_invoice", invoiceId=iid, field="amount", value="9000")
    router.handle(NUM, {"text": "set that invoice to 9000"})
    assert db.get_invoice(iid)["amountPence"] == 900000

    _intent("create_invoice")
    r = router.handle(NUM, {"text": "add invoice for Acme Ltd 1200 dated 2026-09-01"})
    assert any("Acme Ltd" in _say(x) for x in r)

    db.add_event(iid, "confirmed", "whatsapp", "owner", {})
    _intent("timeline", invoiceId=iid)
    assert "History" in _say(router.handle(NUM, {"text": "history of that invoice"})[0])

    _intent("debtors", query="biffa waste")
    assert "BIFFA WASTE SERVICES LIMITED" in _say(router.handle(NUM, {"text": "check biffa waste"})[0])

    _intent("mark_paid", invoiceId=iid)
    router.handle(NUM, {"text": "mercer has paid"})
    assert db.get_invoice(iid)["status"] == "paid"

    print("\n".join(f"'{t}' -> {o[:70]!r}" for t, o in checks))


def test_guards_and_fallbacks(ready):
    # cross-business invoice is never touched
    other = db.create_business({"name": "Other Ltd", "email": "o@x.test", "cognitoSub": "s9"})
    oinv = db.create_invoice(other["businessId"], {"debtorName": "X", "amountPence": 1000,
                                                   "invoiceDate": "2026-07-01", "status": "confirmed"})
    _intent("open_invoice", invoiceId=oinv["invoiceId"])   # intent must reject a non-owned id -> menu
    assert any(r.get("type") == "interactive" for r in router.handle(NUM, {"text": "open that one"}))
    [r] = router.handle(NUM, {"tap_id": f"inv:{oinv['invoiceId']}"})
    assert "couldn't find" in _say(r).lower()
    # a truly unknown message falls back to the menu, not an error
    _intent("unknown")
    assert any(r.get("type") == "interactive" for r in router.handle(NUM, {"text": "zxcvbnm"}))


def test_cannot_act_before_login(business):
    num = "+233555001234"
    # any message -> welcome + login, never the menu or an action
    [r] = router.handle(num, {"text": "show me my invoices"})
    assert _row_ids(r) == ["login"]
    [r] = router.handle(num, {"tap_id": "summary"})   # a stray tap still can't reach data
    assert _row_ids(r) == ["login"]
