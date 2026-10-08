"""The WhatsApp navigation state machine.

Loads the session; if not AUTHED routes to wa.auth (except global HELP); else maps
commands, interactive taps and the current screen context to wa.menus / wa.views /
wa.actions. Enforces that a number only ever acts on its linked business.
Depends on wa.session, wa.auth, wa.menus, wa.views, wa.actions, wa.inbound.
Contract fixed by the spec — agent fills the body.
"""
from __future__ import annotations


def handle(wa_number: str, inbound: dict) -> list[dict]:
    """inbound = {"text": str|None, "tap_id": str|None, "tap_title": str|None,
    "media": dict|None}. Returns a list of Replies (wa.messages dicts) to send in order."""
    raise NotImplementedError
