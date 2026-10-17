# Campaign41: offline closure and Gmail reconciliation

Task `BHM-CLOSE41-OFFLINE-2026-10-17`. Closed out 2026-10-17 22:47:41 CEST. **DONE within the user's final offline scope.** Runtime activation was explicitly declined; this is ready for the user's manual startup, not a live-runtime claim.

## Verified result

Canonical project: `C:\Users\info\AGENTS\BHM Mailer`, `ProgresLab/BHM-mailer`, branch `main`. Entry HEAD and fresh remote main: `d7462c6e06687ddffd3f75d2cde1d2d82540e741`. Existing local activation documentation changes were saved privately and remain outside this task commit.

At entry,8000 had no listener and there was no BHM process to stop. The old runtime manifest/PID21732 is historical. Port bind and SMTP plus IMAP OS-lock fences succeeded;no in-flight/unknown SMTP attempt or pending admin notification existed. Operational database is `data/bhm_mailer.sqlite3`;assets are `uploads/campaign_assets`. No migration or .env edit.

Campaign41 was identified from SQLite, not inferred from the screen:created2026-10-17 14:01:25 CEST,1000 snapshots,713 accepted messages (505 accepted_by_smtp+208 bounced_later),287 untouched pending. Execution was interrupted/manual_pause=1 and held reservation41.

`tools/close_and_reconcile.py prepare/apply` permanently changed campaign and execution to **completed_with_errors**, released only reservation41 and appended one operator-close-v1 audit. All287 pending rows are now **cancelled**,without accepted_at/sent_at,attempt history or contacts.last_sent_at changes. Terminal resume was rejected on an exact in-memory copy;closure replay is a no-op. No accepted recipient was cancelled. All287 contacts remain active/eligible for a separate explicit selection;none had older send rows in this database. Across the whole database,every existing contact last_sent_at and prior attempt/SMTP/admin/selection history were compared and preserved. All1000 snapshots and both immutable assets remain intact.

After verified later reports,41 has490 accepted_by_smtp+223 bounced_later+287 cancelled. **713 historical acceptances remain**;a later bounce does not negate SMTP acceptance. No pending,delivery_unknown or sending row remains in41. Older paused campaigns17/18/28 were preserved without recovery writes.

## Gmail scope and decisions

Existing Gmail connector was available. Three scoped `in:anywhere` searches without a lower date cutoff covered BHM delivery reports,mailer-daemon/postmaster,Undeliverable,DSN,delayed,one.com and info/marketing unsubscribe sources. Completed12+1+11 search pages: **1153 unique messages**,full MIME read for every ID;one report needed RAW fallback. Search completion2026-10-17 22:41:27 CEST;final newest-page rescan22:46 CEST found0 new IDs. Coverage includes the whole current-campaign window and available older delayed reports matching these queries;it is not a claim about inaccessible mailboxes or an automatic Gmail subscription.

The existing deterministic MIME/DSN reconciliation parser checked accepted-attempt campaigns36/37/38/40/41,exact original recipient/Message-ID/receipt time,routing and aligned Gmail receiver DKIM. Verified unsubscribe additionally required info source,campaign,token and signed snapshot timestamp. Subject alone was never sufficient. Microsoft5.4.1 required the complete recognized DBEB diagnostic;temporary,policy and unverified reports did not disable contacts. Existing unsubscribed statuses were preserved.

Distinct report/message decisions across the matching campaign plans (categories overlap the duplicate count):

| Category | Count |
| --- | ---: |
| Verified invalid-address evidence |768|
| Verified unsubscribe evidence |20|
| Delayed |129|
| Sender policy/reputation |67|
| Unverified/unresolved reports |162|
| No action/ordinary messages |7|
| Already-seen or repeated evidence |956|

