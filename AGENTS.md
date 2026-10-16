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
- Mailing/database changes: run `.venv/Scripts/python -m unittest discover -s tests -v` on its isolated fixtures; avoid real SMTP unless explicitly approved.
- `tools/qa_server.py` is the synthetic visual-QA launcher (port 8017, SMTP forced off); it never targets operational SQLite.
- Recipient regression QA uses `tools/recipient_qa_server.py` (8018, separate synthetic SQLite, SMTP OFF) and `tools/recipient_browser_qa.cjs`. Checkbox changes are temporary; only explicit Add persists. Add is cumulative; Remove and confirmed Clear are the only deletion paths. Keep the frontend/backend workflow compatibility gate.
- Preserve immutable campaign assets together with database backups. Do not delete assets referenced by drafts or historical snapshots.
- Keep the 20-second worker interval, 1800 active / 300 break contract, explicit restart recovery and uncertainty gate. Do not restore direct SMTP calls outside the singleton worker.
- IMAP uses a separate OS-locked thread, EXAMINE/PEEK only, durable UID/UIDVALIDITY and shared Gmail evidence deduplication. Unknown receiver headers, unmatched attempts and conflicting evidence require review. Keep IMAP off in unrelated QA; `tools/sync_qa_server.py` uses fake IMAP on 8019, SMTP OFF.
- Safe definite 4xx cooldown is at least 900 seconds with at most three automatic resumes per queue; R6/reputation/authentication/uncertain outcomes require an operator. Manual pause and process recovery always win.
- Operational migration/activation requires a separately authorized backup and copied-database preflight. A running older process is not proof of the new source behavior.
- Approved operator mode uses `start-imap-safe.bat` / `tools/run_imap_safe.py`: canonical DB/assets, IMAP ON, SMTP forced OFF, port bind before startup to avoid duplicate recovery. Leave the operator instance running; never infer send/resume authorization from IMAP activation.
- Normal operational mode is explicitly `start-bhm-operational.bat` / `tools/run_bhm_operational.py` (IMAP ON + SMTP ON). Bind 8000 before imports; require complete one.com identity/HMAC, idle/unreserved account, no unsent/uncertain admin notification, no unresolved attempts/cooldown, intact assets and copied startup preflight. Existing interrupted-queue timestamp/audit writes require exact operator approval; `--approve-recovery-for` is an approval acknowledgement, never a testing bypass. No automatic campaign start/resume. Keep the IMAP-only launcher separate. Legacy `start.bat` is setup only and is not an operational launcher.
- Material tasks maintain one `Requirements & Acceptance` register and exactly one dated task entry in `PROJECT_BRIEF.md → Change Log`.

## Project Brief Update Rule

Update `PROJECT_BRIEF.md` only when scope, status, architecture, integrations, deployment, major decisions, or important TODOs change. Do not update it for small copy, spacing, CSS, or typo fixes unless explicitly asked.

## Final Report Format

Final reports must include only:

- Changed files
- Validation/tests
- Risks
- What was not done
