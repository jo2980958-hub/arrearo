"""Author-time script: reduce the UK payment-practices CSV to a small committed seed.

Usage: python build_debtors.py payment-practices.csv > debtors.json
Takes the latest filing per company number for a list of well-known names. Figures are
self-reported by the company (check-payment-practices.service.gov.uk); nothing is invented.
"""
import csv
import json
import sys

NAMES = ["tesco", "sainsbury", "vodafone", "network rail", "balfour beatty", "kier", "costain", "wates", "mace ",
         "taylor wimpey", "barratt", "persimmon", "capita", "serco", "rolls-royce", "bae systems", "unilever",
         "marks and spencer", "whitbread", "wolseley", "travis perkins", "jewson", "screwfix", "kingfisher",
         "carillion", "morgan sindall", "laing o'rourke", "galliford", "willmott dixon", "bt group", "british telecom",
         "royal mail", "dixons", "currys", "john lewis", "asda", "morrisons", "greene king", "compass group", "sodexo",
         "mitie", "interserve", "amey", "veolia", "biffa", "go-ahead", "stagecoach", "firstgroup", "bupa"]


def num(v):
    try:
        f = float(v)
        return f if f < 1000 else None
    except (TypeError, ValueError):
        return None


def band(avg, p60, late):
    if (avg or 0) > 55 or (p60 or 0) >= 20 or (late or 0) >= 40:
        return "high"
    if (avg or 0) > 40 or (p60 or 0) >= 8 or (late or 0) >= 20:
        return "medium"
    return "low"


latest = {}
with open(sys.argv[1], newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        n = row["Company"].lower()
        if any(k in n for k in NAMES) and "capital" not in n and num(row["Average time to pay"]) is not None:
            k = row["Company number"]
            if k not in latest or row["Filing date"] > latest[k]["Filing date"]:
                latest[k] = row
out = []
for k, r in sorted(latest.items(), key=lambda kv: kv[1]["Company"]):
    avg, p60, late = num(r["Average time to pay"]), num(r["% Invoices paid later than 60 days"]), num(r["% Invoices not paid within agreed terms"])
    out.append({"debtorKey": k, "name": r["Company"], "companyNumber": k, "avgDaysToPay": int(avg),
                "pctPaidWithin30": num(r["% Invoices paid within 30 days"]), "pct31to60": num(r["% Invoices paid between 31 and 60 days"]),
                "pct60plus": p60, "pctPaidLate": late, "pctInvoicesDisputed": num(r["% Invoices not paid due to dispute"]),
                "reportPeriodEnd": r["End date"], "filingDate": r["Filing date"], "reportUrl": r["URL"],
                "riskBand": band(avg, p60, late), "source": "payment-practices"})
json.dump(out, sys.stdout, indent=1)
