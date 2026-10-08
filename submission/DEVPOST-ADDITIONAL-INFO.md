# Arrearo — Devpost "Additional info" (for judges and organizers)

Paste-ready answers for the judge/organizer-only section. Items marked PENDING need an action from you first.

**AWS Partner Company Name**
Brownshift Technologies

**AWS Partner Headquarter Country**
Ghana

**Which CDS service(s) does your solution use?** (RCS / WhatsApp / SMS / SES)
Select: **WhatsApp** and **SES**.
(Not RCS, not SMS. The runtime CDS calls are AWS End User Messaging Social for WhatsApp and Amazon SES v2 for email.)

**Did you use AWS End User Messaging Social (WhatsApp) as the sole CDS service or one of multiple?**
**One of multiple AWS CDS services** (WhatsApp + SES).

**Describe how AWS End User Messaging Social (EUM - WhatsApp) was used.**
Arrearo runs as a full app inside WhatsApp, and End User Messaging Social is the channel for all of it. Inbound messages reach an SNS topic that triggers our webhook Lambda, which fetches invoice photos and PDFs with GetWhatsAppMessageMedia. Outbound, the Lambdas call SendWhatsAppMessage for text, for interactive buttons and list menus, and for documents; when the agent sends a designed invoice, statement or letter as a PDF, it uploads the file with PostWhatsAppMessageMedia and sends it as a WhatsApp document. The whole product works over this one channel: a one-time-code login that links a WhatsApp number to the business account, a menu and natural-language navigation, the chases that cite the statutory interest, and the PDF documents. Every one of these calls is made at runtime by the deployed Lambdas (see services/layer/python/common/cds.py), not by a script. SES is the second CDS service, used for the login codes, email chases and the Letter Before Action PDF.

**Code Repository Access**
PENDING. Push `arrearo/` to a public GitHub repo (account handle jo2980958) with the MIT LICENSE file visible in the About panel, then paste the URL. If kept private instead, share it with testing@devpost.com and aws-cds-partner@amazon.com. The repo shows the CDS SDK imported and called at runtime in `services/layer/python/common/cds.py` and the three Lambdas under `services/functions/`.

**Architecture Diagram**
Upload `arrearo/submission/architecture.png` (also at `arrearo/docs/architecture.png`).

**ACE Opportunity ID**
PENDING. Create a net-new opportunity in AWS Partner Central ACE, sourced from marketing activity with the campaign `AWS CDS Agentic AI Hackathon -Sept. 2026` (exact string, note the space before "Sept." and the trailing full stop). Paste the alphanumeric Opportunity ID (an O followed by 8 characters).

**Country of residence (individual/team)**
Ghana.

**Entrant / corporate email (for registration)**
devpost-demo@brownshift.com (a Brownshift domain address, on the APN-registered domain).

**Confirmations**
- Age of majority (Section 3): confirm — yes.
- No conflict of interest (Section 3): confirm — yes (no involvement in running the hackathon, not employing a judge, no immediate family or household member at AWS or Devpost). Only tick this if it is true for you and any teammates.

---

## Still to do before you can submit this entry
1. Push the public GitHub repo (MIT visible in About) and paste its URL.
2. Create the ACE opportunity with the exact campaign tag and paste the Opportunity ID.
3. Upload `submission/architecture.png`.
4. Fill the main project fields from `submission/DEVPOST.md`, and the ~3-minute YouTube demo link.
