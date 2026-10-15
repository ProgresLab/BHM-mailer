# HTTP 500 — campaign creation, 2026-10-15

Task: `BHM-HTTP500-2026-10-15`. Local runtime repair only. GitHub read-only; no commit, push, deployment or real SMTP.

## Confirmed cause

The original port-8000 process returned HTTP 500 for `GET /campaigns/new`. Its console traceback ends with:

```text
app/templates/campaign_new.html, line 4
jinja2.exceptions.UndefinedError: 'form' is undefined
```

PID 33344 (launcher 19596), owned by the local `info` account, started at 19:57:25 Europe/Warsaw. Its working directory was this repository. Command: `.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`; underlying interpreter `C:\Python314\python.exe`. It had no reload. The old handler called `render_template(request, "campaign_new.html")`, without `form`. Jinja loaded the new template from disk, including `form.id`, after the process had started. Current source already passes `{"form": {}}`. This is a stale process/new-template mismatch, manifested as missing Jinja context; no dependency or editor defect was found.

Port 8017: PID 26324 (launcher 35328), same root/interpreter, `tools/qa_server.py`, started 21:20:39 Europe/Warsaw; `BHM_DB_PATH=output/qa/synthetic.sqlite3`, private QA assets, `SMTP_ENABLED=false`. Its actual `GET /campaigns/new` returned 200. It was not stopped or moved onto operational SQLite.

Evidence: `output/evidence/http500-original-traceback.txt`, `http500-runtime-before.json`, `output/playwright/http500-before-8000.png`. Console traceback source-line snippets can reflect newer on-disk Python; the loaded function's old line number, original route contract, process start time and exact Jinja exception establish the mismatch.

## Database and startup gate

Fresh inspection contradicted the earlier modernization closeout: operational SQLite already contained the new execution tables and rich-text/banner columns before this task made any writes. The prior report is historical evidence, not current schema proof. Its original metadata recorded 39,198,720 bytes; this task found 39,350,272 bytes, last modified 22:32:53 Europe/Warsaw. The provenance of those intervening changes was not established here.

All three SMTP execution rows were already `interrupted`, with `manual_pause=1`; no send row was `sending`, no execution was running/in an automatic break, and no notification was queued/sending. Repeated operational hashes stayed unchanged before restart. The old process had no external established TCP connection. Campaigns still labelled `sending` therefore were not evidence of an actively sending worker.

An SQLite backup into memory exercised `init_db()` and `worker.recover()` without changing the original. Initialization changed neither schema nor rows. Recovery changed only execution metadata and added one restart event for each of the three interrupted queues. No migration was necessary or performed on operational SQLite.

The user separately approved that recovery and restart with SMTP forced off, conditional on a verified backup and unchanged business data. A consistent backup via SQLite backup API was created at `backups/http500-20261015T204801Z/bhm_mailer.sqlite3`. `integrity_check=ok`, no foreign-key violations, logical dump identical to the source. Operational campaign-assets directory was absent; zero assets were referenced, so there were no immutable banners to copy. Manifest: `output/evidence/http500-backup.json` and the backup folder's `manifest.json`.

Pre-restart operational SHA-256: `08b54d016374ff6ad3e54260f24a7c7d33c259d5b592c7a67f302c3f7762dfcb`. Backup file SHA differs because SQLite backup reconstructs database pages; logical contents were compared independently and matched.

## Runtime repair and verification incident

The confirmed old process was stopped. The current canonical application started on port 8000 with `SMTP_ENABLED=false` in its process environment, explicit operational DB/assets paths, one uvicorn process and normal startup/worker lifecycle. `.env` and SMTP credentials/configuration files were not edited. Its first `GET /campaigns/new` returned 200.

The initial post-start comparison script used SQLite `rowid` without an alias; SQLite returned the integer-primary-key column name instead. That inspection failed and its fail-closed wrapper stopped replacement PID 11312. This was a verification-script defect, not evidence of an unexpected application write. After correcting the alias, every table matched the backup except exactly three `campaign_execution.updated` values (campaign IDs 17, 18, 28) and three appended recovery events. Schema, contacts, campaign content, email history/snapshots, unsubscribe rows and attempt ledgers matched exactly.

