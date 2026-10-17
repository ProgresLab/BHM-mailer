# BHM Mailer

Local FastAPI application for BHM Chemicals mailing workflows: contact import, contact editing, single-language campaign creation, HTML/plain-text preview, recipient selection, dry-run or SMTP sending, unsubscribe handling, campaign history, CSV export, and Message Trace CSV import.

Source repository: <https://github.com/ProgresLab/BHM-mailer>.

Git tracks application source, documentation, branding assets, and the non-secret `.env.example` configuration template. Local `.env` files, databases, contact imports, backups, logs, and virtual environments are excluded. Publishing source to GitHub does not deploy the application.

## Setup and Run

Offline campaign41 closure (`BHM-CLOSE41-OFFLINE-2026-10-17`): **DONE within the final offline scope**. Campaign/execution completed_with_errors;713 historical SMTP acceptances preserved (223 now bounced_later),287 unattempted rows cancelled without sent_at/accepted_at or contact last-send changes. All287 remain active/eligible for explicit future selection;resume rejected and reservation released. Full-history Gmail scan:1153 complete MIME messages,24 search pages,12 new invalid+5 unsubscribed,21 later-bounce projections,32 evidence audits;956 duplicates skipped and162 unresolved reports retained privately. Consistent DB/2-assets backup,exact copy simulation,independent per-recipient readback and Gmail/closure no-op replay passed.119 isolated tests,14 recipient browser scenarios,8 sync/sort browser checks and compileall passed. No real SMTP,new campaign,Gmail changes or migration. Operator8000 and QA ports are free. User explicitly declined startup/recovery;ready for manual start-bhm-operational.bat,whose current copy preflight requires updated+one recovery event each for17/18/28. [Report](docs/campaign41-offline-2026-10-17.md). Earlier runtime paragraphs are historical.

Permanent closure and activation (`BHM-CLOSE-ACTIVATE-2026-10-17`): **DONE; actual127.0.0.1:8000 PID21732, IMAP ON / SMTP ON**. Campaign40 is completed_with_errors:661 historical SMTP acceptances (199 later bounces),312 cancelled without send timestamps,0 pending/unknown. Reservation released; resume rejected. Fresh199-message Gmail scan across accepted-attempt campaigns36/37/38/40:0 new invalid/0 unsubscribe,197 duplicates,1 new unmatched review; previous4/3 changes preserved. Verified DB/assets backups, exact copied closure/replay and independent readback.119 tests,1000-contact autonomous SMTP simulation (1000 accepted/1006 fake calls/0 manual resumes),8 synthetic browser checks and actual8000 desktop/mobile GET-only acceptance passed. Applied only authorized recovery updated/events for17/18/28; no40 recovery, no real SMTP attempt/new campaign/resume. New campaign editor and empty selection ready; QA stopped. [Full report](docs/close-activate-2026-10-17.md). All older runtime paragraphs below are historical.

Controlled iteration (`BHM-CONTROLLED-2026-10-17`): Gmail reconciliation APPLIED and independent readback PASS. Campaign40:973 snapshots,661 historical SMTP acceptances (199 later bounces),312 identical pending,0 unknown/inflight,manual pause preserved.290 Gmail messages/286 DSN:4 new invalid+3 unsubscribed,7 later-bounce updates,10 audits;277 prior evidence duplicates skipped. SQLite/assets backup and replay no-op verified. SMTP transient/backoff/R6/uncertainty and IMAP bounded fetch/re-analysis implemented;115 isolated tests and browser acceptance passed. Port8000 stopped after identifying prior PID25844; startup still requires exact recovery approval for17/18/28/40. No real send/resume/new campaign/deploy. [Evidence, counts and activation boundary](docs/controlled-iteration-2026-10-17.md). All older runtime paragraphs below are historical.

Current operator status (2026-10-16 23:33 CEST): **IMAP ON + SMTP ON**, <http://127.0.0.1:8000>, PID25844. Controlled activation and exact recovery approval completed; all old queues remain paused and no mail was sent. Use **`start-bhm-operational.bat`** after a future shutdown; do not launch another instance while8000 responds. New campaign preparation and its real-send confirmation are separate manual actions. [Activation and preservation evidence](docs/operational-preparation-2026-10-16.md). Older runtime paragraphs below are historical.

