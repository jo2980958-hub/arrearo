import json
from pathlib import Path
import pytest
import loader, score as S

SEED = Path(__file__).parent / "arrearo-debtors-seed.json"
DOC = json.loads(SEED.read_text())


def test_seed_shape_and_size():
    assert SEED.stat().st_size < 2_000_000
    assert 100 <= len(DOC["companies"]) <= 1000
    for c in DOC["companies"]:
        assert c["source"] == "payment-practices"
        assert c["riskBand"] in ("low", "medium", "high")
        assert 0 <= c["avgDaysToPay"] <= 365
    assert len({c["companyNumber"] for c in DOC["companies"]}) == len(DOC["companies"])


def test_score_by_number_and_zero_padding():
    c = DOC["companies"][0]
    r = S.score(company_number=c["companyNumber"])
    assert r["name"] == c["name"] and r["avgDaysToPay"] == c["avgDaysToPay"]
    assert set(r) == {"name", "companyNumber", "avgDaysToPay", "pctPaidLate", "riskBand", "reportPeriodEnd", "source"}
    pad = next(c for c in DOC["companies"] if c["companyNumber"].startswith("0"))
    assert S.score(company_number=pad["companyNumber"].lstrip("0"))["companyNumber"] == pad["companyNumber"]


def test_score_by_name_is_exact_but_punctuation_insensitive():
    r = S.score(name="tesco stores ltd")
    assert r and r["companyNumber"] == "00519500"
    assert S.score(name="Tesco Stor") is None  # no fuzzy guessing


def test_unknown_is_none():
    assert S.score(company_number="99999999") is None
    assert S.score(name="Definitely Not A Real Co") is None
    assert S.score() is None


def test_number_beats_name():
    assert S.score(company_number="00519500", name="Nonsense")["companyNumber"] == "00519500"


@pytest.mark.parametrize("days,late,band", [
    (20, 0, "low"), (39, 14, "low"), (40, 0, "medium"), (30, 15, "medium"),
    (54, 34, "medium"), (55, 0, "high"), (10, 35, "high"), (30, None, "low"), (45, None, "medium"),
])
def test_risk_band_thresholds(days, late, band):
    assert loader.risk_band(days, late) == band


def _row(**kw):
    base = {"Company": "X LTD", "Company number": "1", "Average time to pay": "30", "Filing date": "2026-01-01",
            "End date": "2025-12-31", "% Invoices not paid within agreed terms": "5"}
    return {**base, **kw}


def test_blank_and_absurd_days_dropped_not_fabricated():
    assert loader.parse_row(_row(**{"Average time to pay": ""})) is None
    assert loader.parse_row(_row(**{"Average time to pay": "4323394"})) is None
    assert loader.parse_row(_row())["avgDaysToPay"] == 30


def test_latest_filing_wins_even_if_it_is_blank():
    rows = [_row(**{"Filing date": "2020-01-01"}), _row(**{"Filing date": "2026-01-01", "Average time to pay": ""})]
    recs = {k: loader.parse_row(r) for k, r in loader.latest_per_company(rows).items()}
    assert recs["1"] is None  # newest filing is unusable -> unknown, not the stale one
