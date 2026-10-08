"""Build the Arrearo debtor-intelligence seed from the UK payment-practices CSV.

    python loader.py --csv /path/export.csv            # use a local file
    python loader.py --download /tmp/pp.csv            # fetch it first (~100MB, not committed)

Source: https://check-payment-practices.service.gov.uk/export/csv/ (self-reported by
large UK companies). We keep the latest filing per company number, drop rows with no
usable average-days figure (never fabricate), and write arrearo-debtors-seed.json.

riskBand thresholds (documented, see risk_band):
    high    avgDaysToPay >= 55  OR  pctPaidLate >= 35
    medium  avgDaysToPay >= 40  OR  pctPaidLate >= 15
    low     otherwise
pctPaidLate is the report's "% Invoices not paid within agreed terms".
"""
import argparse, csv, json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

URL = "https://check-payment-practices.service.gov.uk/export/csv/"
HERE = Path(__file__).parent
SEED = HERE / "arrearo-debtors-seed.json"
MAX_DAYS = 365          # larger values in the file are data-entry errors
FRESH_FROM = "2024-10-01"  # seed only includes filings on/after this date

HIGH_DAYS, HIGH_LATE = 55, 35
MED_DAYS, MED_LATE = 40, 15

# Well-known brands/contractors; matched as a name prefix. Used to curate the seed.
BRANDS = """TESCO;SAINSBURY;ASDA;MORRISONS;WM MORRISON;MARKS AND SPENCER;MARKS & SPENCER;WAITROSE;JOHN LEWIS;
ALDI;LIDL;CO-OP;CO OP;THE CO-OPERATIVE;BOOTS;SUPERDRUG;ARGOS;CURRYS;DIXONS;B&Q;KINGFISHER;SCREWFIX;
HOMEBASE;WICKES;TRAVIS PERKINS;SPORTS DIRECT;NEXT;PRIMARK;ASSOCIATED BRITISH FOODS;GREGGS;
PIZZA HUT;MCDONALD;COMPASS GROUP;SODEXO;ISS;MITIE;SERCO;CAPITA;G4S;SECURITAS;
BALFOUR BEATTY;KIER;COSTAIN;MORGAN SINDALL;GALLIFORD;WILLMOTT DIXON;LAING O'ROURKE;SKANSKA;
VINCI;BOUYGUES;MACE;SISK;INTERSERVE;AMEY;ATKINS;JACOBS;ARUP;WSP;MOTT MACDONALD;MURPHY;
BARRATT;PERSIMMON;TAYLOR WIMPEY;BELLWAY;VISTRY;BERKELEY;REDROW;CREST NICHOLSON;
BT GROUP;BRITISH TELECOM;VODAFONE;VIRGIN MEDIA;SKY;TALKTALK;EE LIMITED;O2;THREE;OPENREACH;
BRITISH GAS;CENTRICA;E.ON;EDF;SCOTTISH POWER;SSE;OCTOPUS;NATIONAL GRID;THAMES WATER;SEVERN TRENT;UNITED UTILITIES;
ROYAL MAIL;DHL;DPD;HERMES;EVRI;FEDEX;UPS;WINCANTON;XPO;
BP ;SHELL;BARCLAYS;HSBC;LLOYDS;NATWEST;SANTANDER;ROLLS-ROYCE;BAE SYSTEMS;AIRBUS;BOEING;
JAGUAR;LAND ROVER;NISSAN;TOYOTA;FORD MOTOR;VAUXHALL;UNILEVER;PROCTER;DIAGEO;NESTLE;
CADBURY;COCA-COLA;PEPSICO;DANONE;KELLOGG;HEINEKEN;CARLSBERG;
AMAZON;MICROSOFT;GOOGLE;IBM;ORACLE;ACCENTURE;DELOITTE;PWC;PRICEWATERHOUSE;KPMG;ERNST
""".replace("\n", "").split(";")
BRANDS = [b.strip() for b in BRANDS if b.strip()]