For normal operation on Windows (IMAP ON + SMTP ON, separate campaign confirmation):

```powershell
.\start-bhm-operational.bat
```

Use `start-imap-safe.bat` for IMAP ON / SMTP forced OFF. Both explicit launchers reuse existing dependencies and configuration, pin the canonical database/assets, and bind 8000 before loading the app. Keep the server running; closing the browser is safe, sleep/shutdown interrupts work. Neither launcher starts or resumes a campaign.

**Legacy `start.bat` is a setup helper, not the operator launcher.** It installs dependencies and uses `.env` SMTP behavior; its original Uvicorn command can import the application before detecting a busy port. Do not run it alongside an existing instance or use it to switch operational modes. It is retained for compatibility. The explicit launchers above do not edit `.env` or install packages.

Before operational activation take a fresh consistent SQLite/assets backup with `tools/mail_sync_preflight.py` and inspect the copied startup delta. The operational launcher refuses incomplete identity/signature/IMAP configuration, busy or uncertain work, account reservation/cooldown, missing assets and any unsent admin notification (including legacy pending records). Notifications are preserved for an operator decision, not sent as part of activation. It also refuses unexpected migration/recovery. For already interrupted, manually paused queues, existing recovery changes only `updated` and appends one audit event each; an interactive exact `RECOVERY 17,18,28` acknowledgement is required for the current three queues. Headless use requires separately granted approval, passed as `--approve-recovery-for 17 18 28`. This never approves campaign delivery. If the predicted scope differs, stop and review it again.

The operational process forces SSL transport (`SMTP_USE_SSL=true`, `SMTP_USE_TLS=false`) and validates the existing one.com host465/account/From/Reply-To/envelope sender and HTTPS signed unsubscribe configuration. Credentials and `.env` remain untouched. TLS/AUTH/NOOP alone does not prove delivery or absence of a recipient-stage provider restriction. [Preparation and current activation status](docs/operational-preparation-2026-10-16.md).

Manual run:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
.\start-imap-safe.bat
```

Open: <http://127.0.0.1:8000>

## Build and Test

No build step is required. Install test dependencies and run the isolated suite (synthetic SQLite and fake SMTP; never the operational database):

```powershell
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m unittest discover -s tests -v
```

Useful syntax check:

```powershell
python -m compileall app
```

## Configuration

Configuration is loaded from `.env`. Do not commit real secrets.

Key variables from `.env.example`:

- `SMTP_ENABLED`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_FROM_NAME`
- `SMTP_FROM_EMAIL`
- `SMTP_REPLY_TO`
- `SMTP_ENVELOPE_FROM`
- `SMTP_USE_SSL`
- `SMTP_USE_TLS`
- `PUBLIC_UNSUBSCRIBE_BASE_URL`
- `ADMIN_NOTIFICATION_EMAIL`
- `EMAIL_SEND_DELAY_SECONDS`
- `UNSUBSCRIBE_SECRET`

The existing default SMTP direction is one.com campaign SMTP with `send.one.com`, port `465`, SSL, and `marketing@bhm-chemicals.com` as the technical sender. Real sending requires complete SMTP configuration and `SMTP_ENABLED=true`.

`SMTP_PASSWORD` and `UNSUBSCRIBE_SECRET` must stay local in `.env`.

## Data

SQLite is created automatically at:

```text
data/bhm_mailer.sqlite3
```

The database stores contacts, campaigns, send snapshots/statuses, and unsubscribe events. Uploads are stored in `uploads/`. Treat both folders as private operational data.

## Main Workflows

Email layout (`BHM-EMAIL-LAYOUT-2026-10-16`): newly rendered HTML uses a fluid **720 px** card/banner/MSO wrapper, a full-width navy CTA with **24 px** table-based spacing below it, and **8 px** outer corners (square fallback in clients ignoring radius). Existing saved HTML and sent snapshots are not regenerated. Desktop/mobile synthetic QA and limitations: [layout acceptance](docs/email-layout-qa-2026-10-16.md). Native Outlook rendering and operational activation remain unverified for this delta.

