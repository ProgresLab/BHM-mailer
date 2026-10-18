# PROJECT_BRIEF.md

Last updated: 2026-10-18

Status: in development

## Project Name

BHM Mailer / BHM Chemicals Mailing Tool

## Purpose

Local mailing application for importing and managing BHM Chemicals contacts, preparing single-language campaigns, previewing email output, selecting recipients, sending in dry-run or configured SMTP mode, and reviewing campaign delivery/status history.

## Current Status

Campaign43 closure and startup repair (`BHM-CLOSE43-RECOVERY-2026-10-18`): **DONE**. Campaign/execution completed_with_errors;914 historical SMTP acceptances preserved (368 later bounces),85 unattempted rows cancelled,1 definite451/R7 refusal finalized as smtp_failed,0 pending/uncertain;reservation released and resume blocked. Gmail full-history scan2505 MIME/52 pages/6 RAW:3 invalid+5 unsubscribe,3 bounce projections,15 audits,2140 duplicate records;278 unresolved and104 sender-policy records remain review-only. SQLite/WAL+2-assets backups, exact copied simulation, independent full-row readback and replay passed;no false send/contact dates. Recovery now preserves safe interrupted/manual_paused queues without timestamps/events or RECOVERY prompt;126 isolated tests include3 successive startup/recovery cycles and uncertain-start protection. Actual127.0.0.1:8000 PID24896, IMAP ON/SMTP ON,10 GET-only browser checks plus14 recipient/9 sync browser scenarios passed;zero new SMTP/admin attempts and only ordinary IMAP scheduling changed at startup. Duplicate launch reports PID/CWD/owner and exits;own QA stopped. No real send,new campaign,migration,secrets/provider/DNS changes or deploy. [Acceptance](docs/closure43-recovery-2026-10-18.md). Older runtime/preflight statements below are historical.

Gmail double-check (`BHM-GMAIL-DOUBLECHECK-2026-10-18`): **DONE, offline**. Latest campaign42 and execution remain completed_with_errors;1000 historical acceptances preserved (654 accepted_by_smtp+346 bounced_later). Full-history scoped Gmail scan:1980 candidate messages,38 fully paginated search pages,complete MIME plus4 RAW fallbacks;5 new invalid+3 unsubscribed,5 hard-bounce projections and17 evidence audits applied. Final contacts:4528 active/1119 invalid/29 unsubscribed.1619 previously reconciled reports (1070 IMAP/549 Gmail)+1 in-batch duplicate skipped;196 delayed,89 policy and224 unresolved reports retained without contact changes. Consistent SQLite/WAL+2-assets backup,exact simulation,independent all-row readback,integrity OK/FK0 and no-op replay passed;119 isolated tests and compileall passed.8000/SMTP/IMAP were stopped at entry and remain stopped;no campaign start/closure/resume,recovery,migration or real send. [Report](docs/gmail-doublecheck-2026-10-18.md). Older runtime statements below are historical.

Offline campaign41 closure (`BHM-CLOSE41-OFFLINE-2026-10-17`): **DONE within the final offline scope**. Campaign/execution completed_with_errors;713 historical SMTP acceptances preserved (223 now bounced_later),287 unattempted rows cancelled without sent_at/accepted_at or contact last-send changes. All287 remain active/eligible for explicit future selection;resume rejected and reservation released. Full-history Gmail scan:1153 complete MIME messages,24 search pages,12 new invalid+5 unsubscribed,21 later-bounce projections,32 evidence audits;956 duplicates skipped and162 unresolved reports retained privately. Consistent DB/2-assets backup,exact copy simulation,independent per-recipient readback and Gmail/closure no-op replay passed.119 isolated tests,14 recipient browser scenarios,8 sync/sort browser checks and compileall passed. No real SMTP,new campaign,Gmail changes or migration. Operator8000 and QA ports are free. User explicitly declined startup/recovery;ready for manual start-bhm-operational.bat,whose current copy preflight requires updated+one recovery event each for17/18/28. [Report](docs/campaign41-offline-2026-10-17.md). Earlier runtime paragraphs are historical.

