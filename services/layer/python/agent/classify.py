"""Debtor reply -> intent (Haiku, forced tool call)."""
from __future__ import annotations

from datetime import date
from typing import Optional

from agent import llm
from common import config

INTENTS = ["promise_to_pay", "dispute", "not_received", "paid", "question", "other"]

CLASSIFY_TOOL = {"toolSpec": {
    "name": "classify_reply",
    "description": "Classify a debtor's WhatsApp reply to a payment chase.",
    "inputSchema": {"json": {
        "type": "object",
        "properties": {
            "intent": {"type": "string", "enum": INTENTS},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "promisedDate": {"type": ["string", "null"], "description": "ISO date the debtor says they will pay, else null"},
            "optOut": {"type": "boolean", "description": "True if they ask us to stop contacting them"},
        },
        "required": ["intent", "confidence"],
    }},
}}

SYSTEM = ("You classify replies from a customer who has been chased about a late invoice. "
          "promise_to_pay: says they will pay (resolve relative dates against today's date). "
          "dispute: disagrees with the amount or the work. not_received: never got the invoice or goods. "
          "paid: says it has already been paid. question: asks something. other: anything else. "
          "Output only via the tool.")


def classify_reply(text: str, invoice: Optional[dict] = None, today: Optional[date] = None) -> dict:
    today = today or date.today()
    ctx = ""
    if invoice:
        ctx = (f"Invoice context: {invoice.get('reference') or 'no reference'}, "
               f"{config.gbp(invoice['amountPence'])}, status {invoice.get('status')}.\n")
    r = llm.converse_tool(config.BEDROCK_EXTRACT_MODEL, SYSTEM,
                          [{"text": f"Today is {today.isoformat()} ({today.strftime('%A')}).\n{ctx}Reply: {text!r}"}],
                          CLASSIFY_TOOL, max_tokens=300)
    intent = r.get("intent") if r.get("intent") in INTENTS else "other"
    promised = r.get("promisedDate")
    try:
        promised = date.fromisoformat(promised).isoformat() if promised else None
    except ValueError:
        promised = None
    return {"intent": intent, "confidence": float(r.get("confidence") or 0),
            "extracted": {"promisedDate": promised} if promised else {},
            "optOut": bool(r.get("optOut"))}
