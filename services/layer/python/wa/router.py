"""The WhatsApp navigation state machine.

Loads the session; if not AUTHED routes to wa.auth (except global HELP); else maps
commands, interactive taps and the current screen context to wa.menus / wa.views /
wa.actions. A number only ever acts on its own linked business (the views/actions
re-check ownership with the business id from the session).
"""
from __future__ import annotations

from wa import actions, auth, menus, messages, session, views


def _as_list(reply) -> list[dict]:
    if reply is None:
        return []
    return reply if isinstance(reply, list) else [reply]


def _split(tap_id):
    """A tap id is a screen key, optionally 'key:arg' (e.g. 'inv:<id>', 'more:2')."""
    if not tap_id:
        return None, None
    key, _, rest = tap_id.partition(":")
    return key, (rest or None)


def handle(wa_number: str, inbound: dict) -> list[dict]:
    inbound = inbound or {}
    text = inbound.get("text")
    tap_id = inbound.get("tap_id")
    media = inbound.get("media")
    cmd = menus.parse_command(text)

    # Help is available in any state.
    if cmd == menus.HELP:
        return [menus.help_text()]

    sess = session.get(wa_number)
    state = sess.get("state", session.LOGGED_OUT)
    if state != session.AUTHED:
        return _unauthed(wa_number, state, text, tap_id)

    bid = sess.get("businessId")

    # Global commands first.
    if cmd in (menus.MENU, menus.START):
        return [menus.main_menu()]
    if cmd == menus.SUMMARY:
        return _as_list(views.summary(bid))
    if cmd == menus.LOGOUT:
        return _as_list(auth.logout(wa_number))

    # An explicit tap wins over loose text.
    if tap_id:
        return _dispatch(wa_number, bid, *_split(tap_id))

    # No tap: interpret media or free text against the current screen context.
    ctx = sess.get("context") or {}
    screen = ctx.get("screen")
    if media:
        session.clear_context(wa_number)
        return _as_list(actions.ingest_media(bid, media))
    if screen == "awaiting_debtor" and text:
        session.clear_context(wa_number)
        return _as_list(views.debtor(bid, text.strip()))
    if screen == "awaiting_invoice":
        return [messages.text("Please send the invoice as a photo or a PDF.")]

    return [messages.text("I didn't catch that. Here's the menu."), menus.main_menu()]


def _dispatch(wa_number: str, bid: str, key: str, arg) -> list[dict]:
    if key == "menu":
        return [menus.main_menu()]
    if key == "summary":
        return _as_list(views.summary(bid))
    if key == "invoices":
        return _as_list(views.invoice_list(bid, 0))
    if key == "more":
        try:
            page = int(arg)
        except (TypeError, ValueError):
            page = 0
        return _as_list(views.invoice_list(bid, page))
    if key == "add_invoice":
        session.set_context(wa_number, "awaiting_invoice")
        return [messages.text("Send a photo or a PDF of the invoice and I'll read it.")]
    if key == "debtors":
        session.set_context(wa_number, "awaiting_debtor")
        return [messages.text("Type the company name and I'll check its payment risk.")]
    if key == "settings":
        return _as_list(views.settings(bid))
    if key == "help":
        return [menus.help_text()]
    if key == "logout":
        return _as_list(auth.logout(wa_number))
    if key == "inv":
        return _as_list(views.invoice_detail(bid, arg))
    if key == "confirm":
        return _as_list(actions.confirm(bid, arg))
    if key == "chase":
        return _as_list(actions.chase_draft(bid, arg))
    if key == "chasego":
        return _as_list(actions.chase_send(bid, arg))
    if key == "paid":
        return _as_list(actions.mark_paid(bid, arg))
    if key == "lba":
        return _as_list(actions.lba_draft(bid, arg))
    if key == "lbago":
        return _as_list(actions.lba_send(bid, arg))
    return [messages.text("I didn't catch that. Here's the menu."), menus.main_menu()]


def _unauthed(wa_number: str, state: str, text, tap_id) -> list[dict]:
    key, _ = _split(tap_id)
    if state == session.AWAITING_EMAIL:
        if text:
            return _as_list(auth.submit_email(wa_number, text.strip()))
        return [messages.text("Please type the email on your Arrearo account.")]
    if state == session.AWAITING_OTP:
        if text:
            replies = _as_list(auth.submit_otp(wa_number, text.strip()))
            if session.get(wa_number).get("state") == session.AUTHED:
                replies.append(menus.main_menu())
            return replies
        return [messages.text("Please type the 6-digit code I emailed you.")]
    # LOGGED_OUT or unknown
    if key == "login":
        return _as_list(auth.start_login(wa_number))
    return [menus.welcome_logged_out()]
