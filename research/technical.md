# CDS Recoup: technical + legal facts (research date 2026-10-08)

Provenance tags used throughout:
- **[CLI]** read from `aws ... help` (aws-cli 2.27.1) or from the botocore service model (boto3 1.43.95), i.e. authoritative
- **[VALIDATED]** the snippet was run through botocore param validation with a Stubber (no network call). The request shape is accepted by the real service model. It has NOT been sent live.
- **[FETCHED]** pulled by curl from the named URL today
- **[LIVE]** read-only call against the AWS account on this machine (854924711083, Brownshift) today
- **[TRAINING]** from model knowledge, not re-verified today. Treat as unverified.

---

## 0. What already exists on this machine (all [LIVE], read-only)

| Item | Value |
|---|---|
| AWS account | 854924711083 (Brownshift), default region us-east-1 |
| WABA | `waba-fc7e800db8f4433ab28a07f47089a226`, Meta WABA id `4433154917000184`, name "Brownshift Technologies", registrationStatus COMPLETE, linked 2026-09-17, **us-east-1 only** (eu-west-2 has none) |
| WhatsApp phone number | `+233 55 906 2312` (Ghana number), qualityRating GREEN |
| **originationPhoneNumberId** | `phone-number-id-0d66a9b3b8fc463bb9bf999932643060` |
| Meta phone number id | `1370934536097424` (this is what appears in inbound `metadata.phone_number_id`; it is NOT the AWS id) |
| Event destination (SNS) | `arn:aws:sns:us-east-1:854924711083:brownshift-whatsapp-events` |
| SES us-east-1 | **sandbox** (`ProductionAccessEnabled=false`), 200/24h, 1/sec. Identities: `brownshift.com` (DOMAIN, **VerificationStatus FAILED**, sending disabled), `kasamafo.awsapps.com` + `kasamafo.africa` (DOMAIN, SUCCESS), `rkobeng007@st.ug.edu.gh` (EMAIL, SUCCESS). |
| SES eu-west-2 | sandbox, 200/24h, 1/sec, **no identities** |
| Bedrock profiles | us-east-1: `us.` and `global.` for both Haiku 4.5 (`...haiku-4-5-20251001-v1:0`) and Sonnet 4.5 (`...sonnet-4-5-20250929-v1:0`), all ACTIVE. eu-west-2: `eu.` and `global.` for both, ACTIVE. **The `us.` prefix only works from US regions; from eu-west-2 use `eu.` or `global.`.** |

Implications for the build:
1. Do the WhatsApp side in **us-east-1** (the WABA is there). The SNS topic and Lambda that receive events must also be in us-east-1.
2. The `us.` model IDs from the brief work in us-east-1 as written. Keep Bedrock, SES and the WABA all in us-east-1 to avoid region juggling.
3. SES is in sandbox in both regions. The `brownshift.com` identity FAILED (DKIM CNAMEs never found within 72h). Easiest unblock tonight: use `kasamafo.africa` (already verified, SUCCESS) as the From domain, or verify a single recipient address (sandbox only sends to verified recipients). See section B.

---

## A. AWS End User Messaging Social (`socialmessaging`)

### A1. `send-whatsapp-message` exact shape [CLI][VALIDATED]

CLI synopsis (all three are **required**):
```
aws socialmessaging send-whatsapp-message
  --origination-phone-number-id <string>   # "phone-number-id-" + 32 hex (AWS id, not Meta's)
  --message <blob>                         # a WhatsApp Cloud API message object, as JSON bytes
  --meta-api-version <string>              # e.g. v20.0 (formatted v{VersionNumber})
```
Botocore model: operation `SendWhatsAppMessage`, `POST /v1/whatsapp/send`, input members `originationPhoneNumberId` (string, required), `message` (blob, required), `metaApiVersion` (string, required); output `{messageId}`.

