"""Tests for the deterministic legal engine. Pure stdlib; run with pytest."""
from datetime import date, datetime, timedelta, timezone

import engine as e


# ── fixed recovery sum tiers ─────────────────────────────────────────────────
def test_fixed_sum_under_1000():
    assert e.fixed_recovery_sum_pence(99_999) == 40_00      # £999.99 -> £40


def test_fixed_sum_at_1000():
    assert e.fixed_recovery_sum_pence(100_000) == 70_00     # £1,000 -> £70


def test_fixed_sum_just_under_10000():
    assert e.fixed_recovery_sum_pence(999_999) == 70_00     # £9,999.99 -> £70


def test_fixed_sum_at_10000():
    assert e.fixed_recovery_sum_pence(1_000_000) == 100_00  # £10,000 -> £100


# ── statutory rate ───────────────────────────────────────────────────────────
def test_statutory_rate_adds_eight():
    assert e.statutory_rate(3.75) == 11.75
    assert e.statutory_rate() == round(e.BASE_RATE_PCT + 8.0, 4)


def test_statutory_rate_for_h1_2026_uses_prev_dec():
    rate, ref, base = e.statutory_rate_for(date(2026, 3, 15))
    assert ref == "2025-12-31" and base == 3.75 and rate == 11.75


def test_statutory_rate_for_h2_2025_uses_jun():
    rate, ref, base = e.statutory_rate_for(date(2025, 9, 1))
    assert ref == "2025-06-30" and base == 4.25 and rate == 12.25


def test_statutory_rate_for_h2_2026_uses_jun():
    rate, ref, base = e.statutory_rate_for(date(2026, 8, 1))
    assert ref == "2026-06-30" and rate == 11.75


# ── due / late dates ─────────────────────────────────────────────────────────
def test_agreed_date_wins():
    agreed = date(2026, 3, 1)
    assert e.due_date(date(2026, 1, 1), None, agreed, "business") == agreed
    assert e.legally_late_date(date(2026, 1, 1), None, agreed) == agreed + timedelta(days=1)


def test_default_30_days_from_invoice():
    assert e.due_date(date(2026, 1, 1), None, None, "business") == date(2026, 1, 31)
    assert e.legally_late_date(date(2026, 1, 1)) == date(2026, 2, 1)


def test_default_runs_from_later_delivery():
    # delivery after invoice -> clock starts at delivery
    assert e.due_date(date(2026, 1, 1), date(2026, 1, 10), None, "business") == date(2026, 2, 9)


def test_public_authority_30_days():
    assert e.due_date(date(2026, 1, 1), None, None, "public_authority") == date(2026, 1, 31)


# ── days late ────────────────────────────────────────────────────────────────
def test_days_late_counts_inclusive():
    late_from = date(2026, 2, 1)
    assert e.days_late(late_from, date(2026, 1, 31)) == 0
    assert e.days_late(late_from, date(2026, 2, 1)) == 1
    assert e.days_late(late_from, date(2026, 2, 10)) == 10


# ── interest ─────────────────────────────────────────────────────────────────
def test_full_year_interest_at_1000():
    # £1,000 at 11.75% for 365 days = £117.50
    assert e.interest_accrued_pence(100_000, 365, 11.75) == 117_50


def test_no_interest_before_late():
    assert e.interest_accrued_pence(100_000, 0, 11.75) == 0
    assert e.interest_accrued_pence(100_000, -5, 11.75) == 0


def test_interest_rounds_to_penny():
    # 1 day on £1,000 at 11.75% = 11750/365 = 32.19p -> 32p
    assert e.interest_accrued_pence(100_000, 1, 11.75) == 32


def test_total_owed_sums_parts():
    assert e.total_owed_pence(100_000, 117_50, 70_00) == 100_000 + 11_750 + 7_000


# ── conduct: wording ─────────────────────────────────────────────────────────
def test_compliance_flags_criminal_threat():
    v = e.compliance_scan("Pay now or we will begin criminal proceedings against you.")
    assert any(x.code == "conduct" for x in v)


def test_compliance_flags_false_authority():
    assert e.compliance_scan("This is an official notice on behalf of the court.")


def test_compliance_allows_lawful_chase():
    text = ("Your invoice is 10 days overdue. Statutory interest of £3.22 is now "
            "accruing daily. Please pay £1,117.50 to settle.")
    assert e.compliance_scan(text) == []


def test_compliance_allows_possibility_of_ccj():
    # stating a county court judgment *may* follow is lawful; asserting one exists is not
    assert e.compliance_scan("If this is not paid, a county court judgment may follow.") == []


# ── conduct: cadence ─────────────────────────────────────────────────────────
def test_can_contact_first_time():
    assert e.can_contact_now(None, None, "first_chase") is True


def test_cannot_contact_too_soon():
    now = datetime(2026, 2, 10, tzinfo=timezone.utc)
    last = now - timedelta(days=2)
    assert e.can_contact_now(last, now, "first_chase") is False  # needs 7 days


def test_can_contact_after_gap():
    now = datetime(2026, 2, 10, tzinfo=timezone.utc)
    last = now - timedelta(days=8)
    assert e.can_contact_now(last, now, "first_chase") is True


# ── LBA checklist ────────────────────────────────────────────────────────────
def test_lba_protocol_applies_to_sole_trader():
    fields = e.lba_required_fields(
        {"debtorType": "sole_trader", "debtorName": "A Smith", "amountPence": 150_000,
         "description": "Consulting"},
        {"name": "Acme Ltd", "bankAccount": "1234"}, {})
    assert fields["protocol_applies"] is True
    assert fields["includes_reply_form"] is True
    assert fields["reply_period_days"] == 30


def test_lba_protocol_not_for_company():
    fields = e.lba_required_fields(
        {"debtorType": "company", "debtorName": "Beta Ltd", "amountPence": 150_000},
        {"name": "Acme Ltd", "bankAccount": "1234"}, {})
    assert fields["protocol_applies"] is False
    assert fields["reply_period_days"] == 14