Actual new contact changes:**12 invalid+5 unsubscribed** (36:1 unsubscribe;38:6 invalid;41:6 invalid+4 unsubscribe). Final contact totals:4879 active,771 invalid,26 unsubscribed.21 historical send projections were updated to later-bounce evidence (6 in38,15 in41);32 reconciliation audits were appended. Reports and provenance remain in private input/manifests;unmatched reports remain review-only. No contacts were deleted and Gmail messages/labels/folders were unchanged.

## Backup, simulation and independent readback

- Pre-write backup:`backups/close-reconcile-20261017T204331204995Z/`,SQLite SHA256 `4b77d40285eeeff96e35ee7c419fd588f84541e33037b01bbcc79a493cc382c3`. SQLite backup API includes committed WAL;both assets copied/hash-verified.
- Prepare simulated reconciliation plus closure,checked every table/schema and exact delta,then verified committed-copy Gmail and closure idempotency. Apply required unchanged source/input/assets and independently matched the whole operational database to the simulation.
- Separate read-only SQLite audit checked every one of287 cancelled rows,no attempts/no dates,all713 accepted rows,contact last_sent_at across all contacts,snapshots,ledger/selection preservation,unsubscribed priority,schema and assets. Integrity **OK**,foreign-key errors **0**. Re-import across36/37/38/40/41 proposes no contacts,sends or new persisted evidence;closure replay makes no change.
- Fresh post-write startup backup:`backups/imap-sync-20261017T204540Z/`,SQLite SHA256 `4d2c0249ffab976c13596d30197e3ba9fa33d236248f0aaada64ec263386482b`. Both assets verified;copied init requires no migration. Copied recovery changes only updated plus one audit each for17/18/28.41 remains terminal.

## Tests, cleanup and manual use

**119 isolated unit tests passed**,including hard bounce,unsubscribe priority,delayed/policy/false reports,IMAP/Gmail deduplication,idempotency,inactive selection exclusion,terminal closure and resume rejection. Fake SMTP simulations include1000 contacts and bounded temporary failures;no real SMTP send occurred. `python -m compileall app` passed.

Chrome with existing repository harnesses: **14 recipient browser scenarios** (UI→API→SQLite→reload→summary,500+500,1000 limit,explicit Add/Remove/Clear,blocked inactive contacts,desktop/mobile) and **8 sync/sort/monitor checks** passed on synthetic8018/8019. The default bundled browser was unavailable;installed Chrome was used. No dependency installation or source repair was needed. Both own QA PIDs11904/21252 were verified and stopped;8000/8017/8018/8019 have no listener. The existing approved39 has an empty selection;no campaign was created (maximum ID41 unchanged). Source guarantees a new campaign starts with its own empty selection.

The user explicitly declined operational startup and recovery now. **IMAP and SMTP processes are stopped**;configuration preflight confirms both are ready for standard operational mode. There is no live8000 UI/IMAP scan acceptance in this offline task. Automatic info-mailbox unsubscribe coverage remains incomplete;this Gmail reconciliation is a one-shot supplement.

For later manual startup,use **`start-bhm-operational.bat`** in the canonical root. With the currently verified state,the launcher requests **`RECOVERY 17,18,28`** before writing3 updated timestamps and3 audit events;review a fresh preflight/backup at that time. A changed scope requires a new review. This acknowledgement leaves queues interrupted/manual-paused and never starts/resumes a campaign. SMTP is enabled only after that explicit operational startup;new campaign selection and real-send confirmation remain separate operator actions.

## Context and Git

AGENTS reviewed;responsibilities unchanged. README/current status and the single Requirements & Acceptance register updated;exactly one new append-only Change Log entry. Public task artifacts contain aggregate results only. Private MIME,contacts,SQLite,backups,manifests,per-recipient audit and logs stay ignored under output/backups/data/uploads. Task-only staged/outgoing diff and secret/private-data checks precede the authorized main commit/push;the final response records actual remote SHA. Prior local activation edits remain unstaged. No deployment or external-service configuration was performed.
