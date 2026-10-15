# AGENTS.md

## Project Purpose

BHM Mailer is a local FastAPI mailing tool for BHM Chemicals. It supports contact import, contact management, single-language campaign drafts, HTML/plain-text email preview, recipient selection, dry-run or SMTP sending, unsubscribe handling, campaign history, and CSV status/trace workflows.

## Source of Truth

Before non-trivial work, read:

- `PROJECT_BRIEF.md`
- `README.md`
- Relevant files in `app/`

Use `requirements.txt`, `start.bat`, `.env.example`, and the source files as implementation references. Do not treat generated files, local databases, uploaded spreadsheets, or caches as source of truth.

## How to Work in This Repo

- Work only in this project unless the user explicitly provides another scope.
- Work on source files, not build artifacts, caches, local SQLite data, uploads, or virtual environments.
- Use minimal changes matched to the requested task.
- Preserve existing behavior unless the user asks to change it.
- Treat referenced external projects as read-only unless explicitly told otherwise.
- Do not refactor opportunistically during feature, bugfix, or docs work.
- Keep documentation practical and concise.

## Safety Rules

- Never hardcode or print secrets.
- Do not edit `.env`; use placeholders and `.env.example` for documented configuration.
- Do not commit local database files, uploaded contact spreadsheets, private contact data, logs, or generated caches.
- Do not run destructive commands without explicit approval.
- Do not invent clients, claims, prices, certifications, statistics, APIs, deployment details, or business decisions.
- For mailing changes, be careful with SMTP, unsubscribe links, recipient status, and send-status semantics. `accepted_by_smtp` is not final delivery.

## Testing Expectations

Choose the smallest useful validation for the change:

- Docs-only: confirm files exist, content is accurate, and no secrets or invented claims were added.
- Python/source changes: run `python -m compileall app` at minimum.
- UI/template/static changes: run locally and check desktop/mobile basics when relevant.
- Mailing/database changes: test dry-run path and one edge case; avoid real SMTP sends unless explicitly approved.

## Project Brief Update Rule

Update `PROJECT_BRIEF.md` only when scope, status, architecture, integrations, deployment, major decisions, or important TODOs change. Do not update it for small copy, spacing, CSS, or typo fixes unless explicitly asked.

## Final Report Format

Final reports must include only:

- Changed files
- Validation/tests
- Risks
- What was not done
