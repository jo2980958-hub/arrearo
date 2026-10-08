import os
import sys
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "layer" / "python"), str(ROOT / "functions")]
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
os.environ.pop("SEND_MODE", None)

from common import cds, config, db  # noqa: E402


def _gsi(name, hash_key, range_key=None):
    keys = [{"AttributeName": hash_key, "KeyType": "HASH"}]
    if range_key:
        keys.append({"AttributeName": range_key, "KeyType": "RANGE"})
    return {"IndexName": name, "KeySchema": keys, "Projection": {"ProjectionType": "ALL"}}


# Mirrors infra/template.yaml
SCHEMAS = {
    config.TBL_BUSINESSES: ([("businessId", "S")], [("businessId", "HASH")],
                            [_gsi("byCognitoSub", "cognitoSub"), _gsi("byWhatsapp", "whatsappNumber")],
                            [("cognitoSub", "S"), ("whatsappNumber", "S")]),
    config.TBL_INVOICES: ([("invoiceId", "S")], [("invoiceId", "HASH")],
                          [_gsi("byBusiness", "businessId", "createdAt"),
                           _gsi("byDebtorWhatsapp", "debtorWhatsapp", "createdAt")],
                          [("businessId", "S"), ("createdAt", "S"), ("debtorWhatsapp", "S")]),
    config.TBL_DEBTORS: ([("debtorKey", "S")], [("debtorKey", "HASH")], [], []),
    config.TBL_CONVERSATIONS: ([("whatsappNumber", "S"), ("createdAt#messageId", "S")],
                               [("whatsappNumber", "HASH"), ("createdAt#messageId", "RANGE")], [], []),
    config.TBL_EVENTS: ([("invoiceId", "S"), ("createdAt#seq", "S")],
                        [("invoiceId", "HASH"), ("createdAt#seq", "RANGE")], [], []),
}


@pytest.fixture(autouse=True)
def aws():
    with mock_aws():
        res = boto3.resource("dynamodb", region_name="us-east-1")
        for name, (attrs, keys, gsis, gsi_attrs) in SCHEMAS.items():
            defs = {a: t for a, t in attrs + gsi_attrs}
            kw = dict(TableName=name, BillingMode="PAY_PER_REQUEST",
                      AttributeDefinitions=[{"AttributeName": a, "AttributeType": t} for a, t in defs.items()],
                      KeySchema=[{"AttributeName": a, "KeyType": k} for a, k in keys])
            if gsis:
                kw["GlobalSecondaryIndexes"] = gsis
            res.create_table(**kw)
        db.set_resource(res)
        cds._clients.clear()
        yield res


@pytest.fixture
def business():
    return db.create_business({"name": "Acme Joinery Ltd", "ownerName": "Sam Acme", "email": "sam@acme.test",
                               "whatsappNumber": "+447700900001", "cognitoSub": "sub-1", "bankName": "Monzo",
                               "bankSortCode": "04-00-04", "bankAccount": "12345678"})


@pytest.fixture
def invoice(business):
    return db.create_invoice(business["businessId"], {
        "debtorName": "Bluebell Builders Ltd", "debtorType": "company", "amountPence": 250_000,
        "invoiceDate": "2026-07-01", "reference": "INV-1042", "description": "Kitchen fit-out",
        "status": "confirmed", "debtorWhatsapp": "447700900123", "debtorEmail": "accounts@bluebell.test"})
