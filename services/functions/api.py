"""API Gateway HTTP API (payload v2) router. Cognito JWT claims arrive in
requestContext.authorizer.jwt.claims; every record is scoped to the caller's business."""
from __future__ import annotations

import base64
import json
import logging
import re
from datetime import date

from agent import draft as drafter
from common import config, db, flows
from legal import engine

log = logging.getLogger()
log.setLevel(logging.INFO)

INVOICE_FIELDS = {"debtorName", "debtorCompanyNumber", "debtorType", "debtorEmail", "debtorWhatsapp", "amountPence",
                  "invoiceDate", "deliveryDate", "agreedDueDate", "reference", "description", "promisedDate"}
BUSINESS_FIELDS = {"name", "ownerName", "email", "whatsappNumber", "sector", "defaultTermsDays", "bankName",
                   "bankSortCode", "bankAccount"}
DEBTOR_TYPES = ("company", "sole_trader", "individual", "public_authority")
STATUSES = ("extracted", "confirmed", "due", "chasing", "promised", "disputed", "paid", "lba", "escalated")
HEADERS = {"content-type": "application/json"}


class HttpError(Exception):
    def __init__(self, status, message, **extra):
        self.status, self.message, self.extra = status, message, extra


def resp(status, body):
    return {"statusCode": status, "headers": HEADERS, "body": json.dumps(body, default=str)}


def body_of(event) -> dict:
    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode()
    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        raise HttpError(400, "body must be JSON")
    if not isinstance(data, dict):
        raise HttpError(400, "body must be a JSON object")
    return data


def claims_of(event) -> dict:
    return (((event.get("requestContext") or {}).get("authorizer") or {}).get("jwt") or {}).get("claims") or {}


def current_business(event, required=True):
    sub = claims_of(event).get("sub")
    if not sub:
        raise HttpError(401, "unauthenticated")
    biz = db.get_business_by_sub(sub)
    if not biz and required:
        raise HttpError(404, "no business set up for this user; PUT /me first")
    return biz


def owned_invoice(event, invoice_id):
    biz = current_business(event)
    inv = db.get_invoice(invoice_id)
    if not inv or inv["businessId"] != biz["businessId"]:
        raise HttpError(404, "invoice not found")
    return biz, inv


def pick(data, allowed):
    return {k: v for k, v in data.items() if k in allowed}


def validate_invoice(fields, partial=False):
    if not partial:
        for k in ("debtorName", "amountPence", "invoiceDate"):
            if fields.get(k) in (None, ""):
                raise HttpError(400, f"{k} is required")
    if "amountPence" in fields and (not isinstance(fields["amountPence"], int) or isinstance(fields["amountPence"], bool)
                                    or fields["amountPence"] <= 0):
        raise HttpError(400, "amountPence must be a positive integer (pence)")
    if "debtorType" in fields and fields["debtorType"] not in DEBTOR_TYPES:
        raise HttpError(400, f"debtorType must be one of {DEBTOR_TYPES}")
    for k in ("invoiceDate", "deliveryDate", "agreedDueDate", "promisedDate"):
        if fields.get(k) and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(fields[k])):
            raise HttpError(400, f"{k} must be YYYY-MM-DD")


# ── routes ──────────────────────────────────────────────────────────────────
def health(event, params):
    return 200, {"ok": True, "service": config.APP_SLUG, "brand": config.BRAND}


def get_me(event, params):
    c = claims_of(event)
    biz = current_business(event, required=False)
    rate, _, base = engine.statutory_rate_for(date.today())
    return 200, {"user": {"sub": c.get("sub"), "email": c.get("email")}, "business": biz,
                 "brand": config.BRAND, "statutoryRatePct": rate, "baseRatePct": base}


def put_me(event, params):
    c = claims_of(event)
    data = pick(body_of(event), BUSINESS_FIELDS)
    if "whatsappNumber" in data:
        data["whatsappNumber"] = db.normalise_e164(data["whatsappNumber"])
    biz = current_business(event, required=False)
    if biz:
        biz = db.update_business(biz["businessId"], data)
    else:
        if not data.get("name"):
            raise HttpError(400, "name is required")
        data.setdefault("email", c.get("email"))
        data.setdefault("defaultTermsDays", 30)
        biz = db.create_business({**data, "cognitoSub": c["sub"]})
    return 200, {"business": biz}


def list_invoices(event, params):
    biz = current_business(event)
    invoices = db.list_invoices_by_business(biz["businessId"])
    status = (event.get("queryStringParameters") or {}).get("status")
    if status:
        invoices = [i for i in invoices if i["status"] == status]
    return 200, {"invoices": invoices, "summary": flows.portfolio_summary(invoices)}


def get_invoice(event, params):
    biz, inv = owned_invoice(event, params["id"])
    debtor = db.get_debtor(db.debtor_key(inv["debtorName"], inv.get("debtorCompanyNumber")))
    return 200, {"invoice": inv, "debtor": debtor, "events": db.list_events(inv["invoiceId"]),
                 "messages": db.list_messages(inv["debtorWhatsapp"]) if inv.get("debtorWhatsapp") else []}


def create_invoice(event, params):
    biz = current_business(event)
    fields = pick(body_of(event), INVOICE_FIELDS)
    validate_invoice(fields)
    fields.setdefault("debtorType", "company")
    inv = db.create_invoice(biz["businessId"], {**fields, "status": "confirmed", "sourceChannel": "dashboard",
                                                "confirmedAt": db.now_iso()})
    db.add_event(inv["invoiceId"], "created", "system", "owner", {})
    db.add_event(inv["invoiceId"], "confirmed", "system", "owner", {})
    flows.score_debtor(inv)
    return 201, {"invoice": db.get_invoice(inv["invoiceId"])}


