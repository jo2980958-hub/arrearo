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
- **[LIVE smoke test, 2026-10-08, us-east-1, account 854924711083]** Both calls succeeded: Haiku 4.5 with an 8x8 red PNG as an `image` block plus forced tool `toolChoice:{tool:{name}}` returned `stopReason: "tool_use"`, `input: {"colour": "red"}` (689 tokens). Sonnet 4.5 with a forced tool returned `tool_use` (682 tokens). So model access is granted, the `us.` profiles work from us-east-1, the image block shape is right, and forced-tool structured output works on both. The `usage` dict also reports `cacheReadInputTokens`/`cacheWriteInputTokens`.
- `toolUse` blocks come back with `type: "tool_use"` as an extra key; harmless.

---

## D. UK legal facts to encode

Scope warning. The three regimes below apply to **different debtors**. A recovery agent must branch on debtor type first:

| Debtor | Interest + fixed sum | Pre-action | Harassment law |
|---|---|---|---|
| Limited company / LLP / other B2B (both sides acting in the course of a business) | **Late Payment Act 1998** applies (D1-D3) | Practice Direction Pre-Action Conduct (D5b) | AJA 1970 s.40 (D6) |
| Sole trader / individual (even if they bought for business) | LPCDA **can** apply if the sole trader is acting in the course of a business [Act s.2(1)]; does not apply to consumers | **Pre-Action Protocol for Debt Claims** (D5a), because debtor is an individual | AJA s.40 (D6) |
| Consumer (private individual buying for personal use) | **Act does NOT apply** [s.2(1)]. Only contractual interest, and the Consumer Credit Act / consumer law apply | Debt PAP (D5a) | AJA s.40 s.(3A) carve-out; consumer practices fall under DMCC Act 2024 (D6) |

Practical suggestion: the product should ask or infer "is the debtor a limited company, sole trader or consumer?" and refuse to apply the statutory interest block for consumers. Since the brief says the user is a business chasing other businesses, treat sole traders as the edge case that triggers the Debt PAP.

### D1. Statutory interest: 8% + Bank of England base rate [FETCHED]

Sources: GOV.UK "Interest on late commercial payments" (fetched 2026-10-08): "8% plus the Bank of England base rate for business to business transactions. You cannot claim statutory interest if there's a different rate of interest in a contract." Rate mechanism: SI 2002/1675 art.4 (legislation.gov.uk/uksi/2002/1675/made, fetched 2026-10-08).

**The rate is NOT the live base rate. It is 8% over the Bank Rate in force on a fixed reference date** [FETCHED, SI 2002/1675 art.4]:
> "8 per cent per annum over the official dealing rate in force on the 30th June (in respect of interest which starts to run between 1st July and 31st December) or the 31st December (in respect of interest which starts to run between 1st January and 30th June) immediately before the day on which statutory interest starts to run."

The rate is fixed at the moment interest starts to run, and does not float afterwards. GOV.UK's own worked example uses a flat "base rate" because it simplifies; the Order is the authoritative rule. Interest is **simple** (Act s.1(1)), daily = principal x rate / 365, as GOV.UK's example does.

**Current Bank of England Bank Rate: 3.75%** [FETCHED]. Series IUDBEDR, CSV from
`https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp?csv.x=yes&Datefrom=01/Jan/2025&Dateto=now&SeriesCodes=IUDBEDR&CSVF=TN&UsingCodes=Y&VPD=Y&VFD=N`
last data point **06 Oct 2026 = 3.75**. The BoE page "the-interest-rate-bank-rate" confirms "Bank rate maintained at 3.75% - September 2026 Monetary Policy Summary and Minutes".

