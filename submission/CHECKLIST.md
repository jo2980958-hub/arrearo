# Arrearo — Devpost submission checklist

What the hackathon requires, and where each item stands. Done means it is in the repo or live on AWS. Pending means it is an external step the owner does (push, upload, Partner Central), not code.

## In the repo / live (done)

- [x] New project built inside the submission window, committed incrementally (not one dump). 21+ commits on `master`.
- [x] AWS SDK client imported and called at runtime. See the CDS table in `DEVPOST.md` and the README.
- [x] At least one accepted CDS client: `socialmessaging` (WhatsApp) and `sesv2` (SES). Both called by the Lambdas.
- [x] MIT licence file in the repo: `arrearo/LICENSE`.
- [x] Architecture diagram: `submission/architecture.png` (also `docs/architecture.png`).
- [x] README carries the hackathon AI disclosure.
- [x] Live app reachable: dashboard + API on AWS, demo login works.
- [x] Demo script written: `docs/DEMO.md` (the ~3 min walkthrough).

## External steps the owner does (pending)

- [ ] **Public GitHub repo.** Push `arrearo/` to its own public repo, licence visible in the About panel. (If kept private instead, share with testing@devpost.com and aws-cds-partner@amazon.com.) Use the GitHub account tied to this entry, per the one-repo-per-project rule.
- [ ] **Demo video, about 3 minutes, public on YouTube or Vimeo.** Film the `docs/DEMO.md` walkthrough on the live app. Put the URL in `DEVPOST.md` and the repo README.
- [ ] **Net-new ACE opportunity** in Partner Central, created after 14 Sep 2026, tagged with the exact campaign string `AWS CDS Agentic AI Hackathon -Sept. 2026` (note the space before "Sept." and the trailing full stop). Record the O-prefixed id in `DEVPOST.md`.
- [ ] **Corporate email on the domain tied to this submission's APN registration**, used for the Devpost entrant registration.
- [ ] **Paste the Devpost form** from `DEVPOST.md`, with the three links filled in.
- [ ] **Screenshots** in `submission/screenshots/` (optional but helps the Devpost gallery).

## Optional polish before filming

- [ ] Flip `SendMode=live` and verify a recipient so a real WhatsApp chase and a real SES email can be shown on camera. Open the 24h window first by messaging the number. See the README Known limitations.
- [ ] Rename the default branch `master` to `main` if you want it to match GitHub's default.

## Judging weights (for reference)

Technical Execution 40, Value/Impact 20, Demo 20, Creativity 10, Functionality 10. Separate $10,000 Meta prize for the best WhatsApp submission.
