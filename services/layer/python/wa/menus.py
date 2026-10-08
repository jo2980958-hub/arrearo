"""Static menus and the global command parser. Returns Replies via wa.messages."""
from __future__ import annotations

from typing import Optional

from wa import messages

# canonical global commands
START = "START"
MENU = "MENU"
SUMMARY = "SUMMARY"
BACK = "BACK"
HELP = "HELP"
LOGOUT = "LOGOUT"

# text -> command. Keys are compared against the lowercased, stripped message.
_WORDS = {
    "start": START, "/start": START, "hi": START, "hello": START, "hey": START,
    "menu": MENU, "/menu": MENU, "main menu": MENU, "home": MENU,
    "summary": SUMMARY, "/summary": SUMMARY, "overview": SUMMARY,
    "back": BACK, "/back": BACK,
    "help": HELP, "/help": HELP,
    "logout": LOGOUT, "/logout": LOGOUT, "log out": LOGOUT, "sign out": LOGOUT,
}


def parse_command(text: Optional[str]) -> Optional[str]:
    """Map free text like 'start', '/menu' or 'log out' to a command constant, else None."""
    if not text:
        return None
    return _WORDS.get(text.strip().lower())


def welcome_logged_out() -> dict:
    body = ("Welcome to Arrearo, the assistant that chases your late invoices on WhatsApp "
            "and adds the interest you are legally owed.\n\n"
            "Log in to see your invoices, chase a debtor, or add a new invoice.")
    return messages.buttons(body, [("login", "Log in")], header="Arrearo")


def main_menu() -> dict:
    sections = [{"title": "Arrearo", "rows": [
        {"id": "summary", "title": "Summary", "description": "What you are owed and the interest accruing"},
        {"id": "invoices", "title": "Invoices", "description": "Your open invoices"},
        {"id": "add_invoice", "title": "Add an invoice", "description": "Send a photo or PDF"},
        {"id": "debtors", "title": "Debtors", "description": "Check a customer's payment risk"},
        {"id": "settings", "title": "Settings", "description": "Your business details"},
        {"id": "help", "title": "Help", "description": "What I can do"},
        {"id": "logout", "title": "Log out", "description": "Unlink this number"},
    ]}]
    return messages.list_message("What would you like to do?", "Open menu", sections, header="Arrearo")


def help_text() -> dict:
    return messages.text(
        "I'm Arrearo. I track your late invoices and chase them on WhatsApp with the "
        "statutory interest added.\n\n"
        "Anytime you can type:\n"
        "• MENU to open the menu\n"
        "• SUMMARY for what you are owed\n"
        "• LOGOUT to unlink this number\n\n"
        "To add an invoice, send a photo or a PDF.")
