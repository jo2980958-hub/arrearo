"""Static menus and the global command parser. Returns Replies via wa.messages.

Contract fixed by the spec — agent fills the bodies.
"""
from __future__ import annotations

from typing import Optional

# canonical global commands
START = "START"
MENU = "MENU"
SUMMARY = "SUMMARY"
BACK = "BACK"
HELP = "HELP"
LOGOUT = "LOGOUT"


def parse_command(text: Optional[str]) -> Optional[str]:
    """Map free text like 'start', '/menu', 'log out' to one of the constants, else None."""
    raise NotImplementedError


def welcome_logged_out() -> dict:
    """Welcome for an unlinked number: what Arrearo is + a single `Log in` button."""
    raise NotImplementedError


def main_menu() -> dict:
    """The logged-in list menu: Summary, Invoices, Add an invoice, Debtors, Settings,
    Help, Log out. Row ids are stable screen keys consumed by wa.router."""
    raise NotImplementedError


def help_text() -> dict:
    raise NotImplementedError
