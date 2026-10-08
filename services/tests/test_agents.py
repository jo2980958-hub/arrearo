import pytest
from fakes import FakeBedrock

from agent import classify, draft, extract, llm
from common import db


def test_extract_converts_to_pence_and_never_invents(monkeypatch):
    fake = FakeBedrock([{"is_invoice": True, "customer_name": "Bluebell Builders Ltd", "invoice_number": "INV-9",
                         "invoice_date": "2026-07-01", "payment_terms_days": 14, "gross_amount": 1234.5,
                         "confidence": 0.95}])
    llm.set_client(fake)
    r = extract.extract_from_image(b"\xff\xd8", "image/jpeg")
    assert r["amountPence"] == 123450
    assert r["agreedDueDate"] == "2026-07-15"
    assert r["needsConfirmation"] is False
    img = fake.calls[0]["messages"][0]["content"][0]["image"]
    assert img["format"] == "jpeg"
    assert fake.calls[0]["toolConfig"]["toolChoice"] == {"tool": {"name": "record_invoice"}}


def test_extract_missing_amount_forces_confirmation():
    llm.set_client(FakeBedrock([{"is_invoice": True, "customer_name": "X Ltd", "invoice_date": "2026-07-01",
                                 "gross_amount": None, "net_amount": 100, "vat_amount": None, "confidence": 0.99}]))
    r = extract.extract_from_text("invoice for X")
    assert r["amountPence"] is None and r["needsConfirmation"] and r["extractionConfidence"] <= 0.5


def test_extract_net_plus_vat_only_when_both_printed():
    llm.set_client(FakeBedrock([{"is_invoice": True, "customer_name": "X", "invoice_date": "2026-07-01",
                                 "net_amount": 100.0, "vat_amount": 20.0, "confidence": 0.9}]))
    assert extract.extract_from_text("x")["amountPence"] == 12000


def test_classify_promise_resolves_date():
    llm.set_client(FakeBedrock([{"intent": "promise_to_pay", "confidence": 0.9, "promisedDate": "2026-10-16"}]))
    r = classify.classify_reply("I'll pay Friday", {"amountPence": 100, "reference": "R", "status": "chasing"})
    assert r["intent"] == "promise_to_pay" and r["extracted"] == {"promisedDate": "2026-10-16"} and not r["optOut"]


def test_classify_bad_intent_falls_back_to_other():
    llm.set_client(FakeBedrock([{"intent": "nonsense", "confidence": 0.2}]))
    assert classify.classify_reply("???")["intent"] == "other"


@pytest.fixture
def derived(invoice, business):
    from datetime import date
    return db.get_invoice(invoice["invoiceId"], date(2026, 8, 30)), business


def good(derived_inv):
    return (f"Hello, invoice INV-1042 for {'£2,500.00'} is overdue. Total now owed {draft.config.gbp(derived_inv['totalOwedPence'])}. "
            "Interest runs under the Late Payment of Commercial Debts (Interest) Act 1998.")


def test_chase_passes_scan_and_cites_engine_figures(derived):
    inv, biz = derived
    fake = FakeBedrock(texts=[good(inv)])
    llm.set_client(fake)
    text = draft.draft_chase(inv, biz)
    assert draft.config.gbp(inv["totalOwedPence"]) in text
    prompt = fake.calls[0]["messages"][0]["content"][0]["text"]
    assert draft.config.gbp(inv["interestAccruedPence"]) in prompt           # injected as a fact


def test_chase_redrafts_once_on_violation(derived):
    inv, biz = derived
    fake = FakeBedrock(texts=["Pay up or we involve the police. £2,500.00", good(inv)])
    llm.set_client(fake)
    assert "police" not in draft.draft_chase(inv, biz)
    assert len(fake.calls) == 2 and "rejected" in fake.calls[1]["messages"][0]["content"][0]["text"]


def test_chase_blocks_after_second_violation(derived):
    inv, biz = derived
    llm.set_client(FakeBedrock(texts=["We will prosecute. £2,500.00", "Still a criminal matter £2,500.00"]))
    with pytest.raises(draft.ComplianceBlock) as e:
        draft.draft_chase(inv, biz)
    assert e.value.violations


def test_chase_omitting_figures_is_rejected(derived):
    inv, biz = derived
    llm.set_client(FakeBedrock(texts=["Please pay soon.", "Please pay soon, thanks."]))
    with pytest.raises(draft.ComplianceBlock):
        draft.draft_chase(inv, biz)


def test_individual_debtor_gets_no_statutory_interest_facts(derived):
    inv, biz = derived
    inv = {**inv, "debtorType": "individual"}
    f = draft.facts_for(inv, biz)
    assert "statutoryRate" not in f and f["totalNowOwed"] == "£2,500.00"


def test_lba_includes_protocol_checklist(derived):
    inv, biz = derived
    inv = {**inv, "debtorType": "sole_trader"}
    llm.set_client(FakeBedrock(texts=[good(inv)]))
    out = draft.draft_lba(inv, biz)
    assert out["protocol"]["protocol_applies"] is True and out["protocol"]["reply_period_days"] == 30


def test_digest_totals_come_from_code(derived):
    inv, biz = derived
    fake = FakeBedrock(texts=["Outstanding £2,500.00 today."])
    llm.set_client(fake)
    assert draft.draft_digest(biz, [inv]).startswith("Outstanding")
    assert "£2,500.00" in fake.calls[0]["messages"][0]["content"][0]["text"]


def test_markdown_and_subject_line_are_stripped(derived):
    inv, biz = derived
    llm.set_client(FakeBedrock(texts=["Subject: Overdue\n\n**" + good(inv) + "**"]))
    out = draft.draft_chase(inv, biz)
    assert "**" not in out and not out.lower().startswith("subject")
