# IMAP / SMTP auto-resume / recipient sorting acceptance

Task: `BHM-IMAP-AUTORESUME-2026-10-16`.

## Result and operational boundary

Source implementation and isolated acceptance are complete. Operational activation is pending explicit approval for the additive migration and startup recovery. No operational schema/status change, SMTP send, campaign start/resume, `.env` edit or deployment was performed. Port 8000 was stopped at entry; historical PID14944 notes are not current runtime evidence.

Confirmed root: `C:\Users\info\AGENTS\BHM Mailer`; public repository `ProgresLab/BHM-mailer`, branch `main`, starting local and freshly read remote SHA `9fe9b11828df683a7d89f95a2a512f06c43dc404`. GitHub settings: no Actions workflows, webhooks or Pages configured. Source push is authorized; no deployment is requested. Prior local activation documentation is preserved in the worktree and excluded from this task's commit.

## Implemented contract

- Independent IMAP thread, one OS lock per canonical database/mailbox, persisted manual requests and scan guard. Verified TLS to `imap.one.com:993`, 20-second timeout, EXAMINE/PEEK only. No mailbox write commands. SMTP exceptions cannot stop this thread and IMAP exceptions cannot stop SMTP.
- 900-second interval after a complete scan; bounded catch-up batches of 200 messages / 60 seconds, numeric UID windows of 1000, maximum body 1 MiB. Cursor, UIDVALIDITY, message dispositions, unique evidence and counters are durable. No message-date cutoff; UIDVALIDITY replay deduplicates through evidence. The SQLite transaction covers only local processing/cursor commit, never network waits.
- Existing Gmail MIME/DSN parser extended for raw bytes. IMAP receiver evidence is accepted only inside the inspected one.com storage/ingress header boundary, with aligned DKIM, exact accepted Message-ID, recipient and receipt-time match. Unknown/forged/nested verdicts, conflicting Trace, missing match and ambiguous reports stay in review. Verified hard bounce updates `invalid`/`bounced`; unsubscribe has priority. Delays and policy/reputation reports never disable contacts. Original SMTP acceptances, snapshots and attempt history remain intact.
- Cross-source canonical keys recognize historical Gmail ledger entries even before the new tables existed; the existing offline Gmail prepare/apply delta validator remains compatible without new table writes. Untrusted copies cannot suppress later trusted reports. Audit never goes to GitHub; raw bodies are not retained in the new tables.
- One SMTP worker: 20 seconds between starts, 1800 active seconds then 300-second break. Manual pause, planned break and SMTP cooldown do not count as active work. Existing shared 20/5min and 200/hour rolling limits include admin notifications.
- Definite safe 4xx enters durable `auto_cooldown` for at least 900 seconds, or a longer numeric provider retry interval. Maximum three automatic resumes per queue, conservatively across error kinds. Manual pause wins even during an in-flight refusal. R6 / 4.7.*, reputation/policy/account/authentication, permanent refusals and uncertain delivery require the operator. OS singleton, identity fingerprint, contact status recheck, restart recovery and uncertainty gate remain enforced. Worker suspension over 120 seconds also blocks automatic resume. Account-wide 50 distinct failures/hour (definite SMTP failures and verified later bounces) block new attempts and auto-resume; repeats for one send count once.
- Monitoring distinguishes manual pause, standard break, SMTP cooldown and intervention; shows reason, resume time, countdown and ETA. IMAP dashboard/monitor panel shows successful/next scan, totals, review/alert counts and secret-free errors; manual scan is queued in SQLite and coalesced.
- Recipient SQL sorting uses an allowlist and stable contact-ID ties before LIMIT/OFFSET. Email/company/date ASC/DESC covers the full filtered set; 500/page and maximum 1000 stay intact. Never/oldest first for date ASC, newest first for DESC. Actual and legacy SMTP acceptance timestamps display in Warsaw time with campaign link; dry-run is excluded. Saved Add selections survive sorting and reload. `tzdata` supplies IANA timezone data on Windows; see [Python zoneinfo documentation](https://docs.python.org/3/library/zoneinfo.html).

## Evidence: isolated and read-only real source

- Full unit suite: **89 tests PASS**, isolated SQLite, fake SMTP/IMAP and controlled clocks. Coverage includes 900-second scan, UIDVALIDITY, late arrival, restart, duplicate Gmail/IMAP, socket loss after partial commit, fake DSN/authentication boundary, unsubscribe precedence, Trace conflict, active queue status recheck, singleton ownership, manual scan coalescing, cooldown/pause/R6/auth/5xx/unknown/retry cap, sleep recovery, global sorting and page boundaries, legacy history.
- 1000 fake SMTP attempts: 1000 unique queue rows, minimum start gap20 seconds, automatic break starts at active1800 seconds and then every1800 active seconds; 11 breaks, 300 seconds each, elapsed23300 seconds at20-second observation resolution. No real SMTP socket was used.
- Browser QA on synthetic8019: **5 grouped scenarios PASS**, no JS errors; header toggles, Warsaw date/Nigdy, Add → API → direct SQLite → reload → summary, cooldown cause/time/countdown, IMAP manual scan → direct SQLite → reload, desktop1440 and mobile390. Screenshots remain private in `output/sync-qa/`: `monitor-desktop.png`, `recipients-desktop.png`, `monitor-mobile.png`, `recipients-mobile.png`. Fake IMAP results in these screenshots are synthetic.
- Compileall, JS syntax and outgoing whitespace checks passed. Native multi-hour Windows running/sleep behavior is covered by controlled-clock tests, not an overnight field run.
- Actual TLS login reused the existing local SMTP password only after verifying the same mailbox username. No credential was printed/copied. Read-only source search:623 messages from the established provider notification sender; no matching info unsubscribe notifications in either of the two selectable mailbox folders. This is a bounded source search, not proof that every possible unsubscribe format is absent.
- Full real INBOX read applied **only on copied SQLite**:2173 messages;263 review cases;0 newly recognized hard bounces;0 unsubscribe;0 new contact-status changes. Existing Gmail evidence did not reapply status changes. Copy scan completed2026-10-16 **21:15:45 Europe/Warsaw**. This is not an operational sync time. The mailbox was not modified.

## Backup and approval needed

Fresh SQLite backup uses SQLite backup API; complete campaign assets copied and hashes verified (2 assets). Private backup manifests live in ignored `backups/imap-sync-*`. Operational database hash was unchanged across copy QA; integrity check `ok`, foreign-key errors0. Current preflight verifies no in-flight send/attempt, reserved account or queued/sending admin notification.

Final source copied-database preflight adds **3 columns** (`smtp_cooldown_until`, `auto_resume_count`, `failure_kind`), **3 tables** (`mail_sync_state`, `mail_sync_messages`, `mail_evidence`) and supporting indexes. Existing values are preserved. Startup recovery predicts only three execution timestamps (campaigns17/18/28) and three appended restart events; interrupted real queues remain manually paused.

Approval request covers: fresh backup if needed; this additive migration; those recovery writes; one localhost8000 launch with IMAP ON and SMTP forced OFF; automatic application of future unequivocal mailbox evidence. No real SMTP test/start/resume is authorized. While approval is pending, operational SQLite remains unchanged and no current application instance is claimed.

## Unresolved source coverage

Marketing IMAP currently lacks the established unsubscribe notification source. The existing controlled Gmail export and `tools/reconcile_gmail.py` is the smallest supplementary path without external changes. It requires a separately authorized acquisition/application when used; no recurring Gmail OAuth credential is available to this app. No forwarding, second mailbox password or public endpoint configuration was invented. Full automatic unsubscribe coverage remains incomplete and the UI states this explicitly.

Unknown provider header layouts and messages over1 MiB require review. IMAP scope is the configured folder (default INBOX); other folders are not automatically scanned. A loser second application instance does not take over a terminated owner's thread until restarted; OS lock prevents overlap, not failover. The computer and application must stay running; no Windows service or system scheduled task was installed.

## Handoff and cleanup

Exactly one task row is maintained in `PROJECT_BRIEF.md → Change Log`, alongside register I01–I09. Private data, backups, mailbox headers, runtime logs and screenshots are excluded from the public source commit. Source publication and remote SHA readback are recorded by Git and the final report. Final browser acceptance repeated on current source; own QA parent/child and browser closed. TCP probes confirm 8000/8017/8018/8019 are free; no own QA process remains. Operational startup awaits approval. No deploy.
