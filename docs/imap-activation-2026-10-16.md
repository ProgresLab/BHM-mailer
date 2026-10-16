# Approved operational IMAP activation — 2026-10-16

Task continuation: `BHM-IMAP-AUTORESUME-2026-10-16`. Operator explicitly approved additive migration, three recovery timestamp/event writes, one localhost8000 startup with IMAP ON / SMTP OFF and automatic application of unequivocal verified evidence. This report supersedes prior pending-activation statements; it does not authorize SMTP sends or queue resume.

## Actual runtime

- Root/source: `C:\Users\info\AGENTS\BHM Mailer`; main source baseline `aef19eaaf53cdaec743cb52907318f0da1415685` plus the reviewed safe launcher/documentation delta. No core application source changed during activation.
- One application startup at **2026-10-16 21:56:40 CEST**; listener/application PID **18152**, venv bootstrap parent9152. Launcher: `tools/run_imap_safe.py`, the helper invoked by `start-imap-safe.bat`. CWD/source and canonical `data/bhm_mailer.sqlite3` / `uploads/campaign_assets` paths independently recorded.
- URL: <http://127.0.0.1:8000>. SMTP **forced OFF** by the launcher before importing mail settings; IMAP **ON**, configured. HTTP200 on dashboard,new campaign editor,existing35 summary/recipients and IMAP API. Actual DOM confirms SMTP option disabled; no submit/resume was clicked.
- The helper binds8000 before application import. A second invocation was rejected before migration/recovery; the original PID remained running and only the approved three restart events exist relative to backup.
- Current hidden process is intentionally left running. After a future computer restart use `start-imap-safe.bat` and keep its window open. It performs no dependency install and leaves `.env` untouched. Ordinary `start.bat` retains its previous configuration behavior and is not the safe-mode launcher.

## Backup, migration and independent database readback

Fresh consistent SQLite backup and both campaign assets: private `backups/imap-sync-20261016T195543Z`. Schema/all rows and asset hashes matched the live source immediately before startup. Copied initialization/recovery passed, integrity `ok`, foreign-key errors0; no active/reserved queue, in-flight attempt or queued/sending admin notification was present.

Startup added the approved3 execution columns,3 IMAP tables and supporting indexes. Independent readback uses a new SQLite backup connection and compares every original table/field with the pre-activation backup:

| Surface | Actual delta |
| --- | --- |
| Contacts, campaigns, snapshots/email_sends, attempts, notifications, selection, recovery decisions, SMTP control | All original rows unchanged |
| Existing campaign_execution | Only `updated` for17/18/28; three new columns have default values |
| execution_events | +24: exactly3 approved recovery events and21 appended unverified-DSN review audits |
| mail_sync_state | 1 mailbox state |
| mail_sync_messages | 2173 durable processed UID records |
| mail_evidence | 222 private evidence/review records |
| Real SMTP / admin notification attempts | +0 / +0 |
| Asset files and `.env` | Hash-identical to baseline |
| Integrity / foreign keys | `ok` /0 errors |

Campaigns17/18/28 remain **interrupted, manual_pause=1**; SMTP account reservation remains NULL. No old queue resumed. Original acceptance/attempt records, historical statuses and snapshots were preserved.

## Real IMAP result

First and last completed operational sync at verification cutoff: **2026-10-16 21:59:55 CEST**. Next persisted sync: **2026-10-16 22:14:55 CEST**, exactly900 seconds later.

| Operational counter | Result |
| --- | ---: |
| Newly processed messages | 2173 |
| Newly recognized hard bounces | 0 |
| Verified unsubscribe | 0 |
| Review cases | 263 |
| Reputation/policy alerts | 0 |
| Contact-status changes | 0 |
| Last error | None |

The263 review cases comprise222 evidence records and41 oversized messages (over1 MiB) retained as review dispositions without loading the full body.21 of the evidence records link to history but lack sufficient verification and are also appended to the existing campaign audit ledger. No uncertain report changed a contact. Prior Gmail evidence was not applied again. Source mailbox access used certificate-verified TLS/EXAMINE/PEEK and did not modify flags/messages.

## Validation and cleanup

The existing89 isolated tests passed again after activation(64.335 seconds): synthetic SQLite,fake SMTP/IMAP,controlled clocks; no operational test mutation. Compileall for app and the new launcher passed. Actual browser QA permits GET/HEAD only, confirms panel active/HTTP200/SMTP option disabled/selection handshake and original selected count1. No JS errors. The read probe waited for initial catch-up before final verification; no application restart was performed.

Private screenshots: `output/imap-activation/imap-panel.png` and `recipients-redacted.png`(contact/content fields masked in screenshot DOM only). Browser closed in finally; no QA server was started. Operator8000 stays active;8017/8018/8019 are free. Runtime/backup/readback/browser logs remain private under ignored output/backups directories.

## Remaining limits

Full automatic unsubscribe coverage remains **incomplete**: the checked marketing folders had no matching established info notification source. Existing separately controlled Gmail import remains available; no new credential, forwarding rule, second account or public endpoint change was made. Unknown provider routing,unmatched reports and bodies over1 MiB remain review-only. No real SMTP transport/send, campaign start/resume, deployment, service or OS scheduled task was performed. Closing the app or sleeping the computer interrupts background work; no autonomous real queue resume after restart.900-second scheduling is validated with controlled clocks and persisted next-sync time; a second natural fifteen-minute production cycle was not required for this activation acceptance.

Context pack reviewed; the original task retains exactly one Change Log entry and register I01–I09. Public Git handoff includes only the safe launcher and factual documentation; excludes all private evidence/data and prior unrelated activation edits.
