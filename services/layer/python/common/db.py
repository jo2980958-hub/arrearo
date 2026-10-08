"""DynamoDB access for every Arrearo table (SPEC section 1).

Money is stored as integer pence. DynamoDB returns numbers as Decimal, so every
read goes through `_clean`, which turns whole Decimals back into int and the
rest into float. Derived money fields (daysLate, interestAccruedPence,
fixedRecoverySumPence, totalOwedPence) are never stored: `with_derived` computes
them on every read from `legal.engine`, so they cannot go stale.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

import boto3
from boto3.dynamodb.conditions import Key

from common import config
from legal import engine

_resource = None
_DAY = timedelta(hours=24)


def resource():
    global _resource
    if _resource is None:
        _resource = boto3.resource("dynamodb", region_name=config.REGION)
    return _resource


def set_resource(res) -> None:
    """Swap the DynamoDB resource (tests point this at a stubbed/moto one)."""
    global _resource
    _resource = res


def table(name: str):
    return resource().Table(name)


# ── helpers ─────────────────────────────────────────────────────────────────
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def new_id() -> str:
    return str(uuid.uuid4())


def _to_ddb(value: Any) -> Any:
    """Python -> DynamoDB: floats become Decimal, empty strings/None are dropped."""
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _to_ddb(v) for k, v in value.items() if v is not None and v != ""}
    if isinstance(value, (list, tuple)):
        return [_to_ddb(v) for v in value if v is not None]
    return value


def _clean(value: Any) -> Any:
    """DynamoDB -> Python: Decimal -> int when whole, else float."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean(v) for v in value]
    return value


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    return date.fromisoformat(str(value)[:10])


def _put(tbl: str, item: dict, **kw) -> dict:
    item = _to_ddb(item)
    table(tbl).put_item(Item=item, **kw)
    return _clean(item)


def _update(tbl: str, key: dict, fields: dict) -> dict:
    """SET the given fields (None removes the attribute) and return the new item."""
    fields = {k: v for k, v in fields.items() if k not in key}
    sets, removes, names, values = [], [], {}, {}
    for i, (k, v) in enumerate(fields.items()):
        names[f"#f{i}"] = k
        if v is None or v == "":
            removes.append(f"#f{i}")
        else:
            sets.append(f"#f{i} = :v{i}")
            values[f":v{i}"] = _to_ddb(v)
    expr = ""
    if sets:
        expr += "SET " + ", ".join(sets)
    if removes:
        expr += " REMOVE " + ", ".join(removes)
    if not expr:
        return _clean(table(tbl).get_item(Key=key).get("Item", {}))
    kwargs = {"Key": key, "UpdateExpression": expr.strip(), "ExpressionAttributeNames": names,
              "ReturnValues": "ALL_NEW", "ConditionExpression": "attribute_exists(#k0)"}
    kwargs["ExpressionAttributeNames"]["#k0"] = next(iter(key))
    if values:
        kwargs["ExpressionAttributeValues"] = values
    return _clean(table(tbl).update_item(**kwargs)["Attributes"])


def _query_all(tbl: str, **kw) -> list[dict]:
    items, start = [], None
    while True:
        if start:
            kw["ExclusiveStartKey"] = start
        r = table(tbl).query(**kw)
        items += r.get("Items", [])
        start = r.get("LastEvaluatedKey")
        if not start:
            return [_clean(i) for i in items]


# ── businesses ──────────────────────────────────────────────────────────────
def create_business(data: dict) -> dict:
    item = {"businessId": new_id(), "createdAt": now_iso(), **data}
    return _put(config.TBL_BUSINESSES, item)


def get_business(business_id: str) -> Optional[dict]:
    r = table(config.TBL_BUSINESSES).get_item(Key={"businessId": business_id})
    return _clean(r["Item"]) if "Item" in r else None


def update_business(business_id: str, fields: dict) -> dict:
    return _update(config.TBL_BUSINESSES, {"businessId": business_id}, fields)


def get_business_by_sub(cognito_sub: str) -> Optional[dict]:
    items = _query_all(config.TBL_BUSINESSES, IndexName="byCognitoSub",
                       KeyConditionExpression=Key("cognitoSub").eq(cognito_sub))
    return items[0] if items else None


