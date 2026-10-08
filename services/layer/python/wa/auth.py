"""WhatsApp login: email -> emailed OTP -> verify -> link the number.

No passwords in chat, ever. A 6-digit code, hashed at rest, 10-minute expiry,
3 verify attempts, resend throttle, per-number hourly request cap. Depends on
wa.session, common.db.get_business_by_email, common.cds.send_email, common.config.
Each public function returns a Reply (a wa.messages message dict) or a list of them.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from common import cds, config, db
from wa import messages, session

OTP_TTL_SECONDS = 10 * 60
MAX_ATTEMPTS = 3
RESEND_THROTTLE_SECONDS = 60
MAX_REQUESTS_PER_HOUR = 5

CODE_DIGITS = 6


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _gen_code() -> str:
    """A 6-digit code from a cryptographic source, zero-padded."""
    return f"{secrets.randbelow(10 ** CODE_DIGITS):0{CODE_DIGITS}d}"


def _hash(code: str, salt: str) -> str:
    """Salted SHA-256 of the code. The code itself is never stored."""
    return hashlib.sha256((salt + code).encode("utf-8")).hexdigest()


def _business_email(business: dict) -> str:
    for field in ("email", "contactEmail", "ownerEmail"):
        value = business.get(field)
        if value:
            return str(value)
    return ""


def _mask_email(email: str) -> str:
    name, sep, domain = email.partition("@")
    if not sep or not name:
        return email
    return f"{name[0]}***@{domain}"


def start_login(wa_number: str) -> dict:
    """Set AWAITING_EMAIL and ask for the account email."""
    session.set_state(wa_number, session.AWAITING_EMAIL)
    return messages.text(
        "Let's log you in. What's the email on your Arrearo account? "
        "Send it and I'll email you a 6-digit code."
    )


def submit_email(wa_number: str, email: str) -> dict:
    """Resolve the account; on a hit issue and email an OTP and set AWAITING_OTP,
    on a miss report it and stay AWAITING_EMAIL."""
    business = db.get_business_by_email((email or "").strip())
    if not business:
        return messages.text(
            "I couldn't find an Arrearo account for that email. Check it and send it again."
        )

    current = session.get(wa_number)
    now = _now()
    requests = [r for r in (current.get("otpRequests") or [])
                if (now - _parse_iso(r)).total_seconds() < 3600]

    if requests:
        last = max(_parse_iso(r) for r in requests)
        if (now - last).total_seconds() < RESEND_THROTTLE_SECONDS:
            return messages.text("I just sent a code. Give it a minute before asking for another.")

    if len(requests) >= MAX_REQUESTS_PER_HOUR:
        return messages.text("That's too many code requests for now. Please try again in an hour.")

    code = _gen_code()
    salt = secrets.token_hex(16)
    requests.append(db.now_iso())
    expires = (now + timedelta(seconds=OTP_TTL_SECONDS)).isoformat(
        timespec="microseconds").replace("+00:00", "Z")

    session.set_state(
        wa_number, session.AWAITING_OTP,
        otpHash=_hash(code, salt), otpSalt=salt, otpExpiresAt=expires,
        otpAttempts=0, otpRequests=requests,
        pendingBusinessId=business["businessId"], pendingEmail=_business_email(business),
    )

    to_email = _business_email(business)
    cds.send_email(
        to=to_email,
        subject="Your Arrearo login code",
        body=(f"Your {config.BRAND} login code is {code}.\n\n"
              "It expires in 10 minutes. If you didn't ask to log in, you can ignore this email."),
    )
    return messages.text(
        f"I've emailed a 6-digit code to {_mask_email(to_email)}. It's good for 10 minutes. "
        "Send it back to me here."
    )


def submit_otp(wa_number: str, code: str) -> dict:
    """Verify the code; on success link the number, on failure count the attempt
    and return a retry, or restart after MAX_ATTEMPTS."""
    current = session.get(wa_number)
    expires = current.get("otpExpiresAt")

    if not expires or _now() > _parse_iso(expires):
        session.set_state(
            wa_number, session.AWAITING_EMAIL,
            otpHash=None, otpSalt=None, otpExpiresAt=None, otpAttempts=None,
            pendingBusinessId=None, pendingEmail=None,
        )
        return messages.text("That code has expired. Send your account email and I'll send a fresh one.")

    typed = "".join(ch for ch in str(code) if ch.isdigit())
    expected = current.get("otpHash") or ""
    candidate = _hash(typed, current.get("otpSalt") or "")

    if expected and hmac.compare_digest(candidate, expected):
        business_id = current.get("pendingBusinessId")
        session.link(wa_number, business_id)
        business = db.get_business(business_id) if business_id else None
        name = (business or {}).get("name") or "your account"
        return messages.text(f"You're logged in as {name}.")

    attempts = int(current.get("otpAttempts") or 0) + 1
    if attempts >= MAX_ATTEMPTS:
        session.set_state(
            wa_number, session.AWAITING_EMAIL,
            otpHash=None, otpSalt=None, otpExpiresAt=None, otpAttempts=None,
            pendingBusinessId=None, pendingEmail=None,
        )
        return messages.text(
            "That code was wrong too many times. Send your account email to start over."
        )

    session.set_state(wa_number, session.AWAITING_OTP, otpAttempts=attempts)
    remaining = MAX_ATTEMPTS - attempts
    plural = "attempt" if remaining == 1 else "attempts"
    return messages.text(f"That code didn't match. You have {remaining} {plural} left.")


def logout(wa_number: str) -> dict:
    session.unlink(wa_number)
    return messages.text("You're logged out.")
