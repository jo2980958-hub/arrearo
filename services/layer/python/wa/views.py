"""Read-only screens that mirror the dashboard. Each returns a Reply (or list).

Depends on common.db (reads), common.flows (portfolio_summary, score_debtor),
common.config (gbp formatting), wa.messages. No writes here.
Contract fixed by the spec — agent fills the bodies.
"""
from __future__ import annotations


def summary(business_id: str) -> dict:
    """Outstanding total, interest/day, counts open/overdue/promised, via
    flows.portfolio_summary. Returns text + buttons."""
    raise NotImplementedError


def invoice_list(business_id: str, page: int = 0) -> dict:
    """A list message of open invoices, 10 per page, `MORE` to page. Rows open an invoice."""
    raise NotImplementedError


def invoice_detail(business_id: str, invoice_id: str) -> dict:
    """Full figures + legal basis + latest timeline event + action buttons by status."""
    raise NotImplementedError


def debtor(business_id: str, query: str) -> dict:
    """Risk band, avg days to pay, share paid late for a named debtor; unknown stays unknown."""
    raise NotImplementedError


def settings(business_id: str) -> dict:
    """Business details, bank account masked to the last two digits. View-only."""
    raise NotImplementedError