Permanent closure and activation (`BHM-CLOSE-ACTIVATE-2026-10-17`): **DONE; actual127.0.0.1:8000 PID21732, IMAP ON / SMTP ON**. Campaign40 is completed_with_errors:661 historical SMTP acceptances (199 later bounces),312 cancelled without send timestamps,0 pending/unknown. Reservation released; resume rejected. Fresh199-message Gmail scan across accepted-attempt campaigns36/37/38/40:0 new invalid/0 unsubscribe,197 duplicates,1 new unmatched review; previous4/3 changes preserved. Verified DB/assets backups, exact copied closure/replay and independent readback.119 tests,1000-contact autonomous SMTP simulation (1000 accepted/1006 fake calls/0 manual resumes),8 synthetic browser checks and actual8000 desktop/mobile GET-only acceptance passed. Applied only authorized recovery updated/events for17/18/28; no40 recovery, no real SMTP attempt/new campaign/resume. New campaign editor and empty selection ready; QA stopped. [Full report](docs/close-activate-2026-10-17.md). All older runtime paragraphs below are historical.

Controlled iteration (`BHM-CONTROLLED-2026-10-17`): Gmail reconciliation APPLIED and independent readback PASS. Campaign40:973 snapshots,661 historical SMTP acceptances (199 later bounces),312 identical pending,0 unknown/inflight,manual pause preserved.290 Gmail messages/286 DSN:4 new invalid+3 unsubscribed,7 later-bounce updates,10 audits;277 prior evidence duplicates skipped. SQLite/assets backup and replay no-op verified. SMTP transient/backoff/R6/uncertainty and IMAP bounded fetch/re-analysis implemented;115 isolated tests and browser acceptance passed. Port8000 stopped after identifying prior PID25844; startup still requires exact recovery approval for17/18/28/40. No real send/resume/new campaign/deploy. [Evidence, counts and activation boundary](docs/controlled-iteration-2026-10-17.md). All older runtime paragraphs below are historical.

Operational preparation (`BHM-OPERATIONAL-2026-10-16`): **DONE — IMAP ON + SMTP ON**, actual localhost8000 PID25844, started once through `start-bhm-operational.bat --approve-recovery-for 17 18 28` at2026-10-16 23:33 CEST after exact operator approval. Fresh SQLite/2-assets backup and copied startup preflight passed. Graceful shutdown of confirmed18152; port and both locks released before activation. Independent readback: only3 approved updated timestamps+3 appended recovery events and ordinary IMAP last_success/next_sync changes; all other tables/schema/assets/.env unchanged,0 SMTP/admin attempts added.17/18/28 remain interrupted/manual-paused. Actual8000 browser confirms IMAP/SMTP ON, default dry-run and unchecked separate SMTP acknowledgement; no campaign start/resume. Last successful IMAP23:33:07 CEST, next23:48:07,0 contact changes/errors. Contacts5303 active/355 invalid/18 unsubscribed/0 bounced;76 active contacts with historical bounced_later still require evidence review. Operator25844 left running; QA ports free. See `docs/operational-preparation-2026-10-16.md`. Runtime statements below are historical.

IMAP/SMTP/sorting task (`BHM-IMAP-AUTORESUME-2026-10-16`): **operational activation completed under explicit approval; IMAP ON, SMTP forced OFF**, PID18152, localhost8000. Fresh consistent SQLite/assets backup and copied-database preflight verified, then one startup applied3 execution columns,3 IMAP tables/indexes and the approved3 recovery timestamps/events. Campaigns17/18/28 remain interrupted/manual-paused. First completed operational scan 2026-10-16 21:59:55 CEST:2173 messages,263 review cases,0 new hard bounce,0 unsubscribe,0 contact changes; next 2026-10-16 22:14:55 CEST. Independent SQLite readback preserves contacts,campaigns,snapshots,SMTP attempt history,selection and assets;0 SMTP/admin attempts added. Actual HTTP200 and read-only browser/IMAP panel PASS. Safe future launcher `start-imap-safe.bat`; no .env edit or external changes. Full automatic unsubscribe remains incomplete because info notifications are absent from the checked marketing folders. See `docs/imap-activation-2026-10-16.md`. Earlier runtime statements below are historical.

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
- Startup audit/timestamp churn fixed2026-10-18: safely interrupted/manual-paused queues remain unchanged. Real interruption/uncertain attempts still require review and explicit resume; migration remains a separate gate.
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

Current task C43-01–C43-08: `BHM-CLOSE43-RECOVERY-2026-10-18`.

