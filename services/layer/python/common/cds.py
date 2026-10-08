"""Runtime wrappers around the AWS CDS messaging SDKs.

These are the only places Arrearo talks to WhatsApp and email. Each function is
one boto3 call, made at runtime inside a Lambda:

  - AWS End User Messaging Social  ->  boto3.client("socialmessaging")
  - Amazon SES v2                  ->  boto3.client("sesv2")

Request shapes follow research/technical.md (validated against the botocore
service models).
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Optional

import boto3

from common import config

META_API_VERSION = "v20.0"
log = logging.getLogger(__name__)


def live() -> bool:
    """Sends are real only when SEND_MODE=live. Anything else logs the payload and
    returns a dry-run id, so no stray WhatsApp or email leaves the account until
    the owner switches it on (a stack parameter)."""
    return os.environ.get("SEND_MODE", "dry") == "live"

_clients: dict = {}


def client(service: str):
    """Lazily-created boto3 client; tests inject stubbed ones with set_client."""
    if service not in _clients:
        _clients[service] = boto3.client(service, region_name=config.REGION)
    return _clients[service]


def set_client(service: str, c) -> None:
    _clients[service] = c


def wa_id(number: str) -> str:
    """AWS SendWhatsAppMessage wants the destination in E.164 WITH a leading '+'.
    Inbound webhooks give the number without it (e.g. '233547738808'), and a
    plain-digits 'to' is rejected with InvalidParametersException (confirmed with
    a live send on 2026-10-08: no '+' failed, '+233...' delivered)."""
    digits = "".join(ch for ch in str(number) if ch.isdigit())
    return "+" + digits if digits else ""


def send_whatsapp_text(to: str, body: str, reply_to_wamid: Optional[str] = None) -> str:
    """Send a free-form text over the Brownshift WABA. Only valid inside the 24h
    customer-service window. Returns the wamid of the sent message."""
    msg = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": wa_id(to),
        "type": "text",
        "text": {"preview_url": False, "body": body[:4096]},
    }
    if reply_to_wamid:
        msg["context"] = {"message_id": reply_to_wamid}
    if not live():
        log.info("DRY-RUN whatsapp to=%s body=%s", msg["to"], body)
        return f"dry-run-{uuid.uuid4().hex[:12]}"
    resp = client("socialmessaging").send_whatsapp_message(
        originationPhoneNumberId=config.ORIGINATION_PHONE_NUMBER_ID,
        message=json.dumps(msg).encode("utf-8"),
        metaApiVersion=META_API_VERSION,
    )
    return resp["messageId"]


def send_whatsapp_raw(to: str, message: dict) -> str:
    """Send a pre-built Meta WhatsApp message (interactive buttons/list, document,
    etc.) built by wa.messages. The builder omits 'to'; we add it here. Valid only
    inside the 24h window. Returns the wamid (or a dry-run id when SEND_MODE != live)."""
    msg = {"messaging_product": "whatsapp", "recipient_type": "individual",
           "to": wa_id(to), **message}
    if not live():
        log.info("DRY-RUN whatsapp(raw) to=%s type=%s", msg["to"], message.get("type"))
        return f"dry-run-{uuid.uuid4().hex[:12]}"
    resp = client("socialmessaging").send_whatsapp_message(
        originationPhoneNumberId=config.ORIGINATION_PHONE_NUMBER_ID,
        message=json.dumps(msg).encode("utf-8"),
        metaApiVersion=META_API_VERSION,
    )
    return resp["messageId"]


def fetch_whatsapp_media(media_id: str, bucket: str, key: str) -> dict:
    """Ask the service to write an inbound media file to S3. The call does not
    return the bytes: it returns {mimeType, fileSize}; read the object from S3."""
    return client("socialmessaging").get_whatsapp_message_media(
        mediaId=media_id,
        originationPhoneNumberId=config.ORIGINATION_PHONE_NUMBER_ID,
        destinationS3File={"bucketName": bucket, "key": key},
    )


def read_s3(bucket: str, key: str) -> bytes:
    return client("s3").get_object(Bucket=bucket, Key=key)["Body"].read()


def send_email(to: str, subject: str, body: str, attachment: Optional[dict] = None,
               from_addr: Optional[str] = None, reply_to: Optional[str] = None) -> str:
    """Send a plain-text email through SES v2. `attachment` is
    {"filename", "content": bytes, "content_type"} (e.g. the LBA PDF).
    Returns the SES MessageId."""
    simple = {
        "Subject": {"Data": subject, "Charset": "UTF-8"},   # UTF-8 so a pound sign is safe
        "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
    }
    if attachment:
        simple["Attachments"] = [{
            "RawContent": attachment["content"],
            "FileName": attachment["filename"],
            "ContentType": attachment.get("content_type", "application/pdf"),
            "ContentDisposition": "ATTACHMENT",
            "ContentTransferEncoding": "BASE64",
        }]
    params = {
        "FromEmailAddress": from_addr or f"{config.BRAND} <{config.SES_SENDER}>",
        "Destination": {"ToAddresses": [to]},
        "Content": {"Simple": simple},
    }
    if reply_to:
        params["ReplyToAddresses"] = [reply_to]
    if not live():
        log.info("DRY-RUN email to=%s subject=%s attachment=%s", to, subject, bool(attachment))
        return f"dry-run-{uuid.uuid4().hex[:12]}"
    return client("sesv2").send_email(**params)["MessageId"]