How `--message` is passed:
- It is a **blob that holds the raw WhatsApp Cloud API message JSON**. It is not a nested AWS structure and is not pre-base64'd by you.
- **boto3**: pass `json.dumps(msg).encode()` (bytes). I also validated passing a plain `str`; botocore accepts it. boto3 does the base64/HTTP encoding for you.
- **CLI v2**: inline JSON works, but you must add `--cli-binary-format raw-in-base64-out` (or set `cli_binary_format` in config), otherwise the CLI tries to base64-decode your JSON. This is from the AWS User Guide pages [FETCHED]. `fileb://` also works for a blob but is not needed.
- The docs examples use `--meta-api-version v20.0` [FETCHED]. The CLI help says supported versions per region are listed in the AWS General Reference "End User Messaging endpoints" page (not fetched). v20.0 is what AWS's own examples use, so use it.
- `to` takes the recipient's phone number. The AWS examples use a bare number or `+`-prefixed E.164. **[TRAINING]**: Meta accepts either, and the safest form is digits with country code and no `+` spaces (e.g. `447700900123`). Reply to the inbound `from` value verbatim, which is already in the right format.

boto3 snippet, TEXT message inside the 24h window [VALIDATED shape, not sent live]:
```python
import json, boto3

sm = boto3.client("socialmessaging", region_name="us-east-1")   # WABA lives in us-east-1
PHONE_ID = "phone-number-id-0d66a9b3b8fc463bb9bf999932643060"   # AWS id, not Meta's 1370934536097424

def send_text(to_wa_id: str, body: str, reply_to_wamid: str | None = None) -> str:
    msg = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_wa_id,                       # e.g. "447700900123" (use inbound messages[].from)
        "type": "text",
        "text": {"preview_url": False, "body": body},   # body max 4096 chars (Meta limit, TRAINING)
    }
    if reply_to_wamid:                        # quote the customer's message (TRAINING: Cloud API "context")
        msg["context"] = {"message_id": reply_to_wamid}
    resp = sm.send_whatsapp_message(
        originationPhoneNumberId=PHONE_ID,
        message=json.dumps(msg).encode("utf-8"),
        metaApiVersion="v20.0",
    )
    return resp["messageId"]                  # a wamid.* id; status events refer to it
```

Other message bodies that go in the same `message` blob:

| Purpose | `message` JSON | Source |
|---|---|---|
| Template (works outside the 24h window) | `{"messaging_product":"whatsapp","to":"<num>","type":"template","template":{"name":"statement","language":{"code":"en_US"},"components":[{"type":"body","parameters":[{"type":"text","text":"1000"}]}]}}` | [FETCHED] AWS guide |
| Template with no components | `{"messaging_product":"whatsapp","to":"<num>","type":"template","template":{"name":"simple_template","language":{"code":"en_US"}}}` | [FETCHED] |
| Image by uploaded media id | `{"messaging_product":"whatsapp","to":"<num>","type":"image","image":{"id":"<MEDIA_ID>"}}` | [FETCHED] |
| Mark inbound as read (blue ticks) | `{"messaging_product":"whatsapp","message_id":"<wamid>","status":"read"}` (no `to`) | [FETCHED] |
| Document (e.g. the LBA PDF) | `{"messaging_product":"whatsapp","to":"<num>","type":"document","document":{"id":"<MEDIA_ID>","filename":"Letter-Before-Action.pdf","caption":"..."}}` | [TRAINING], Cloud API document message; verify before relying |

Template message named parameters (`parameter_name`) and button components are Meta Cloud API features [TRAINING]. Check them against the Meta docs when writing the template.

Sending media requires a two step flow [FETCHED + CLI]: (1) put the file in S3, (2) `post-whatsapp-message-media --origination-phone-number-id <id> --source-s3-file bucketName=<b>,key=<k>` returns `{mediaId}`, (3) send a message that references `{"id": mediaId}`. **Only the same `originationPhoneNumberId` that uploaded the media can send it** [CLI]. WhatsApp keeps uploaded media for 30 days [FETCHED]. boto3: `sm.post_whatsapp_message_media(originationPhoneNumberId=..., sourceS3File={"bucketName":..., "key":...})` (validated shape: output `{mediaId}`).

