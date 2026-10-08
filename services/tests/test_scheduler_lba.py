import boto3
from botocore.stub import ANY, Stubber
from fakes import FakeBedrock

import scheduler
from agent import llm
from common import cds, db, flows


def test_sweep_dry_mode_writes_nothing(invoice):
    r = scheduler.due_sweep()
    assert r["live"] is False and r["skipped"][0]["reason"] == "dry-run"
    assert db.list_events(invoice["invoiceId"]) == []
    assert db.get_invoice(invoice["invoiceId"])["status"] == "confirmed"


def test_sweep_live_chases_by_email_and_respects_cadence(invoice, monkeypatch):
    monkeypatch.setenv("SEND_MODE", "live")
    ses = boto3.client("sesv2", region_name="us-east-1")
    cds.set_client("sesv2", ses)
    inv = db.get_invoice(invoice["invoiceId"])
    llm.set_client(FakeBedrock(texts=[f"£2,500.00 overdue, total {db.config.gbp(inv['totalOwedPence'])}"]))
    st = Stubber(ses)
    st.add_response("send_email", {"MessageId": "ses-1"}, {"FromEmailAddress": ANY, "Destination": ANY,
                                                          "Content": ANY, "ReplyToAddresses": ANY})
    with st:
        r = scheduler.due_sweep()
        assert [c["invoiceId"] for c in r["chased"]] == [invoice["invoiceId"]]
        assert db.get_invoice(invoice["invoiceId"])["status"] == "chasing"
        again = scheduler.due_sweep()                     # same day: s.40 cadence blocks a re-chase
        assert again["chased"] == [] and again["skipped"][0]["reason"] == "too_soon"
    assert [e["type"] for e in db.list_events(invoice["invoiceId"])] == ["due", "chased"]


def test_lba_sends_pdf_and_marks_status(invoice, monkeypatch):
    monkeypatch.setenv("SEND_MODE", "live")
    ses = boto3.client("sesv2", region_name="us-east-1")
    cds.set_client("sesv2", ses)
    inv = db.get_invoice(invoice["invoiceId"])
    llm.set_client(FakeBedrock(texts=[f"Dear Sirs, £2,500.00 owed, total {db.config.gbp(inv['totalOwedPence'])}."]))
    seen = {}
    ses.meta.events.register("before-parameter-build.sesv2.SendEmail", lambda params, **kw: seen.update(params))
    st = Stubber(ses)
    st.add_response("send_email", {"MessageId": "ses-2"})
    with st:
        out = flows.send_lba(invoice["invoiceId"])
    assert out["sent"] is True
    att = seen["Content"]["Simple"]["Attachments"][0]
    assert att["FileName"] == "Letter-Before-Action.pdf" and att["RawContent"].startswith(b"%PDF")
    assert db.get_invoice(invoice["invoiceId"])["status"] == "lba"
    assert [e["type"] for e in db.list_events(invoice["invoiceId"])] == ["lba_drafted", "lba_sent"]


def test_digest_dry(business, invoice):
    inv = db.get_invoice(invoice["invoiceId"])
    llm.set_client(FakeBedrock(texts=["Outstanding £2,500.00 across 1 invoice."]))
    out = scheduler.daily_digest()
    assert out["digests"][0]["sent"] is False
