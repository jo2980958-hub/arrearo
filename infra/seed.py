#!/usr/bin/env python3
"""Seed the deployed stack: payment-practices debtors + a demo business with four invoices
spanning the demo states (extracted / due today / promised / aged-to-LBA).

  python infra/seed.py --sub <cognito sub> [--owner-whatsapp +44...] [--debtor-whatsapp +44...]

Idempotent: does nothing if a business already exists for the Cognito sub. No deletes.
"""
import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "layer" / "python"))
from common import db  # noqa: E402


def days_ago(n, hour=9):
    d = datetime.now(timezone.utc).replace(hour=hour, minute=0, second=0, microsecond=0) - timedelta(days=n)
    return d.isoformat(timespec="microseconds").replace("+00:00", "Z")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sub", required=True)
    ap.add_argument("--email", default="owner@arrearo.com")
    ap.add_argument("--owner-whatsapp", default="+447700900001")
    ap.add_argument("--debtor-whatsapp", default="+447700900123")
    a = ap.parse_args()

    for d in json.load(open(Path(__file__).parent / "seed" / "debtors.json")):
        db.put_debtor(d)
    print("debtors loaded")

    if db.get_business_by_sub(a.sub):
        print("business already seeded; leaving as is")
        return
    biz = db.create_business({
        "name": "Hartley & Finch Joinery Ltd", "ownerName": "Sam Hartley", "email": a.email,
        "whatsappNumber": a.owner_whatsapp, "sector": "construction", "defaultTermsDays": 30,
        "bankName": "Monzo Business", "bankSortCode": "04-00-04", "bankAccount": "12345678", "cognitoSub": a.sub})
    today = date.today()
    iso = lambda n: (today - timedelta(days=n)).isoformat()   # noqa: E731

    specs = [
        # (a) just extracted from a WhatsApp photo, waiting for the owner's YES
        dict(debtorName="Northfield Catering Ltd", amountPence=48_000, invoiceDate=iso(2), reference="HF-2291",
             description="Bar and shelving install", status="extracted", sourceChannel="whatsapp",
             extractionConfidence=0.93, debtorEmail="accounts@northfield-catering.example"),
        # (b) due today, first chase next (real company, real payment record)
        dict(debtorName="BIFFA WASTE SERVICES LIMITED", debtorCompanyNumber="00946107", amountPence=245_000,
             invoiceDate=iso(30), agreedDueDate=today.isoformat(), reference="HF-2268",
             description="Site hoarding and doors", status="due", sourceChannel="whatsapp", extractionConfidence=0.97,
             debtorEmail="payables@biffa.example", debtorWhatsapp=a.debtor_whatsapp, confirmedAt=days_ago(29)),
        # (c) promised to pay
        dict(debtorName="Redcliffe Signs Ltd", amountPence=118_000, invoiceDate=iso(52), reference="HF-2240",
             description="Shopfront joinery", status="promised", sourceChannel="dashboard", promisedDate=(today + timedelta(days=4)).isoformat(),
             debtorEmail="finance@redcliffe-signs.example", confirmedAt=days_ago(51)),
        # (d) aged: two chases sent, ready for a Letter Before Action
        dict(debtorName="Mercer Plant Hire Ltd", amountPence=860_000, invoiceDate=iso(110), reference="HF-2177",
             description="Staircase and balustrade", status="chasing", sourceChannel="whatsapp", extractionConfidence=0.9,
             debtorEmail="office@mercer-plant.example", confirmedAt=days_ago(109)),
    ]
    for s in specs:
        s.setdefault("debtorType", "company")
        inv = db.create_invoice(biz["businessId"], {**s, "createdAt": days_ago(max(0, (today - date.fromisoformat(s["invoiceDate"])).days - 1))})
        i = inv["invoiceId"]
        age = (today - date.fromisoformat(s["invoiceDate"])).days
        db.add_event(i, "created", s["sourceChannel"] if s["sourceChannel"] == "whatsapp" else "system", "owner", {}, at=days_ago(age - 1))
        if s["sourceChannel"] == "whatsapp":
            db.add_event(i, "extracted", "whatsapp", "agent", {"confidence": s.get("extractionConfidence")}, at=days_ago(age - 1, 10))
        if s["status"] != "extracted":
            db.add_event(i, "confirmed", "whatsapp" if s["sourceChannel"] == "whatsapp" else "system", "owner", {}, at=days_ago(age - 1, 11))
            d = db.get_debtor(db.debtor_key(s["debtorName"], s.get("debtorCompanyNumber")))
            db.add_event(i, "debtor_scored", "system", "agent",
                         {"riskBand": d["riskBand"], "avgDaysToPay": d["avgDaysToPay"], "source": d["source"]} if d
                         else {"riskBand": "unknown", "source": "unknown"}, at=days_ago(age - 1, 11))
        if s["status"] == "due":
            db.add_event(i, "due", "system", "system", {}, at=days_ago(0, 6))
        if s["status"] == "promised":
            db.add_event(i, "chased", "email", "agent", {"sent": True, "stage": "first_chase"}, at=days_ago(8))
            db.add_event(i, "replied", "email", "debtor", {"intent": "promise_to_pay"}, at=days_ago(6))
            db.add_event(i, "promised", "email", "debtor", {"promisedDate": s["promisedDate"]}, at=days_ago(6, 10))
        if s["status"] == "chasing":
            db.add_event(i, "chased", "email", "agent", {"sent": True, "stage": "first_chase"}, at=days_ago(60))
            db.add_event(i, "chased", "email", "agent", {"sent": True, "stage": "second_chase"}, at=days_ago(40))
            db.add_event(i, "chased", "email", "agent", {"sent": True, "stage": "final_notice"}, at=days_ago(18))
    print("seeded business", biz["businessId"], "with", len(specs), "invoices")


if __name__ == "__main__":
    main()