Transient error to handle [FETCHED]: WhatsApp error **131042** "Business eligibility payment issue" is often transient. AWS advises exponential backoff 1s, 2s, 4s, 8s, up to 5 retries. If it persists for hours across recipients it likely means credit line sharing was revoked for the WABA.

Outbound failure for someone not on WhatsApp [FETCHED]: a status event with `status: "failed"` is generated.

### A2. INBOUND message: how it arrives [FETCHED + TRAINING for the SNS envelope]

Setup requirement [FETCHED]: the WABA must have an **event destination** (an SNS topic). Each WABA has exactly one. Here it is already `brownshift-whatsapp-events` in us-east-1. Subscribe a Lambda (or SQS) to that topic. This also delivers **status** events for outbound messages.

It is **triple-wrapped**:
1. **SNS envelope** (what a Lambda SNS trigger gives you): `event["Records"][0]["Sns"]["Message"]` is a **string** [TRAINING for the SNS part; standard SNS-to-Lambda shape].
2. That string is JSON: the AWS header with `context`, `aws_account_id`, `message_timestamp`, `messageId`, and **`whatsAppWebhookEntry`, which is itself a JSON *string*** [FETCHED, AWS says "received from WhatsApp ... as a JSON string and can be converted to JSON"].
3. The inner string is Meta's webhook entry (`id`, `changes[].value`, `field:"messages"`).

AWS header [FETCHED]:
```json
{
  "context": {
    "MetaWabaIds": [{"wabaId": "1234567890abcde", "arn": "arn:aws:social-messaging:us-east-1:123456789012:waba/fb2594..."}],
    "MetaPhoneNumberIds": [{"metaPhoneNumberId": "abcde1234567890", "arn": "arn:aws:social-messaging:us-east-1:123456789012:phone-number-id/976c72a7..."}]
  },
  "whatsAppWebhookEntry": "{\"id\":\"...\",\"changes\":[...]}",
  "aws_account_id": "123456789012",
  "message_timestamp": "2025-01-08T23:30:43.271279391Z",
  "messageId": "6d69f07a-c317-4278-9d5c-6a84078419ec"
}
```

Decoded `whatsAppWebhookEntry` for an inbound TEXT message [FETCHED]:
```json
{
  "id": "365731266123456",
  "changes": [{
    "field": "messages",
    "value": {
      "messaging_product": "whatsapp",
      "metadata": {"display_phone_number": "12065550100", "phone_number_id": "321010217712345"},
      "contacts": [{"profile": {"name": "Diego"}, "wa_id": "12065550102"}],
      "messages": [{
        "from": "14255550150",
        "id": "wamid.HBgLMTQyNTY5ODgzMDIVAgASGCBD...",
        "timestamp": "1723506035",
        "type": "text",
        "text": {"body": "Hi"}
      }]
    }
  }]
}
```
Decoded for an inbound IMAGE (an invoice photo) [FETCHED]:
```json
"messages": [{
  "from": "14255550150",
  "id": "wamid.HBgLMTQyNTY5ODgzMDIVAgASGCBD...",
  "timestamp": "1723506230",
  "type": "image",
  "image": {"mime_type": "image/jpeg", "sha256": "BTD0xlqSZ7l02o+/upusiNStlEZhA/urkvKf143Uqjk=", "id": "530339869524171"}
}]
```
Note that the AWS docs example shows `from` and `wa_id` as different numbers (it is sample data). In real traffic they match. Reply to `messages[].from`. An image sent with a caption carries `image.caption` [TRAINING]. A PDF arrives as `type:"document"` with `document.id`, `document.mime_type`, `document.filename` [TRAINING].

