# PROJECT_BRIEF.md

Last updated: 2026-10-16

Status: in development

## Project Name

BHM Mailer / BHM Chemicals Mailing Tool

## Purpose

Local mailing application for importing and managing BHM Chemicals contacts, preparing single-language campaigns, previewing email output, selecting recipients, sending in dry-run or configured SMTP mode, and reviewing campaign delivery/status history.

## Current Status

IMAP/SMTP/sorting task (`BHM-IMAP-AUTORESUME-2026-10-16`): source implementation and isolated acceptance complete; operational migration/startup pending explicit approval. IMAP TLS login with the same local SMTP credential verified; full real INBOX scan applied only on a copy: 2173 messages, 263 review cases, zero new status changes. Both available marketing folders contain zero matching info unsubscribe notifications, so automatic unsubscribe coverage is incomplete. New schedule: 20 seconds, 1800 active / 300 break; safe definite SMTP cooldown >=900 seconds, maximum three auto-resumes, R6/policy/auth/uncertainty blocked. Recipient sorting is global before pagination and retains saved selection. Fresh consistent private backups/assets verified; operational DB unchanged. See `docs/imap-sync-acceptance-2026-10-16.md`.

Gmail reconciliation (`BHM-GMAIL-RECONCILIATION-2026-10-16`): campaign **38** completed its queue (1000 SMTP acceptances / 1004 attempts). One-shot read-only Gmail scan: 555 unique messages, 510 DSNs + 10 verified unsubscribe events, with uncertain reports preserved privately. Verified SQLite/assets backup, isolated simulation and independent operational readback: **354 invalid, 10 unsubscribed, 430 bounced_later**, 515 appended evidence events; all SMTP acceptance/attempt history and other tables preserved. No migration, SMTP send, restart or deploy. Port 8000 was already unavailable and remains stopped. See `docs/gmail-reconciliation-2026-10-16.md`; earlier runtime status below is historical.

Email renderer source update (`BHM-EMAIL-LAYOUT-2026-10-16`): new renders use a fluid 720 px card, full-width CTA with a 24 px table spacer and an 8 px outer radius. Verified only with synthetic HTML/browser fixtures and isolated tests; existing stored HTML/snapshots and operational runtime are not updated. See `docs/email-layout-qa-2026-10-16.md`.

Latest verified runtime status (`BHM-RECIPIENT-RUNTIME-2026-10-16`): recipient selection on actual 8000 is **BLOCKED / needs authorized activation**. PID 15184 retains the older POST-only selection route; actual browser GET `/campaigns/32/selection` returns 405, `Allow: POST`, with zero JS errors and current JS matching disk. Canonical source already has the correct GET/explicit_add_v1 API and passes fresh isolated QA. No application/UI change is needed; controlled SMTP-OFF restart is required. Read-only copy preflight finds no migration, only `campaign_execution.updated` for 17/18/28 and three appended recovery events. This current finding supersedes earlier runtime acceptance for the recipient workflow. See `docs/recipient-runtime-diagnosis-2026-10-16.md`.

The repo contains a local FastAPI application with SQLite persistence, Jinja templates, XLSX import, controlled rich text, private campaign banners/CID, draft editing and approval, persistent recipient selection (500/page, maximum 1000), a single sequential worker, durable pause/recovery, a separate monitor, per-attempt history, CSV export and Message Trace import. Modernization is implemented locally and validated with synthetic data, fake SMTP and isolated SQLite. During the subsequent HTTP-500 diagnosis, operational SQLite already had the modernized schema; this task performed no migration. After a verified backup and explicitly approved recovery, current code is running on port 8000 with process-level SMTP OFF; `/campaigns/new` returns HTTP 200 and passed actual desktop/mobile editor checks. Only the approved three execution timestamps and six new recovery events changed in operational SQLite; contacts, campaign content and message history matched the backup. See `docs/http500-diagnosis-2026-10-15.md`.

Source repository: `https://github.com/ProgresLab/BHM-mailer` (public). Source publication excludes local secrets, operational databases, uploaded contact files, backups, logs, and virtual environments; `.env.example` is a non-secret setup template. Runtime remains local.

