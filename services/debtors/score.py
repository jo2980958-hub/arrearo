"""Runtime debtor lookup. Pure: reads the committed seed JSON (or a loaded DynamoDB dump).
Unknown is unknown: no fuzzy guessing, no defaults."""
import json, re
from functools import lru_cache
from pathlib import Path

SEED_PATH = Path(__file__).parent / "arrearo-debtors-seed.json"
_SUFFIX = re.compile(r"\b(LIMITED|LTD|PLC|LLP|LP|UK|THE)\b")


def normalize_number(n):
    n = re.sub(r"\s+", "", str(n or "")).upper()
    return n.zfill(8) if n.isdigit() else n  # '519500' -> '00519500'; 'SC173199' unchanged


def normalize_name(s):
    s = re.sub(r"[^A-Z0-9 ]", " ", (s or "").upper().replace("&", " AND "))
    return " ".join(_SUFFIX.sub(" ", s).split())


@lru_cache(maxsize=4)
def _index(path):
    companies = json.loads(Path(path).read_text())["companies"]
    by_num = {c["companyNumber"]: c for c in companies}
    by_name = {}
    for c in companies:
        by_name.setdefault(normalize_name(c["name"]), []).append(c)
    return by_num, by_name


def score(company_number=None, name=None, seed_path=SEED_PATH):
    """-> {name, companyNumber, avgDaysToPay, pctPaidLate, riskBand, reportPeriodEnd, source} or None.
    Company number wins. A name matches only exactly (case/punctuation/suffix-insensitive)
    and only if that normalised name is unambiguous."""
    by_num, by_name = _index(str(seed_path))
    rec = None
    if company_number:
        rec = by_num.get(normalize_number(company_number))
    elif name:
        hits = by_name.get(normalize_name(name), [])
        rec = hits[0] if len(hits) == 1 else None
    if not rec:
        return None
    return {k: rec.get(k) for k in ("name", "companyNumber", "avgDaysToPay", "pctPaidLate",
                                    "riskBand", "reportPeriodEnd", "source")}