Lambda parser (handles all three layers, both message and status events):
```python
import json

def parse_sns_event(event):
    for rec in event["Records"]:
        outer = json.loads(rec["Sns"]["Message"])                  # layer 1 -> AWS header
        entry = json.loads(outer["whatsAppWebhookEntry"])          # layer 2 -> Meta entry (string inside JSON)
        for ch in entry.get("changes", []):
            v = ch["value"]
            phone_id_meta = v["metadata"]["phone_number_id"]        # Meta id, not the AWS phone-number-id-...
            for m in v.get("messages", []):                         # inbound customer messages
                yield {"kind": "message", "from": m["from"], "wamid": m["id"], "type": m["type"],
                       "text": m.get("text", {}).get("body"),
                       "media_id": (m.get(m["type"]) or {}).get("id") if m["type"] in ("image", "document") else None,
                       "mime": (m.get(m["type"]) or {}).get("mime_type"),
                       "name": (v.get("contacts") or [{}])[0].get("profile", {}).get("name"),
                       "ts": int(m["timestamp"]), "aws_message_id": outer.get("messageId")}
            for s in v.get("statuses", []):                         # delivery events for our outbound msgs
                conv = s.get("conversation") or {}
                yield {"kind": "status", "wamid": s["id"], "status": s["status"], "to": s["recipient_id"],
                       "ts": int(s["timestamp"]),
                       "window_expires_at": int(conv["expiration_timestamp"]) if conv.get("expiration_timestamp") else None,
                       "errors": s.get("errors")}
```
Idempotency: SNS can redeliver. De-duplicate on `messages[].id` (wamid). Return 200 quickly. **Do the Bedrock work asynchronously** (SQS or Step Functions) because an image-to-JSON call plus reasoning can exceed SNS retry patience.

### A3. Fetch an inbound image: `get-whatsapp-message-media` [CLI][FETCHED][VALIDATED]

There is **no API that returns the bytes in the response**. The service pulls the media from Meta and writes it to **S3** (or a presigned PUT URL) for you, then you read from S3.

```
aws socialmessaging get-whatsapp-message-media
  --media-id <string>                         # REQUIRED  = messages[].image.id  (e.g. 530339869524171)
  --origination-phone-number-id <string>      # REQUIRED  = phone-number-id-0d66a9b3b8fc463bb9bf999932643060
  [--metadata-only | --no-metadata-only]      # true = just mimeType/fileSize, nothing written
  [--destination-s3-file bucketName=<b>,key=<k>]                 # EITHER this ...
  [--destination-s3-presigned-url url=<https>,headers={Content-Type=image/jpeg}]  # ... OR this. Both => InvalidParameterException
```
Output: `{"mimeType": "image/jpeg", "fileSize": 78144}`. Botocore: `POST /v1/whatsapp/media/get`.

```python
def fetch_inbound_media(media_id: str, bucket: str) -> tuple[bytes, str]:
    key = f"inbound/{media_id}"
    r = sm.get_whatsapp_message_media(
        mediaId=media_id,
        originationPhoneNumberId=PHONE_ID,
        destinationS3File={"bucketName": bucket, "key": key},   # bucketName min length 3
    )
    s3 = boto3.client("s3")
    data = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    return data, r["mimeType"]            # feed straight to Bedrock as bytes
```
Gotchas:
- The S3 bucket must be in the same Region as the WABA (us-east-1). The service needs permission to write to it. The caller's IAM needs `social-messaging:GetWhatsAppMessageMedia` plus `s3:PutObject` on the bucket (AWS's docs state the caller needs S3 permission; exact policy not fetched, [TRAINING]).
- The `key` you choose has no extension added. The docs sample saves as `inbound_<MEDIA_ID>` and then copies `inbound_<MEDIA_ID>.jpeg`; use `mimeType` from the response to decide the Bedrock `format`.
- Meta media download URLs are short-lived (about 5 min) and the media id is valid about 30 days [TRAINING], so fetch immediately on receipt.
- Supported inbound types are in "Supported media file types and sizes in WhatsApp" (page not read). **[TRAINING]**: images jpeg/png up to 5 MB, documents up to 100 MB. Verify before promising PDF invoices.

### A4. The 24-hour customer service window [FETCHED]

