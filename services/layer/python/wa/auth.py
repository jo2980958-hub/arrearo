"""WhatsApp login: email -> emailed OTP -> verify -> link the number.

No passwords in chat, ever. A 6-digit code, hashed at rest, 10-minute expiry,
3 verify attempts, resend throttle, per-number hourly request cap. Depends on
wa.session, common.db.get_business_by_email, common.cds.send_email, common.config.
Each public function returns a Reply (a wa.messages message dict) or a list of them.
Contract fixed by the spec — agent fills the bodies.
"""
from __future__ import annotations

OTP_TTL_SECONDS = 10 * 60
MAX_ATTEMPTS = 3
RESEND_THROTTLE_SECONDS = 60
MAX_REQUESTS_PER_HOUR = 5


def start_login(wa_number: str) -> dict:
    """Set AWAITING_EMAIL and ask for the account email."""
    raise NotImplementedError


def submit_email(wa_number: str, email: str) -> dict:
    """Resolve the account; on hit issue + email an OTP and set AWAITING_OTP,
    on miss report it and stay AWAITING_EMAIL."""
    raise NotImplementedError


def submit_otp(wa_number: str, code: str) -> dict:
    """Verify the code; on success link the number and return the main menu,
    on failure decrement attempts and return a retry (or restart)."""
    raise NotImplementedError


def logout(wa_number: str) -> dict:
    raise NotImplementedError