def get_business_by_whatsapp(number: str) -> Optional[dict]:
    items = _query_all(config.TBL_BUSINESSES, IndexName="byWhatsapp",
                       KeyConditionExpression=Key("whatsappNumber").eq(normalise_e164(number)))
    return items[0] if items else None


def list_businesses() -> list[dict]:
    items, start = [], None
    while True:
        r = table(config.TBL_BUSINESSES).scan(**({"ExclusiveStartKey": start} if start else {}))
        items += r.get("Items", [])
        start = r.get("LastEvaluatedKey")
        if not start:
            return [_clean(i) for i in items]


def normalise_e164(number: str) -> str:
    """WhatsApp 'from' values arrive as bare digits; the data model stores +E.164."""
    digits = "".join(c for c in str(number) if c.isdigit())
    return f"+{digits}" if digits else ""


# ── invoices ────────────────────────────────────────────────────────────────
def create_invoice(business_id: str, data: dict) -> dict:
    """Insert an invoice. legallyLateDate is computed here by the engine, never supplied."""
    item = {"invoiceId": new_id(), "businessId": business_id, "currency": config.CURRENCY,
            "status": "extracted", "createdAt": now_iso(), **data}
    if item.get("debtorWhatsapp"):
        item["debtorWhatsapp"] = normalise_e164(item["debtorWhatsapp"])
    item["legallyLateDate"] = _compute_late_date(item).isoformat()
    return _put(config.TBL_INVOICES, item)


def _compute_late_date(inv: dict) -> date:
    return engine.legally_late_date(
        _parse_date(inv["invoiceDate"]), _parse_date(inv.get("deliveryDate")),
        _parse_date(inv.get("agreedDueDate")), inv.get("debtorType") or "business")


def get_invoice_raw(invoice_id: str) -> Optional[dict]:
    r = table(config.TBL_INVOICES).get_item(Key={"invoiceId": invoice_id})
    return _clean(r["Item"]) if "Item" in r else None


def get_invoice(invoice_id: str, today: Optional[date] = None) -> Optional[dict]:
    inv = get_invoice_raw(invoice_id)
    return with_derived(inv, today) if inv else None


_DATE_FIELDS = {"invoiceDate", "deliveryDate", "agreedDueDate", "debtorType"}


def update_invoice(invoice_id: str, fields: dict) -> dict:
    """Patch an invoice; recomputes legallyLateDate when a date input changes."""
    fields = dict(fields)
    if fields.get("debtorWhatsapp"):
        fields["debtorWhatsapp"] = normalise_e164(fields["debtorWhatsapp"])
    if _DATE_FIELDS & fields.keys():
        current = get_invoice_raw(invoice_id)
        if current is None:
            raise KeyError(invoice_id)
        merged = {**current, **fields}
        fields["legallyLateDate"] = _compute_late_date(merged).isoformat()
    return _update(config.TBL_INVOICES, {"invoiceId": invoice_id}, fields)


def list_invoices_by_business(business_id: str, today: Optional[date] = None) -> list[dict]:
    """Newest first, via the byBusiness GSI."""
    items = _query_all(config.TBL_INVOICES, IndexName="byBusiness", ScanIndexForward=False,
                       KeyConditionExpression=Key("businessId").eq(business_id))
    return [with_derived(i, today) for i in items]


def list_open_invoices_by_debtor_whatsapp(number: str, today: Optional[date] = None) -> list[dict]:
    items = _query_all(config.TBL_INVOICES, IndexName="byDebtorWhatsapp", ScanIndexForward=False,
                       KeyConditionExpression=Key("debtorWhatsapp").eq(normalise_e164(number)))
    open_ = [i for i in items if i.get("status") not in ("paid", "extracted")]
    return [with_derived(i, today) for i in open_]


