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

No build step or automated test suite was detected.

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
- Create campaign drafts in `pl` or `en`.
- Preview Outlook-compatible table-based HTML and plain-text fallback.
- Select recipients manually with filters.
- Send as dry-run when SMTP is not configured, or through SMTP when enabled.
- Review campaign history and live progress.
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