The user explicitly approved one further startup, at most six recovery events in total against the existing verified backup, and instructed that the server remain running. The final startup at 23:06:00 Europe/Warsaw uses listener PID 15184 (launcher 34948), the same `.venv` entrypoint/root and underlying Python 3.14 interpreter, with `SMTP_ENABLED=false`. Port 8000 returns HTTP 200 and is left running. Port 8017 remains the separate synthetic QA process. No additional operational restart was performed.

An independent read-only final audit, with no process-control commands, compared every table against the original backup: exactly six new recovery events, two per campaign 17/18/28, and changes only to `campaign_execution.updated` for those same three rows. Every other table and the entire schema matched; integrity and foreign-key checks passed. No operational campaign was created during validation. The failed verification did not roll back or delete the first authorized events. Evidence: `output/evidence/http500-final-database-delta.json`, `http500-runtime-after.json`, `http500-8000-final-stderr.log`.

## Regression and browser checks

- Added `test_new_campaign_requires_form_context_without_database_access`: removing `form` reproduces the exact `UndefinedError`; current GET returns 200, supplies an empty form and renders the editor/toolbar without accessing SQLite or creating a draft.
- Full suite: **41 tests passed** (the previous 40 plus this regression), 41.299 seconds. Includes old campaign/logo compatibility, fake SMTP, selection, pacing, breaks, recovery and persistence. `compileall app` passed. Log: `output/evidence/http500-tests.log`.
- Synthetic QA on 8017: actual new-campaign form; enter text, toolbar bold/link; 1440/390/360 widths with no horizontal overflow; save, reopen with formatting/link retained, edit and save again; preview with/without uploaded synthetic banner; mobile preview. Zero JavaScript errors or failed asset requests. Only synthetic campaign 6 was created. No operational draft was created.
- Browser evidence: `output/evidence/http500-browser.json`; screenshots `output/playwright/http500-qa-editor-{desktop,390,360}.png`, `http500-qa-preview-no-banner.png`, `http500-qa-preview-banner.png`, `http500-qa-preview-banner-mobile.png`.
- Final target-port browser acceptance: `http://127.0.0.1:8000/campaigns/new` returned **200**; editor and toolbar visible; actual typing/bold/link interaction passed. Desktop 1440 and mobile 390/360 had no horizontal overflow. Zero JavaScript errors, failed requests or write requests; operational draft count unchanged. Screenshots were visually inspected. Evidence: `output/evidence/http500-browser-8000.json`, `output/playwright/http500-fixed-8000-{1440,390,360}.png`, `http500-fixed-8000-formatting.png`. The browser script blocks all non-GET/HEAD requests and closes only its own browser, leaving the server running. The application URL was opened in the Codex browser panel.
- No application Python, template, JS, CSS, email layout, pacing or worker behavior was changed: the source already contained the correct handler. The repair is loading that source in the target runtime, with regression coverage and startup guidance.

## Recovery and remaining boundaries

Repeated-recovery finding (requested read-only investigation): `recover()` selects all campaigns whose business status remains `sending`; it appends a restart event even when the corresponding execution is already `interrupted` and manually paused. Two calls against an **in-memory copy of the verified backup** produced +3 then +3 events. Thus repeated restart events for unchanged interrupted queues are confirmed; they do not prove a new SMTP attempt. The mechanism was not changed and the live server was not restarted for this check. Evidence: `output/evidence/http500-recovery-repeat-check.json`. Avoid further operational restarts until their recovery writes are included in the authorized scope; making recovery idempotent is a separately scoped improvement.

The final comparison detected no broader writes. Preserve the original backup and logs. Restoring the backup is a separate destructive action requiring approval; never overwrite SQLite while the app is running. Restore immutable assets with their corresponding database if present. No migration plan is needed for this observed current schema; any future schema change still requires its own backup/copy/approval gate.

Real SMTP remains forbidden. Do not treat successful browser/QA checks as SMTP delivery or Outlook acceptance. Current process SMTP OFF is an environment override, not a permanent `.env` change. A later ordinary launch can load the existing `.env`; enabling real sending requires separate authorization.