Recipient delta `BHM-RECIPIENTS-2026-10-15`: explicit temporary checkboxes → Add → cumulative SQLite selection → separate summary/removal is implemented and browser-validated on isolated 8018. No schema change. Port 8000 retains its old Python process (PID 15184, SMTP OFF); the new frontend blocks selection mutations until it can confirm the matching API. Operational SQLite is byte/hash/mtime unchanged during this task. Activation is pending separate authorization for backup and a restart that, on the current in-memory preflight, changes three execution rows and adds three recovery events.

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
- Arbitrary HTML, unrestricted styling, and frontend frameworks for the editor.

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
- Recipient checkbox state is temporary per page; explicit Add unions eligible IDs into the existing `campaign_selection` table under `BEGIN IMMEDIATE`. Only explicit Remove or confirmed Clear deletes saved selection. No second persistent state source. Summary reads all saved rows, identifies excluded statuses and preserves the separate final-send fingerprint/acknowledgement gate. A versioned JS URL and matching API handshake protect the workflow during source/runtime version mismatch.
- The confirmation screen defaults to explicit dry-run, regardless of SMTP configuration. Real SMTP requires operator selection, acknowledgement, complete configuration and the same identity fingerprint as the prepared queue.
- `accepted_by_smtp` means SMTP accepted the message, not final inbox delivery.
- Message Trace CSV is used as a later delivery-status evidence source.
- New migrations are additive (columns, tables and indexes); historical messages/snapshots are not regenerated. Operational activation remains a separate gate.
- Fixed start-to-start interval: 20 seconds; automatic 300-second break after 1800 active seconds. Manual/automatic pauses do not count as active time. Legacy delay/skip environment flags cannot override this.
- OS process lock plus SQLite singleton reservation prevent concurrent campaign workers. Resume is explicit after restart; uncertain outcomes require trace evidence or an audited operator decision.
- Application limits use headroom: 20 attempts/5 minutes and 200/hour, sharing the ledger with admin unsubscribe notifications. External account traffic remains unknown.
- Admin unsubscribe notifications are queued durably and processed by the same worker after campaign completion. The public token/signature contract is unchanged.
- The small native browser editor uses contenteditable/execCommand and bounded document undo/redo; server allowlists remain authoritative. Browser-specific behavior requires future regression checks.

## Open TODOs

- TODO: Confirm intended long-term status: in development, staging, live, or maintenance.
- TODO: Document the external public unsubscribe endpoint source/repo if it exists.
- Before any future operational schema change: authorize and take a fresh operational SQLite/assets backup, then migrate/test a copy. The HTTP-500 task found the schema already current and performed no migration; the source of the intervening schema changes is unverified.
- TODO: Real one.com SMTP acceptance/delivery and real Outlook/client visual acceptance require separate authorization and evidence.
- TODO: Clarify whether the local app should ever be deployed, or remain local-only.
- Confirmed maintenance issue: each startup appends restart events for campaigns still labelled `sending`, including already interrupted/manual-paused executions. Reproduced on an in-memory copy; no mechanism change authorized in the HTTP-500 task. Any fix requires separate scope and regression checks.
- Recipient activation pending: authorize fresh operational SQLite/assets backup, copy preflight and exactly one SMTP-OFF restart including its recovery writes (currently three updated execution rows and three new events); then verify actual 8000. No restart or operational campaign mutation was authorized/performed in the recipient task.

## Risks / Constraints

- Mailing tools can send real emails when SMTP is enabled; avoid unapproved live sends.
- `.env` may contain secrets and must not be printed or committed.
- `data/` and `uploads/` may contain private contact/campaign data.
- SMTP acceptance is not final delivery confirmation.
- Public unsubscribe link verification depends on `UNSUBSCRIBE_SECRET` matching the external endpoint.

## Update Rule

Update this brief only when project scope, status, architecture, integrations, deployment, major decisions, or important TODOs change. Do not update it for small copy, spacing, CSS, or typo fixes unless explicitly requested.


## Requirements & Acceptance

Current task I01–I09: `BHM-IMAP-AUTORESUME-2026-10-16`.

