# Arrearo — Devpost submission checklist

What the hackathon requires, and where each item stands. Done means it is in the repo or live on AWS. Pending means it is an external step the owner does.

## In the repo / live (done)

- [x] New project built inside the submission window, committed incrementally. Many small commits.
- [x] AWS SDK clients imported and called at runtime: WhatsApp (send text/interactive/documents, fetch and upload media), SES, Bedrock. See the table in `DEVPOST.md`.
- [x] At least one accepted CDS client: `socialmessaging` (WhatsApp) and `sesv2` (SES), both called by the Lambdas.
- [x] MIT licence file in the repo: `arrearo/LICENSE`.
- [x] Architecture diagram: `submission/architecture.png`.
- [x] README carries the AI disclosure (note: README still needs a refresh for the WhatsApp app before filming).
- [x] Live app on AWS: WhatsApp app + web dashboard, both reachable.
- [x] Full WhatsApp app: OTP login, menu, natural-language control, edit parity, designed PDF documents. 130+ tests, incl. a full-surface audit.
- [x] SES sender verified: `brownshift.com` (domain + DKIM) in account 854924711083; login codes send from `billing@brownshift.com`.
- [x] Demo script: `docs/DEMO.md` (needs a short addendum for the WhatsApp app flow).
- [ ] Submission images / thumbnails: `submission/images/` (being generated).

## External steps the owner does (pending)

- [ ] **Public GitHub repo.** Push `arrearo/` to its own public repo, MIT visible in About. Use the account tied to this entry (handle `jo2980958`). If private, share with testing@devpost.com and aws-cds-partner@amazon.com.
- [ ] **Demo video, ~3 minutes, public on YouTube or Vimeo.** Show the WhatsApp app: log in, navigate, a live chase, an invoice PDF delivered. Put the URL in `DEVPOST.md` and the README.
- [ ] **Net-new ACE opportunity** in Partner Central, created after 14 Sep 2026, tagged exactly `AWS CDS Agentic AI Hackathon -Sept. 2026`. Record the O-prefixed id in `DEVPOST.md`.
- [ ] **Entrant email** on the submission: `devpost-demo@brownshift.com` (corporate address on the APN domain).
- [ ] **Paste the Devpost form** from `DEVPOST.md` with the three links filled.

## Before filming

- [ ] Refresh `README.md` for the WhatsApp app + the `brownshift.com` sender.
- [ ] Confirm `arrearo-webhook` is `SEND_MODE=live` (every redeploy resets it to dry).
- [ ] Have the login code inbox (`devpost-demo@brownshift.com`) open on screen for the demo.

## Judging weights (for reference)

Technical Execution 40, Value/Impact 20, Demo 20, Creativity 10, Functionality 10. Separate $10,000 Meta prize for the best WhatsApp submission.