def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def parse_row(r):
    """CSV row -> record, or None when there is no usable average-days figure."""
    avg = _num(r.get("Average time to pay"))
    if avg is None or avg < 0 or avg > MAX_DAYS:
        return None
    num = (r.get("Company number") or "").strip().upper()
    if not num:
        return None
    late = _num(r.get("% Invoices not paid within agreed terms"))
    rec = {
        "debtorKey": num,
        "name": (r.get("Company") or "").strip(),
        "companyNumber": num,
        "avgDaysToPay": int(avg),
        "pctPaidWithin30": _num(r.get("% Invoices paid within 30 days")),
        "pct31to60": _num(r.get("% Invoices paid between 31 and 60 days")),
        "pct60plus": _num(r.get("% Invoices paid later than 60 days")),
        "pctPaidLate": late,
        "pctInvoicesDisputed": _num(r.get("% Invoices not paid due to dispute")),
        "reportPeriodEnd": r.get("End date") or None,
        "filingDate": r.get("Filing date") or None,
        "reportUrl": r.get("URL") or None,
        "source": "payment-practices",
    }
    rec["riskBand"] = risk_band(rec["avgDaysToPay"], rec["pctPaidLate"])
    return rec


def risk_band(avg_days, pct_late):
    if avg_days >= HIGH_DAYS or (pct_late is not None and pct_late >= HIGH_LATE):
        return "high"
    if avg_days >= MED_DAYS or (pct_late is not None and pct_late >= MED_LATE):
        return "medium"
    return "low"


def latest_per_company(rows):
    """Keep the row with the latest Filing date per company number (rows kept raw so a
    newer filing with a blank figure correctly replaces an older complete one)."""
    latest = {}
    for r in rows:
        k = (r.get("Company number") or "").strip().upper()
        if k and (k not in latest or (r.get("Filing date") or "") > (latest[k].get("Filing date") or "")):
            latest[k] = r
    return latest


def load_records(csv_path):
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        latest = latest_per_company(csv.DictReader(f))
    recs = {k: parse_row(r) for k, r in latest.items()}
    return {k: v for k, v in recs.items() if v}, len(latest)


def _brand(rec):
    n = rec["name"].upper()
    for b in BRANDS:
        if n.startswith(b):
            return b
    return None


def select_seed(records, target=400, per_brand=4):
    fresh = [r for r in records.values() if (r["filingDate"] or "") >= FRESH_FROM]
    chosen, count = {}, {}
    for r in sorted(fresh, key=lambda r: (len(r["name"]), r["name"])):
        b = _brand(r)
        if b and count.get(b, 0) < per_brand:
            chosen[r["companyNumber"]] = r
            count[b] = count.get(b, 0) + 1
    # top up with an even spread across bands so the demo has high/medium/low examples
    rest = sorted((r for r in fresh if r["companyNumber"] not in chosen),
                  key=lambda r: (r["avgDaysToPay"], r["companyNumber"]))
    need = target - len(chosen)
    if need > 0 and rest:
        step = max(1, len(rest) // need)
        for r in rest[::step][:need]:
            chosen[r["companyNumber"]] = r
    return sorted(chosen.values(), key=lambda r: r["name"])


def build(csv_path, out=SEED, target=400):
    records, total = load_records(csv_path)
    seed = select_seed(records, target)
    doc = {
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "payment-practices",
        "sourceUrl": URL,
        "note": "Self-reported by large UK companies. Absence from this file does not mean a good payer.",
        "thresholds": {"high": f"avgDaysToPay>={HIGH_DAYS} or pctPaidLate>={HIGH_LATE}",
                       "medium": f"avgDaysToPay>={MED_DAYS} or pctPaidLate>={MED_LATE}", "low": "otherwise"},
        "companies": seed,
    }
    Path(out).write_text(json.dumps(doc, separators=(",", ":"), ensure_ascii=False))
    return total, len(records), len(seed)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv")
    ap.add_argument("--download", help="download the CSV to this path first")
    ap.add_argument("--target", type=int, default=400)
    a = ap.parse_args(argv)
    path = a.csv
    if a.download:
        subprocess.run(["curl", "-sL", "-A", "Mozilla/5.0", "-f", "-o", a.download, URL], check=True)
        path = a.download
    if not path:
        sys.exit("give --csv FILE or --download FILE")
    total, usable, n = build(path, target=a.target)
    print(f"{total} companies, {usable} with usable avg days, {n} in seed -> {SEED}")


if __name__ == "__main__":
    main()