- Import contacts from paste input or XLSX.
- Normalize and deduplicate emails.
- Manage contact statuses: `active`, `unsubscribed`, `bounced`, `invalid`.
- Create/edit campaign drafts in `pl` or `en` with separate internal name, Subject and headline.
- Use controlled rich text (bold/italic/underline, headings, five sizes, lists/checkmarks, links, paste and undo/redo). Pasted content is sanitized on the server; arbitrary HTML/styles are removed.
- Upload campaign JPG/PNG banners: recommended 1200×400, 3:1, preferably under 300 KB; hard upload cap 5 MB, accepted dimensions 600×200 to 6000×2000. Images are resized without cropping, metadata removed, privately stored and embedded via CID.
- Approve content before selecting recipients; approval locks content. Reopen to draft only before any snapshot exists.
- Preview table-based HTML intended for popular clients including Outlook and plain-text fallback.
- Select recipients with filters and 500/page. Checkboxes are temporary: click **Dodaj do kampanii** to add them cumulatively to the existing SQLite selection (maximum 1000, enforced in one transaction). Added rows are labelled and locked against duplicate selection. Change filters/pages, then add more. **Przejdź do podsumowania** opens the stored recipient list, metadata and ETA; remove individual recipients there. Clearing the campaign's entire stored list requires confirmation. Active status is rechecked at confirmation and before each attempt; SMTP start remains a separate explicit action.
- Confirmation defaults to dry-run, even when SMTP is enabled. Real SMTP requires explicit mode selection and acknowledgement.
- One worker starts attempts at least 20 seconds apart. After 1800 active seconds it pauses for 300 seconds, then resumes unless manually paused. There is no extra 20-second delay after a slow SMTP call.
- Manual pause stops new reservations; an in-flight attempt finishes or is recorded as uncertain. Resume preserves spacing/cooldowns and sends only remaining eligible rows.
- After process restart, delivery stays interrupted until operator review and explicit resume. Timeout/disconnect/crash during an attempt becomes `delivery_unknown` with an uncertainty flag; no automatic resend. Resolve using Trace or an audited operator decision in history. Requeue requires an explicit evidence-backed confirmation of non-acceptance.
- Safe definite SMTP 4xx triggers at least 15 minutes of automatic cooldown (maximum three automatic resumes per queue); policy/authentication/uncertain failures require an operator. Permanent recipient rejection is recorded and skipped; other SMTP problems pause the campaign.
- A changed SMTP identity blocks the queue. Legacy in-flight queues without the new identity fingerprint require a separate compatibility review before real resume.
- OS lock file prevents multiple workers for the same SQLite; SQLite reserves the account for one campaign, including manual pauses. Run a single uvicorn process, without reload during campaigns. Do not use separate databases to bypass the shared-account lock.
- After start, use the separate monitor (2.5-second polling); the full recipient/history list is available through a separate link. ETA is approximate and withheld during manual pause/problem/recovery.
- Review contact history and campaign attempt ledger; repeated temporary rejections retain earlier attempt outcomes. Dry-run records are simulations and never update actual send timestamps or `last_sent_at`.
- Export campaign status CSV.
- Import external Message Trace CSV to update delivery evidence.

## Send Status Notes

`accepted_by_smtp` means the SMTP provider accepted the message. It is not final delivery confirmation.

Trace-related statuses include:

- `delivered_by_trace`
- `failed_by_trace`
- `quarantined_by_trace`
- `delivery_pending`
- `delivery_unknown`

Skipped/error statuses include:

- `smtp_failed`
- `rate_limited`
- `bounced_later`
- `skipped_unsubscribed`
- `skipped_invalid`
- `skipped_duplicate`
- `cancelled`

## Unsubscribe Notes

The local app generates signed public unsubscribe URLs using `UNSUBSCRIBE_SECRET`. `PUBLIC_UNSUBSCRIBE_BASE_URL` should point to the public unsubscribe endpoint.

Existing project notes reference:

```text
https://unsubscribe.mail.bhm-chemicals.com/unsubscribe
```

TODO: Document the source/repo and deployment process for that public endpoint if it exists.

## Deployment

Detected deployment mode for this repo is local execution. No production deployment config for the FastAPI app was found.

The unsubscribe endpoint appears to be external and must use the same `UNSUBSCRIBE_SECRET` to verify signatures.

## Folder Structure