| ID / Requirement | Implementation | Evidence | Status |
| --- | --- | --- | --- |
| I01 scope/runtime/Git | exact root/main/origin, remote 9fe9b11; no listeners 8000/8017/8018; no in-flight/reserved SMTP | private preflight and fresh GitHub settings | VERIFIED; no autodeploy found |
| I02 safe IMAP | TLS EXAMINE/PEEK, 900 sec, bounded UID/body/batches, OS singleton, separate thread | fake IMAP/clock/restart/connection tests; real read on copy | PASS source/copy |
| I03 classification/audit | shared MIME/DSN parser, receiver boundary and accepted attempt match, Gmail dedupe, durable audit; unsubscribe precedence | synthetic verified/forged/delay/policy/conflict/replay tests | PASS |
| I04 unsubscribe source | both marketing folders checked; no matching info notifications; existing controlled Gmail import retained | read-only mailbox preflight | PARTIAL coverage; no invented second credential |
| I05 SMTP pacing/recovery | 20 sec; 1800/300 active schedule; independent manual/break/cooldown/problem; limits/identity/recovery preserved | 1000 fake SMTP starts, 11 breaks, zero duplicate attempts | PASS isolated |
| I06 safe auto-resume | >=900 sec, longer provider interval, max3, account-wide 50 failures/hour guard; manual pause/R6/policy/auth/uncertain/restart gates | fake SMTP/clock/SQLite tests and monitor browser QA | PASS isolated |
| I07 recipient sorting | allowlisted global SQL email/company/date, stable IDs, real acceptance/legacy support, 500/page and1000 retained | ASC/DESC pagination and Add/API/SQLite/reload/summary | PASS isolated |
| I08 operational activation | fresh SQLite/assets backup; final migration/recovery on copy; 3 columns+3 tables+indexes and3 recovery timestamps/events | private manifests; source acceptance report | PENDING explicit operational approval |
| I09 closeout/Git | AGENTS/README/brief updated; one dated task entry; public source allowlist, outgoing review, remote SHA readback | acceptance report and Git history | VALIDATED / cleanup complete; source handoff via Git; no deploy |

Gmail task G01–G07: `BHM-GMAIL-RECONCILIATION-2026-10-16`.

| ID / Requirement | Implementation | Evidence | Status |
| --- | --- | --- | --- |
| G01 scope/queue/runtime | root/main/origin and campaign38 verified; queue completed, no SMTP attempt;8000 unavailable at entry | reconciliation report; private baseline | VERIFIED |
| G02 complete Gmail read | four in:anywhere queries, pagination,555 unique full reads, RAW fallback; final search unchanged | private search/MIME manifests | VERIFIED at scan cutoff |
| G03 classification/identity | deterministic MIME, exact accepted Message-ID/recipient/time, Gmail DKIM; token/source/snapshot for unsubscribe | private plan; synthetic tests | VERIFIED;72 reports retained for review |
| G04 backup/simulation/write | consistent SQLite+2 assets; copy simulation, compare all tables, BEGIN IMMEDIATE and independent readback | private manifest/applied-readback | APPLIED:354 invalid,10 unsubscribed,430 later bounces |
| G05 history/idempotency/exclusion | existing execution_events evidence, SMTP columns/attempts preserved, replay no-op; import/new and existing queue exclusions | private audit; tests | VERIFIED;worker priority fix source only |
| G06 4xx diagnostics | four451/R6 failures threshold;20.0025s min,15/5min,175/h;no schedule change | redacted diagnostics and report | VERIFIED;rate alone not established as cause |
| G07 closeout/publication | AGENTS reviewed, README/brief/report;one dated task entry;private/previous activation deltas excluded | staged/outgoing audit and fresh remote readback | Source publication;no deploy or runtime activation |

Task V01–V06: `BHM-EMAIL-LAYOUT-2026-10-16` (source/rendering only; prior runtime entries remain historical).

| ID / Requirement | Implementation | Evidence | Status |
| --- | --- | --- | --- |
| V01 width/responsiveness | 720 px card/MSO/banner, original padding, fluid mobile | 1200/390/360 browser measurements, 3:1 image | VERIFIED Chromium |
| V02 CTA/spacing | 100% content width, white centered text, navy, 6 px radius, table spacer 24 px | CTA 662/308/278 px; gap 24 px at all sizes | VERIFIED Chromium; native Outlook untested |
| V03 outer frame | 8 px radius, original white/grey/border, square fallback | screenshots and simulated radius-disabled render | VERIFIED Chromium; native Outlook untested |
| V04 protected elements | same text/links/CIDs/plain text/footer/logo, no saved HTML rewrite | 10 comparative fixtures and 47 isolated regressions | VERIFIED source/synthetic only |
| V05 evidence/cleanup | 30 before/after renders, screenshot review; browser closed, no test server | layout report; ports 8017/8018/8019 free | COMPLETE; operational 8000 not controlled |
| V06 closeout/publication | AGENTS reviewed, README/brief/report updated, one task entry; exclude prior local activation edits | layout report; reviewed staged diff and Git history | Source-only publication; no deploy/activation |

