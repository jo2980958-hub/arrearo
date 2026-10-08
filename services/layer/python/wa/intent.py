"""Natural-language intent for the WhatsApp app.

When a message is not a menu tap or an expected answer, Claude maps it to a screen,
an action, or a short spoken reply, so the user can just say what they want:
"add an invoice", "show me the one for 2450 pounds", "what am I owed", "show menu".

Claude only decides WHERE the user meant to go, or answers from facts we hand it. It
never computes money, dates or interest: those come from the deterministic engine, and
any invoice it names is validated against the caller's own invoices before we act.
A low-confidence or unparseable message falls back to the menu.
"""
from __future__ import annotations

from agent import llm
from common import config, db, flows

ACTIONS = ["summary", "invoices", "add_invoice", "debtors", "settings", "help", "menu",
           "logout", "open_invoice", "chase", "mark_paid", "lba", "confirm", "answer", "unknown"]

ROUTE_TOOL = {"toolSpec": {
    "name": "route",
    "description": "Decide what the user wants to do in the Arrearo WhatsApp app.",
    "inputSchema": {"json": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ACTIONS,
                       "description": "The single best match for the user's message."},
            "invoiceId": {"type": "string",
                          "description": "For open_invoice/chase/mark_paid/lba/confirm: the exact "
                                         "invoiceId copied from the Invoices list. Never invent one."},
            "query": {"type": "string", "description": "For debtors: the company name to look up."},
            "answer": {"type": "string",
                       "description": "For action=answer: a short plain-English reply using ONLY the "
                                      "facts provided. Never state a number that is not in the facts."},
        },
        "required": ["action"],
    }},
}}

SYSTEM = (
    "You route messages in Arrearo, a WhatsApp app UK small businesses use to chase late invoices. "
    "Choose the single action that matches what the user wants. "
    "For anything about one specific invoice (open it, chase it, mark it paid, send a letter before "
    "action, or confirm it), set action accordingly and copy its invoiceId EXACTLY from the Invoices "
    "list; match on amount, debtor name or invoice reference. Never invent an invoiceId. "
    "Use 'answer' for a question you can answer from the facts given, and keep it to one or two short "
    "sentences; never state a figure that is not in the facts. "
    "Use 'menu' when they ask for the menu or options. Use 'unknown' when you are not sure."
)

_PREFIX = {"open_invoice": "inv", "chase": "chase", "mark_paid": "paid", "lba": "lba", "confirm": "confirm"}
_PLAIN = {"summary", "invoices", "add_invoice", "settings", "help", "menu", "logout"}


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


def resolve(text: str, business_id: str) -> dict:
    """Return one of:
    {"kind":"route","tap_id": "<key[:arg]>"} | {"kind":"debtor","query": q}
    | {"kind":"answer","text": s} | {"kind":"menu"}  (the safe fallback)."""
    content = [{"text": f"User said: {text}\n\nContext:\n{_context(business_id)}"}]
    try:
        out = llm.converse_tool(config.BEDROCK_EXTRACT_MODEL, SYSTEM, content, ROUTE_TOOL, max_tokens=400)
    except Exception:
        return {"kind": "menu"}

    action = out.get("action")
    if action in _PLAIN:
        return {"kind": "route", "tap_id": action}
    if action == "debtors":
        return {"kind": "debtor", "query": out["query"]} if out.get("query") else {"kind": "route", "tap_id": "debtors"}
    if action in _PREFIX:
        iid = out.get("invoiceId")
        inv = db.get_invoice(iid) if iid else None
        if not inv or inv.get("businessId") != business_id:   # validate: never act on a guessed id
            return {"kind": "menu"}
        return {"kind": "route", "tap_id": f"{_PREFIX[action]}:{iid}"}
    if action == "answer" and out.get("answer"):
        return {"kind": "answer", "text": out["answer"]}
    return {"kind": "menu"}