```text
app/
  main.py                 FastAPI routes and UI flow
  db.py                   SQLite setup and migrations
  mailer.py               SMTP, dry-run, send statuses, unsubscribe signing
  importer.py             Paste/XLSX import logic
  email_renderer.py       HTML/text email rendering
  models.py               Shared constants and normalization helpers
  templates/              Jinja templates
  static/                 CSS, JS, assets
data/                     Local SQLite data; private
docs/                     Project notes
uploads/                  Uploaded files; private
requirements.txt          Python dependencies
start.bat                 Windows local startup helper
```

## Maintenance Notes

- Read `AGENTS.md` and `PROJECT_BRIEF.md` before non-trivial changes.
- Work on source files, not `__pycache__`, `.venv`, local database files, or uploads.
- Keep SMTP and unsubscribe changes conservative.
- Do not run real campaigns or live SMTP tests without explicit approval.
- After changing `.env`, restart the server.
- For mailing changes, verify dry-run behavior and at least one edge case before real use.


## Gmail reconciliation (2026-10-16)

Campaign38 was reconciled after its queue completed:354 contacts invalid,10 unsubscribed,430 later bounces;original1000 SMTP acceptances and1004 attempts preserved. A consistent SQLite/assets backup, isolated simulation and independent readback passed. Port8000 was unavailable before this operation and remains stopped;older activation notes below are historical. No new SMTP send,restart,migration or deploy. [Results and limitations](docs/gmail-reconciliation-2026-10-16.md).

`app/reconciliation.py` deterministically parses Gmail connector MIME/RAW exports. `tools/reconcile_gmail.py` runs offline, uses the existing execution_events evidence ledger and never imports app.main or starts a worker. Gmail acquisition uses the existing authorized connector with all pages/in:anywhere, including a separate unsubscribe search for notifications sent to info@. Private exports, reports and backups must remain in ignored output/backups directories. No OAuth integration was added.

For a separately authorized follow-up, first obtain fresh complete connector exports, then run `prepare` with `--database`, `--campaign`, `--input` and a new private `--manifest` path. Inspect the backup/plan/simulation before using `apply` with the same arguments. The tool refuses a noncompleted or reserved queue,missing MIME,changed input/data/assets and conflicting statuses. Exact accepted Message-ID,recipient,time and authenticated source are required;unverified records stay in the private report. Unsubscribe additionally requires the notification identity,source,token,campaign and snapshot timestamp. Same evidence replay does not duplicate changes. SMTP acceptance is never final delivery proof.

## Controlled local activation and QA

Current recipient runtime diagnosis (2026-10-16): **8000 activation blocked pending approval**. PID 15184 still exposes only POST on `/campaigns/{campaign_id}/selection`; the current frontend's GET returns 405 (`Allow: POST`). Canonical source already implements the matching GET and passes QA. A restart must be separately authorized because startup updates `campaign_execution.updated` for 17/18/28 and appends three recovery events. No schema migration is needed. Keep SMTP explicitly OFF. See [confirmed runtime diagnosis and activation scope](docs/recipient-runtime-diagnosis-2026-10-16.md); earlier runtime acceptance below is historical.

Read-only checks: `.venv/Scripts/python tools/recipient_activation_preflight.py` runs init/recover only in an in-memory copy. `node tools/recipient_runtime_probe.cjs` uses the same Playwright environment as recipient QA, permits only GET/HEAD on 8000 and masks private content in its screenshot. These tools do not activate the application. The recipient browser QA additionally reads SQLite directly after Add/reload and 500+500.

Recipient workflow delta `BHM-RECIPIENTS-2026-10-15` is validated on **8018 only**. The existing port-8000 process (PID 15184, SMTP OFF) was not restarted and retains the previous Python routes. Templates/static assets are shared with source, so the new selection UI requires an `explicit_add_v1` API handshake and visibly blocks mutations against the old process. Do not treat changed templates as operational activation. Read-only in-memory startup preflight predicts three execution-metadata changes and three appended recovery events; a fresh backup and explicit authorization for those writes are required before a controlled restart. No operational migration is needed for this delta. See [recipient selection diagnosis and acceptance](docs/recipient-selection-fix-2026-10-15.md).

