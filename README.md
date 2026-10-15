# BHM Mailer

Local FastAPI application for BHM Chemicals mailing workflows: contact import, contact editing, single-language campaign creation, HTML/plain-text preview, recipient selection, dry-run or SMTP sending, unsubscribe handling, campaign history, CSV export, and Message Trace CSV import.

Source repository: <https://github.com/ProgresLab/BHM-mailer>.

Git tracks application source, documentation, branding assets, and the non-secret `.env.example` configuration template. Local `.env` files, databases, contact imports, backups, logs, and virtual environments are excluded. Publishing source to GitHub does not deploy the application.

## Setup and Run

Recommended on Windows:

```powershell
.\start.bat
```

`start.bat` creates `.venv` if needed, installs dependencies, creates `.env` from `.env.example` if missing, starts the app on `127.0.0.1:8000`, waits for a response, and opens the browser.

Manual run:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
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
- One worker starts attempts at least 20 seconds apart. After 3600 active seconds it pauses for 300 seconds, then resumes unless manually paused. There is no extra 20-second delay after a slow SMTP call.
- Manual pause stops new reservations; an in-flight attempt finishes or is recorded as uncertain. Resume preserves spacing/cooldowns and sends only remaining eligible rows.
- After process restart, delivery stays interrupted until operator review and explicit resume. Timeout/disconnect/crash during an attempt becomes `delivery_unknown` with an uncertainty flag; no automatic resend. Resolve using Trace or an audited operator decision in history. Requeue requires an explicit evidence-backed confirmation of non-acceptance.
- SMTP 4xx pauses the account for at least 15 minutes; operator resume is required after expiry. Permanent recipient rejection is recorded and skipped; other SMTP problems pause the campaign.
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