Rule (AWS User Guide, send-message.html, fetched today): "When a user messages you, a 24-hour timer called a customer service window starts or refreshes. All message types, except for template messages, can only be sent when a customer service window is open between you and the user. Template messages can be sent at any time, as long as the user has opted in to receive messages from you."

So for a debt recovery flow:
- **First contact to a debtor is necessarily a template message** (business-initiated), and the debtor must have **opted in**. This is a legal/ToS issue, see Section D8.
- Once the debtor replies, free-form text/interactive/media is allowed for 24h from their **latest** inbound message. Each new inbound message refreshes the timer.
- Outside the window, only an approved template works. Sending free-form outside the window fails with a Meta error (code 131047, "Re-engagement message") [TRAINING]. Track `last_inbound_ts` and compute `now < last_inbound_ts + 86400` before choosing text vs template.

Detecting expiry from events. A **status** event carries a `conversation` object [FETCHED, example from AWS docs, status "sent"]:
```json
"statuses": [{
  "id": "wamid.HBgL...", "status": "sent", "timestamp": "1736379042", "recipient_id": "01234567890",
  "conversation": {"id": "62374592e84cb58e52bdaed31example", "expiration_timestamp": "1736461020", "origin": {"type": "utility"}},
  "pricing": {"billable": true, "pricing_model": "CBP", "category": "utility"}
}]
```
`conversation.expiration_timestamp` is a Unix-epoch **string**. Parse with `int()`. Caveats [TRAINING, important]:
- Meta moved to per-message pricing on 1 July 2025 (the `pricing_model: "CBP"` in the AWS example reflects that). The `conversation` object is **only present in some status events** now (it was reliably present only for service-window conversations), and may be absent. **Do not rely on it as the only expiry signal.** The robust method is `last_inbound_message_timestamp + 24h`, which you control. Use `expiration_timestamp` as a cross-check when present.
- Statuses: `accepted`, `sent`, `delivered`, `read`, `failed`, `deleted`, `warning`, plus "Message retries exhausted, dropping message" after the 180 min retry window [FETCHED]. `read` only arrives if the customer has read receipts on. A `deleted` status means you should delete your copy of the message [FETCHED], which matters for GDPR handling.

### A5. Operational notes for the build
- Keep a per-debtor state row: `last_inbound_ts`, `opted_in`, `opt_out`, `last_outbound_wamid`, `status`.
- Honour "STOP" style replies immediately and permanently (see D7).
- `put-whatsapp-business-account-event-destinations --id waba-... --event-destinations eventDestinationArn=<sns arn>` is how the destination is set (already done here).
- Template creation/approval happens in the Meta/WhatsApp Manager, not via this API (the CLI listing has no create-template op). Create the debt-reminder template in the console tonight; approval can take minutes to hours [TRAINING]. Utility vs marketing category matters for approval and price. A debt reminder normally goes in as **utility** if it is account-specific [TRAINING]; Meta can recategorise.

---

## B. SES v2 (`sesv2`)

### B1. `send_email`, Simple, with PDF attachment [CLI][VALIDATED]

SES v2 `Simple` content **supports attachments natively** (`Content.Simple.Attachments[]`). You do not need hand-built MIME for a PDF. Each attachment: `RawContent` (blob, boto3 base64s it for you), `FileName`, `ContentType`, `ContentDisposition` (`ATTACHMENT`|`INLINE`), `ContentDescription`, `ContentId`, `ContentTransferEncoding` (`BASE64`|`QUOTED_PRINTABLE`|`SEVEN_BIT`). **[CLI]** SES restricts certain file extensions (see "Unsupported attachment types" in the SES guide; `.pdf` is fine).