def with_derived(inv: dict, today: Optional[date] = None) -> dict:
    """Add daysLate / interest / fixed sum / total, computed by the legal engine.

    A paid invoice stops accruing at its paidAt date. The fixed recovery sum only
    applies once the debt is actually late.
    """
    out = dict(inv)
    today = today or datetime.now(timezone.utc).date()
    if inv.get("status") == "paid" and inv.get("paidAt"):
        today = min(today, _parse_date(inv["paidAt"]))
    late_from = _parse_date(inv.get("legallyLateDate")) or _compute_late_date(inv)
    rate, ref_date, base = engine.statutory_rate_for(late_from)
    amount = int(inv["amountPence"])
    days = engine.days_late(late_from, today)
    interest = engine.interest_accrued_pence(amount, days, rate)
    fixed = engine.fixed_recovery_sum_pence(amount) if days > 0 else 0
    out.update({
        "legallyLateDate": late_from.isoformat(),
        "daysLate": days,
        "statutoryRatePct": rate,
        "baseRatePct": base,
        "dailyInterestPence": float(round(engine.daily_interest_pence(amount, rate), 4)),
        "interestAccruedPence": interest,
        "fixedRecoverySumPence": fixed,
        "totalOwedPence": engine.total_owed_pence(amount, interest, fixed),
    })
    return out


# ── debtors ─────────────────────────────────────────────────────────────────
def debtor_key(name: str, company_number: Optional[str] = None) -> str:
    if company_number:
        return str(company_number).strip().upper().zfill(8) if str(company_number).isdigit() else str(company_number).strip().upper()
    return " ".join(str(name).lower().split())


def put_debtor(data: dict) -> dict:
    item = {"debtorKey": data.get("debtorKey") or debtor_key(data["name"], data.get("companyNumber")),
            "fetchedAt": now_iso(), **data}
    return _put(config.TBL_DEBTORS, item)


def get_debtor(key: str) -> Optional[dict]:
    r = table(config.TBL_DEBTORS).get_item(Key={"debtorKey": key})
    return _clean(r["Item"]) if "Item" in r else None


# ── conversations ───────────────────────────────────────────────────────────
def add_message(whatsapp_number: str, direction: str, message_id: str, body: Optional[str] = None,
                **extra) -> dict:
    """Append a conversation row. extra: mediaId, intent, invoiceId, windowExpiresAt, raw."""
    created = now_iso()
    item = {"whatsappNumber": normalise_e164(whatsapp_number), "createdAt#messageId": f"{created}#{message_id}",
            "createdAt": created, "direction": direction, "messageId": message_id, "body": body, **extra}
    return _put(config.TBL_CONVERSATIONS, item)


def list_messages(whatsapp_number: str, limit: int = 50) -> list[dict]:
    r = table(config.TBL_CONVERSATIONS).query(
        KeyConditionExpression=Key("whatsappNumber").eq(normalise_e164(whatsapp_number)),
        ScanIndexForward=False, Limit=limit)
    return [_clean(i) for i in r.get("Items", [])]


def window_expires_at(whatsapp_number: str) -> Optional[str]:
    """The 24h free-form window: latest inbound message + 24h (never trust status events alone)."""
    for m in list_messages(whatsapp_number, limit=50):
        if m.get("direction") == "in":
            ts = datetime.fromisoformat(m["createdAt"].replace("Z", "+00:00"))
            return (ts + _DAY).isoformat(timespec="seconds").replace("+00:00", "Z")
    return None



def window_open(whatsapp_number: str, now: Optional[datetime] = None) -> bool:
    exp = window_expires_at(whatsapp_number)
    if not exp:
        return False
    now = now or datetime.now(timezone.utc)
    return now < datetime.fromisoformat(exp.replace("Z", "+00:00"))


def claim_message(message_id: str, ttl_days: int = 7) -> bool:
    """Idempotency guard for SNS redelivery: True the first time a wamid is seen."""
    from botocore.exceptions import ClientError
    try:
        table(config.TBL_EVENTS).put_item(
            Item={"invoiceId": f"dedupe#{message_id}", "createdAt#seq": "0",
                  "ttl": int(datetime.now(timezone.utc).timestamp()) + ttl_days * 86400},
            ConditionExpression="attribute_not_exists(invoiceId)")
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise


# ── events (audit timeline) ─────────────────────────────────────────────────
def add_event(invoice_id: str, type_: str, channel: str = "system", actor: str = "system",
              detail: Optional[dict] = None) -> dict:
    created = now_iso()
    item = {"invoiceId": invoice_id, "createdAt#seq": f"{created}#{uuid.uuid4().hex[:6]}",
            "type": type_, "channel": channel, "actor": actor, "detail": detail or {}, "createdAt": created}
    return _put(config.TBL_EVENTS, item)


def list_events(invoice_id: str) -> list[dict]:
    return _query_all(config.TBL_EVENTS, KeyConditionExpression=Key("invoiceId").eq(invoice_id))
