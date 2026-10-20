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
- Safe definite 4xx cooldown is at least 900 seconds; account failures allow at most three consecutive automatic resumes, reset by acceptance. Recipient transients allow at most three attempts with backoff, then remain failed without stopping other contacts. R6 permits one probe per queue after at least 3600 seconds (longer provider waits win), then requires an operator if still blocked. Reputation/authentication/TLS/configuration failures stop the account. Unknown outcomes are never retried, including through a new campaign; three consecutive transport uncertainties stop the account. Manual pause and process recovery always win.
- Operational migration/activation requires a separately authorized backup and copied-database preflight. A running older process is not proof of the new source behavior.
- Approved operator mode uses `start-imap-safe.bat` / `tools/run_imap_safe.py`: canonical DB/assets, IMAP ON, SMTP forced OFF, port bind before startup to avoid duplicate recovery. Leave the operator instance running; never infer send/resume authorization from IMAP activation.
- Normal operational mode is explicitly `start-bhm-operational.bat` / `tools/run_bhm_operational.py` (IMAP ON + SMTP ON), without recovery arguments for ordinary startup. Bind 8000 before imports; require complete one.com identity/HMAC, idle account or a reservation held by an already manually paused queue, no unsent/uncertain admin notification, no unresolved attempts/cooldown, intact assets and copied startup preflight. Already safe interrupted/manual_paused queues remain byte-for-byte logically unchanged, including timestamps/events; recovery is idempotent and never resumes them. Real recovery/migration mutations still require exact separate review/authorization; never supply `--approve-recovery-for` blindly. A busy port reports PID/CWD/owner where OS access permits and exits before application startup. Preserve reservations and keep the IMAP-only launcher separate. Legacy `start.bat` is setup only.
- Offline Gmail `--paused-history` reconciliation requires the stopped-runtime port/SMTP/IMAP lock fence, no in-flight work, exact accepted historical attempts, backup/copy simulation/readback and unchanged pending rows. Keep `ensure_idle` for other protected imports. Large IMAP reports can expand one PEEK from 1 MiB to at most 8 MiB; incomplete MIME never advances the cursor. Re-analysis requires a known review UID, matching UIDVALIDITY and full MIME; do not weaken receiver trust or infer automatic info-mailbox coverage.
- Permanent offline closure requires explicit operator authorization, the stopped-runtime fence, verified DB/assets backup, exact pending count, copied simulation and independent readback. `tools/close_and_reconcile.py` cancels only unattempted pending rows, preserves contacts/send timestamps/snapshots/history, records one closure audit, finishes campaign/execution and releases only that campaign's reservation. Terminal execution cannot resume. Closure is never invalid-address or SMTP-acceptance evidence; eligible cancelled contacts remain available for an explicit new selection.
- Closure may additionally finalize an explicitly counted deferred row as smtp_failed only with complete finished, definite 4xx refusal history and no acceptance/uncertainty; retain every original attempt/reply. Gmail closure imports keep sender policy/delayed/review send projections unchanged. R7 queue saturation stops the account for manual review after at least 3600 seconds (longer provider waits win), without an automatic probe or invalidating recipients. Show the exact sanitized provider reply and exception class for new failures; earliest control time is not a provider availability guarantee.
- Material tasks maintain one `Requirements & Acceptance` register and exactly one dated task entry in `PROJECT_BRIEF.md → Change Log`.
- Explicit all-previous-queues closure may count legacy unaccepted 4xx rows without an attempt ledger using `--expected-preserved-refused`. Preserve those send rows byte-for-byte while terminally closing the campaign; never infer smtp_failed, SMTP acceptance, invalidity or missing attempts. Default refusal validation remains strict; pending cancellation still requires no attempt history. Retain the stopped-runtime fence, exact backup/simulation/readback and terminal resume block.

## Project Brief Update Rule

Update `PROJECT_BRIEF.md` only when scope, status, architecture, integrations, deployment, major decisions, or important TODOs change. Do not update it for small copy, spacing, CSS, or typo fixes unless explicitly asked.

## Final Report Format

Final reports must include only:

- Changed files
- Validation/tests
- Risks
- What was not done
