"""Read-only screens that mirror the dashboard. Each returns a Reply (or list).

Depends on common.db (reads), common.flows (portfolio_summary, OPEN_STATUSES,
CHASEABLE), common.config (gbp formatting), wa.messages. No writes here.

Button and row ids are the stable screen keys the router dispatches on:
`invoices`, `menu`, `inv:<id>`, `more:<page>`, `confirm:<id>`, `chase:<id>`,
`paid:<id>`, `lba:<id>`. Money is integer pence, rendered only with config.gbp.
"""
from __future__ import annotations

from common import config, db, flows
from wa import messages

# WhatsApp lists allow 10 rows. When more pages remain, the tenth slot holds the
# "More results" link, so a continued list shows up to 9 invoices and stays
# lossless: every invoice is reachable by paging.
PAGE_SIZE = 9


def summary(business_id: str) -> dict:
    """Outstanding total, interest/day, counts open/overdue/promised, via
    flows.portfolio_summary. Returns text + buttons."""
    invoices = db.list_invoices_by_business(business_id)
    s = flows.portfolio_summary(invoices)
    promised = sum(1 for i in invoices if i.get("status") == "promised")

    lines = [f"You are owed {config.gbp(s['totalOwedPence'])} across "
             f"{s['openCount']} open invoice{'' if s['openCount'] == 1 else 's'}."]
    daily = s.get("dailyInterestPence") or 0
    if daily > 0:
        lines.append(f"Interest is adding {config.gbp(round(daily))} a day.")
    lines.append(f"{s['openCount']} open · {s['overdueCount']} overdue · {promised} promised.")

    buttons = [("invoices", "Invoices"), ("menu", "Main menu")]
    return messages.buttons("\n".join(lines), buttons)


def invoice_list(business_id: str, page: int = 0) -> dict:
    """A list message of open invoices, newest first, paged. Rows open an invoice."""
    invoices = db.list_invoices_by_business(business_id)
    open_ = [i for i in invoices if i.get("status") in flows.OPEN_STATUSES]

    start = page * PAGE_SIZE
    window = open_[start:start + PAGE_SIZE]
    if not window:
        return messages.text("You have no open invoices right now.")

    rows = [{
        "id": f"inv:{i['invoiceId']}",
        "title": i.get("debtorName") or "Invoice",
        "description": f"{config.gbp(i['totalOwedPence'])} · {i['status']} · {i['daysLate']}d",
    } for i in window]

    if len(open_) > start + PAGE_SIZE:
        rows.append({"id": f"more:{page + 1}", "title": "More results"})

    sections = [{"title": "Your invoices", "rows": rows}]
    return messages.list_message("Tap an invoice to open it.", "Open", sections)


def invoice_detail(business_id: str, invoice_id: str) -> dict:
    """Full figures + legal basis + action buttons by status."""
    inv = db.get_invoice(invoice_id)
    if not inv or inv.get("businessId") != business_id:
        return messages.text("I couldn't find that invoice.")

    lines = [inv.get("debtorName") or "Invoice"]
    if inv.get("reference"):
        lines.append(f"Ref: {inv['reference']}")
    if inv.get("description"):
        lines.append(inv["description"])
    lines += [
        "",
        f"Invoice amount: {config.gbp(inv['amountPence'])}",
        f"Days late: {inv['daysLate']}",
        f"Statutory rate: {inv['statutoryRatePct']}%",
        f"Base rate: {inv['baseRatePct']}%",
        f"Interest accrued: {config.gbp(inv['interestAccruedPence'])}",
        f"Fixed recovery sum: {config.gbp(inv['fixedRecoverySumPence'])}",
        f"Total owed: {config.gbp(inv['totalOwedPence'])}",
        f"Status: {inv['status']}",
        f"Becomes legally late: {inv['legallyLateDate']}",
        "",
        "Legal basis: Late Payment of Commercial Debts (Interest) Act 1998.",
    ]
    detail = "\n".join(lines)

    iid = inv["invoiceId"]
    status = inv.get("status")
    if status == "extracted":
        actions = [(f"confirm:{iid}", "Confirm")]
    elif status in flows.CHASEABLE:
        actions = [(f"chase:{iid}", "Send chase"),
                   (f"paid:{iid}", "Mark paid"),
                   (f"lba:{iid}", "Letter Before Action")]
    else:
        actions = []

    if not actions:
        return messages.text(detail)
    if len(detail) <= 1000:
        return messages.buttons(detail, actions)
    return [messages.text(detail), messages.buttons("What next?", actions)]


def timeline(business_id: str, invoice_id: str) -> dict:
    """The recent history of one invoice: created, extracted, confirmed, chased, replied."""
    inv = db.get_invoice(invoice_id)
    if not inv or inv.get("businessId") != business_id:
        return messages.text("I couldn't find that invoice.")
    events = db.list_events(invoice_id)
    if not events:
        return messages.text(f"No history yet for {inv.get('debtorName') or 'that invoice'}.")
    label = {"created": "received", "extracted": "read", "confirmed": "confirmed",
             "scored": "risk scored", "chased": "chased", "replied": "debtor replied",
             "promised": "promise to pay", "disputed": "disputed", "paid": "marked paid",
             "lba_drafted": "LBA drafted", "lba_sent": "LBA sent"}
    lines = [f"History for {inv.get('debtorName') or 'invoice'} (ref {inv.get('reference') or '-'}):"]
    for e in events[-12:]:
        when = str(e.get("createdAt", ""))[:10]
        lines.append(f"- {when}  {label.get(e.get('type'), e.get('type'))}")
    return messages.text("\n".join(lines))


def debtor(business_id: str, query: str) -> dict:
    """Risk band, avg days to pay, share paid late for a named debtor; unknown stays unknown."""
    d = db.find_debtor_by_name(query)
    if not d:
        return messages.text(f'I don\'t have payment data on "{query}" yet.')

    lines = [d.get("name") or query]
    if d.get("riskBand"):
        lines.append(f"Risk band: {d['riskBand']}")
    if d.get("avgDaysToPay") is not None:
        lines.append(f"Average days to pay: {d['avgDaysToPay']}")
    if d.get("pctPaidLate") is not None:
        lines.append(f"Paid late: {d['pctPaidLate']}%")
    if d.get("source"):
        lines.append(f"Source: {d['source']}")
    return messages.text("\n".join(lines))


def settings(business_id: str) -> dict:
    """Business details, bank account masked to the last two digits. View-only."""
    b = db.get_business(business_id)
    if not b:
        return messages.text("I couldn't load your business details.")

    acct = str(b.get("bankAccount") or "")
    if len(acct) >= 2:
        masked = "•" * (len(acct) - 2) + acct[-2:]
    elif acct:
        masked = acct
    else:
        masked = "not set"

    lines = [b.get("name") or "Your business"]
    if b.get("email"):
        lines.append(f"Email: {b['email']}")
    if b.get("bankName"):
        lines.append(f"Bank: {b['bankName']}")
    if b.get("bankSortCode"):
        lines.append(f"Sort code: {b['bankSortCode']}")
    lines.append(f"Account: {masked}")
    lines += ["", "To change any of these, just tell me, e.g. \"update the sort code to 01-02-03\"."]
    return messages.text("\n".join(lines))