| ID / Requirement | Evidence and result | Status |
| --- | --- | --- |
| C43-01 source/runtime | canonical root/main/origin and remote e0efc19 verified;no8000 listener/in-flight work at entry;campaign43 derived from SQLite;prior local docs preserved | PASS |
| C43-02 permanent closure |85 pending without attempts cancelled;1 fully verified4xx deferred row→smtp_failed;914 acceptances/918 attempts preserved;terminal/reservation=NULL/resume rejected | PASS |
| C43-03 Gmail completeness |4 full-history in:anywhere searches,52 pages,2505 unique MIME+6 RAW;final3-query head check no new IDs;campaigns36/37/38/40/41/42/43 | PASS |
| C43-04 exact Gmail delta |3 invalid+5 unsubscribe,3 later hard bounces,15 audits;2140 duplicates;278 unresolved+104 policy records retained;delayed260 unchanged | APPLIED |
| C43-05 SMTP diagnosis |4 definite451 4.7.1 [R7] queue saturation;historic900s cooldowns respected;no auto-resume exhaustion;exact reply/exception diagnostics+manual3600s R7 floor | PASS;remote unblock unproven |
| C43-06 idempotent startup |3 isolated ordinary starts/recoveries with no input/data delta;actual8000 startup recovery_ids=[] and no migration/recovery writes;uncertain/admin/cooldown gates preserved | PASS |
| C43-07 validation/readiness |126 tests,fake SMTP/IMAP,compileall;14 recipient+9 sync browser checks;actual10 GET-only checks,desktop/mobile;IMAP/SMTP ON,zero new attempts;QA ports free | PASS |
| C43-08 preservation/closeout |consistent backup+2 assets,exact simulation/full-row readback/replay,integrityOK/FK0;AGENTS/README/brief updated,one task entry;public source/aggregate docs only | PASS;Git receipt verified separately |

Current task G42-01–G42-07: `BHM-GMAIL-DOUBLECHECK-2026-10-18`.

| ID / Requirement | Evidence and result | Status |
| --- | --- | --- |
| G42-01 source/runtime | canonical root,main,origin;local and fresh remote89ccc2b;latest42 completed_with_errors;no in-flight SMTP/reservation/active IMAP;8000 and both lock types free | VERIFIED |
| G42-02 complete Gmail | three scoped in:anywhere searches without lower cutoff;20+17+1 pages;1980 unique MIME,4 RAW;available dates2026-07-02 to2026-10-18;final three-query head rescan no new IDs | COMPLETE at09:58:49 CEST |
| G42-03 deterministic evidence | existing parser/plan/apply;accepted campaigns36/37/38/40/41/42;recipient/Message-ID/time/source/token/snapshot checks;unsubscribe priority | VERIFIED;224 unresolved |
| G42-04 exact authorized delta |5 invalid+3 unsubscribed,5 later hard bounces,17 audits;policy/delay/review never change contact or send status;no source/parser change | APPLIED |
| G42-05 backup/readback/idempotency | fresh SQLite backup API includes committed WAL;2 immutable assets copied/hash-verified;exact simulation and independent full-table comparison;integrity OK/FK0;all six campaign replays no-op | PASS |
| G42-06 history/eligibility/tests | all dates/acceptance columns/attempts/snapshots/campaign and execution rows preserved;1148 inactive contacts excluded,4528 eligible;119 isolated tests+compileall | PASS;no app/QA startup |
| G42-07 context/privacy/Git | AGENTS/README reviewed unchanged;one new task register and one appended dated entry;aggregate report only;prior local docs/private data excluded from task commit | Validated for authorized main commit/push;final remote receipt recorded separately |

Current task F01–F08: `BHM-CLOSE41-OFFLINE-2026-10-17` (final operator instruction: offline only).

| ID / Requirement | Evidence and result | Status |
| --- | --- | --- |
| F01 root/Git/runtime | canonical root/main/origin;fresh remote d7462c6;8000 and SMTP/IMAP locks free;prior local docs preserved outside task commit | VERIFIED |
| F02 permanent41 closure | exact287 pending without any attempt→cancelled;campaign/execution completed_with_errors;reservation released;one closure audit;resume rejected on copy | APPLIED |
| F03 history/date preservation | all713 acceptance timestamps,1000 snapshots,attempts,assets and every contact last_sent_at preserved;all287 individually checked and eligible | PASS independent SQLite |
| F04 full Gmail analysis | in:anywhere,three queries,24 pages,1153 unique full MIME;one RAW fallback;accepted attempts36/37/38/40/41;source/recipient/Message-ID/time/token checks | COMPLETE;162 unresolved review reports |
| F05 authorized contact/evidence writes |12 invalid+5 unsubscribed;21 later-bounce projections;32 audits;no other contact fields changed;unsubscribed priority | APPLIED;956 duplicates skipped |
| F06 backup/readback/replay | WAL-consistent SQLite API backup+2 assets;exact simulation equality;integrity OK/FK0;Gmail and closure replay no-op | PASS |
| F07 tests/cleanup/manual readiness |119 tests;14+8 browser checks;compileall;QA stopped;no8000 startup/recovery;copied init no-op and recovery only17/18/28 | READY FOR USER MANUAL START |
| F08 context/publication | AGENTS reviewed unchanged;README/brief/report updated;one appended task Change Log entry;task-only public diff excludes private evidence and prior local edits | Authorized main commit/push;verify remote in closeout |

