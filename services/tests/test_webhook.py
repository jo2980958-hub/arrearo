import io
import json

import boto3
from botocore.stub import Stubber
from fakes import FakeBedrock

import webhook
from agent import llm
from common import cds, db


def sns_event(message: dict, status=False):
    value = {"messaging_product": "whatsapp", "metadata": {"phone_number_id": "1370934536097424"},
             "contacts": [{"profile": {"name": "Pat"}, "wa_id": "447700900123"}]}
    value["statuses" if status else "messages"] = [message]
    entry = {"id": "1", "changes": [{"field": "messages", "value": value}]}
    outer = {"context": {}, "whatsAppWebhookEntry": json.dumps(entry), "messageId": "aws-1",
             "aws_account_id": "854924711083", "message_timestamp": "2026-10-08T10:00:00Z"}
    return {"Records": [{"EventSource": "aws:sns", "Sns": {"Message": json.dumps(outer)}}]}


def text_msg(wamid, sender, body):
    return sns_event({"from": sender, "id": wamid, "timestamp": "1760000000", "type": "text", "text": {"body": body}})


def test_parse_triple_wrapped_text_and_image_and_status():
    [t] = list(webhook.parse_sns_event(text_msg("wamid.T", "447700900123", "hi")))
    assert (t["kind"], t["from"], t["text"], t["media_id"]) == ("message", "447700900123", "hi", None)
    img = sns_event({"from": "44770", "id": "wamid.I", "timestamp": "1", "type": "image",
                     "image": {"mime_type": "image/jpeg", "id": "5303", "sha256": "x"}})
    [i] = list(webhook.parse_sns_event(img))
    assert (i["media_id"], i["mime"]) == ("5303", "image/jpeg")
    st = sns_event({"id": "wamid.S", "status": "delivered", "timestamp": "5", "recipient_id": "44770",
                    "conversation": {"expiration_timestamp": "1736461020"}}, status=True)
    [s] = list(webhook.parse_sns_event(st))
    assert (s["kind"], s["window_expires_at"]) == ("status", 1736461020)


def test_debtor_reply_classified_stored_and_timeline_updated(invoice):
    llm.set_client(FakeBedrock([{"intent": "promise_to_pay", "confidence": 0.92, "promisedDate": "2026-10-16"}]))
    out = webhook.handler(text_msg("wamid.R1", "447700900123", "I'll pay Friday"))
    [r] = out["results"]
    assert r["role"] == "debtor" and "2026-10-16" in r["reply"]
    inv = db.get_invoice(invoice["invoiceId"])
    assert inv["status"] == "promised" and inv["promisedDate"] == "2026-10-16"
    types = [e["type"] for e in db.list_events(invoice["invoiceId"])]
    assert "replied" in types and "promised" in types
    msg = db.list_messages("447700900123")[0]
    assert msg["intent"] == "promise_to_pay" and msg["invoiceId"] == invoice["invoiceId"]
    assert db.window_open("447700900123")                      # reply opens the 24h window


def test_duplicate_delivery_is_ignored(invoice):
    llm.set_client(FakeBedrock([{"intent": "question", "confidence": 0.7}]))
    ev = text_msg("wamid.D", "447700900123", "who is this?")
    webhook.handler(ev)
    [again] = webhook.handler(ev)["results"]
    assert again["skipped"] == "duplicate" and len(db.list_messages("447700900123")) == 1


def test_unknown_sender_is_logged_and_ignored():
    [r] = webhook.handler(text_msg("wamid.U", "447700999999", "hello"))["results"]
    assert r["skipped"] == "unknown_sender"


def test_owner_invoice_photo_is_fetched_extracted_and_stored(business, monkeypatch):
    monkeypatch.setattr(webhook, "MEDIA_BUCKET", "media-bkt")
    sm = boto3.client("socialmessaging", region_name="us-east-1")
    cds.set_client("socialmessaging", sm)
    st = Stubber(sm)
    st.add_response("get_whatsapp_message_media", {"mimeType": "image/jpeg", "fileSize": 4},
                    {"mediaId": "5303", "originationPhoneNumberId": cds.config.ORIGINATION_PHONE_NUMBER_ID,
                     "destinationS3File": {"bucketName": "media-bkt",
                                           "key": f"inbound/{business['businessId']}/5303"}})
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="media-bkt")
    s3.put_object(Bucket="media-bkt", Key=f"inbound/{business['businessId']}/5303", Body=b"\xff\xd8jpeg")
    cds.set_client("s3", s3)
    llm.set_client(FakeBedrock([{"is_invoice": True, "customer_name": "Bluebell Builders Ltd",
                                 "invoice_number": "INV-7", "invoice_date": "2026-09-01", "gross_amount": 480.0,
                                 "confidence": 0.93}]))
    ev = sns_event({"from": "447700900001", "id": "wamid.IMG", "timestamp": "1", "type": "image",
                    "image": {"mime_type": "image/jpeg", "id": "5303"}})
    with st:
        [r] = webhook.handler(ev)["results"]
    assert r["role"] == "owner" and "£480.00" in r["reply"] and "Reply YES" in r["reply"]
    [inv] = db.list_invoices_by_business(business["businessId"])
    assert inv["status"] == "extracted" and inv["amountPence"] == 48000 and inv["sourceChannel"] == "whatsapp"
    assert [e["type"] for e in db.list_events(inv["invoiceId"])] == ["created", "extracted"]
    # YES confirms it
    [r2] = webhook.handler(text_msg("wamid.YES", "447700900001", "Yes"))["results"]
    assert "Confirmed" in r2["reply"]
    assert db.get_invoice(inv["invoiceId"])["status"] == "confirmed"


def test_bad_message_does_not_raise(invoice):
    llm.set_client(FakeBedrock([]))          # classify will blow up
    [r] = webhook.handler(text_msg("wamid.X", "447700900123", "hello"))["results"]
    assert r["error"] is True
