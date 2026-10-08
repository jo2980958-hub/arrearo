"""End-to-end test of the WhatsApp app: login through navigation, driving the real
wa.router against the real session/auth/menus/views/actions modules."""
import re

import pytest

from common import cds, db
from wa import router, session


def body(reply: dict) -> str:
    """Pull the human text out of any Reply (text / buttons / list)."""
    if reply.get("type") == "text":
        return reply["text"]["body"]
    if reply.get("type") == "interactive":
        return reply["interactive"]["body"]["text"]
    return ""


def ids(reply: dict) -> list:
    """Button ids / list row ids in a Reply, for asserting navigation targets."""
    if reply.get("type") != "interactive":
        return []
    inter = reply["interactive"]
    if inter["type"] == "button":
        return [b["reply"]["id"] for b in inter["action"]["buttons"]]
    return [r["id"] for s in inter["action"]["sections"] for r in s["rows"]]


NUM = "+233555000111"


@pytest.fixture
def capture_email(monkeypatch):
    sent = {}

    def fake_send_email(to, subject, body, **kw):
        sent["to"] = to
        sent["code"] = re.search(r"\b(\d{6})\b", body).group(1)
        return "ses-test-id"

    monkeypatch.setattr(cds, "send_email", fake_send_email)
    return sent


def login(number, email, capture_email):
    """Run the whole login handshake and return the final replies."""
    router.handle(number, {"text": "hi"})                 # welcome
    router.handle(number, {"tap_id": "login"})            # ask for email
    router.handle(number, {"text": email})                # emails the code
    return router.handle(number, {"text": capture_email["code"]})  # verify -> linked


def test_logged_out_sees_only_welcome_and_login(business):
    [welcome] = router.handle(NUM, {"text": "hello"})
    assert "Arrearo" in body(welcome)
    assert ids(welcome) == ["login"]


def test_full_login_links_the_number(business, capture_email):
    replies = login(NUM, "sam@acme.test", capture_email)
    assert capture_email["to"] == "sam@acme.test"
    assert "logged in" in body(replies[0]).lower()
    assert "Acme Joinery Ltd" in body(replies[0])
    # the menu follows the confirmation
    assert "summary" in ids(replies[-1]) and "invoices" in ids(replies[-1])
    assert session.get(NUM)["state"] == session.AUTHED
    assert session.get(NUM)["businessId"] == business["businessId"]


def test_wrong_email_does_not_log_in(business):
    router.handle(NUM, {"text": "hi"})
    router.handle(NUM, {"tap_id": "login"})
    [r] = router.handle(NUM, {"text": "nobody@nowhere.test"})
    assert "couldn't find" in body(r).lower()
    assert session.get(NUM)["state"] != session.AUTHED


def test_navigation_after_login(business, invoice, capture_email):
    login(NUM, "sam@acme.test", capture_email)

    [summary] = router.handle(NUM, {"tap_id": "summary"})
    assert "owed" in body(summary).lower()

    [lst] = router.handle(NUM, {"tap_id": "invoices"})
    inv_rows = [i for i in ids(lst) if i.startswith("inv:")]
    assert f"inv:{invoice['invoiceId']}" in inv_rows

    detail = router.handle(NUM, {"tap_id": f"inv:{invoice['invoiceId']}"})
    assert "Late Payment of Commercial Debts" in body(detail[0])
    assert any("paid:" in i for r in detail for i in ids(r))


def test_mark_paid_through_the_router(business, invoice, capture_email):
    login(NUM, "sam@acme.test", capture_email)
    [r] = router.handle(NUM, {"tap_id": f"paid:{invoice['invoiceId']}"})
    assert "paid" in body(r).lower()
    assert db.get_invoice(invoice["invoiceId"])["status"] == "paid"


def test_cannot_touch_another_businesses_invoice(business, invoice, capture_email):
    other = db.create_business({"name": "Other Ltd", "email": "other@x.test", "cognitoSub": "sub-2"})
    other_inv = db.create_invoice(other["businessId"], {
        "debtorName": "X", "amountPence": 1000, "invoiceDate": "2026-07-01", "status": "confirmed"})
    login(NUM, "sam@acme.test", capture_email)
    [r] = router.handle(NUM, {"tap_id": f"inv:{other_inv['invoiceId']}"})
    assert "couldn't find" in body(r).lower()


def test_logout_unlinks(business, capture_email):
    login(NUM, "sam@acme.test", capture_email)
    [r] = router.handle(NUM, {"tap_id": "logout"})
    assert "logged out" in body(r).lower()
    assert session.get(NUM)["state"] == session.LOGGED_OUT