Current task L01–L08: `BHM-CLOSE-ACTIVATE-2026-10-17`.

| ID / Requirement | Implementation | Evidence | Status |
| --- | --- | --- | --- |
| L01 exact source/runtime | canonical root/main/origin/de7ef9e;8000 initially free;single standard operational launcher | OS process/port;runtime source commit38e16ef and hashes;GET backend acceptance | PASS actual21732 |
| L02 permanent40 closure |312 unattempted pending→cancelled;campaign/execution completed_with_errors;one closure audit;reservation NULL;resume rejected | exact expected-count/inflight/uncertainty gates;copy simulation;independent readback | APPLIED |
| L03 preserve real history |973 snapshots,661 acceptances incl199 later bounces;no contact/status/last_sent_at/attempt/asset deletion or change | full-row delta validator,backup hashes,readback,zero SMTP attempt additions | PASS |
| L04 fresh Gmail |01:40:38–13:40:38 CEST;2+1 pages,199 complete MIME;accepted campaigns36/37/38/40 evaluated |0 new invalid/0 unsubscribe/0 later-bounce changes;197 duplicates;1 new unmatched review | PASS;review retained |
| L05 autonomy |20s/1800s/300s and bounded safe retry/R6/unknown guards retained;normal transient1000 contacts without manual resume |1006 fake calls/1000 accepted/29600 virtual seconds/0 manual resumes;119 tests | PASS synthetic |
| L06 exact startup |post-close copied init no-op;only updated+one audit each17/18/28,40 unchanged |fresh DB+2-assets backup;actual full readback;.env/source hashes preserved | APPLIED within explicit approval |
| L07 operator readiness |IMAP ON/SMTP ON;new editor200;existing39 empty selection;500/page/last-send sort;40 resume disabled |actual8000 Chromium desktop/mobile GET-only;IMAP scan success/no error;QA ports released | PASS actual runtime |
| L08 context/Git/privacy |one new task entry;prior local docs preserved outside commit;private MIME/DB/logs/backups ignored |source and final context diffs reviewed;remote SHA verified at publication | DONE;no deploy |


Current task C01–C09: `BHM-CONTROLLED-2026-10-17`.

| ID / Requirement | Implementation | Evidence | Status |
| --- | --- | --- | --- |
| C01 root/process/Git | canonical root/main/origin/2965d80; elevated PID25844 identity; known instance stopped | OS listener/owner, remote SHA, private preserved earlier diff | VERIFIED |
| C02 campaign integrity |40:973 total,661 accepted,199 later bounces,312 pending,0 uncertain; no false send dates | full table diff, ledger/last_sent_at/older campaigns/readback | PASS |
| C03 Gmail completeness | fixed12h Warsaw/UTC;3 pages+notification search;290 MIME/286 DSN | private exports/input hashes;196 hard/42 delayed/14 policy/34 review/3 unsubscribe | PASS |
| C04 authorized writes |4 invalid+3 unsubscribe;7 later-bounce rows;10 audits;other tables/schema exact | verified backup+2 assets, simulation, replay and independent live readback | APPLIED |
| C05 SMTP continuity | list warning without loop;>=900s/backoff;bounded R6>=3600s probe;unknown isolation/config stop | fake-clock1000 mixed contacts/30020s/1003 calls/997 accepted/2 failed/1 unknown | PASS synthetic |
| C06 IMAP | EXAMINE/PEEK;full305 review diagnosis;41 oversized;8MiB bounded reports,partial MIME guard,re-analysis | live read-only connection, private copy, fake IMAP/regressions | PASS;info unsubscribe source still incomplete |
| C07 UI/new campaigns | monitor states/uncertain ETA;history+unfinished warnings;unknown blocked across campaigns;500/page,max1000 | browser UI/API/SQLite/reload, desktop/mobile,115 tests | PASS synthetic |
| C08 activation/cleanup | normal operational launcher;exact recovery17/18/28/40 required;no automatic resume | copied startup delta;no schema migration;port8000 stopped pending approval | NEEDS EXACT RECOVERY APPROVAL |
| C09 context/Git/privacy | context reviewed;one task Change Log entry;task-only public diff;private evidence ignored | staged/outgoing review and actual remote verification in Git history | Source publication independent of runtime |