Run the isolated recipient sandbox with `.venv/Scripts/python tools/recipient_qa_server.py`, then open <http://127.0.0.1:8018/campaigns/32/recipients?search=marcin>. It has 1504 synthetic contacts, one approved QA campaign and SMTP forced OFF. Existing QA fixtures are reused. `tools/recipient_browser_qa.cjs` runs the actual checkbox → API → SQLite → summary regression; set `NODE_PATH` to the bundled Node package directory and, when needed, `PLAYWRIGHT_CHROMIUM_EXECUTABLE` to the installed Chromium executable. It only targets 8018, changes only this synthetic campaign's selection and leaves one `marcin@example.test` recipient. It never starts a queue. Evidence and screenshots are under `output/recipient-qa/` and `output/playwright/` (ignored by Git).

The original 2026-10-15 modernization closeout covered isolated synthetic data and left the existing port-8000 process running. A later HTTP-500 investigation found that operational `data/bhm_mailer.sqlite3` already contained the modernized schema. That investigation performed no migration, verified a consistent backup, and obtained explicit approval for startup recovery with SMTP forced off. The current application is running on **127.0.0.1:8000** with `SMTP_ENABLED=false` in its process environment; `/campaigns/new` returned 200 and passed desktop/mobile editor checks. Operational contacts, campaigns and message history match the backup; only the approved recovery timestamps and six new restart events changed. `.env` was not edited: the SMTP-OFF override applies to this running process, not a later ordinary `start.bat` launch. Current details and evidence: [HTTP-500 diagnosis](docs/http500-diagnosis-2026-10-15.md).

Safe preview (forces SMTP off and uses `output/qa/synthetic.sqlite3` and private QA assets):

```powershell
.\.venv\Scripts\python tools/qa_server.py
```

Open <http://127.0.0.1:8017>. QA fixtures are reused, never reset automatically. They contain 5676 synthetic contacts and clearly labelled test campaigns. Startup leaves the 1000-record dry-run queue interrupted; use its monitor to resume. All QA screenshots/runtime output are excluded from Git. Stop this QA server after review; its PID is recorded in `output/qa/server.pid`.

Before separately authorized operational activation: stop the old app, take a fresh SQLite backup using SQLite backup API, preserve all of `uploads/campaign_assets/` alongside the database, apply initialization to a copy first, compare preserved records/snapshots and run integrity/foreign-key checks. Then migrate the operational database only within the approved activation scope. Never copy test fixtures over operational data. Regular startup runs additive migrations, so it is part of that activation gate.

After updating Python source and templates, identify the actual process listening on the target port and restart it only after checking active sending and startup/database effects. A long-running non-reloading Python process can retain old route code while Jinja loads new templates from disk; `/campaigns/new` then fails with `UndefinedError: 'form' is undefined` despite the corrected source. Do not hide this version mismatch with template defaults. Verify `GET /campaigns/new` and the actual editor on **8000**, not only a QA preview on 8017. A green test suite does not reload an existing server. Normal worker startup also records recovery events, even for already interrupted queues; include those writes in the approved activation scope. Do not use reload or multiple workers during campaigns.

Private banners are immutable and are never automatically garbage-collected. Backups/restores must include the DB and its asset directory together. Optional process environment variables: `BHM_DB_PATH`, `BHM_ASSET_DIR`; leave unset for normal local paths. Never mount `uploads/` as static content.

The fixed 20-second pacing ignores legacy `EMAIL_SEND_DELAY_SECONDS` / `DRY_RUN_SKIP_DELAY` overrides. Rolling application safeguards allow up to 20 attempts/5 min and 200/hour (headroom below the documented one.com limits). They count app campaign attempts and admin notifications; mail sent by other programs is unknown and can still cause provider rejection. Admin unsubscribe notifications are queued, share the same worker and wait until campaign completion. A crashed/ambiguous admin notification is preserved as uncertain instead of retried automatically. The public unsubscribe URL/HMAC parameters and secret remain unchanged.

The browser can be closed while the local process continues. The application and computer must stay running. Sleep or shutdown can interrupt delivery; no automatic real send after restart. The local admin accepts only loopback/localhost hosts and rejects cross-site POSTs; it is not an authenticated public service.

The native editor uses browser `contenteditable`/`execCommand` for formatting and caret handling, plus a bounded undo/redo history that includes checklist attributes, with authoritative server sanitization. Validated in the Chromium in-app browser; native Word clipboard variations, other browsers and actual mail clients require additional acceptance. Table HTML, inline CSS, CID and an MSO width wrapper are implemented, but **Outlook rendering has not been visually tested**.

