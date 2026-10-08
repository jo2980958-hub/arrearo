import json

import boto3
import pytest
from botocore.stub import Stubber

from common import cds, config


@pytest.fixture
def live(monkeypatch):
    monkeypatch.setenv("SEND_MODE", "live")


def stubbed(service):
    c = boto3.client(service, region_name="us-east-1")
    cds.set_client(service, c)
    return c, Stubber(c)


def test_send_whatsapp_text_exact_shape(live):
    c, st = stubbed("socialmessaging")
    msg = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": "447700900123", "type": "text",
           "text": {"preview_url": False, "body": "Hi"}}
    st.add_response("send_whatsapp_message", {"messageId": "wamid.OUT"},
                    {"originationPhoneNumberId": config.ORIGINATION_PHONE_NUMBER_ID,
                     "message": json.dumps(msg).encode(), "metaApiVersion": "v20.0"})
    with st:
        assert cds.send_whatsapp_text("+44 7700 900123", "Hi") == "wamid.OUT"
        st.assert_no_pending_responses()


def test_fetch_media_writes_to_s3(live):
    c, st = stubbed("socialmessaging")
    st.add_response("get_whatsapp_message_media", {"mimeType": "image/jpeg", "fileSize": 10},
                    {"mediaId": "m1", "originationPhoneNumberId": config.ORIGINATION_PHONE_NUMBER_ID,
                     "destinationS3File": {"bucketName": "bkt", "key": "k"}})
    with st:
        assert cds.fetch_whatsapp_media("m1", "bkt", "k")["mimeType"] == "image/jpeg"


def test_send_email_with_pdf_attachment(live):
    c, st = stubbed("sesv2")
    st.add_response("send_email", {"MessageId": "ses-1"}, {
        "FromEmailAddress": f"{config.BRAND} <{config.SES_SENDER}>",
        "Destination": {"ToAddresses": ["a@b.test"]},
        "Content": {"Simple": {
            "Subject": {"Data": "Pay £5", "Charset": "UTF-8"},
            "Body": {"Text": {"Data": "body", "Charset": "UTF-8"}},
            "Attachments": [{"RawContent": b"%PDF", "FileName": "L.pdf", "ContentType": "application/pdf",
                             "ContentDisposition": "ATTACHMENT", "ContentTransferEncoding": "BASE64"}]}}})
    with st:
        assert cds.send_email("a@b.test", "Pay £5", "body",
                              attachment={"filename": "L.pdf", "content": b"%PDF"}) == "ses-1"


def test_dry_mode_never_calls_aws():
    c, st = stubbed("socialmessaging")        # no responses queued: any call would raise
    with st:
        assert cds.send_whatsapp_text("447700900123", "Hi").startswith("dry-run-")
    c2, st2 = stubbed("sesv2")
    with st2:
        assert cds.send_email("a@b.test", "s", "b").startswith("dry-run-")