```python
import boto3
ses = boto3.client("sesv2", region_name="us-east-1")

def send_lba(to_addr: str, subject: str, text_body: str, html_body: str, pdf_bytes: bytes,
             from_addr="Recoup <recovery@kasamafo.africa>", reply_to=None) -> str:
    resp = ses.send_email(
        FromEmailAddress=from_addr,                      # must be on a verified identity
        Destination={"ToAddresses": [to_addr]},
        ReplyToAddresses=[reply_to] if reply_to else [],
        Content={"Simple": {
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {"Text": {"Data": text_body, "Charset": "UTF-8"},
                     "Html": {"Data": html_body, "Charset": "UTF-8"}},
            "Attachments": [{
                "RawContent": pdf_bytes,
                "FileName": "Letter-Before-Action.pdf",
                "ContentType": "application/pdf",
                "ContentDisposition": "ATTACHMENT",
                "ContentTransferEncoding": "BASE64",
            }],
            "Headers": [{"Name": "X-Recoup-Case", "Value": "case-123"}],   # optional custom headers
        }},
        # ConfigurationSetName="recoup-events",          # for bounce/complaint/delivery events (optional)
    )
    return resp["MessageId"]
```
Plain text only (no attachment): same call with `Body` and no `Attachments`.

Raw/MIME alternative (use if you need exact control, e.g. `Message-ID`, `In-Reply-To` threading) [CLI][TRAINING for the MIME code]:
```python
from email.message import EmailMessage
m = EmailMessage()
m["From"] = "Recoup <recovery@kasamafo.africa>"; m["To"] = to_addr; m["Subject"] = subject
m.set_content(text_body); m.add_alternative(html_body, subtype="html")
m.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename="Letter-Before-Action.pdf")
ses.send_email(Content={"Raw": {"Data": m.as_bytes()}})   # From/Destination come from the MIME headers if omitted
```
Raw rules [CLI]: header+body separated by one blank line; no single line over 1,000 chars; non-ASCII content must be encoded; attachment types must be supported. **Subject must be 7-bit ASCII unless you use RFC 2047 encoded-word or set Charset UTF-8** [CLI]; the `£` sign in a subject needs `Charset: "UTF-8"`.

Message size limit is 40 MB total (including attachments) in v2 [TRAINING]. Page `send-email-concepts-limits.html` did not return the figure in my text scan, so verify if you plan large attachments (an LBA PDF is tiny).

### B2. Domain identity verification [CLI][VALIDATED shape]

`create_email_identity(EmailIdentity="example.co.uk", DkimSigningAttributes={"NextSigningKeyLength": "RSA_2048_BIT"})` returns (output shape validated, values are examples):
```json
{"IdentityType": "DOMAIN", "VerifiedForSendingStatus": false,
 "DkimAttributes": {"SigningEnabled": true, "Status": "PENDING",
                    "Tokens": ["tok1", "tok2", "tok3"], "SigningAttributesOrigin": "AWS_SES"}}
```
- **Easy DKIM** returns **3 `Tokens`**. For each token create a CNAME in your DNS [CLI says tokens "you use to create a set of CNAME records"; the exact record form below is TRAINING]:
  `<token>._domainkey.example.co.uk  CNAME  <token>.dkim.amazonses.com`
- SES searches for the records for up to **72 hours** [CLI]. Status goes `PENDING` -> `SUCCESS` (or `FAILED`; that is what happened to `brownshift.com` here). Poll with `get_email_identity(EmailIdentity=...)` and read `DkimAttributes.Status` and `VerifiedForSendingStatus`.
- A verified DKIM domain is enough to send **from any address on that domain**. No separate address verification needed.
- Optional custom MAIL FROM (`put_email_identity_mail_from_attributes`, needs an MX + SPF TXT record) gives DMARC alignment on SPF [TRAINING]. Skip for the hackathon; DKIM alignment suffices for DMARC.
- Single address verification (sandbox shortcut): `create_email_identity(EmailIdentity="you@gmail.com")`. SES emails a link the recipient must click.