Current task D01–D06: `BHM-RECIPIENT-RUNTIME-2026-10-16`; operational acceptance remains BLOCKED until separately authorized activation. Earlier R/H/S acceptance is historical and scoped as recorded.

| ID / Requirement | Implementation | Evidence | Status |
| --- | --- | --- | --- |
| D01 actual runtime and source | PID 15184, exact project cwd/DB/assets, SMTP OFF, older POST-only routes; source changed after process start | `output/recipient-runtime/process.json`, `8000-browser.json`, diagnosis report | CONFIRMED |
| D02 failed request and gate | actual GET selection returns 405 / Allow POST; runtime OpenAPI POST only; JS matches source; no JS errors; gate preserved | browser evidence and process access log in report | CONFIRMED root cause |
| D03 canonical repair boundary | existing GET/Add source works in fresh QA; no UI rebuild/fallback; activation is the required repair | source and isolated 8018; `activation-preflight.json` | BLOCKED pending restart authorization |
| D04 complete recipient path | search/check/Add/direct SQLite/reload/count/summary; 500+500 via pagination, direct SQLite 500/1000 and summary 1000 | `output/recipient-qa/browser.json` including sqliteChecks, screenshots | VERIFIED QA only |
| D05 regressions and preservation | 47 isolated tests, compileall, JS syntax, 14 browser scenarios; copy init no-op, integrity ok/FK 0; no operational writes | tests.log, preflight and `closeout.json` in output/recipient-runtime | VERIFIED local; 8000 still blocked |
| D06 context and activation scope | AGENTS reviewed, README/brief/report updated; exactly one task entry; backup + one SMTP-OFF restart needs approval for 3 timestamps and 3 recovery events | diagnosis report, closeout.json | COMPLETE preparation; activation NOT DONE |

Single acceptance register: R01–R15 cover `BHM-MODERNIZATION-2026-10-15`; H01–H05 cover `BHM-HTTP500-2026-10-15`; S01–S08 cover `BHM-RECIPIENTS-2026-10-15`. Original R/H evidence remains historical; S rows describe the current recipient delta. PASS never means live SMTP or Outlook acceptance.

