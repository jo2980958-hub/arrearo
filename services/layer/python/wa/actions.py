"""Write actions over WhatsApp, each returning a Reply (or list).

Thin wrappers over common.flows and agent.extract that add the WhatsApp draft ->
Approve/Cancel interaction. Every action re-checks the invoice belongs to business_id.
Depends on common.flows, common.db, agent.extract, wa.messages.
Contract fixed by the spec — agent fills the bodies.
"""
from __future__ import annotations


def confirm(business_id: str, invoice_id: str) -> dict:
    raise NotImplementedError


def chase_draft(business_id: str, invoice_id: str) -> dict:
    """Compose a chase via flows.draft_chase_for and present Approve/Cancel."""
    raise NotImplementedError


def chase_send(business_id: str, invoice_id: str) -> dict:
    """Send the approved chase via flows.send_chase (honours SEND_MODE + window)."""
    raise NotImplementedError


def mark_paid(business_id: str, invoice_id: str) -> dict:
    raise NotImplementedError


def lba_draft(business_id: str, invoice_id: str) -> dict:
    raise NotImplementedError


def lba_send(business_id: str, invoice_id: str) -> dict:
    raise NotImplementedError


def ingest_media(business_id: str, media: dict) -> dict:
    """media = {media_id, mime, bucket, key}. Fetch, extract (image or PDF), store as an
    `extracted` invoice, return a short summary + Confirm/Discard."""
    raise NotImplementedError
