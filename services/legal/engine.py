"""Recoup's legal engine: the deterministic core.

Every figure a debtor or a court could see is computed HERE, in plain Python,
never by a language model. The model phrases a chase; the numbers in it come
from this module. All money is in integer **pence**; interest is computed with
Decimal and rounded half-up to the penny.

UK basis (Late Payment of Commercial Debts (Interest) Act 1998, as amended):
  - Statutory interest = 8% + the Bank of England base rate.
  - A fixed recovery sum is owed once per debt: £40 / £70 / £100 by size.
  - With no agreed payment date, payment is due 30 days after the later of the
    invoice arriving or the goods/service being received. Interest runs from the
    day after the due date.
  - Public-authority contracts: 30-day maximum. Business-to-business: a longer
    period may be agreed but 60 days is the outer limit before it is challengeable.

Conduct basis (Administration of Justice Act 1970, s.40): an automated chaser
must never imply that criminal proceedings follow non-payment, never imply
official authority, never produce anything styled as an official/court document,
and must not contact at an oppressive frequency. `compliance_scan` enforces the
wording; `can_contact_now` enforces the cadence.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

# ── Bank of England base rate ───────────────────────────────────────────────
# The statutory add-on is fixed at 8%. The base rate moves; a scheduled job
# (services/debtors or a dedicated updater) refreshes BASE_RATE_PCT from the
# Bank of England series IUDBEDR. This dated constant is the safe fallback the
# engine always has, so a chase is never blocked on a live fetch.
BASE_RATE_PCT: float = 3.75          # VERIFY: Bank of England base rate
BASE_RATE_AS_OF: str = "2026-09-24"  # as-of date for the constant above
BASE_RATE_SOURCE: str = "Bank of England base rate (series IUDBEDR)"
STATUTORY_ADDON_PCT: float = 8.0

DAYS_IN_YEAR = 365  # the convention used for statutory daily interest

# Fixed recovery sum tiers, in pence, by debt size (the principal, excl. interest).
_FIXED_SUM_TIERS = [
    (100_000, 40_00),      # debt < £1,000  -> £40
    (1_000_000, 70_00),    # £1,000 <= debt < £10,000 -> £70
    (None, 100_00),        # debt >= £10,000 -> £100
]

# Default statutory payment terms (days) when no date is agreed, by debtor type.
_DEFAULT_TERMS_DAYS = {
    "public_authority": 30,
    "business": 30,        # statutory default with no agreement is 30 days
    "company": 30,
    "sole_trader": 30,
    "individual": 30,
}
# Maximum agreed term before it is challengeable (not used to compute lateness,
# kept for advice/validation).
MAX_AGREED_TERM_DAYS = {"public_authority": 30, "default": 60}


@dataclass(frozen=True)
class Violation:
    code: str
    message: str
    span: str


def _d(pence: int) -> Decimal:
    return Decimal(int(pence))


def _round_pence(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def boe_base_rate() -> tuple[float, str, str]:
    """The base rate the engine uses, with its as-of date and source.

    Returns the dated constant. A separate updater may overwrite BASE_RATE_PCT
    from the live BoE series; the engine stays deterministic either way.
    """
    return (BASE_RATE_PCT, BASE_RATE_AS_OF, BASE_RATE_SOURCE)


def statutory_rate(base_pct: Optional[float] = None) -> float:
    """Statutory interest rate (%/yr) = base rate + 8% (using today's base)."""
    base = BASE_RATE_PCT if base_pct is None else base_pct
    return round(base + STATUTORY_ADDON_PCT, 4)


# Bank of England base rate at each statutory reference date (30 Jun / 31 Dec).
# A debt's statutory rate is FIXED by the Bank Rate on the reference date that
# falls before it went overdue (Late Payment Order SI 2002/1675, art. 4): a debt
# overdue in H1 uses the previous 31 Dec; one overdue in H2 uses that 30 Jun.
# VERIFY against the Bank of England IUDBEDR history before relying beyond 2026.
_REFERENCE_RATES = {
    "2024-06-30": 5.25,
    "2024-12-31": 4.75,
    "2025-06-30": 4.25,
    "2025-12-31": 3.75,   # -> H1 2026 debts: 11.75%
    "2026-06-30": 3.75,   # -> H2 2026 debts: 11.75%
}


def _reference_date_for(overdue_date: date) -> date:
    if overdue_date.month <= 6:
        return date(overdue_date.year - 1, 12, 31)
    return date(overdue_date.year, 6, 30)


def statutory_rate_for(overdue_date: date) -> tuple[float, str, float]:
    """The statutory rate that applies to a debt by WHEN it went overdue.

    Returns (rate_pct, reference_date_iso, base_rate_pct). Falls back to the
    current base-rate constant for reference dates not in the table.
    """
    ref = _reference_date_for(overdue_date)
    base = _REFERENCE_RATES.get(ref.isoformat(), BASE_RATE_PCT)
    return round(base + STATUTORY_ADDON_PCT, 4), ref.isoformat(), base


def _terms_days(debtor_type: str) -> int:
    return _DEFAULT_TERMS_DAYS.get(debtor_type, 30)


def due_date(
    invoice_date: date,
    delivery_date: Optional[date] = None,
    agreed_due_date: Optional[date] = None,
    debtor_type: str = "business",
) -> date:
    """The date payment is due.

    An agreed date wins. Otherwise the statutory default term (30 days) runs
    from the later of the invoice date and the delivery date.
    """
    if agreed_due_date is not None:
        return agreed_due_date
    start = invoice_date
    if delivery_date is not None and delivery_date > start:
        start = delivery_date
    return start + timedelta(days=_terms_days(debtor_type))


def legally_late_date(
    invoice_date: date,
    delivery_date: Optional[date] = None,
    agreed_due_date: Optional[date] = None,
    debtor_type: str = "business",
) -> date:
    """The first day the debt is late and statutory interest begins to run:
    the day after the due date."""
    return due_date(invoice_date, delivery_date, agreed_due_date, debtor_type) + timedelta(days=1)


def days_late(late_from: date, today: Optional[date] = None) -> int:
    """Whole days the debt has been late (0 before the late date)."""
    today = today or datetime.now(timezone.utc).date()
    return max(0, (today - late_from).days + 1) if today >= late_from else 0


def daily_interest_pence(amount_pence: int, rate_pct: Optional[float] = None) -> Decimal:
    """Statutory interest for one day, as an un-rounded Decimal (pence)."""
    rate = Decimal(str(statutory_rate() if rate_pct is None else rate_pct))
    return _d(amount_pence) * rate / Decimal(100) / Decimal(DAYS_IN_YEAR)


def interest_accrued_pence(amount_pence: int, days: int, rate_pct: Optional[float] = None) -> int:
    """Statutory interest accrued over `days`, rounded to the penny."""
    if days <= 0:
        return 0
    return _round_pence(daily_interest_pence(amount_pence, rate_pct) * Decimal(days))


def fixed_recovery_sum_pence(amount_pence: int) -> int:
    """The one-off fixed recovery sum owed on a late commercial debt."""
    for ceiling, sum_pence in _FIXED_SUM_TIERS:
        if ceiling is None or amount_pence < ceiling:
            return sum_pence
    return _FIXED_SUM_TIERS[-1][1]


def total_owed_pence(amount_pence: int, interest_pence: int, fixed_sum_pence: int) -> int:
    return amount_pence + interest_pence + fixed_sum_pence


# ── Conduct: Administration of Justice Act 1970, s.40 ────────────────────────
# Minimum days between contacts, by chase stage. A tighter cadence than a human
# would use reads as harassment, which s.40(1)(a) treats as an offence.
_MIN_GAP_DAYS = {"reminder": 3, "first_chase": 7, "second_chase": 7, "final_notice": 14, "lba": 14}

# Phrases that imply criminal proceedings, official authority, or an official
# document — each prohibited for a private creditor's automated chaser.
_PROHIBITED_PATTERNS = [
    (r"\b(criminal|prosecut\w*|arrest\w*|police|fraud\w*|jail|prison|imprison\w*)\b",
     "implies criminal proceedings (s.40(1)(b))"),
    (r"\b(bailiff|court order|county court judgment|ccj)\b(?!.{0,40}\bmay\b)",
     "implies action already taken/authorised (state possibility, not certainty)"),
    (r"\b(on behalf of (the )?(court|government|hmrc|ministry)|official notice|government agency)\b",
     "implies official authority (s.40(1)(c))"),
    (r"\b(summons|warrant|writ|statutory demand)\b",
     "styled as an official/court document (s.40(1)(d))"),
]


def compliance_scan(text: str) -> list[Violation]:
    """Flag wording a private creditor's chaser may not use. Empty list = clean."""
    found: list[Violation] = []
    low = text.lower()
    for pattern, message in _PROHIBITED_PATTERNS:
        m = re.search(pattern, low)
        if m:
            found.append(Violation(code="conduct", message=message, span=m.group(0)))
    return found


def can_contact_now(last_contact_at: Optional[datetime], now: Optional[datetime], stage: str) -> bool:
    """True if enough time has passed since the last contact for this stage."""
    if last_contact_at is None:
        return True
    now = now or datetime.now(timezone.utc)
    gap = _MIN_GAP_DAYS.get(stage, 7)
    return (now - last_contact_at) >= timedelta(days=gap)


def lba_required_fields(invoice: dict, business: dict, debtor: dict) -> dict:
    """The checklist a compliant Letter Before Action must carry under the
    Pre-Action Protocol for Debt Claims (which applies where the debtor is an
    individual or a sole trader, not a company)."""
    applies = invoice.get("debtorType") in ("sole_trader", "individual")
    return {
        "protocol_applies": applies,
        "creditor_name": business.get("name"),
        "debtor_name": invoice.get("debtorName"),
        "debt_amount_pence": invoice.get("amountPence"),
        "basis_of_debt": invoice.get("description") or invoice.get("reference"),
        "interest_and_charges_explained": True,
        "how_to_pay": bool(business.get("bankAccount")),
        "reply_period_days": 30 if applies else 14,
        "includes_information_sheet": applies,   # the Protocol's Information Sheet + Reply Form
        "includes_reply_form": applies,
        "statement_of_account_offered": True,
    }