Current task O01–O08: `BHM-OPERATIONAL-2026-10-16`.

| ID / Requirement | Implementation | Evidence | Status |
| --- | --- | --- | --- |
| O01 root/Git/ownership | exact root/main/origin; baseline e4df57f; user-owned18152/9152; earlier local docs preserved | remote ls-remote, CIM owner, prior-docs patch | VERIFIED |
| O02 backup/startup | consistent SQLite +2 assets; integrity/FK; copied init no-op, recovery only updated17/18/28 +3 audits | private preflight manifest, launcher in-memory gate | VERIFIED; exact operator approval applied once |
| O03 explicit launcher | IMAP+SMTP, SSL, identity/HMAC, canonical paths, bind-before-import, one worker; IMAP-only unchanged | new helper/BAT and isolated tests | PASS actual8000; IMAP/SMTP ON |
| O04 no automatic send | idle/account/uncertainty/admin/cooldown gates; exact recovery approval; dry-run default + separate SMTP ack retained | synthetic gates and actual8000 GET-only probe | PASS;0 mail sent |
| O05 contacts/unsubscribe | active5303/invalid355/unsubscribed18/bounced0; historical bounced_later430;0 new info unsubscribe found | read-only SQLite/Gmail, report | VERIFIED; reviews remain |
| O06 pacing/concurrency |20s/1800s/300s,>=900s/max3 safe resumes; R6/manual/restart/uncertainty protections unchanged |101 isolated tests; concurrent fake IMAP/SMTP;14+5 browser scenarios | PASS |
| O07 target/runtime/cleanup | actual8000 PID25844 IMAP/SMTP ON;17/18/28 paused;0 SMTP/admin attempts; QA ports free | GET-only browser, complete independent backup readback, netstat/ownership/locks | PASS; operator left running |
| O08 context/Git | context pack reviewed, one task entry; source-only commit/push; earlier local changes excluded | staged/outgoing privacy review and fresh remote SHA | Final Git evidence in report/history |

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
| I08 operational activation | approved fresh SQLite/assets backup,copy preflight,one startup3 columns+3 tables/indexes;3 recovery timestamps/events | actual8000 and independent readback; activation report | VERIFIED:IMAP ON / SMTP OFF;17/18/28 paused |
| I09 closeout/Git | safe future launcher,AGENTS/README/brief current,one dated task entry; private data excluded | activation report,89 tests,actual browser,process/port checks and Git | COMPLETE; operator8000 stays running; no deploy |

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

- 2026-10-17 — `BHM-CLOSE-ACTIVATE-2026-10-17`: Explicitly authorized permanent40 closure:312 pending→cancelled,completed_with_errors campaign/execution,one audit and SMTP reservation released;661 acceptances/199 bounces,all snapshots/contact timestamps/attempt history preserved,resume rejected. Fresh199-message12h Gmail scan evaluated36/37/38/40:0 new invalid/0 unsubscribe,197 duplicates,1 new unmatched review. Verified consistent DB/2-assets backup,exact simulation/replay/live readback and post-close startup copy.119 tests and1000-contact transient run1000 accepted/1006 fake calls/0 manual resumes passed;8 synthetic browser checks and actual8000 desktop/mobile GET-only acceptance. Standard launcher activated IMAP+SMTP ON,PID21732,only approved updated/3 recovery audits for17/18/28;40 unchanged,0 real SMTP attempts. New editor/empty selection ready,QA stopped. Terminal monitor shows cancelled counts and permanent closure. Context Pack Closeout complete;exactly one new task entry,source-only GitHub publication,earlier local docs preserved,no deploy. See docs/close-activate-2026-10-17.md.