Bank Rate changes in the fetched series (since 1 Jan 2025): 02 Jan 2025 4.75 -> 06 Feb 2025 4.50 -> 08 May 2025 4.25 -> 07 Aug 2025 4.00 -> 18 Dec 2025 **3.75** (unchanged to 06 Oct 2026). (The series starts 2 Jan 2025; the 4.75 on 31 Dec 2024 is inferred from the first value. Nov 2024's cut to 4.75 is from [TRAINING].)

**Reference rates and resulting statutory rate, by when interest starts to run:**

| Interest starts to run | Reference date | Bank Rate on that date | **Statutory rate (8% + Bank Rate)** |
|---|---|---|---|
| 1 Jan - 30 Jun 2025 | 31 Dec 2024 | 4.75% (inferred) | 12.75% |
| 1 Jul - 31 Dec 2025 | 30 Jun 2025 | 4.25% | **12.25%** |
| 1 Jan - 30 Jun 2026 | 31 Dec 2025 | 3.75% | **11.75%** |
| **1 Jul - 31 Dec 2026 (now)** | **30 Jun 2026** | **3.75%** | **11.75%** |
| 1 Jan - 30 Jun 2027 | 31 Dec 2026 | unknown yet (depends on Nov/Dec 2026 MPC) | 8% + that rate |

**So for any invoice that became overdue between 1 Jan 2026 and 31 Dec 2026, the statutory rate is 11.75% per year (8% + 3.75%).** Equivalent to about 0.0322% per day. Even if the base rate were quoted as "current 3.75%", the total is the same 11.75% today, but the code must use the reference-date lookup so that older invoices get 12.25% / 12.75%. The next reference date is 31 Dec 2026; the next MPC decision dates after Sept 2026 should be checked on the BoE site [TRAINING: MPC meets 8 times a year].

Tested calculator (also in the scratchpad, run today):
```python
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

# Bank Rate on the reference dates (BoE IUDBEDR, fetched 2026-10-08)
REFERENCE_RATE = {date(2024,12,31): Decimal("4.75"),   # inferred
                  date(2025,6,30):  Decimal("4.25"),
                  date(2025,12,31): Decimal("3.75"),
                  date(2026,6,30):  Decimal("3.75")}
# Add date(2026,12,31) once the Dec 2026 MPC decision is known.

def reference_date(interest_starts: date) -> date:      # SI 2002/1675 art.4
    return date(interest_starts.year, 6, 30) if interest_starts.month >= 7 else date(interest_starts.year - 1, 12, 31)

def fixed_sum(debt: Decimal) -> Decimal:                 # LPCDA 1998 s.5A(2)
    return Decimal(40) if debt < 1000 else Decimal(70) if debt < 10000 else Decimal(100)

def late_payment_claim(principal: Decimal, relevant_day: date, as_of: date) -> dict:
    start = relevant_day + timedelta(days=1)             # s.4(2): interest starts the day AFTER the relevant day
    annual = Decimal(8) + REFERENCE_RATE[reference_date(start)]
    days = max((as_of - relevant_day).days, 0)
    interest = (principal * annual / 100 * days / 365).quantize(Decimal("0.01"), ROUND_HALF_UP)
    daily = (principal * annual / 100 / 365).quantize(Decimal("0.01"), ROUND_HALF_UP)
    return dict(annual_pct=annual, days=days, interest=interest, daily=daily,
                fixed=fixed_sum(principal), total=principal + interest + fixed_sum(principal))
```
Outputs verified by running it (as of 2026-10-08):
- £2,400, relevant day 31 Aug 2026: 11.75%, 38 days, interest **£29.36**, £0.77/day, fixed sum **£70**, total £2,499.36
- £999.99, relevant day 15 Jan 2026: 11.75% (ref 31 Dec 2025), 266 days, interest £85.63, fixed £40
- £12,000, relevant day 1 Sep 2025: **12.25%** (ref 30 Jun 2025), 402 days, interest £1,619.01, fixed £100

Day-count convention. Whether to count `as_of - relevant_day` or `as_of - start` changes the result by one day. The GOV.UK example divides by 365 and multiplies by days, which is what the code does. I counted from the relevant day (interest accrues from the next day, and the day the calculation is made is included). This is a one-day judgement call, so show the figure to the user as "approximately" or state the formula in the letter.

### D2. Fixed recovery sum tiers [FETCHED, confirmed twice]

Source 1: GOV.UK "Claim debt recovery costs on late payments" (fetched 2026-10-08): up to £999.99 -> **£40**; £1,000 to £9,999.99 -> **£70**; £10,000 or more -> **£100**. "You can only charge the business once for each payment." "These amounts are set by late payment legislation."
Source 2: LPCDA 1998 **s.5A(2)** (legislation.gov.uk, fetched 2026-10-08): (a) debt **less than £1,000** -> £40; (b) £1,000 or more but less than £10,000 -> £70; (c) £10,000 or more -> £100.
- **s.5A(1)**: the fixed sum is owed "once statutory interest begins to run" and is "in addition to the statutory interest".
- **s.5A(2A)** (added 2013): if the supplier's *reasonable* recovery costs exceed the fixed sum, they can also claim the difference. GOV.UK: "you can also claim for reasonable costs each time you try to recover the debt."
- The fixed sum is per **debt** (per invoice), not per customer. Tier uses the amount of the debt. Whether VAT is included in "the debt" is **not stated in the text I fetched** [TRAINING: the tier is judged on the debt due, which includes VAT, but flag as unverified].
- GOV.UK: "Send a new invoice if you decide to add interest to the money you're owed."

### D3. Lateness rules and the Act's essentials [FETCHED: LPCDA 1998 s.1-s.9, legislation.gov.uk, today]

Statute is "Late Payment of Commercial Debts (Interest) Act 1998", c.20. s.4 was last amended on **24/02/2025** (changes list on legislation.gov.uk). The text I read is the revised version, current "with no known outstanding effects".

Essentials:
- **s.1(1)**: implied term; any qualifying debt carries **simple** interest ("statutory interest").
- **s.2(1)**: applies to a contract for the **supply of goods or services where both the purchaser and supplier are acting in the course of a business** ("business" includes profession, government department, local/public authority). Excepted: consumer credit agreements and security contracts. **Consumers are out**.
- **s.3(1)**: "qualifying debt" = a debt for the whole or part of the contract price. s.3(2): doesn't carry statutory interest where another enactment gives a right to interest. s.3(3): not if the creditor actually exercises a common-law right to demand interest on it (**you cannot claim both** a contractual or common-law rate and statutory interest).
- **s.4(2)**: interest starts on the **day after the "relevant day"**.
- **s.4(2A)** relevant day: (a) the **agreed payment day**, unless (2D)/(2E)/(2G) displace it; (b) if none was agreed, the **last day of the 30-day period**.
- **"Relevant 30-day period" (s.4(2H))** = 30 days beginning with the **later** of (a) the day the supplier performs its obligation (delivery of goods / service), (b) the day the purchaser has notice of the amount of the debt (the invoice) ... (c) the day determined for an acceptance/verification procedure where s.4(5A) applies.
- **Public authority purchaser (s.4(2D))**: if the last day of the 30-day period falls **earlier** than the agreed payment day, the relevant day is the end of the **30-day period**. So public authorities effectively cannot have more than 30 days.
- **Non-public purchaser (s.4(2E)/(2F))**: if the last day of the **60-day period** falls earlier than the agreed payment day, the relevant day is the end of the 60-day period, **unless** the agreed day is **not grossly unfair to the supplier** (s.4(7A), not fetched) in which case the agreed day stands. So 60 days is the default cap, with a "grossly unfair" escape hatch in the supplier's favour test.
- Advance payments (s.4(2G)): relevant day is the day the debt is treated as created under s.11.
- Acceptance/verification (s.4(5A)-(5D)): if the contract has a procedure to check conformity, the clock runs from completion, but treated as completed at most 30 days after performance, unless a longer period is expressly agreed and not grossly unfair.
- **s.5A**: fixed sum (D2).
- **s.6 and SI 2002/1675 art.4**: the rate (D1).
- **Part II, s.7-s.9**: you can only contract out of statutory interest if there is a **"substantial remedy"** (s.8(1)). Contract terms excluding the right are void unless a substantial contractual remedy for late payment exists. s.9(1): a remedy is substantial unless it is insufficient both to compensate and to deter **and** it would be unfair to let it oust the statutory interest. This applies only to terms agreed **before** the debt is created (s.7(2)); after that, the parties can agree anything.
- Practical encoding: lateness date = `agreed_payment_day` if it exists and `agreed_payment_day <= invoice_notice_date + 60 days` (or +30 for a public authority), else `max(performance_date, invoice_date) + 30 days`, then clamp as above. When the user's contract says "30 days from invoice", the relevant day is invoice date + 30; use the day the debtor received the invoice, not the issue date, if known.
- Not fetched, flagged [TRAINING]: s.5 (interest when a payment-day is to be set by an event), s.12-14 (cross-border/Scottish). Not relevant for tonight.

2025 context [TRAINING, unverified]: the UK Government's July 2025 "Small Business Plan" promised legislation to cap contractual payment terms at 60 days and make statutory interest non-waivable. The Act's own change log shows an amendment on 24/02/2025 (probably from the Procurement Act 2023 commencement). I could not confirm any reform in force by October 2026. Treat 8% + Bank Rate and the 60-day default as current law and re-check gov.uk before relying on it commercially.

### D4. (Reserved: the payment-practices dataset is in D8.)

### D5. Pre-action requirements

**(a) Pre-Action Protocol for Debt Claims** [FETCHED, full PDF read: `https://www.justice.gov.uk/documents/debt-pap.pdf`; the old justice.gov.uk protocol page URL now 404s]
- **para 1.1**: applies to "any business (including sole traders and public bodies) claiming payment of a debt from an **individual (including a sole trader)**". It "does **not** apply to business-to-business debts **unless the debtor is a sole trader**."
- **para 1.4**: not for debts under another protocol (Construction and Engineering, Mortgage Arrears) or HMRC claims.
- **para 1.3**: where a regulator's rules (e.g. FCA Handbook) conflict, the regulatory rule wins.
- **para 3.1** the creditor sends a **Letter of Claim** containing:
  - (a)(i) the amount of the debt; (ii) whether interest or other charges are continuing; (iii) for an oral agreement: who made it, what was agreed (and as far as possible the words used), when and where; (iv) for a written agreement: its date, the parties, and that a copy **can be requested**; (v) if assigned: original debt and creditor, when assigned and to whom; (vi) if the debtor is offering or paying instalments: why that is not acceptable and why a claim is still considered; (vii) **how to pay** (method and address) and how to discuss payment options; (viii) the **address to return the Reply Form** to.
  - (b) one of: an up-to-date **statement of account** including interest and charges; or the latest statement plus the interest/charges since; or, if none was issued, a statement of interest and charges since the debt was incurred.
  - (c) enclose the **Information Sheet and Reply Form** (Annex 1, template in the PDF).
  - (d) enclose a **Financial Statement** form (Annex 2; Standard Financial Statement from sfs.moneyadviceservice.org.uk).
- **para 3.2**: the letter must be **clearly dated toward the top of the first page** and posted that day or the next.
- **para 3.3**: must be sent **by post**. Email may be used *in addition*. If the debtor explicitly asked for no post and gave other contact details, use those. A clause in standard terms is not such a request. **An email- or WhatsApp-only LBA does not satisfy the protocol for individuals/sole traders.**
- **para 3.4**: if there is no reply within **30 days of the date at the top of the letter**, the creditor may start proceedings (allowing for a reply posted late in the period).
- **para 4.2**: if the debtor is seeking debt advice, allow a reasonable period; in any case do not issue less than **30 days after receiving the completed Reply Form** (or 30 days after supplying requested documents, whichever is later).
- **para 4.4**: if the debtor needs time to pay, try to agree instalments based on income and expenditure; reasons for refusal go **in writing**.
- **para 5.2**: documents requested by the debtor must be provided (or an explanation given) within **30 days**.
- **para 6.4**: while an agreed repayment arrangement is being kept to, don't issue; a fresh Letter of Claim is needed if you later want to.
- **para 8.2**: if the debtor responded but no agreement, give at least **14 days' notice** of intention to issue (unless exceptional urgency such as limitation).
- **para 7.1**: the court takes non-compliance into account (costs/directions) but isn't concerned with minor technical breaches.
- The Information Sheet tells the debtor: 30 days from the letter date to return the Reply Form; free debt advice bodies (Citizens Advice, StepChange, National Debtline, etc.); a CCJ stays on the register for six years unless paid within one month.

**(b) Business-to-business (limited companies): Practice Direction – Pre-Action Conduct and Protocols** [FETCHED: justice.gov.uk/courts/procedure-rules/civil/rules/pd_pre-action_conduct]
- **para 6(a)**: claimant writes to defendant with **concise details of the claim**: the **basis** of the claim, a **summary of the facts**, **what the claimant wants** and, if money, **how the amount is calculated**.
- **para 6(b)**: defendant responds within a reasonable time, **14 days in a straightforward case and no more than 3 months in a very complex one**, stating whether the claim is accepted and, if not, why.
- **para 6(c)**: parties disclose key documents.
- **para 8**: litigation as a last resort; consider ADR. **para 13-16** (not read): sanctions for non-compliance. **para 4**: protocols must not be used tactically.
- So a B2B Letter Before Action should: state the invoice(s), dates and amounts; the contractual or statutory basis (LPCDA); the interest calculation (rate, start date, per-diem); the fixed sum; the total; a **14-day deadline**; how to pay; a statement that proceedings may follow (a factual statement, see D6); and an offer of ADR/discussion.

**(c) Template LBA fields to render** (satisfies both): date at top; creditor and debtor names and addresses; invoice number(s), invoice date(s), goods/services; the amount due; interest (rate %, start date, daily rate, accrued to date, whether continuing); fixed sum under s.5A; total; payment method and bank details; response deadline (14 days B2B / 30 days individual+Reply Form); the Information Sheet + Reply Form + Financial Statement (individuals/sole traders only); right to request the contract; contact for payment plan; statement about ADR. Post by first-class mail on the date shown; email copy is optional.

### D6. Administration of Justice Act 1970 s.40: hard limits on a chaser [FETCHED, legislation.gov.uk, "up to date with all changes known to be in force on or before 05 October 2026"]

Verbatim s.40(1): A person commits an offence if, **with the object of coercing another person to pay money claimed from the other as a debt due under a contract**, he:
- **(a)** harasses the other with demands for payment which, "in respect of their **frequency** or the **manner or occasion** of making any such demand, or of any **threat or publicity** by which any demand is accompanied, are calculated to subject him or members of his **family or household** to **alarm, distress or humiliation**";
- **(b)** **falsely represents**, in relation to the money claimed, that **criminal proceedings lie** for failure to pay it;
- **(c)** **falsely represents himself to be authorised in some official capacity** to claim or enforce payment; or
- **(d)** utters a document **falsely represented** by him to have **some official character** or purporting to have some official character which he knows it has not.

Other subsections: **(2)** liable if he concerts with others (a campaign by several). **(3)** (a) does not apply to anything **reasonable** (and otherwise lawful) to secure discharge of a debt owed to himself or those he acts for, or to protect from future loss, or to enforce liability by legal process. **(3A)** (inserted 2008, substituted 6 Apr 2025) the subsection (1) offence does **not** apply to a "commercial practice" within Chapter 1 of Part 4 of the **Digital Markets, Competition and Consumers Act 2024** where the other is a **consumer**. That means consumer-facing aggressive practices are policed under the DMCC Act (unfair commercial practices, which includes harassment and coercion) instead. **(4)** penalty on summary conviction: a fine up to **level 5 on the standard scale** (unlimited fine for offences after 13 March 2015 [TRAINING]).

What this means as agent behaviour rules (my reading; not legal advice):
1. **Never** say or imply **criminal** proceedings, prosecution, arrest or "police" for non-payment of a contractual debt. Civil debt is not a crime. (s.40(1)(b))
2. **Never claim to be a bailiff, court, enforcement agent, solicitor, or any official body**. Identify as the creditor's own collections assistant. Don't claim the "agent" has legal authority it does not. (s.40(1)(c)) Also an AI disclosure: identify as automated assistant [TRAINING: good practice, and matches the DMCC 2024 / transparency expectations].
3. **No official-looking documents**: no court-style headers, no "County Court" crests, no "FINAL NOTICE OF SUMMONS", no fake claim forms or "Enforcement Notice". A letter is a letter from the creditor. A genuine **Letter Before Action is allowed** and should say it is a letter before claim, not a court document. (s.40(1)(d))
4. **Cadence/frequency (s.40(1)(a))**: the Act gives **no numeric limit**. "Harassment" turns on frequency, manner, occasion, threats, publicity, and alarm/distress/humiliation. Encode conservatively. **A suggested policy, not law**: max 1 contact per channel per 3-7 days; no more than 2 contacts in any 7 days across channels; only 08:00-20:00 UK time Mon-Sat (nothing on Sundays/bank holidays) [TRAINING; common industry guidance: FCA CONC 7 requires "reasonable" frequency but is for regulated consumer debt; the Debt PAP and the "Credit Services Association" code are the usual references]; an escalation ladder (friendly -> firm -> formal LBA) spaced by the statutory/protocol waiting periods; **stop immediately on dispute, "STOP", a request to cease contact, or a debt-advice notice**.
5. **No publicity or third-party disclosure**: never message a debtor's family, employer or colleagues, never name the debtor on social media or in group chats (`threat or publicity`, and "family or household"). Only message the number/email the debtor gave you.
6. **Statement of what can happen must be truthful**: "we may issue a county court claim and add interest and costs" is a **true, conditional** statement for a civil debt. Don't state a claim "has been issued", "will be issued tomorrow", that a CCJ "will" be registered, or that they "will go to prison", unless true.
7. Reasonable steps (s.40(3)) are a defence: sending a polite reminder, a statement of account and a proper LBA to recover a genuine debt is plainly lawful. The risk is tone and volume.
8. Other regimes to mention but not verified today [TRAINING]: UK GDPR/Data Protection Act 2018 (lawful basis, transparency, deletion on WhatsApp `deleted` events, subject access); PECR is about direct marketing, and a reminder about an existing debt is a service message rather than marketing, but keep the template category **utility**; Meta/WhatsApp Business Messaging Policy requires **opt-in** before business-initiated templates and honouring opt-outs (AWS doc line fetched in A4: "your user must opt in to receive messages from you"); Equality Act / vulnerable-customer care (FCA for regulated). If the creditor is itself FCA-regulated or the debt is consumer credit, FCA CONC 7 governs; out of scope for B2B invoices.

### D7. Opt-out and dispute handling (derived from D5/D6 and the WhatsApp rule)
Treat any of "stop", "unsubscribe", "don't contact me", "it's disputed", "I've paid" (flag: verify), "I'm seeking debt advice" as a **hard stop**: no further automated chasing until a human clears it. The Debt PAP para 4.2 requires waiting for advice; para 5 requires disclosing documents on dispute; para 4.4 requires written reasons when rejecting a payment plan.

### D8. UK payment practices dataset [FETCHED]

Landing: `https://check-payment-practices.service.gov.uk/` (the service "Payment practices reporting", GOV.UK).
- **CSV export URL confirmed**: `https://check-payment-practices.service.gov.uk/export/csv/` -> HTTP 200, `content-type: text/csv`, **no auth, GET only** (HEAD returns 405, so use GET). Size today: **103,061,154 bytes (~103 MB), 355,495 lines (multi-line text fields), 115,384 reports, 10,264 distinct companies**, latest filing date in file **2026-10-07**. Download takes seconds. Cache it locally (S3/Lambda layer); do not hit it per request.
- **51 columns.** The ones that matter: `Report Id`, `Policy Regime`, `Start date`, `End date`, `Filing date`, `Company`, **`Company number`** (8 chars, zero padded, matches Companies House, e.g. `01070807`), **`Average time to pay`** (days, integer as text), `Total value invoices paid within 30 days`, `... between 31 and 60 days`, `... later than 60 days` (values), **`% Invoices paid within 30 days`**, **`% Invoices paid between 31 and 60 days`**, **`% Invoices paid later than 60 days`**, `Total value invoices paid later than agreed terms`, **`% Invoices not paid within agreed terms`**, `% Invoices not paid due to dispute`, `Shortest (or only) standard payment period`, `Longest standard payment period`, `Standard payment terms`, `Maximum contractual payment period`, `Dispute resolution process`, `Participates in payment codes`, `E-Invoicing offered`, `Supply-chain financing offered`, and **`URL`** (e.g. `https://check-payment-practices.service.gov.uk/report/2`). Retention-clause columns are for construction.
- Report period is six months (e.g. 2017-04-29 to 2017-10-28). One company has many rows over time, so **take the row with the latest `Filing date`** per company number.
- The data is **self-reported** (the report page says "This information is as reported by the business").
- Data quality [measured today on the latest report per company]: 1,198 of 10,264 have a blank `Average time to pay`; there is at least one absurd value (max 4,323,394 days), so clamp/ignore values above a sane bound (say > 365); median 32 days, p90 59 days; 1,999 companies report >=20% of invoices paid 61+ days later; the latest filing per company ranges from 2017-11-22 to 2026-10-07, so **old filings are stale** (show the filing date). Companies below the reporting thresholds (only large companies: [TRAINING] turnover > £36m and balance sheet > £18m and > 250 employees, two of three) are **not in the data at all**; absence does not mean good payer.
- **Lookup of a given company**: (1) Offline, preferred: load the CSV, index by `Company number`, keep the latest `Filing date`. Companies House number is the join key. (2) Web: the search form at `https://check-payment-practices.service.gov.uk/search/` takes "business name or company number" but is a **POST with a CSRF token** (a plain GET with `?q=` or `?query=` just re-renders the empty form, tested), so it is not scriptable simply. Individual reports can be fetched by GET at `/report/<Report Id>/` (200, HTML) using the `URL` column. There is **no `/company/<number>` route (404) and no JSON API** (`/api/v1/` 404).
- Suggested use in the product: a "payer risk" score for the debtor company: `avg_days_to_pay`, `%_paid_61+`, `%_not_within_terms`, and their stated standard terms, shown with the report URL and filing date. If their standard terms are 60+ days, use it for the "grossly unfair" analysis in D3.

Example lookup:
```python
import csv, io, requests
r = requests.get("https://check-payment-practices.service.gov.uk/export/csv/", timeout=120)
latest = {}
for row in csv.DictReader(io.StringIO(r.text)):
    k = row["Company number"]
    if k not in latest or row["Filing date"] > latest[k]["Filing date"]:
        latest[k] = row
rec = latest.get("01070807")        # keep 8-char zero-padded string, not int
print(rec["Company"], rec["Average time to pay"], rec["% Invoices paid later than 60 days"], rec["Filing date"], rec["URL"])
# Returns that company's most recent filing. (The earliest MEDTRONIC row, report 2 from 2017, shows avg 25 days and 3% paid 61+ days.)
```
(`requests` was not exercised against the live URL in this script; I used `curl` for the download and Python's `csv` for the parsing and measured the numbers above from that file.)

---

## E. Open items / unverified list (read before building)

1. **No live WhatsApp send or SES send was made.** Shapes are validated against the service models; first real send is untested. Do a smoke send to your own number (must be inside a window, i.e. message the business number first, or use an approved template).
2. **WhatsApp template**: needs creating and approval in Meta/WhatsApp Manager; not possible via `socialmessaging` (no create-template op in the CLI listing). Without an approved template you can only reply inside a 24h window opened by the debtor. For a demo, have the "debtor" (your phone) message the business first. This is the biggest schedule risk for tonight.
3. **Ghana number as sender**: the only linked phone is `+233 55 906 2312`. UK recipients can receive from a Ghana-registered WhatsApp business number, but the display looks foreign. Not a technical block [TRAINING].
4. **Opt-in**: Meta policy requires opt-in before business-initiated template messages [AWS doc line, fetched]. The demo should include an explicit opt-in capture step.
5. **SES**: sandbox, and `brownshift.com` is FAILED. Use verified `kasamafo.africa` as sender (already SUCCESS in us-east-1) and verify recipient addresses. (Note: those identities are visible in account 854924711083 us-east-1 even though my notes say Kasamafo has its own account 747452892491; I read what is there, I did not investigate why.)
6. `conversation.expiration_timestamp` may be absent under per-message pricing; compute the window yourself (A4).
7. Media inbound sizes/types (A3) and WhatsApp document message shape (A1) are [TRAINING].
8. Legal: statutory text and the Protocol were read from official sources today, but the **interpretation and the suggested contact-cadence policy are mine**, not legal advice. Items I could not verify: whether VAT counts toward the fixed-sum tier; s.4(7A) "grossly unfair" definition; any 2025-26 reform of the payment-terms cap; the PD-PAC paras 13-16 sanctions; exact FCA position if the creditor is regulated; GDPR specifics.
9. Bank Rate next change: check the BoE MPC calendar before 31 Dec 2026; the 31 Dec 2026 reference value will set the rate for interest starting 1 Jan - 30 Jun 2027.

## F. Source index (all fetched 2026-10-08 unless marked)
- AWS: `aws socialmessaging|sesv2|bedrock-runtime ... help` (aws-cli 2.27.1); botocore models in boto3 1.43.95; docs.aws.amazon.com/social-messaging/latest/userguide/{send-message,send-message-text,send-message-media,receive-message,receive-message-image,managing-event-destinations,managing-event-destination-dlrs,managing-event-destinations-status,example-response,send-message-transient-errors}.html; docs.aws.amazon.com/ses/latest/dg/request-production-access.html
- BoE: bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp (IUDBEDR); bankofengland.co.uk/monetary-policy/the-interest-rate-bank-rate
- GOV.UK: gov.uk/late-commercial-payments-interest-debt-recovery/{charging-interest-commercial-debt,claim-debt-recovery-costs}
- legislation.gov.uk: ukpga/1998/20/section/{1,2,3,4,5A,6,7,8,9}; uksi/2002/1675/made; ukpga/1970/31/section/40
- justice.gov.uk: /documents/debt-pap.pdf (Pre-Action Protocol for Debt Claims); /courts/procedure-rules/civil/rules/pd_pre-action_conduct
- check-payment-practices.service.gov.uk: /export/csv/, /report/2/, /search/
- Local test scripts: scratchpad `work/validate.py`, `work/smoke.py`, `work/interest.py`