def patch_invoice(event, params):
    biz, inv = owned_invoice(event, params["id"])
    data = body_of(event)
    fields = pick(data, INVOICE_FIELDS)
    validate_invoice(fields, partial=True)
    status = data.get("status")
    if status is not None and status not in STATUSES:
        raise HttpError(400, f"status must be one of {STATUSES}")
    if fields:
        db.update_invoice(inv["invoiceId"], fields)
    if status == "confirmed" and inv["status"] != "confirmed":
        return 200, {"invoice": flows.confirm_invoice(inv["invoiceId"])}
    if status == "paid" and inv["status"] != "paid":
        return 200, {"invoice": flows.mark_paid(inv["invoiceId"])}
    if status and status != inv["status"]:
        db.update_invoice(inv["invoiceId"], {"status": status})
        if status in ("disputed", "promised"):
            db.add_event(inv["invoiceId"], status, "system", "owner", {})
    return 200, {"invoice": db.get_invoice(inv["invoiceId"])}


def chase(event, params):
    """body {mode: "draft"|"send", message?, stage?, channel?}. Draft returns text for approve/edit/send."""
    biz, inv = owned_invoice(event, params["id"])
    data = body_of(event)
    mode = data.get("mode", "draft")
    if mode not in ("draft", "send"):
        raise HttpError(400, "mode must be draft or send")
    if inv["status"] in ("paid", "extracted"):
        raise HttpError(409, f"cannot chase an invoice that is {inv['status']}")
    try:
        if mode == "draft" or not data.get("message"):
            d = flows.draft_chase_for(inv["invoiceId"], data.get("stage"), data.get("channel"))
        else:
            d = {"message": data["message"], "stage": data.get("stage") or flows.choose_stage(inv),
                 "channel": data.get("channel") or flows.pick_channel(inv) or "email"}
        if mode == "draft":
            return 200, {"draft": d, "sent": False}
        if d["channel"] == "whatsapp" and not inv.get("debtorWhatsapp"):
            raise HttpError(422, "no WhatsApp number on this invoice")
        if d["channel"] == "email" and not inv.get("debtorEmail"):
            raise HttpError(422, "no email address on this invoice")
        result = flows.send_chase(inv["invoiceId"], d["message"], d["stage"], d["channel"], actor="owner")
    except drafter.ComplianceBlock as blocked:
        raise HttpError(422, "blocked by the compliance check; nothing was sent",
                        violations=[{"message": v.message, "span": v.span} for v in blocked.violations],
                        draft=blocked.text)
    return 200, {"draft": d, **result}


def lba(event, params):
    """body {mode: "draft"|"send", text?}."""
    biz, inv = owned_invoice(event, params["id"])
    data = body_of(event)
    mode = data.get("mode", "draft")
    if mode not in ("draft", "send"):
        raise HttpError(400, "mode must be draft or send")
    try:
        if mode == "draft" and not data.get("text"):
            debtor = db.get_debtor(db.debtor_key(inv["debtorName"], inv.get("debtorCompanyNumber")))
            return 200, {**drafter.draft_lba(inv, biz, debtor), "sent": False}
        return 200, flows.send_lba(inv["invoiceId"], data.get("text"), actor="owner")
    except drafter.ComplianceBlock as blocked:
        raise HttpError(422, "blocked by the compliance check; nothing was sent",
                        violations=[{"message": v.message, "span": v.span} for v in blocked.violations],
                        draft=blocked.text)


def invoice_events(event, params):
    biz, inv = owned_invoice(event, params["id"])
    return 200, {"events": db.list_events(inv["invoiceId"])}


def get_debtor(event, params):
    current_business(event)
    key = params["key"]
    debtor = db.get_debtor(key) or db.get_debtor(db.debtor_key(key))
    if not debtor:
        return 200, {"debtor": {"debtorKey": key, "riskBand": "unknown", "source": "unknown"}}
    return 200, {"debtor": debtor}


ROUTES = [
    ("GET", r"/health", health, False),
    ("GET", r"/me", get_me, True),
    ("PUT", r"/me", put_me, True),
    ("GET", r"/invoices", list_invoices, True),
    ("POST", r"/invoices", create_invoice, True),
    ("GET", r"/invoices/(?P<id>[^/]+)", get_invoice, True),
    ("PATCH", r"/invoices/(?P<id>[^/]+)", patch_invoice, True),
    ("POST", r"/invoices/(?P<id>[^/]+)/chase", chase, True),
    ("POST", r"/invoices/(?P<id>[^/]+)/lba", lba, True),
    ("GET", r"/invoices/(?P<id>[^/]+)/events", invoice_events, True),
    ("GET", r"/debtors/(?P<key>.+)", get_debtor, True),
]


def handler(event, context=None):
    method = (event.get("requestContext", {}).get("http", {}).get("method") or event.get("httpMethod", "")).upper()
    path = (event.get("rawPath") or event.get("path") or "/").rstrip("/") or "/"
    if method == "OPTIONS":
        return {"statusCode": 204, "headers": {}, "body": ""}
    try:
        for m, pattern, fn, _ in ROUTES:
            match = re.fullmatch(pattern, path)
            if match and m == method:
                status, payload = fn(event, match.groupdict())
                return resp(status, payload)
        known = any(re.fullmatch(p, path) for _, p, _, _ in ROUTES)
        raise HttpError(405 if known else 404, "method not allowed" if known else "not found")
    except HttpError as e:
        return resp(e.status, {"error": e.message, **e.extra})
    except Exception:   # noqa: BLE001
        log.exception("unhandled error on %s %s", method, path)
        return resp(500, {"error": "internal error"})