### B3. Sandbox constraints [FETCHED: docs.aws.amazon.com/ses/latest/dg/request-production-access.html]
While in sandbox: send **only to verified addresses/domains or the mailbox simulator**; max **200 messages per 24h**; max **1 message/second**; account-level suppression management disabled. You must still verify every From/Source/Sender/Return-Path identity even in production.
- Mailbox simulator addresses [TRAINING]: `success@simulator.amazonses.com`, `bounce@simulator.amazonses.com`, `complaint@simulator.amazonses.com`, `suppressionlist@simulator.amazonses.com`.
- Production access request is per Region, via console ("Get set up" page) or CLI `aws sesv2 put-account-details --mail-type TRANSACTIONAL --website-url ... --use-case-description ... --production-access-enabled`. AWS reviews it, typically within about 24h [TRAINING]. **Not achievable "tonight" with certainty. For the demo, verify the recipient addresses you will email (your own inboxes) and stay in the sandbox.**
- Suitable framing for review: a debt recovery chaser that sends legally required pre-action letters is transactional, but expect scrutiny. Be explicit about opt-out and unsubscribe handling.

---

## C. Bedrock `converse` via boto3

Both model IDs exist and are ACTIVE as inference profiles in us-east-1 [LIVE]. The `us.` prefix only works for US-region callers; from eu-west-2 use `eu.` or `global.` [LIVE].

Common client:
```python
import boto3, json
br = boto3.client("bedrock-runtime", region_name="us-east-1")
HAIKU  = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
SONNET = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
```
Converse content-block shapes confirmed from `aws bedrock-runtime converse help` [CLI]: `{"text": str}`, `{"image": {"format": "png|jpeg|gif|webp", "source": {"bytes": <blob>}}}`, `{"document": {...}}`, `{"toolUse": {...}}`, `{"toolResult": {...}}`. `image.format` is a lowercase short name, **not** a MIME type. Tools live in `toolConfig.tools[].toolSpec{name, description, inputSchema{json}}` and `toolChoice` is a tagged union (`auto`/`any`/`tool`).

### C1. Image understanding, invoice photo -> structured JSON (Haiku 4.5) [VALIDATED shape, not invoked live]

Most reliable way to get strict JSON is **forcing a tool call** (`toolChoice: {tool: {name}}`) so the model must return an object matching your schema, instead of hoping it writes parseable text:

```python
INVOICE_TOOL = {"toolSpec": {
    "name": "record_invoice",
    "description": "Record the fields read from an invoice image. Use null when a field is not visible. Never guess.",
    "inputSchema": {"json": {
        "type": "object",
        "properties": {
            "is_invoice":        {"type": "boolean"},
            "supplier_name":     {"type": ["string", "null"]},
            "customer_name":     {"type": ["string", "null"]},
            "invoice_number":    {"type": ["string", "null"]},
            "invoice_date":      {"type": ["string", "null"], "description": "ISO 8601 YYYY-MM-DD"},
            "due_date":          {"type": ["string", "null"], "description": "ISO 8601 YYYY-MM-DD"},
            "payment_terms_days":{"type": ["integer", "null"]},
            "currency":          {"type": ["string", "null"], "description": "ISO 4217, e.g. GBP"},
            "net_amount":        {"type": ["number", "null"]},
            "vat_amount":        {"type": ["number", "null"]},
            "gross_amount":      {"type": ["number", "null"]},
            "confidence":        {"type": "number", "minimum": 0, "maximum": 1},
            "unreadable_fields": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["is_invoice", "confidence"],
    }},
}}

FMT = {"image/jpeg": "jpeg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}

def read_invoice(img_bytes: bytes, mime: str) -> dict:
    r = br.converse(
        modelId=HAIKU,
        system=[{"text": "You extract data from photos of UK invoices. Output only via the tool."}],
        messages=[{"role": "user", "content": [
            {"image": {"format": FMT[mime], "source": {"bytes": img_bytes}}},
            {"text": "Extract the invoice fields. Dates as YYYY-MM-DD. Amounts as numbers without currency symbols."},
        ]}],
        toolConfig={"tools": [INVOICE_TOOL], "toolChoice": {"tool": {"name": "record_invoice"}}},
        inferenceConfig={"maxTokens": 1024, "temperature": 0},
    )
    for block in r["output"]["message"]["content"]:
        if "toolUse" in block:
            return block["toolUse"]["input"]         # already a dict, no json.loads needed
    raise ValueError(f"no tool call; stopReason={r['stopReason']}")
```
Plain-JSON alternative (no tool): send the same content with a text instruction "Return ONLY a JSON object with keys ...", then `json.loads(r["output"]["message"]["content"][0]["text"])`. This is less reliable (code fences, trailing prose), so strip fences if you use it.