- 2026-10-17 — `BHM-CONTROLLED-2026-10-17`: Reconciled290 Gmail messages from the fixed12h window for paused campaign40:4 invalid+3 unsubscribed,7 later bounces,10 audits;277 duplicates skipped. Verified consistent SQLite/2-assets backup, exact simulation/replay/live readback;973 snapshots/661 acceptances/312 pending and all send dates/attempt history preserved. Replaced50-failure loop with receipt-time quality warning;bounded transient backoff,R6 probe,unknown isolation and cross-campaign retry guard. Diagnosed all305 IMAP reviews,41 over1MiB;bounded8MiB fetch and UID-safe re-analysis preserve trust.115 isolated tests,1000-contact virtual-hours failures and desktop/mobile UI/API/SQLite/reload QA passed. Prior identified PID25844 stopped;8000 awaits separate exact recovery approval for17/18/28/40. No real SMTP send/resume,new campaign,Gmail mutation or deploy. Context Pack Closeout: one register/one task entry;validated source authorized for origin/main,earlier local docs preserved separately. See docs/controlled-iteration-2026-10-17.md.


- 2026-10-16 — `BHM-OPERATIONAL-2026-10-16`: Completed explicit prebound8000 IMAP+SMTP launcher, identity/SSL/HMAC and idle/admin/recovery gates.101 isolated tests,14+5 synthetic browser scenarios, target8000 read-only QA and TLS/AUTH235/NOOP250 passed without mail. After exact follow-up approval, fresh SQLite/2-assets backup `imap-sync-20261016T213229Z` and copied no-migration preflight passed; confirmed own18152 stopped gracefully, port/locks released, BAT started once at23:33 CEST as PID25844. Actual IMAP/SMTP ON; independent readback confirms only3 approved updated timestamps+3 recovery events and ordinary IMAP schedule changes; all other tables/schema/assets/.env unchanged,0 SMTP/admin attempts.17/18/28 stay interrupted/manual-paused; no campaign created/started/resumed/imported. Contacts5303 active/355 invalid/18 unsubscribed;76 active historical-bounce contacts remain for review. QA processes closed, operator left running. Context Pack Closeout and one-entry gate complete; source/docs Git handoff preserves prior local work/private evidence;no deploy. See task report.

- 2026-10-16 — `BHM-IMAP-AUTORESUME-2026-10-16` (2026-10-16 22:03 CEST): Implemented IMAP UID/UIDVALIDITY/audit/Gmail deduplication,20s/1800s/300s schedule,safe >=900s SMTP cooldown(max3;R6/auth/policy/uncertainty/50 recent failures blocked) and global recipient sorting.89 isolated tests and5 synthetic browser scenarios PASS. Following explicit approval, fresh SQLite/assets backup and copy preflight passed; one operational startup applied3 columns,3 tables/indexes and3 recovery timestamps/events. IMAP ON / SMTP forced OFF at8000,PID18152; actual HTTP/read-only browser PASS. First real scan 2026-10-16 21:59:55 CEST:2173 messages,263 review cases,0 new hard bounce/unsubscribe/contact changes; next 2026-10-16 22:14:55 CEST. Independent readback:24 appended events(3 recovery+21 unverified-report audits),2173 processed UIDs,222 evidence rows; no original contact/campaign/snapshot/attempt/selection changes,0 SMTP/admin attempts.17/18/28 remain paused; .env/assets preserved. Added `start-imap-safe.bat`; second launch rejected before recovery. Operator8000 left running; QA ports free. Source handoff only,no deploy. Full unsubscribe remains incomplete. See docs/imap-activation-2026-10-16.md.

- 2026-10-16 — `BHM-GMAIL-RECONCILIATION-2026-10-16`: Completed one authorized reconciliation for campaign38 after queue completion. Read555 unique Gmail messages with pagination/full MIME/RAW and final unchanged rescan;510 DSNs+10 verified unsubscribe events,72 uncertain reports retained privately. SQLite/assets backup and isolated simulation/readback passed;operational changes limited to354 invalid+10 unsubscribed contacts,430 bounced_later send projections and515 appended evidence events. All1000 SMTP acceptance timestamps,1004 attempt records and other tables/assets preserved;no migration. Existing ledger provides idempotent evidence;worker source now preserves unsubscribe during in-flight rejection. Four451/R6 failures specifically cite >50 failed deliveries/hour;minimum observed spacing20.0025s,15/5min,175/h,no schedule change.57 isolated tests and compileall passed. Port8000 already stopped and remains stopped;no SMTP send,restart,Gmail mutation,deploy or automation. Context Pack Closeout complete;exactly one task entry. Authorized commit/push scope excludes earlier local activation edits and all private evidence. See `docs/gmail-reconciliation-2026-10-16.md`.

