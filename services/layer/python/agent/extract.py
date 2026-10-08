"""Invoice extraction (Haiku vision / text). Reads fields; never invents an amount.

Money leaves this module as integer pence. A missing or unreadable amount stays
None and forces needsConfirmation, so the owner is always asked rather than the
model guessing.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from agent import llm
from common import config

FMT = {"image/jpeg": "jpeg", "image/jpg": "jpeg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}
CONFIDENCE_FLOOR = 0.8

INVOICE_TOOL = {"toolSpec": {
    "name": "record_invoice",
    "description": "Record the fields read from an invoice. Use null when a field is not visible. Never guess.",
    "inputSchema": {"json": {
        "type": "object",
        "properties": {
            "is_invoice": {"type": "boolean"},
            "supplier_name": {"type": ["string", "null"]},
            "customer_name": {"type": ["string", "null"], "description": "Who is billed: the debtor"},
            "invoice_number": {"type": ["string", "null"]},
            "description": {"type": ["string", "null"], "description": "What the invoice is for, a few words"},
            "invoice_date": {"type": ["string", "null"], "description": "ISO 8601 YYYY-MM-DD"},
            "delivery_date": {"type": ["string", "null"], "description": "Date goods/services delivered, ISO 8601"},
            "due_date": {"type": ["string", "null"], "description": "ISO 8601 YYYY-MM-DD, only if printed"},
            "payment_terms_days": {"type": ["integer", "null"]},
            "currency": {"type": ["string", "null"]},
            "net_amount": {"type": ["number", "null"]},
            "vat_amount": {"type": ["number", "null"]},
            "gross_amount": {"type": ["number", "null"], "description": "Total payable incl. VAT"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "unreadable_fields": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["is_invoice", "confidence"],
    }},
}}

SYSTEM = ("You extract data from photos and text of UK invoices for a late-payment recovery tool. "
          "Output only via the tool. Copy values exactly as printed. If a value is not clearly visible, "
          "return null and list the field in unreadable_fields. Never estimate or calculate an amount.")


def _pence(amount) -> Optional[int]:
    if amount is None:
        return None
    return int((Decimal(str(amount)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _date(v) -> Optional[str]:
    try:
        return date.fromisoformat(str(v)[:10]).isoformat() if v else None
    except ValueError:
        return None


def normalise(raw: dict) -> dict:
    """Tool output -> the invoice fields of SPEC section 1, plus confirmation flags."""
    gross = raw.get("gross_amount")
    if gross is None and raw.get("net_amount") is not None and raw.get("vat_amount") is not None:
        gross = Decimal(str(raw["net_amount"])) + Decimal(str(raw["vat_amount"]))
    amount = _pence(gross)
    invoice_date = _date(raw.get("invoice_date"))
    agreed = _date(raw.get("due_date"))
    if agreed is None and invoice_date and raw.get("payment_terms_days"):
        agreed = (date.fromisoformat(invoice_date) + timedelta(days=int(raw["payment_terms_days"]))).isoformat()
    confidence = float(raw.get("confidence") or 0)
    missing = [k for k, v in (("amountPence", amount), ("debtorName", raw.get("customer_name")),
                              ("invoiceDate", invoice_date)) if not v]
    if missing:
        confidence = min(confidence, 0.5)
    out = {
        "isInvoice": bool(raw.get("is_invoice")),
        "debtorName": raw.get("customer_name"),
        "amountPence": amount,
        "currency": (raw.get("currency") or config.CURRENCY).upper(),
        "invoiceDate": invoice_date,
        "deliveryDate": _date(raw.get("delivery_date")),
        "agreedDueDate": agreed,
        "reference": raw.get("invoice_number"),
        "description": raw.get("description"),
        "extractionConfidence": round(confidence, 3),
        "unreadableFields": raw.get("unreadable_fields") or [],
        "missingFields": missing,
    }
    out["needsConfirmation"] = (not out["isInvoice"]) or confidence < CONFIDENCE_FLOOR or bool(missing)
    return out


def extract_from_image(image_bytes: bytes, mime: str) -> dict:
    fmt = FMT.get((mime or "").lower())
    if not fmt:
        raise ValueError(f"unsupported image type: {mime}")
    raw = llm.converse_tool(
        config.BEDROCK_EXTRACT_MODEL, SYSTEM,
        [{"image": {"format": fmt, "source": {"bytes": image_bytes}}},
         {"text": "Extract the invoice fields. Dates as YYYY-MM-DD. Amounts as plain numbers."}],
        INVOICE_TOOL)
    return normalise(raw)


def extract_from_text(text: str) -> dict:
    raw = llm.converse_tool(
        config.BEDROCK_EXTRACT_MODEL, SYSTEM,
        [{"text": f"Extract the invoice fields from this message. Dates as YYYY-MM-DD.\n\n{text}"}],
        INVOICE_TOOL)
    return normalise(raw)
