import json

import api
from common import db


def call(method, path, body=None, sub="sub-1", qs=None):
    ev = {"rawPath": path, "requestContext": {"http": {"method": method},
                                              "authorizer": {"jwt": {"claims": {"sub": sub, "email": "o@x.test"}}}},
          "queryStringParameters": qs}
    if body is not None:
        ev["body"] = json.dumps(body)
    r = api.handler(ev)
    return r["statusCode"], json.loads(r["body"]) if r["body"] else None


def test_health_needs_no_claims():
    r = api.handler({"rawPath": "/health", "requestContext": {"http": {"method": "GET"}}})
    assert r["statusCode"] == 200


def test_me_before_and_after_onboarding():
    code, body = call("GET", "/me", sub="new-user")
    assert code == 200 and body["business"] is None and body["statutoryRatePct"] == 11.75
    assert call("GET", "/invoices", sub="new-user")[0] == 404
    code, body = call("PUT", "/me", {"name": "Fresh Ltd", "whatsappNumber": "07700 900555", "bogus": 1}, sub="new-user")
    assert code == 200 and body["business"]["name"] == "Fresh Ltd" and "bogus" not in body["business"]
    assert call("GET", "/me", sub="new-user")[1]["business"]["email"] == "o@x.test"


def test_invoice_list_detail_events_and_summary(business, invoice):
    code, body = call("GET", "/invoices")
    assert code == 200 and len(body["invoices"]) == 1
    assert body["invoices"][0]["totalOwedPence"] >= 250_000
    assert body["summary"]["openCount"] == 1 and body["summary"]["outstandingPence"] == 250_000
    code, body = call("GET", f"/invoices/{invoice['invoiceId']}")
    assert code == 200 and body["invoice"]["reference"] == "INV-1042" and body["debtor"] is None
    code, body = call("GET", f"/invoices/{invoice['invoiceId']}/events")
    assert code == 200 and body["events"] == []


def test_other_business_cannot_see_invoice(business, invoice):
    db.create_business({"name": "Other", "cognitoSub": "sub-2"})
    assert call("GET", f"/invoices/{invoice['invoiceId']}", sub="sub-2")[0] == 404
    assert call("PATCH", f"/invoices/{invoice['invoiceId']}", {"status": "paid"}, sub="sub-2")[0] == 404


def test_create_invoice_validates_and_logs_events(business):
    assert call("POST", "/invoices", {"debtorName": "X"})[0] == 400
    assert call("POST", "/invoices", {"debtorName": "X", "invoiceDate": "2026-07-01", "amountPence": 12.5})[0] == 400
    code, body = call("POST", "/invoices", {"debtorName": "Acme Ltd", "invoiceDate": "2026-07-01", "amountPence": 99999})
    assert code == 201 and body["invoice"]["status"] == "confirmed" and body["invoice"]["fixedRecoverySumPence"] == 4000
    types = [e["type"] for e in call("GET", f"/invoices/{body['invoice']['invoiceId']}/events")[1]["events"]]
    assert types == ["created", "confirmed", "debtor_scored"]


def test_patch_paid_and_confirm(business, invoice):
    code, body = call("PATCH", f"/invoices/{invoice['invoiceId']}", {"status": "paid"})
    assert code == 200 and body["invoice"]["status"] == "paid" and body["invoice"]["paidAt"]
    assert call("PATCH", f"/invoices/{invoice['invoiceId']}", {"status": "weird"})[0] == 400


def test_chase_draft_then_send_dry_run(business, invoice):
    from agent import llm
    from fakes import FakeBedrock
    from datetime import date
    inv = db.get_invoice(invoice["invoiceId"])
    total = db.config.gbp(inv["totalOwedPence"])
    msg = f"Invoice INV-1042 for £2,500.00 is overdue. Total now owed {total}."
    llm.set_client(FakeBedrock(texts=[msg]))
    code, body = call("POST", f"/invoices/{invoice['invoiceId']}/chase", {"mode": "draft"})
    assert code == 200 and body["draft"]["message"] == msg and body["sent"] is False
    code, body = call("POST", f"/invoices/{invoice['invoiceId']}/chase", {"mode": "send", "message": msg, "channel": "email"})
    assert code == 200 and body["sent"] is False and body["dryRun"] is True      # SEND_MODE unset -> dry
    assert db.list_events(invoice["invoiceId"]) == []                              # nothing recorded as sent


def test_chase_blocked_by_compliance_returns_422(business, invoice):
    code, body = call("POST", f"/invoices/{invoice['invoiceId']}/chase",
                      {"mode": "send", "message": "Pay or the police will visit", "channel": "email"})
    assert code == 422 and body["violations"]
    assert [e["type"] for e in db.list_events(invoice["invoiceId"])] == ["compliance_block"]


def test_debtor_unknown_never_guessed(business):
    code, body = call("GET", "/debtors/acme%20ltd")
    assert code == 200 and body["debtor"]["riskBand"] == "unknown"


def test_unknown_route_and_method():
    assert call("GET", "/nope")[0] == 404
    assert call("DELETE", "/me")[0] == 405