- 2026-10-16 — `BHM-EMAIL-LAYOUT-2026-10-16`: Limited renderer delta: 600→720 px HTML/MSO/banner, full-width centered navy CTA with 6 px corners and a real 24 px table spacer, 8 px card corners with square Outlook fallback. Validated 47 isolated tests, compileall, 10 protected-content comparisons and 30 desktop/390/360 before/after renders; screenshots reviewed. No SMTP/send, operational SQLite/assets, editor, footer, unsubscribe, history, saved HTML or snapshots changed. QA browser closed; no test server started, QA ports free. Context Pack Closeout complete; exactly one task entry. Reviewed source/docs intended for authorized origin/main publication; no deploy or operational restart. See `docs/email-layout-qa-2026-10-16.md`.

- 2026-10-16 — `BHM-SOURCE-PUBLISH-2026-10-16`: User authorized commit/push of the accumulated reviewed BHM Mailer source to origin/main (modernization, recipient workflow, regressions, synthetic QA tools and runtime diagnosis). Release preflight confirmed exact root/branch/fetch+push remote and remote main at 37ce3a7; 39 source/config/docs/test files, no secret matches or private runtime paths. Existing evidence: 47 isolated tests, 14 browser scenarios and syntax checks. Git records the resulting commit and remote verification; this source publication does not authorize restart, operational writes, SMTP, deployment or activation of the blocked port-8000 workflow. Context Pack reviewed; existing activation gate remains in force.

- 2026-10-16 — `BHM-RECIPIENT-RUNTIME-2026-10-16`: Confirmed actual 8000 blocker: PID 15184 runs older POST-only selection API; browser GET /campaigns/32/selection returns 405 / Allow POST, matches server log and runtime OpenAPI; current JS is hash-identical to disk, no JS errors. Canonical GET/Add implementation already correct; gate preserved, no UI/backend rewrite. Added read-only runtime/browser and in-memory activation preflight tools; strengthened QA with direct SQLite reads. 47 isolated tests and 14 browser scenarios verified single contact and 500+500 through reload/summary. Copy init no-op; restart predicts only updated timestamps for executions 17/18/28 and three appended events. Operational 8000 remains BLOCKED pending explicit backup/restart/recovery authorization, SMTP OFF; no operational writes, real send, .env edit, commit/push/deploy. Context Pack reviewed; one entry for this task.

- 2026-10-15 — `BHM-RECIPIENTS-2026-10-15`: Replaced recipient autosave/page replacement with temporary checkboxes and explicit cumulative Add in existing SQLite; separate summary lists/removes saved recipients, Clear requires confirmation, atomic 1000 cap and final-send safeguards retained. Versioned JS and API compatibility gate prevent mutation against stale runtime. Fresh current baseline worked; legacy JS reproduced reported dead listeners, but the original user's browser cache was unavailable, so that incident cause remains unconfirmed. Validation: 47 isolated tests, compileall, JS syntax and 14 Chromium scenarios including marcin/reload/summary, 500+500, 500+300+search, limit 1001, two tabs, duplicate clicks, API errors and desktop/390/360. Operational DB hash/size/mtime unchanged; PID 15184 remains SMTP OFF, without restart. In-memory activation preflight predicts three execution-row changes and three new recovery events; separate approval required. No operational migration/campaign write, real send, .env edit, commit, push or deploy; HEAD main remains 37ce3a7.
- 2026-10-15 — `BHM-MODERNIZATION-2026-10-15`: Implemented local rich-text campaigns, validated CID banners, persistent 500/page selection (cap 1000), sequential 20-second SMTP worker with 5-minute breaks, manual pause/recovery, monitor and per-attempt/contact history. Validation: 40 isolated tests, 1000 fake-SMTP attempts with minimum 20-second spacing and five 300-second breaks, compileall and desktop/mobile browser QA. Operational SQLite, existing runtime, `.env`, real SMTP and Outlook acceptance were not changed/exercised. Git: local working-tree changes only; `main` HEAD and checked remote tip `37ce3a788ba1cd01476a016c8113db52bccd45e9`; no commit, push or deploy.
- 2026-10-15 — `BHM-HTTP500-2026-10-15`: Repaired stale port-8000 handler/new-template mismatch (`form` undefined) by loading the already-correct canonical source in a fresh runtime. PID 15184 remains running with SMTP OFF; actual `/campaigns/new` HTTP 200, editor/bold/link and 1440/390/360 screenshots PASS with no JS/asset errors. Added regression coverage: 41 isolated tests and compileall PASS; QA save/reopen/banner previews PASS. Verified consistent operational backup and no-op initialization. Following a verification-script incident and explicit second-start approval, the final full-table comparison found only 3 updated recovery timestamps and 6 authorized new events. Repeated recovery events reproduced in memory; mechanism unchanged. No contact/campaign/message-history changes, migration, `.env` edit, real SMTP, commit, push or deploy. Exactly one task entry retained.