| ID / Requirement | Implementation | Evidence | Status |
| --- | --- | --- | --- |
| R01 identity and boundaries | root, fetch/push URL, branch, HEAD, remote tip checked before writes; operational runtime separate | `docs/modernization-acceptance-2026-10-15.md`, read-only `git ls-remote` | PASS local; no Git/deploy writes |
| R02 BHM visual identity, canonical paths | original logo, navy/white/grey, restrained green, 600 px tables, inline styles/MSO wrapper, verified URL and CTA paths | live website inspected; screenshots `output/playwright/preview-*.jpg` | PASS browser; Outlook unverified |
| R03 editor and drafts | controlled formatting/paste/undo/link toolbar; server Bleach/CSS/URL allowlist; subject/name/headline separate; PL/EN; draft edit and approval lock | rich text/draft tests; actual clipboard HTML, checklist undo/redo and save/reopen in Chromium | PASS supported format; native Word app not exercised |
| R04 campaign banner | content/dimension/size checks; immutable hashed private JPG/PNG; aspect preserved; CID per snapshot; footer logo | upload/MIME tests; desktop/mobile previews, no broken image | PASS local |
| R05 email structure, CTA, footer, unsubscribe | headline/body/checklists/optional validated CTA/contact/footer; unchanged signed URL contract | renderer, URL and signature tests; blocked-image screenshot | PASS local; public endpoint unchanged/unverified live |
| R06 preview and approval | realistic desktop/mobile iframe, plain text, image blocking, explicit POST approval, frozen snapshot content | draft/start/snapshot tests; browser preview/reopen | PASS local |
| R07 recipient selection | SQLite selection, server 500/page, filters, select-visible, selected-only view, clear, 1000 cap, final eligibility check | 5676 fixture; browser 500+500/refresh/limit; exclusion/dedup tests | PASS |
| R08 pacing/provider limits | starts >=20 s apart; 300 s after 3600 active; rolling headroom and common account spacing | 1000 fake-SMTP clock simulation; interval/break/rate-limit tests | PASS simulation; account traffic outside app unknown |
| R09 pause/resume/recovery | durable manual override, preserved cooldown, atomic reservation, OS owner lock, uncertain outcome gate, identity binding | concurrent starts/owners, in-flight pause, restart during break/attempt, timeout/4xx/550 tests | PASS isolated |
| R10 monitor | separate screen; counts/current-next/progress/active time/ETA/countdowns; 2.5 s polling; only eight events | route/payload tests; desktop/390/360 screenshots; browser pause/resume | PASS browser |
| R11 background/performance | one thread, no SQLite connection held across SMTP/waits, interruptible event wait, no automatic restart send | 1000 simulation; concurrent writer during fake SMTP; responsive routes while blocked | PASS isolated; long real-account soak unverified |
| R12 history | original statuses/export/Trace retained; contact history; append-only attempt ledger with outcomes; audited recovery decisions | Trace/export/history/XLSX/contact regression tests | PASS local |
| R13 data and safety | isolated DB/assets, no `.env` edits, POST and origin/Host checks, dry-run leaves `last_sent_at`/`sent_at`/`accepted_at` empty | baseline-schema copy + backup/idempotence/integrity/FK tests; QA has zero `last_sent_at` | PASS isolated; operational migration NOT DONE |
| R14 automated + visual QA | 40 unittest cases; compileall; synthetic UI 5676 contacts / 1000 queue | `output/evidence/tests.log`, `qa-state.json`, screenshots | PASS local; real SMTP/client tests NOT DONE |
| R15 context and closeout | AGENTS/README/brief reviewed and updated; exactly one task Change Log entry | closeout gate in evidence; HEAD remains baseline | PASS local |
| H01 confirmed HTTP-500 cause | original process console: missing `form`, stale handler/new template; current handler already correct | `docs/http500-diagnosis-2026-10-15.md`, original traceback and runtime evidence | PASS |
| H02 operational safety | verified consistent SQLite backup; in-memory startup preflight; no active sends, no schema migration; SMTP OFF | `http500-backup.json`, `http500-startup-preflight.json`, `http500-final-database-delta.json` under `output/evidence/` | PASS: only 3 updated timestamps + 6 explicitly approved events |
| H03 target runtime on 8000 | current source, PID 15184, SMTP OFF; server left running; actual editor/toolbar/bold/link at 1440/390/360, zero JS/asset errors | `output/evidence/http500-browser-8000.json`, `http500-runtime-after.json`; `http500-fixed-8000-*` screenshots | PASS HTTP 200; no operational draft created |
| H04 regression and synthetic UI | exact missing-context reproduction plus corrected GET, no DB access; full suite; rich text/save/reopen, previews, desktop/mobile | 41 tests PASS, compileall; `http500-tests.log`, `http500-browser.json`, QA screenshots | PASS; no operational draft |
| H05 closeout | AGENTS reviewed; README/brief/report updated; one dated task entry; repeated recovery confirmed only in memory, mechanism unchanged; no Git/deploy writes | diagnosis report, `http500-recovery-repeat-check.json`, `http500-closeout-gate.json` under `output/evidence/` | PASS; repeated recovery remains a documented maintenance issue |
| S01 diagnose reported checkbox failure | fresh current bundle works; legacy JS lacks listeners for new recipient selectors and reproduces dead counter/select-visible; unversioned asset URL identified | `output/recipient-qa/reproduction.json`, `operational-readonly.json`; browser legacy-bundle scenario and screenshot | PARTIAL: legacy mismatch reproduced; user's original browser cache unavailable, so exact incident cause unconfirmed |
| S02 explicit temporary/add workflow | immediate temporary count, explicit Add, labelled saved rows, separate summary, no autosave/navigation/send | actual browser single-contact and select/deselect tests; `app/static/app.js`, recipient template | PASS QA |
| S03 cumulative SQLite + atomic cap | union/add, explicit remove/confirmed clear, dedup, existing table and BEGIN IMMEDIATE, no migration | concurrent unit test; browser 500+500, 500+300+search, 1001, double click, two tabs | PASS QA |
| S04 summary and final safety | all saved rows, active/excluded counts, removal, subject/language/name, ETA, return and unchanged fingerprint/dry-run/SMTP acknowledgement | actual one/1000-row browser summaries, removal; full isolated suite | PASS QA; no queue started in browser |
| S05 single address and persistence | search marcin → temporary 1 → Add → 1/1000 → reload → exactly one summary row | `output/recipient-qa/browser.json`; `output/playwright/recipient-single-desktop.png`, `recipient-summary-desktop.png` | PASS browser + SQLite |
| S06 errors/statuses/responsiveness | API 503/limit error shows no success; inactive statuses blocked by UI/backend; old API visibly blocks mutations; desktop/390/360 | 14 actual browser scenarios, zero JS errors; mobile screenshots visually reviewed | PASS QA |
| S07 operational boundaries/runtime | same PID 15184, SMTP OFF, DB hash/size/mtime identical; init no-op and recovery exercised only in memory | `output/recipient-qa/final-audit.json`; predicts 3 execution-row changes + 3 events on restart | PASS preservation; 8000 activation NOT DONE / needs approval |
| S08 tests/context/Git gate | 47 isolated tests, compileall, JS syntax, 14 browser scenarios; context pack reviewed; one dated task entry; unchanged HEAD/index | `output/recipient-qa/tests.log`, `browser.json`, `closeout-gate.json`; diagnosis report | PASS local; GitHub tip refresh unavailable due network; no commit/push/deploy |

