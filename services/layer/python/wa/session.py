"""Per-number WhatsApp session state and account link.

Owns DynamoDB table ``config.TBL_WA_SESSIONS`` (PK ``waNumber``). Holds the login
state machine, the persisted number->business link, and the transient navigation
context. Reads and writes the table through ``common.db.table`` so tests can stub
the resource with ``db.set_resource``. It never touches other business tables, so
it stays isolated.
"""
from __future__ import annotations

from typing import Optional

from common import config, db

# login states
LOGGED_OUT = "logged_out"
AWAITING_EMAIL = "awaiting_email"
AWAITING_OTP = "awaiting_otp"
AUTHED = "authed"

CONTEXT_TTL_SECONDS = 30 * 60   # navigation context is stale after this

# fields grouped so link/unlink can clear the right ones
_LINK_FIELDS = ("businessId", "linkedAt")
_OTP_FIELDS = ("otpHash", "otpSalt", "otpExpiresAt", "otpAttempts",
               "otpRequests", "pendingBusinessId", "pendingEmail")
_CONTEXT_FIELD = "context"


def _table():
    return db.table(config.TBL_WA_SESSIONS)


def get(wa_number: str) -> dict:
    """Return the session record, or a fresh default {waNumber, state: LOGGED_OUT}."""
    item = _table().get_item(Key={"waNumber": wa_number}).get("Item")
    if not item:
        return {"waNumber": wa_number, "state": LOGGED_OUT}
    return db._clean(item)


def save(session: dict) -> None:
    """Write the whole record back. A put replaces the item, so a field dropped
    from the dict is removed from storage. None and empty values are not stored."""
    item = dict(session)
    item.setdefault("state", LOGGED_OUT)
    item["updatedAt"] = db.now_iso()
    _table().put_item(Item=db._to_ddb(item))


def set_state(wa_number: str, state: str, **fields) -> dict:
    """Set the state and merge the given fields. A field passed as None is removed."""
    session = get(wa_number)
    session["state"] = state
    for key, value in fields.items():
        if value is None:
            session.pop(key, None)
        else:
            session[key] = value
    save(session)
    return session


def set_context(wa_number: str, screen: str, params: Optional[dict] = None) -> dict:
    """Stamp the transient navigation context. Callers treat it stale after
    CONTEXT_TTL_SECONDS by comparing now against contextAt."""
    session = get(wa_number)
    session[_CONTEXT_FIELD] = {"screen": screen, "params": params or {}, "contextAt": db.now_iso()}
    save(session)
    return session


def clear_context(wa_number: str) -> None:
    session = get(wa_number)
    session.pop(_CONTEXT_FIELD, None)
    save(session)


def link(wa_number: str, business_id: str) -> dict:
    """Persist the number->business link and set state AUTHED.
    Clears the pending login and OTP working fields."""
    session = get(wa_number)
    session["state"] = AUTHED
    session["businessId"] = business_id
    session["linkedAt"] = db.now_iso()
    for field in _OTP_FIELDS:
        session.pop(field, None)
    save(session)
    return session


def unlink(wa_number: str) -> dict:
    """Clear the link, context and OTP fields and set state LOGGED_OUT."""
    session = get(wa_number)
    session["state"] = LOGGED_OUT
    for field in _LINK_FIELDS + _OTP_FIELDS + (_CONTEXT_FIELD,):
        session.pop(field, None)
    save(session)
    return session