Evidence and limitations: [modernization acceptance](docs/modernization-acceptance-2026-10-15.md). The single requirements register and one task Change Log entry are in `PROJECT_BRIEF.md`.


## IMAP sync, SMTP cooldown and recipient sorting (2026-10-16)

Current acceptance: source, isolated QA and approved operational activation complete; IMAP ON / SMTP forced OFF at localhost8000. Port8000 was stopped at task entry and was started once after backup/copy preflight. See [acceptance and activation boundary](docs/imap-sync-acceptance-2026-10-16.md).

- The local application owns one SMTP worker and one independent OS-locked IMAP thread per database/mailbox. Both stop with the process. Closing a browser is safe; sleep/shutdown interrupts work and never authorizes real queue recovery.
- Fixed IMAP connection: `imap.one.com:993`, certificate-verified TLS, read-only `EXAMINE` and `UID FETCH BODY.PEEK`, 20-second network timeout. No mailbox flag changes, moving, deletion or send. UID windows are at most 1000, each message at most 1 MiB; batches stop after 200 messages or 60 seconds (plus the current bounded call). Backlog continues in short batches; completed scans repeat after 900 seconds. Oversized reports require review.
- Enable with process environment `IMAP_ENABLED=true`. `IMAP_USER` defaults to the campaign mailbox; `IMAP_FOLDER` defaults to `INBOX`. An optional local `IMAP_PASSWORD` overrides the password; otherwise `SMTP_PASSWORD` is reused only when the normalized usernames match. No `.env` change or secret publication is required. Default remains OFF for ordinary launches; the approved safe launcher below forces IMAP ON / SMTP OFF.
- Durable tables `mail_sync_state`, `mail_sync_messages` and `mail_evidence` store cursor, schedule, deduplication and audit. UIDVALIDITY changes replay the mailbox safely through the shared evidence key. Restart catches up by UID, without a message-date cutoff. Message bodies are not retained in these tables. An OS lock prevents a second app instance from running the same scan; manual requests are persisted and coalesced.
- Classification reuses `app/reconciliation.py`. IMAP trusts only the inspected one.com storage/ingress receiver segment and its aligned DKIM verdict, plus exact historical accepted SMTP Message-ID, recipient and receipt time. Gmail's `mx.google.com` verdict is never substituted for IMAP proof. Changed/unknown routing fails closed to review. Previous Gmail evidence is deduplicated even when created before the new tables existed. `unsubscribed` always wins; accepted timestamps, snapshots and attempt ledgers remain intact.
- The dashboard/monitor shows last/next successful scan, totals, errors and a guarded **Sprawdź teraz** button. Error categories omit arbitrary provider text and secrets. Review evidence is private SQLite; it is not a contact status and never deletes contacts.
- Unsubscribe coverage is **incomplete**: a read-only search of both available marketing mailbox folders found no notifications from the established info notification identity. Existing authorized Gmail export + `tools/reconcile_gmail.py` remains the smallest supported supplementary source. It is a separate controlled import, not automatic background Gmail. No forwarding, second account, external endpoint or credentials were configured by assumption.
- Safe, explicit SMTP temporary negative replies enter durable `auto_cooldown` for at least 900 seconds, respecting a longer numeric provider retry interval. At most three automatic resumes are allowed for the whole queue (conservative across error kinds). R6 / 4.7.*, sender policy/reputation, account/auth failures, permanent refusals and uncertain transport outcomes require an operator. At least 50 distinct failures in the last hour (SMTP failures and verified later bounces) block the next attempt and auto-resume. No automatic real resume after restart. Manual pause, identity check, per-contact eligibility, rolling account limits and the singleton worker still apply.
- Recipient headers toggle global SQL sorting by email, company or last real SMTP acceptance before 500-row pagination. Last-send ASC puts never/oldest first; DESC puts newest first. Stable contact IDs break ties. Warsaw time and a history link identify the campaign. Dry-run is excluded, including older accepted records without the modern attempt ledger. Saved Add selections survive sorting/reload; unsaved checkboxes remain temporary. The campaign limit stays 1000.

