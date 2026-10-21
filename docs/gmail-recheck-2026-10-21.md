# Failed DSN correction and Gmail recheck — 2026-10-21

Task `BHM-GMAIL-FAILED-ACTION-2026-10-21`. **APPLIED, offline.** The user's objection was correct:the preceding26 reports were not delivery-delayed dispositions. This public report contains aggregates and sanitized diagnostic examples only. Complete Gmail MIME/RAW, recipient mappings, SQLite, manifests and backups remain private and ignored.

## Cause and correction of the previous report

All26 previously imported messages had `Action: failed` and `Status: 4.0.0`, with Undeliverable subjects and failure text. Fresh Gmail payloads and receipt timestamps match all26 original exports exactly. Their actual reasons are25 final network/transport failures and1 relay-policy failure. The old classifier returned delayed for every4xx status before considering the failed Action. That was an application classification bug.

[RFC3464 section2.3.3](https://www.rfc-editor.org/rfc/rfc3464.html#section-2.3.3) distinguishes failed, where the reporting MTA has ended its delivery attempts, from delayed, where attempts continue. It explicitly permits4xx diagnostics with either Action. The correction follows Action while preserving the diagnostic's meaning for address validity. A final network disconnection, DNS SERVFAIL/TIMEOUT or relay/configuration problem does not establish a nonexistent recipient mailbox.

The existing reconciliation module now classifies a verified failed+4xx report as `delivery_failed`, with no invalid-contact target. Policy/authentication/relay diagnostics retain priority and never project a bounce in the controlled import. A verified final transport failure updates the historical send projection to bounced_later while preserving original acceptance, attempts, timestamps and snapshots. An existing stronger final diagnostic is preserved. Untrusted/unmatched reports remain review-only; unchanged ensure_idle/ensure_paused_history and stopped-runtime gates still apply.

Legacy misclassifications receive one append-only correction linked through reclassifies_key and the shared failed-action-v2 canonical revision. Original audits are preserved. Gmail/IMAP copies and repeated imports deduplicate the correction. The earlier20Oct report has an explicit correction at the erroneous26-delayed statement;its original operational counters remain historical.

## Gmail scope and message-level verification

Verified canonical local root, main and source baseline7454cadfe81a68789968fe0da8edb033e9e5fad2. Earlier local activation-document changes were preserved. Canonical SQLite/assets paths were confirmed;all previous executions were terminal. Port8000 and SMTP/IMAP OS locks were free, with no in-flight SMTP or active IMAP scan. No operational process was stopped or started.

Four BHM-specific in:anywhere queries covered receipt dates from2026-10-20 00:00 CEST, including postmaster/DSN/undeliverable/failed-to-deliver/structured diagnostics and unsubscribe notifications. Initial discovery exhausted7 pages and129 unique candidates. A second complete7-page sweep at **2026-10-21 09:52:39 CEST** found5 additional reports:134 unique candidates overall. Metadata inspection excluded8 unrelated messages without reading their bodies. Temporary Gmail quota errors were followed by backoff;the completed sweeps are the coverage evidence.

Read fresh complete MIME for all **126 relevant messages**, including all previous26 and the5 new arrivals during analysis. Each fresh message had a distinct Gmail message ID and thread ID:126 messages in126 threads. Acquisition used individual message IDs and did not depend on a thread's visible headline. Among the125 DSNs,124 had Action:failed and1 Action:delayed;the remaining message was a verified unsubscribe notification for an already unsubscribed contact.

The fresh inputs were combined with2234 earlier relevant complete MIME exports and4 complete cached RAW fallbacks for attachment-backed reports: **2360 unique reports/notifications** in the reconciliation input. Relevant receipt timestamps span2026-10-08 17:04:18 through2026-10-21 09:52:29 CEST. Every decision rechecked receiver authentication, exact accepted SMTP Message-ID/recipient/campaign and receipt ordering;unsubscribe also checked identity, token and signed snapshot timestamp. No Gmail flags, labels, messages or folders were changed.

| Current126 message decisions | Count |
| --- | ---: |
| Verified final transport failures |114|
| Sender/authentication/relay policy |7|
| Review required:unmatched or insufficient evidence |3|
| Verified invalid mailbox |1|
| Verified unsubscribe, already applied to contact |1|

Raw DSN codes alone do not establish a verified campaign link. The3 review cases include the genuine delayed report and an unmatched final transport failure;neither was imported as verified invalidity.

## Actual operational delta

| Contact status | Before | New changes | After |
| --- | ---: | ---: | ---: |
| active |4140|−1|4139|
| invalid |1491|+1|1492|
| unsubscribed |45|0|45|

One new5.1.1 mailbox failure changed one contact to invalid. No new unsubscribe status or reactivation occurred. **144 historical send projections** were updated:143 verified final transport failures and1 verified invalid-address bounce. These are later delivery outcomes;original SMTP acceptance records and true send dates remain unchanged.

Appended157 evidence audits, including **77 linked corrections** of previous classifications:75 final transport failures and2 policy failures. All26 disputed reports are covered by those corrections.2187 previously processed report records were skipped (1581 IMAP/606 Gmail, mutually exclusive);classification corrections are counted separately from repeated evidence. Original audit rows were neither rewritten nor removed.

Across the full2360-report input, current classifications are143 final transport failures,1491 invalid-address/domain reports,62 verified unsubscribe reports,254 true delayed reports,124 policy reports,283 review records and3 no-action records. These totals include historical duplicates and must not be added to the skipped-duplicate count. The earlier77 misclassifications are now superseded by linked evidence;other ambiguous cases remain private for review.

## Validation, preservation and closeout

A fresh consistent SQLite backup API snapshot including committed WAL and a hash-verified backup of both immutable campaign assets preceded the approved simulation. Two earlier broader simulations were retained as superseded evidence and never applied. Only the final narrow plan was applied behind the port/SMTP/IMAP lock fence with unchanged-source/input/assets checks.

The independent read-only audit compared every table/field with the final simulation and backup. Only one contact's status/updated_at,144 historical send projections and157 appended evidence rows changed. Schema, original audits, all contact send dates, original accepted/sent timestamps, attempt ledgers, snapshots, campaign/execution rows, cancelled rows, selection, SMTP reservation, IMAP state and admin notifications were preserved. Both assets match;integrity **OK**, foreign-key errors **0**. All previous campaigns remain terminal. A complete replay across accepted-attempt campaigns36/37/38/40/41/42/43/44 proposes zero further changes. Actual eligibility excludes all1537 invalid/unsubscribed contacts and finds4139 eligible active contacts.

**134 isolated tests passed**, plus compileall. Regression coverage includes failed4xx versus true delayed,policy/auth/relay protection,missing Action,unchanged address status for transport failures,stronger final diagnostics,one-time legacy corrections,untrusted inputs and shared Gmail/IMAP deduplication. Synthetic transports only;no UI change or operational browser/SMTP test was needed.

AGENTS, README and PROJECT_BRIEF were reviewed and updated. The brief has one task register and exactly one new dated task entry. The20Oct aggregate report explicitly corrects its previous false delayed statement. Publication contains source/tests and aggregate documentation only;earlier local activation edits remain excluded. Runtime stays stopped;no send,new campaign,resume,restart,recovery,migration,provider change or deployment occurred. The cutoff above is a completed one-shot scan,not a background monitor or proof of recipient-domain invalidity from network failures.