Image limits [TRAINING]: Converse accepts up to about 3.75 MB per image and 8000 px on the long side, and up to about 20 images per request. Phone photos from WhatsApp are compressed, usually well under that, but resize with Pillow if the S3 object is above 3.75 MB. Note that WhatsApp inbound images are already re-compressed to roughly 100-300 KB, so legibility of small print is the real risk; keep the `unreadable_fields` field and ask the user to resend when `confidence` is low.

### C2. Tool-use reasoning (Sonnet 4.5) [VALIDATED shape, not invoked live]

A decision agent that is given the case facts and must pick the next action through a tool. Loop pattern with `stopReason == "tool_use"`:

```python
DECIDE_TOOL = {"toolSpec": {
    "name": "decide_next_step",
    "description": "Choose the next recovery step for this overdue invoice.",
    "inputSchema": {"json": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["send_whatsapp_reminder", "send_email_reminder",
                       "send_letter_before_action", "wait", "escalate_to_human", "close_case"]},
            "reason": {"type": "string"},
            "message_draft": {"type": ["string", "null"]},
            "tone": {"type": "string", "enum": ["friendly", "firm", "formal"]},
            "compliance_flags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["action", "reason", "tone", "compliance_flags"],
    }},
}}

def decide(case: dict) -> dict:
    r = br.converse(
        modelId=SONNET,
        system=[{"text": "You are a late-payment recovery assistant for a UK SME. Follow the rules provided. "
                          "Never threaten criminal action, never imply court or bailiff involvement unless a claim has actually been issued, "
                          "never claim official authority."}],
        messages=[{"role": "user", "content": [{"text": json.dumps(case)}]}],
        toolConfig={"tools": [DECIDE_TOOL], "toolChoice": {"tool": {"name": "decide_next_step"}}},
        inferenceConfig={"maxTokens": 1500, "temperature": 0.2},
    )
    return next(b["toolUse"]["input"] for b in r["output"]["message"]["content"] if "toolUse" in b)
```
Multi-tool agent loop (model chooses among several tools, you execute them and feed results back) [CLI shape for toolResult; loop is standard]:
```python
messages = [{"role": "user", "content": [{"text": task}]}]
while True:
    r = br.converse(modelId=SONNET, messages=messages, toolConfig={"tools": TOOLS, "toolChoice": {"auto": {}}},
                    inferenceConfig={"maxTokens": 2000})
    msg = r["output"]["message"]; messages.append(msg)
    if r["stopReason"] != "tool_use": break
    results = []
    for b in msg["content"]:
        if "toolUse" in b:
            tu = b["toolUse"]
            out = run_tool(tu["name"], tu["input"])          # your code
            results.append({"toolResult": {"toolUseId": tu["toolUseId"], "content": [{"json": out}]}})
    messages.append({"role": "user", "content": results})
```
Notes:
- `toolResult.content[]` items may be `text`, `json`, `image`, `document` [CLI lists text/image/document/video; `json` is TRAINING and valid in current SDKs]. If it complains, use `{"text": json.dumps(out)}`.
- `temperature` and `top_p` should not both be set for Claude 4.5 on Bedrock [TRAINING]; set only one (this call sets only `temperature`).
- A forced `toolChoice` of a specific tool is incompatible with extended thinking [TRAINING]; do not combine them.
- Bedrock model access: for Anthropic models you may need to have submitted the use-case form once per account [TRAINING]. The profiles are ACTIVE in this account, but I did not invoke a model (no spend). **Run a one-token smoke test first.**

---
