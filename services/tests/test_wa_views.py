"""Tests for wa.views — the read-only WhatsApp screens.

Uses the autouse moto harness (conftest.py) and the `business` fixture. No live AWS.
"""
from common import config, db
from wa import views


def _mk(business_id, status, debtor="Bluebell Builders Ltd", amount=250_000):
    return db.create_invoice(business_id, {
        "debtorName": debtor, "debtorType": "company", "amountPence": amount,
        "invoiceDate": "2026-01-01", "reference": f"INV-{status}", "description": "Work done",
        "status": status})


def _body(reply):
    """The human-readable body text out of any reply shape."""
    if reply.get("type") == "text":
        return reply["text"]["body"]
    return reply["interactive"]["body"]["text"]


# ── summary ──────────────────────────────────────────────────────────────────
def test_summary_totals_counts_and_buttons(business):
    bid = business["businessId"]
    _mk(bid, "confirmed")          # open, overdue (invoiceDate in the past)
    _mk(bid, "due")                # open, overdue
    _mk(bid, "promised")           # open, overdue, promised
    _mk(bid, "paid")               # not open
    _mk(bid, "extracted")          # not open (not in OPEN_STATUSES)

    r = views.summary(bid)
    assert r["type"] == "interactive" and r["interactive"]["type"] == "button"
    body = _body(r)

    invoices = db.list_invoices_by_business(bid)
    from common import flows
    s = flows.portfolio_summary(invoices)
    assert config.gbp(s["totalOwedPence"]) in body
    assert s["openCount"] == 3
    assert "3 open" in body and "overdue" in body and "1 promised" in body

    ids = [b["reply"]["id"] for b in r["interactive"]["action"]["buttons"]]
    assert ids == ["invoices", "menu"]


def test_summary_interest_per_day_shown_when_overdue(business):
    bid = business["businessId"]
    _mk(bid, "confirmed")
    body = _body(views.summary(bid))
    assert "a day" in body


# ── invoice_list ─────────────────────────────────────────────────────────────
def test_invoice_list_rows_and_ids(business):
    bid = business["businessId"]
    inv = _mk(bid, "confirmed")
    _mk(bid, "paid")               # excluded (not open)

    r = views.invoice_list(bid)
    assert r["interactive"]["type"] == "list"
    sections = r["interactive"]["action"]["sections"]
    assert sections[0]["title"] == "Your invoices"
    rows = sections[0]["rows"]
    assert [row["id"] for row in rows] == [f"inv:{inv['invoiceId']}"]
    assert rows[0]["title"] == "Bluebell Builders Ltd"
    assert config.gbp(db.get_invoice(inv["invoiceId"])["totalOwedPence"]) in rows[0]["description"]


def test_invoice_list_pagination_more_row(business):
    bid = business["businessId"]
    created = [_mk(bid, "confirmed", debtor=f"Debtor {n:02d}") for n in range(12)]
    open_ids = {i["invoiceId"] for i in created}

    page0 = views.invoice_list(bid, 0)
    rows0 = page0["interactive"]["action"]["sections"][0]["rows"]
    assert len(rows0) == 10                      # 9 invoices + the More row
    assert rows0[-1]["id"] == "more:1"
    assert rows0[-1]["title"] == "More results"

    page1 = views.invoice_list(bid, 1)
    rows1 = page1["interactive"]["action"]["sections"][0]["rows"]
    assert len(rows1) == 3                        # remaining invoices, no More row
    assert all(not row["id"].startswith("more:") for row in rows1)

    # every invoice is reachable across the two pages, none duplicated or lost
    seen = {row["id"].split("inv:")[1] for row in rows0 + rows1 if row["id"].startswith("inv:")}
    assert seen == open_ids


def test_invoice_list_empty(business):
    r = views.invoice_list(business["businessId"])
    assert r["type"] == "text" and "no open invoices" in _body(r)


# ── invoice_detail ───────────────────────────────────────────────────────────
def test_invoice_detail_guard_wrong_business(business):
    other = db.create_business({"name": "Other Ltd", "cognitoSub": "sub-9"})
    inv = _mk(business["businessId"], "confirmed")
    r = views.invoice_detail(other["businessId"], inv["invoiceId"])
    assert r["type"] == "text" and _body(r) == "I couldn't find that invoice."


def test_invoice_detail_missing_invoice(business):
    r = views.invoice_detail(business["businessId"], "does-not-exist")
    assert r["type"] == "text" and _body(r) == "I couldn't find that invoice."


def test_invoice_detail_figures_and_legal_basis(business):
    bid = business["businessId"]
    inv = _mk(bid, "confirmed")
    full = db.get_invoice(inv["invoiceId"])
    r = views.invoice_detail(bid, inv["invoiceId"])
    body = _body(r)
    assert config.gbp(full["totalOwedPence"]) in body
    assert config.gbp(full["interestAccruedPence"]) in body
    assert f"{full['statutoryRatePct']}%" in body
    assert f"{full['baseRatePct']}%" in body
    assert "Late Payment of Commercial Debts (Interest) Act 1998." in body


def test_invoice_detail_extracted_shows_confirm_only(business):
    bid = business["businessId"]
    inv = _mk(bid, "extracted")
    r = views.invoice_detail(bid, inv["invoiceId"])
    ids = [b["reply"]["id"] for b in r["interactive"]["action"]["buttons"]]
    assert ids == [f"confirm:{inv['invoiceId']}"]


def test_invoice_detail_chaseable_shows_three_actions(business):
    bid = business["businessId"]
    inv = _mk(bid, "due")
    r = views.invoice_detail(bid, inv["invoiceId"])
    iid = inv["invoiceId"]
    ids = [b["reply"]["id"] for b in r["interactive"]["action"]["buttons"]]
    assert ids == [f"chase:{iid}", f"paid:{iid}", f"lba:{iid}"]


def test_invoice_detail_terminal_status_no_actions(business):
    bid = business["businessId"]
    inv = _mk(bid, "paid")
    r = views.invoice_detail(bid, inv["invoiceId"])
    assert r["type"] == "text"
    assert "Late Payment of Commercial Debts (Interest) Act 1998." in _body(r)


# ── debtor ───────────────────────────────────────────────────────────────────
def test_debtor_known(business):
    db.put_debtor({"name": "Bluebell Builders Ltd", "avgDaysToPay": 52, "pctPaidLate": 30,
                   "riskBand": "high", "source": "payment-practices"})
    r = views.debtor(business["businessId"], "Bluebell Builders Ltd")
    body = _body(r)
    assert "high" in body and "52" in body and "30%" in body


def test_debtor_unknown(business):
    r = views.debtor(business["businessId"], "Nobody Ltd")
    assert r["type"] == "text"
    assert _body(r) == 'I don\'t have payment data on "Nobody Ltd" yet.'


# ── settings ─────────────────────────────────────────────────────────────────
def test_settings_masks_account_to_last_two_digits(business):
    r = views.settings(business["businessId"])
    body = _body(r)
    assert "••••••78" in body            # 12345678 -> last two shown
    assert "12345678" not in body
    assert "Acme Joinery Ltd" in body
    assert "sam@acme.test" in body
    assert "Monzo" in body
