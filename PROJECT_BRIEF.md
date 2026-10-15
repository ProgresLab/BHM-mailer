# PROJECT_BRIEF.md

Last updated: 2026-10-15

Status: in development

## Project Name

BHM Mailer / BHM Chemicals Mailing Tool

## Purpose

Local mailing application for importing and managing BHM Chemicals contacts, preparing single-language campaigns, previewing email output, selecting recipients, sending in dry-run or configured SMTP mode, and reviewing campaign delivery/status history.

## Current Status

The repo contains a working local FastAPI application with SQLite persistence, Jinja templates, static assets, XLSX import support, SMTP configuration through environment variables, unsubscribe handling, campaign history, live progress polling, CSV export, and Message Trace CSV import.

Source repository: `https://github.com/ProgresLab/BHM-mailer` (public). Source publication excludes local secrets, operational databases, uploaded contact files, backups, logs, and virtual environments; `.env.example` is a non-secret setup template. Runtime remains local.

## In Scope

- Local web UI for contacts, imports, campaign creation, preview, recipient selection, and history.
- SQLite database initialized and migrated by application code.
- Dry-run behavior when SMTP is not fully configured.
- SMTP sending through configured environment variables.
- Signed public unsubscribe URL generation.
- Campaign send-status tracking and CSV trace/status workflows.
- Practical documentation for local operation and maintenance.

## Out of Scope

- User authentication and roles.
- Scheduling or automation of campaigns.
- Production deployment of the local app.
- DNS/domain/Microsoft 365 configuration.
- Tracking pixels or advanced analytics.
- Integrations with Mailgun, Brevo, SendGrid, Amazon SES, or similar providers.
- Physical deletion workflows for contacts unless explicitly requested.
- Advanced HTML email editor.

## Main Features

- Contact import from paste input and XLSX files.
- Contact list and edit views.
- Single-language campaign drafts in `pl` or `en`.
- Table-based HTML email rendering and plain-text fallback.
- Manual recipient selection with filters.
- Campaign background sending and live progress endpoint.
- Send history with SMTP identity diagnostics.
- Status export to CSV.
- External Message Trace CSV import.
- Unsubscribe token handling and admin notification path when SMTP is configured.

## Architecture / Stack

- Python FastAPI app in `app/main.py`.
- Jinja2 templates in `app/templates/`.
- Static CSS/JS/assets in `app/static/`.
- SQLite database in `data/bhm_mailer.sqlite3` by default.
- Database schema and additive migrations in `app/db.py`.
- Mailing logic in `app/mailer.py`.
- Import logic in `app/importer.py`.
- Email rendering in `app/email_renderer.py`.
- Dependencies are listed in `requirements.txt`.
- Local startup helper is `start.bat`.

## Deployment

Primary detected mode is local Windows execution through `start.bat` or manual `uvicorn`.

The app generates signed unsubscribe URLs intended for an external public endpoint configured by `PUBLIC_UNSUBSCRIBE_BASE_URL`. Existing documentation references a Netlify unsubscribe endpoint, but this repo does not define a full production deployment for the local FastAPI app.

## Reference Projects

- TODO: No reference projects were identified in this repo.

## Key Decisions

- The app is local-first and stores data in SQLite.
- Real SMTP sending is controlled by `.env`; missing or incomplete SMTP configuration results in dry-run or blocked real sending.
- `accepted_by_smtp` means SMTP accepted the message, not final inbox delivery.
- Message Trace CSV is used as a later delivery-status evidence source.
- Database migrations are additive and preserve historical columns where possible.

## Open TODOs

- TODO: Confirm intended long-term status: in development, staging, live, or maintenance.
- TODO: Document the external public unsubscribe endpoint source/repo if it exists.
- TODO: Add explicit test command or test suite if this project should have automated tests.
- TODO: Clarify whether the local app should ever be deployed, or remain local-only.

## Risks / Constraints

- Mailing tools can send real emails when SMTP is enabled; avoid unapproved live sends.
- `.env` may contain secrets and must not be printed or committed.
- `data/` and `uploads/` may contain private contact/campaign data.
- SMTP acceptance is not final delivery confirmation.
- Public unsubscribe link verification depends on `UNSUBSCRIBE_SECRET` matching the external endpoint.

## Update Rule

Update this brief only when project scope, status, architecture, integrations, deployment, major decisions, or important TODOs change. Do not update it for small copy, spacing, CSS, or typo fixes unless explicitly requested.