- 2026-10-17 22:47:41 CEST — `BHM-CLOSE41-OFFLINE-2026-10-17`: Permanently closed41 with287 unattempted pending→cancelled and713 historical SMTP acceptances preserved (223 later bounces after reconciliation);all1000 snapshots,attempts,contacts and last-send dates retained,resume rejected,reservation released. Full-history read-only Gmail scan1153 complete MIME/24 pages:12 new invalid+5 unsubscribed,21 later-bounce projections,32 evidence audits,956 duplicate events skipped,162 unresolved reports kept private. Verified WAL-consistent SQLite/2-assets backup,exact simulation,independent287-row readback,integrity OK/FK0 and Gmail/closure replay no-op.119 tests,14 recipient+8 sync browser checks,compileall passed;own QA stopped. User declined8000 startup and3 updated/3 recovery events for17/18/28;no operational startup,SMTP send,new campaign,Gmail change,migration or deploy. Ready for manual standard launcher with fresh recovery confirmation. Context Pack Closeout complete;one task entry;authorized task-only commit/push to origin/main excludes earlier local edits and all private inputs/backups. See docs/campaign41-offline-2026-10-17.md.

- 2026-10-18 10:01:13 CEST — `BHM-GMAIL-DOUBLECHECK-2026-10-18`: One-shot offline Gmail double-check after actual campaign42 completion;1980 unique candidate messages,38 search pages,no lower date cutoff,full MIME/4 RAW,final rescan0 new. Existing deterministic parser matched accepted campaigns36/37/38/40/41/42. Applied5 invalid+3 unsubscribed,5 later hard-bounce projections and17 evidence audits;contacts now4528 active/1119 invalid/29 unsubscribed. Skipped1619 prior IMAP/Gmail reports+1 in-batch duplicate;196 delayed/89 policy/224 unresolved reports retained without disabling contacts;two new policy reports also left send status unchanged. Consistent SQLite/WAL+2-assets backup,exact copied simulation,independent all-row readback,integrity OK/FK0 and six-campaign replay no-op passed. All last_sent_at,SMTP acceptance/attempts,snapshots,campaign/execution rows preserved;1148 inactive contacts excluded.119 isolated tests and compileall PASS.8000 and SMTP/IMAP stopped before and after;no startup,recovery,migration,send,campaign creation/closure/resume or Gmail modification. Context Pack Closeout:AGENTS/README reviewed unchanged,one task register/one appended entry,aggregate public report only. Git:validated task-only docs for authorized origin/main commit/push;final remote SHA/receipt recorded separately after publication,prior local changes excluded;no deploy. See docs/gmail-doublecheck-2026-10-18.md.

- 2026-10-18 — `BHM-CLOSE43-RECOVERY-2026-10-18`: Permanently closed43:914 historical acceptances/368 later bounces,85 unattempted cancellations,1 definite451/R7 refusal retained as smtp_failed,0 pending/unknown,reservation released,resume blocked;all918 attempts/snapshots/send/contact dates preserved. Full-history Gmail2505 MIME/52 pages/6 RAW,3 invalid+5 unsubscribed,3 bounce projections,15 audits;2140 duplicates,278 unresolved/104 policy cases retained. Verified consistent SQLite/WAL+2-assets backup,exact simulation,independent full-row readback and replay,integrityOK/FK0. Fixed recovery idempotency without weakening startup gates;R7 exact diagnostics/manual1-hour local floor,nullable MIME headers handled.126 isolated tests,14 recipient+9 sync browser checks,10 actual8000 GET-only checks and compileall passed. Actual8000 PID24896 IMAP ON/SMTP ON with recovery_ids=[];no new SMTP/admin attempt,recovery timestamp/audit or schema change;only IMAP schedule updated. Own QA stopped;no new campaign,send,resume,Gmail mutation,secret/provider/DNS change or deploy. Context Pack Closeout:one register/one dated entry,reviewed source/aggregate evidence for authorized origin/main commit/push;prior local docs and all private data excluded. Final Git receipt recorded separately. See docs/closure43-recovery-2026-10-18.md.
