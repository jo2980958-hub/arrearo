"""Per-number WhatsApp session state and account link.

Owns DynamoDB table ``config.TBL_WA_SESSIONS`` (PK ``waNumber``). Holds the login
state machine, the persisted number->business link, and the transient navigation
context. Does NOT import common.db; it manages its own table so it stays isolated.
Contract fixed by the spec — agent fills the bodies.
"""
from __future__ import annotations

from typing import Optional

# login states
LOGGED_OUT = "logged_out"
AWAITING_EMAIL = "awaiting_email"
AWAITING_OTP = "awaiting_otp"
AUTHED = "authed"

CONTEXT_TTL_SECONDS = 30 * 60   # navigation context is stale after this


def get(wa_number: str) -> dict:
    """Return the session record, or a fresh default {waNumber, state: LOGGED_OUT}."""
    raise NotImplementedError


def save(session: dict) -> None:
    raise NotImplementedError


def set_state(wa_number: str, state: str, **fields) -> dict:
    raise NotImplementedError


def set_context(wa_number: str, screen: str, params: Optional[dict] = None) -> dict:
    raise NotImplementedError


def clear_context(wa_number: str) -> None:
    raise NotImplementedError


def link(wa_number: str, business_id: str) -> dict:
    """Persist the number->business link and set state AUTHED."""
    raise NotImplementedError


def unlink(wa_number: str) -> dict:
    """Clear the link + context and set state LOGGED_OUT."""
    raise NotImplementedError
