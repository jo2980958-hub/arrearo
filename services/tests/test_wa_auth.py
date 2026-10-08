"""Tests for the WhatsApp login state machine (wa.session + wa.auth).

The OTP code is never stored in the clear, so the tests capture the email body
that auth.submit_email sends, pull the six digits out of it, and submit those.
"""
import re
from datetime import datetime, timedelta, timezone

import pytest

from common import cds
from wa import auth, session

NUM = "447700900001"


def _iso_ago(seconds: int) -> str:
    t = datetime.now(timezone.utc) - timedelta(seconds=seconds)
    return t.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _body(reply: dict) -> str:
    return reply["text"]["body"]


@pytest.fixture
def capture_email(monkeypatch):
    """Capture every send_email call and expose the latest OTP code."""
    sent = []

    def fake_send_email(to, subject, body, **kwargs):
        sent.append({"to": to, "subject": subject, "body": body})
        return "ses-stub"

    monkeypatch.setattr(cds, "send_email", fake_send_email)
    return sent


def _code_from(sent) -> str:
    match = re.search(r"\b(\d{6})\b", sent[-1]["body"])
    assert match, f"no 6-digit code in email body: {sent[-1]['body']!r}"
    return match.group(1)


# ── session ──────────────────────────────────────────────────────────────────
def test_session_default_is_logged_out():
    s = session.get(NUM)
    assert s == {"waNumber": NUM, "state": session.LOGGED_OUT}


def test_session_set_state_and_context_roundtrip():
    session.set_state(NUM, session.AWAITING_EMAIL, pendingEmail="x@y.test")
    session.set_context(NUM, "summary", {"page": 2})
    s = session.get(NUM)
    assert s["state"] == session.AWAITING_EMAIL
    assert s["pendingEmail"] == "x@y.test"
    assert s["context"]["screen"] == "summary"
    assert s["context"]["params"] == {"page": 2}
    assert s["context"]["contextAt"]
    session.clear_context(NUM)
    assert "context" not in session.get(NUM)


def test_session_set_state_none_removes_field():
    session.set_state(NUM, session.AWAITING_OTP, otpAttempts=2)
    assert session.get(NUM)["otpAttempts"] == 2
    session.set_state(NUM, session.AWAITING_OTP, otpAttempts=None)
    assert "otpAttempts" not in session.get(NUM)


def test_session_unlink_clears_link_and_context(business):
    session.link(NUM, business["businessId"])
    session.set_context(NUM, "invoices")
    linked = session.get(NUM)
    assert linked["state"] == session.AUTHED and linked["businessId"] == business["businessId"]
    session.unlink(NUM)
    out = session.get(NUM)
    assert out["state"] == session.LOGGED_OUT
    assert "businessId" not in out and "context" not in out


# ── auth ─────────────────────────────────────────────────────────────────────
def test_unknown_email_stays_awaiting_email():
    auth.start_login(NUM)
    reply = auth.submit_email(NUM, "nobody@nowhere.test")
    assert "couldn't find" in _body(reply)
    assert session.get(NUM)["state"] == session.AWAITING_EMAIL


def test_happy_path_links_and_persists(business, capture_email):
    auth.start_login(NUM)
    assert session.get(NUM)["state"] == session.AWAITING_EMAIL

    reply = auth.submit_email(NUM, "sam@acme.test")
    assert "emailed" in _body(reply)
    assert session.get(NUM)["state"] == session.AWAITING_OTP

    code = _code_from(capture_email)
    done = auth.submit_otp(NUM, code)
    assert done == {"type": "text", "text": {"preview_url": False,
                                             "body": "You're logged in as Acme Joinery Ltd."}}

    # the link persists across a fresh read
    s = session.get(NUM)
    assert s["state"] == session.AUTHED
    assert s["businessId"] == business["businessId"]
    assert "otpHash" not in s and "pendingBusinessId" not in s


def test_wrong_code_then_correct(business, capture_email):
    auth.start_login(NUM)
    auth.submit_email(NUM, "sam@acme.test")
    code = _code_from(capture_email)

    wrong = "000000" if code != "000000" else "111111"
    reply = auth.submit_otp(NUM, wrong)
    assert "didn't match" in _body(reply) and "2 attempts left" in _body(reply)
    assert session.get(NUM)["state"] == session.AWAITING_OTP

    ok = auth.submit_otp(NUM, code)
    assert "logged in as Acme Joinery Ltd" in _body(ok)
    assert session.get(NUM)["state"] == session.AUTHED


def test_three_wrong_codes_restart(business, capture_email):
    auth.start_login(NUM)
    auth.submit_email(NUM, "sam@acme.test")
    code = _code_from(capture_email)
    wrong = "000000" if code != "000000" else "111111"

    auth.submit_otp(NUM, wrong)
    auth.submit_otp(NUM, wrong)
    reply = auth.submit_otp(NUM, wrong)
    assert "start over" in _body(reply)
    assert session.get(NUM)["state"] == session.AWAITING_EMAIL
    assert "otpHash" not in session.get(NUM)


def test_expired_code_returns_to_email(business, capture_email):
    auth.start_login(NUM)
    auth.submit_email(NUM, "sam@acme.test")
    code = _code_from(capture_email)
    # force the code to have expired
    session.set_state(NUM, session.AWAITING_OTP, otpExpiresAt=_iso_ago(10))

    reply = auth.submit_otp(NUM, code)
    assert "expired" in _body(reply)
    assert session.get(NUM)["state"] == session.AWAITING_EMAIL


def test_resend_throttle_blocks_second_request(business, capture_email):
    auth.start_login(NUM)
    auth.submit_email(NUM, "sam@acme.test")
    reply = auth.submit_email(NUM, "sam@acme.test")
    assert "Give it a minute" in _body(reply)
    assert len(capture_email) == 1   # no second email went out


def test_hourly_cap_blocks_sixth_request(business, capture_email):
    auth.start_login(NUM)
    # five requests inside the hour but all older than the 60s throttle
    session.set_state(NUM, session.AWAITING_EMAIL,
                      otpRequests=[_iso_ago(s) for s in (120, 240, 360, 480, 600)])
    reply = auth.submit_email(NUM, "sam@acme.test")
    assert "too many code requests" in _body(reply)
    assert len(capture_email) == 0   # capped before sending


def test_email_is_masked_in_reply(business, capture_email):
    auth.start_login(NUM)
    reply = auth.submit_email(NUM, "sam@acme.test")
    assert "s***@acme.test" in _body(reply)
    assert "sam@acme.test" not in _body(reply)


def test_code_is_not_stored_in_plaintext(business, capture_email):
    auth.start_login(NUM)
    auth.submit_email(NUM, "sam@acme.test")
    code = _code_from(capture_email)
    s = session.get(NUM)
    assert code not in str(s)
    assert s["otpHash"] and s["otpSalt"]


def test_logout_unlinks(business):
    session.link(NUM, business["businessId"])
    reply = auth.logout(NUM)
    assert _body(reply) == "You're logged out."
    assert session.get(NUM)["state"] == session.LOGGED_OUT