Reproduce isolated acceptance with `.venv/Scripts/python -m unittest discover -s tests -v`, `.venv/Scripts/python tools/sync_qa_server.py` and `node tools/sync_browser_qa.cjs` (bundled Playwright packages/installed Chromium). Only synthetic 8019 is targeted. Stop the QA server after checking; keep private screenshots in ignored `output/sync-qa/`.

`tools/mail_sync_preflight.py` creates a consistent private SQLite/assets backup and runs init/recover only on a copy. `--scan` additionally reads the authorized mailbox into that copy; it never starts SMTP or initializes operational SQLite. Inspect its private manifest before operational activation, and take a fresh backup if live data has changed. Startup migration adds three execution columns, three IMAP tables and indexes. Current copy preflight also predicts three updated execution timestamps and three appended recovery events for interrupted queues 17/18/28. Those operational effects require explicit approval.


### Approved operation with IMAP ON / SMTP OFF

The following records the earlier IMAP-only activation. Current operational runtime is the IMAP+SMTP instance documented above; the safe-mode launcher remains available separately.

Operational activation completed after explicit user approval. Actual application: `http://127.0.0.1:8000`, PID18152, launched once at 2026-10-16 21:56:40 CEST. First completed IMAP sync: 2026-10-16 21:59:55 CEST; next scheduled scan: 2026-10-16 22:14:55 CEST. Initial2173 messages produced263 review cases and0 new contact-status changes. The three old queues17/18/28 remain manually paused; no SMTP/admin attempt was made. [Activation/readback evidence](docs/imap-activation-2026-10-16.md).

After a future computer restart, double-click **`start-imap-safe.bat`** in this project, or run:

```powershell
Set-Location 'C:\Users\info\AGENTS\BHM Mailer'
.\start-imap-safe.bat
```

Keep its server window open. This launcher uses the existing venv, binds only127.0.0.1:8000, forces `IMAP_ENABLED=true` and **`SMTP_ENABLED=false`**, and pins the canonical SQLite/assets paths. It reuses only the locally configured matching mailbox credential; `.env` is not edited. A second launch exits before loading the application or performing recovery if8000 is occupied. Dependencies must already be installed from `requirements.txt`; the launcher does not install anything or send email.

The current activation was started hidden using the same Python helper `tools/run_imap_safe.py`; the user need not launch it again while8000 is responding. Ordinary `start.bat` retains its existing `.env` behavior and does not provide this SMTP-OFF guarantee. Never use it as a replacement for the safe launcher in this approved mode.

There is no Windows startup task/service. After sleep/process interruption, restart recovery still requires review and explicit operator resume for real queues; opening the browser is not a send instruction. The app automatically catches up IMAP by persisted UID. Unsubscribe coverage remains incomplete; no info mailbox/forwarding/public endpoint was changed.

## Controlled reconciliation and queue continuity (2026-10-17)

Use the existing offline Gmail prepare/apply tool with `--paused-history` only for separately authorized imports while the app is stopped. It holds port8000 and SMTP/IMAP OS locks, validates a durably paused queue and historical accepted attempts, backs up SQLite/assets, simulates exact changes and requires unchanged data/input/assets at apply. It never modifies pending rows or starts workers; the ordinary completed-queue `ensure_idle` gate remains.

Safe SMTP4xx uses at least15 minutes, longer server waits and bounded retry/backoff. Permanent recipient errors continue other contacts; only invalid-address proof disables a contact. R6 waits at least1 hour for one probe per queue, then requires review if blocked. This is a local conservative policy, not a provider recovery guarantee. Unknown attempts never retry, including via a new campaign; three consecutive transport uncertainties stop the account. Accepted sends reset consecutive account cooldown counters. The50-failure quality warning uses receipt/attempt time, not import time, and never creates a resume loop.20s/1800s/300s and the singleton remain.

IMAP initially fetches up to1MiB; recognized reports may expand once to8MiB. Incomplete MIME does not advance UID. `tools/diagnose_imap.py --max-reviews 1000` explicitly re-analyses known review UIDs on a private copy with full MIME and matching UIDVALIDITY. It never writes operational SQLite. Shared deduplication and receiver trust remain mandatory; automatic info-mailbox unsubscribe coverage remains incomplete. Private reports under output/backups must never enter Git. [Complete acceptance and limitations](docs/controlled-iteration-2026-10-17.md).