## Change Log

- 2026-10-16 — `BHM-IMAP-AUTORESUME-2026-10-16` (2026-10-16 21:28 CEST): Implemented read-only singleton IMAP with UID/UIDVALIDITY, shared Gmail/IMAP evidence and monitoring, 20s/1800s/300s worker schedule, bounded safe 4xx auto-resume (>=900s; max3; R6/auth/policy/uncertainty and 50 recent failed deliveries blocked) and global recipient sorting with real/legacy acceptance history. 89 isolated tests and5 grouped browser scenarios, compileall and syntax checks passed; consistent SQLite/assets backup and copied migration/recovery passed. Real IMAP copy scan:2173 messages,263 review cases,0 new contact changes; no matching info unsubscribe notifications in either marketing folder. Operational database unchanged; 8000 stopped, activation awaits explicit migration/recovery approval. Public source Git handoff only; no SMTP send, queue start, .env edit or deploy. See docs/imap-sync-acceptance-2026-10-16.md.

- 2026-10-16 — `BHM-GMAIL-RECONCILIATION-2026-10-16`: Completed one authorized reconciliation for campaign38 after queue completion. Read555 unique Gmail messages with pagination/full MIME/RAW and final unchanged rescan;510 DSNs+10 verified unsubscribe events,72 uncertain reports retained privately. SQLite/assets backup and isolated simulation/readback passed;operational changes limited to354 invalid+10 unsubscribed contacts,430 bounced_later send projections and515 appended evidence events. All1000 SMTP acceptance timestamps,1004 attempt records and other tables/assets preserved;no migration. Existing ledger provides idempotent evidence;worker source now preserves unsubscribe during in-flight rejection. Four451/R6 failures specifically cite >50 failed deliveries/hour;minimum observed spacing20.0025s,15/5min,175/h,no schedule change.57 isolated tests and compileall passed. Port8000 already stopped and remains stopped;no SMTP send,restart,Gmail mutation,deploy or automation. Context Pack Closeout complete;exactly one task entry. Authorized commit/push scope excludes earlier local activation edits and all private evidence. See `docs/gmail-reconciliation-2026-10-16.md`.

- 2026-10-16 — `BHM-EMAIL-LAYOUT-2026-10-16`: Limited renderer delta: 600→720 px HTML/MSO/banner, full-width centered navy CTA with 6 px corners and a real 24 px table spacer, 8 px card corners with square Outlook fallback. Validated 47 isolated tests, compileall, 10 protected-content comparisons and 30 desktop/390/360 before/after renders; screenshots reviewed. No SMTP/send, operational SQLite/assets, editor, footer, unsubscribe, history, saved HTML or snapshots changed. QA browser closed; no test server started, QA ports free. Context Pack Closeout complete; exactly one task entry. Reviewed source/docs intended for authorized origin/main publication; no deploy or operational restart. See `docs/email-layout-qa-2026-10-16.md`.

