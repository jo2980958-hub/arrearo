"""Natural-language intent for the WhatsApp app.

Any message that is not a menu tap or an expected answer goes to Claude, which maps it
to a screen, a write action, or a short spoken reply, so the user can say what they want:
"add an invoice", "the one for 2450 pounds", "update business name to X",
"set Mercer's amount to 9000", "what am I owed", "show menu".

Full web parity: everything the dashboard does is reachable here. Claude only decides
WHERE to go and WHICH field/value the user named; the deterministic engine owns every
number, any invoice it names is validated against the caller's own invoices, and an
uncertain message falls back to the menu.
"""
from __future__ import annotations

from typing import Optional

from agent import llm
from common import config, db, flows

ACTIONS = ["summary", "invoices", "add_invoice", "create_invoice", "debtors", "settings",
           "edit_business", "edit_invoice", "timeline", "help", "menu", "logout",
           "open_invoice", "chase", "mark_paid", "lba", "confirm", "answer", "unknown"]

ROUTE_TOOL = {"toolSpec": {
    "name": "route",
    "description": "Decide what the user wants to do in the Arrearo WhatsApp app.",
    "inputSchema": {"json": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ACTIONS,
                       "description": "The single best match for the user's message."},
            "invoiceId": {"type": "string",
                          "description": "For open_invoice/chase/mark_paid/lba/confirm/edit_invoice/"
                                         "timeline: the exact invoiceId copied from the Invoices list. "
                                         "Never invent one."},
            "field": {"type": "string",
                      "description": "For edit_business: one of business name, email, bank name, sort "
                                     "code, account number, owner name, address. For edit_invoice: one "
                                     "of amount, customer, invoice date, due date, reference, "
                                     "description, debtor email, debtor number."},
            "value": {"type": "string", "description": "For edit_business/edit_invoice: the new value."},
            "query": {"type": "string", "description": "For debtors: the company name to look up."},
            "answer": {"type": "string",
                       "description": "For action=answer: a short plain-English reply using ONLY the "
                                      "facts provided. Never state a figure that is not in the facts."},
        },
        "required": ["action"],
    }},
}}

SYSTEM = (
    "You route messages in Arrearo, a WhatsApp app UK small businesses use to manage and chase late "
    "invoices. It can do everything the web dashboard does, including editing. Choose the single action "
    "that matches the user's message.\n"
    "- For one specific invoice (open it, chase it, mark it paid, letter before action, confirm it, edit "
    "a field on it, or show its history), copy the invoiceId EXACTLY from the Invoices list; match on "
    "amount, debtor name or reference. Never invent an invoiceId.\n"
    "- edit_business changes a business detail (name, email, bank, owner, address): set field and value.\n"
    "- edit_invoice changes a field on an invoice (amount, customer, dates, reference, description): set "
    "invoiceId, field and value.\n"
    "- create_invoice: the user wants to add an invoice and typed its details; add_invoice: they want to "
    "add one but gave no details (we will ask for a photo or PDF).\n"
    "- answer: a question you can answer from the facts given; keep it to one or two short sentences and "
    "never state a figure that is not in the facts (e.g. list the companies they have open invoices with).\n"
    "- menu for the menu or options; unknown when unsure."
)

_PREFIX = {"open_invoice": "inv", "chase": "chase", "mark_paid": "paid", "lba": "lba", "confirm": "confirm"}
_PLAIN = {"summary", "invoices", "add_invoice", "settings", "help", "menu", "logout"}


def _business_field(raw: str) -> Optional[str]:
    f = (raw or "").lower()
    if "owner" in f:
        return "ownerName"
    if "name" in f or "business" in f:
        return "name"
    if "email" in f:
        return "email"
    if "sort" in f:
        return "bankSortCode"
    if "account" in f:
        return "bankAccount"
    if "bank" in f:
        return "bankName"
    if "address" in f:
        return "address"
    return None


def _invoice_field(raw: str) -> Optional[str]:
    f = (raw or "").lower()
    if any(w in f for w in ("amount", "total", "price", "value")):
        return "amountPence"
    if any(w in f for w in ("customer", "debtor", "client")) or f.strip() == "name":
        return "debtorName"
    if "due" in f:
        return "agreedDueDate"
    if "date" in f:
        return "invoiceDate"
    if "ref" in f:
        return "reference"
    if "desc" in f:
        return "description"
    if "email" in f:
        return "debtorEmail"
    if any(w in f for w in ("number", "whatsapp", "phone")):
        return "debtorWhatsapp"
    return None


def _context(business_id: str) -> str:
    invoices = db.list_invoices_by_business(business_id)
    open_ = [i for i in invoices if i.get("status") in flows.OPEN_STATUSES]
    s = flows.portfolio_summary(invoices)
    lines = [f"Summary: {config.gbp(s['totalOwedPence'])} owed across {s['openCount']} open "
             f"invoice(s); {s['overdueCount']} overdue.", "Invoices:"]
    for i in open_[:40]:
        lines.append(f"- invoiceId={i['invoiceId']} | {i.get('debtorName')} | "
                     f"{config.gbp(i['totalOwedPence'])} | ref {i.get('reference') or '-'} | "
                     f"{i['status']} | {i['daysLate']}d late")
    if not open_:
        lines.append("- (no open invoices)")
    return "\n".join(lines)


def resolve(text: str, business_id: str, screen: Optional[str] = None) -> dict:
    """Return one of: route / debtor / answer / edit_business / edit_invoice / timeline /
    create_invoice / menu (the safe fallback)."""
    hint = ""
    if screen == "awaiting_debtor":
        hint = "\n\nThe user was just asked which company to check, so a bare company name means debtors."
    content = [{"text": f"User said: {text}\n\nContext:\n{_context(business_id)}{hint}"}]
    try:
        out = llm.converse_tool(config.BEDROCK_EXTRACT_MODEL, SYSTEM, content, ROUTE_TOOL, max_tokens=500)
    except Exception:
        return {"kind": "menu"}

    action = out.get("action")

    def owned_id():
        iid = out.get("invoiceId")
        inv = db.get_invoice(iid) if iid else None
        return iid if inv and inv.get("businessId") == business_id else None

    if action in _PLAIN:
        return {"kind": "route", "tap_id": action}
    if action == "create_invoice":
        return {"kind": "create_invoice"}
    if action == "debtors":
        return {"kind": "debtor", "query": out["query"]} if out.get("query") else {"kind": "route", "tap_id": "debtors"}
    if action in _PREFIX:
        iid = owned_id()
        return {"kind": "route", "tap_id": f"{_PREFIX[action]}:{iid}"} if iid else {"kind": "menu"}
    if action == "timeline":
        iid = owned_id()
        return {"kind": "timeline", "invoiceId": iid} if iid else {"kind": "menu"}
    if action == "edit_business":
        field = _business_field(out.get("field", ""))
        if field and out.get("value"):
            return {"kind": "edit_business", "field": field, "value": out["value"]}
        return {"kind": "menu"}
    if action == "edit_invoice":
        iid = owned_id()
        field = _invoice_field(out.get("field", ""))
        if iid and field and out.get("value"):
            return {"kind": "edit_invoice", "invoiceId": iid, "field": field, "value": out["value"]}
        return {"kind": "menu"}
    if action == "answer" and out.get("answer"):
        return {"kind": "answer", "text": out["answer"]}
    return {"kind": "menu"}
