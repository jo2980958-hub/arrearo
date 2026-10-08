"""Central configuration. Every service reads from here.

APP_SLUG is the internal, stable identifier (table prefix, resource names) and
never changes. BRAND is the display name shown to users and may be finalised
from market research without touching any internal names.
"""
import os

# ── identity ────────────────────────────────────────────────────────────────
APP_SLUG = "arrearo"                # internal, STABLE — do not change
BRAND = os.environ.get("BRAND", "Arrearo")  # display name
DOMAIN = "arrearo.com"
TAGLINE = "The credit controller that chases your late invoices on WhatsApp and adds the interest you're legally owed."

# ── AWS ─────────────────────────────────────────────────────────────────────
REGION = os.environ.get("AWS_REGION", "us-east-1")
ACCOUNT_ID = "854924711083"         # Brownshift

# Bedrock — inference-profile IDs (direct model IDs are rejected; use us.*)
BEDROCK_REASONING_MODEL = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
BEDROCK_EXTRACT_MODEL = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

# WhatsApp (AWS End User Messaging Social) — Brownshift WABA, us-east-1
WABA_ID = "waba-fc7e800db8f4433ab28a07f47089a226"
ORIGINATION_PHONE_NUMBER_ID = "phone-number-id-0d66a9b3b8fc463bb9bf999932643060"
WHATSAPP_SNS_TOPIC_ARN = "arn:aws:sns:us-east-1:854924711083:brownshift-whatsapp-events"
WHATSAPP_SENDER_DISPLAY = "+233 55 906 2312"

# Cognito user pool (web dashboard identity; the WhatsApp OTP login resolves to it)
COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID", "us-east-1_msvFwkml2")

# SES — sender identity (arrearo.com once its DKIM verifies). Overridable by env.
# arrearo.com couldn't be registered (account hold); the verified sender in this
# account is kasamafo.africa (DKIM SUCCESS). Live send: SendMode=live + verified recipient.
SES_SENDER = os.environ.get("SES_SENDER", "billing@kasamafo.africa")

# ── DynamoDB tables (prefix is APP_SLUG, stable) ────────────────────────────
TBL_BUSINESSES = f"{APP_SLUG}-businesses"
TBL_INVOICES = f"{APP_SLUG}-invoices"
TBL_DEBTORS = f"{APP_SLUG}-debtors"
TBL_CONVERSATIONS = f"{APP_SLUG}-conversations"
TBL_EVENTS = f"{APP_SLUG}-events"
TBL_WA_SESSIONS = f"{APP_SLUG}-wa-sessions"   # WhatsApp login/link + navigation state

# ── money ───────────────────────────────────────────────────────────────────
CURRENCY = "GBP"


def gbp(pence: int) -> str:
    """Render integer pence as a £ string."""
    sign = "-" if pence < 0 else ""
    p = abs(int(pence))
    return f"{sign}£{p // 100:,}.{p % 100:02d}"