- 2026-10-16 — `BHM-SOURCE-PUBLISH-2026-10-16`: User authorized commit/push of the accumulated reviewed BHM Mailer source to origin/main (modernization, recipient workflow, regressions, synthetic QA tools and runtime diagnosis). Release preflight confirmed exact root/branch/fetch+push remote and remote main at 37ce3a7; 39 source/config/docs/test files, no secret matches or private runtime paths. Existing evidence: 47 isolated tests, 14 browser scenarios and syntax checks. Git records the resulting commit and remote verification; this source publication does not authorize restart, operational writes, SMTP, deployment or activation of the blocked port-8000 workflow. Context Pack reviewed; existing activation gate remains in force.

- 2026-10-16 — `BHM-RECIPIENT-RUNTIME-2026-10-16`: Confirmed actual 8000 blocker: PID 15184 runs older POST-only selection API; browser GET /campaigns/32/selection returns 405 / Allow POST, matches server log and runtime OpenAPI; current JS is hash-identical to disk, no JS errors. Canonical GET/Add implementation already correct; gate preserved, no UI/backend rewrite. Added read-only runtime/browser and in-memory activation preflight tools; strengthened QA with direct SQLite reads. 47 isolated tests and 14 browser scenarios verified single contact and 500+500 through reload/summary. Copy init no-op; restart predicts only updated timestamps for executions 17/18/28 and three appended events. Operational 8000 remains BLOCKED pending explicit backup/restart/recovery authorization, SMTP OFF; no operational writes, real send, .env edit, commit/push/deploy. Context Pack reviewed; one entry for this task.

- 2026-10-15 — `BHM-RECIPIENTS-2026-10-15`: Replaced recipient autosave/page replacement with temporary checkboxes and explicit cumulative Add in existing SQLite; separate summary lists/removes saved recipients, Clear requires confirmation, atomic 1000 cap and final-send safeguards retained. Versioned JS and API compatibility gate prevent mutation against stale runtime. Fresh current baseline worked; legacy JS reproduced reported dead listeners, but the original user's browser cache was unavailable, so that incident cause remains unconfirmed. Validation: 47 isolated tests, compileall, JS syntax and 14 Chromium scenarios including marcin/reload/summary, 500+500, 500+300+search, limit 1001, two tabs, duplicate clicks, API errors and desktop/390/360. Operational DB hash/size/mtime unchanged; PID 15184 remains SMTP OFF, without restart. In-memory activation preflight predicts three execution-row changes and three new recovery events; separate approval required. No operational migration/campaign write, real send, .env edit, commit, push or deploy; HEAD main remains 37ce3a7.
- 2026-10-15 — `BHM-MODERNIZATION-2026-10-15`: Implemented local rich-text campaigns, validated CID banners, persistent 500/page selection (cap 1000), sequential 20-second SMTP worker with 5-minute breaks, manual pause/recovery, monitor and per-attempt/contact history. Validation: 40 isolated tests, 1000 fake-SMTP attempts with minimum 20-second spacing and five 300-second breaks, compileall and desktop/mobile browser QA. Operational SQLite, existing runtime, `.env`, real SMTP and Outlook acceptance were not changed/exercised. Git: local working-tree changes only; `main` HEAD and checked remote tip `37ce3a788ba1cd01476a016c8113db52bccd45e9`; no commit, push or deploy.
- 2026-10-15 — `BHM-HTTP500-2026-10-15`: Repaired stale port-8000 handler/new-template mismatch (`form` undefined) by loading the already-correct canonical source in a fresh runtime. PID 15184 remains running with SMTP OFF; actual `/campaigns/new` HTTP 200, editor/bold/link and 1440/390/360 screenshots PASS with no JS/asset errors. Added regression coverage: 41 isolated tests and compileall PASS; QA save/reopen/banner previews PASS. Verified consistent operational backup and no-op initialization. Following a verification-script incident and explicit second-start approval, the final full-table comparison found only 3 updated recovery timestamps and 6 authorized new events. Repeated recovery events reproduced in memory; mechanism unchanged. No contact/campaign/message-history changes, migration, `.env` edit, real SMTP, commit, push or deploy. Exactly one task entry retained.
