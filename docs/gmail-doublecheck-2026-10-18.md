# Gmail double-check after campaign 42

Task `BHM-GMAIL-DOUBLECHECK-2026-10-18`. Closeout: 2026-10-18 10:01:13 CEST. **RESULT: DONE** within the authorized one-shot offline reconciliation. This public report contains aggregate results only; complete MIME, recipient decisions, manifests, SQLite and backups remain local and ignored.

## Source and operational preflight

Verified canonical BHM Mailer root, branch main and origin ProgresLab/BHM-mailer. Local HEAD and fresh remote main both matched `89ccc2b48aea3caae6756e085925ed5c48931e20`. Earlier unstaged activation documentation was preserved and excluded from this task commit.

Configuration resolved to the canonical data/bhm_mailer.sqlite3 and uploads/campaign_assets paths. Elevated OS checks found no 8000 listener or BHM operator process at entry. Canonical8000 port bind and SMTP/IMAP OS-lock fences passed; SQLite integrity/FK checks passed. No in-flight SMTP attempt, sending row, account reservation or active IMAP scan. Old 17/18/28 remain interrupted/manually paused. Two legacy pending admin notifications were preserved; none was sent or requeued. Runtime and configured sending capability are separate:with no operator process, both SMTP and IMAP are stopped.

The actual latest campaign is **42**, created2026-10-17 22:55:00 CEST, completed2026-10-18 05:35:13 CEST. Campaign and execution both remain **completed_with_errors**. All1000 historical SMTP acceptances remain:before 657 accepted_by_smtp+343 bounced_later; after 654+346. No pending/sending/uncertain row or new campaign was introduced. Earlier41 remains terminal with 713 acceptances (488+225 later bounces) and 287 cancelled; 40 retains661 acceptances and 312 cancelled. No campaign/execution row changed.

## Read-only Gmail scope

Three BHM-specific `in:anywhere` queries covered Undeliverable, DSN, mailer-daemon/postmaster, delivery failures/delays, structured diagnostic/recipient fields and info/marketing unsubscribe notifications. No lower date cutoff. Fully exhausted 20+17+1 search pages yielded **1980 unique candidates**, including **1655 report/notification records** and 325 no-action candidates. Read complete MIME for all 1980; four attachment-backed reports required complete RAW fallback. Message bodies were processed deterministically, without model-based classification; local deterministic parsing used the existing reconciliation module. No Gmail message, flag, label, folder or read state was changed.

Available matched-message dates:2026-07-02 09:59:44 through 2026-10-18 09:38:20 CEST. Final newest-page checks for all three queries at09:58:49 CEST found0 additional IDs. Scope means all accessible results of these queries at that cutoff, including older late reports; it does not establish access to other mailboxes or an ongoing subscription.

Existing parser, rec.plan/rec.apply and delta validation checked accepted-attempt campaigns36/37/38/40/41/42. Decisions require exact original recipient, accepted SMTP Message-ID, campaign/history, receipt time, structured Action/Status/Diagnostic-Code and receiver-authenticated source. Microsoft5505.4.1 required the existing complete recognized DBEB diagnostic. Unsubscribe required established info notification identity, source, campaign, token, snapshot timestamp and receipt ordering. Subject and From alone were insufficient. Existing unsubscribe always won.

| Status | Before | New changes | After |
| --- | ---: | ---: | ---: |
| active |4536|−8|4528|
| invalid |1114|+5|1119|
| unsubscribed |26|+3|29|
| bounced |0|0|0|

Five newly disabled addresses:two from41 and three from42. All three new unsubscribes belong to42. Eight distinct contacts changed. Five verified hard bounces updated historical delivery projections; SMTP acceptance columns, attempt records and every contact last_sent_at remained intact. 17 append-only reconciliation evidence events were recorded; no contacts were deleted.

| Report category | Count |
| --- | ---: |
| Verified invalid-address/domain evidence |1118|
| Verified unsubscribe evidence |28|
| Delayed |196|
| Sender policy/reputation |89|
| Unresolved review cases |224|
| No action |325|

The 1980 report decisions include1620 skipped duplicates:1070 previously reconciled by IMAP, 549 by Gmail, and 1 repeated within this input. Categories include previously known evidence and must not be added to the duplicate count. Among new report decisions:five invalid-address reports, eight verified unsubscribe reports (three newly changed contacts; others already unsubscribed), two policy reports, 21 unresolved and 324 no-action candidates.

Policy/delay/review cases never changed contact status. The existing parser's broad failed-DSN projection would also have changed two new policy sends; the private one-shot orchestration narrowed the allowed delta to verified invalid-address/hard-bounce sends. Those two send statuses were preserved and the evidence retained for review. Application/parser source and canonical deduplication keys were unchanged. Unmatched/unverified evidence remains in the private review report; linked review evidence can be audited without changing a contact.

## Backup and independent validation

Before writing, a consistent SQLite backup was made with SQLite's backup API, including committed WAL, and both immutable campaign assets were copied and hash-verified. A copied database simulated the exact narrow delta. The first broader simulation was retained privately as superseded evidence; only the second, narrowed simulation was applied. The private manifest contains full contact-level proposals, input/backup/asset hashes and the precise expected delta.

Apply held canonical8000 and all SMTP/IMAP lock fences, used BEGIN IMMEDIATE and refused changed source/input/assets/proposals. Only contacts(status/updated_at), five email_sends delivery projections and 17 appended execution_events changed. Schema and all remaining tables stayed identical. Committed operational data exactly matched simulation. A separate read-only audit independently compared every row/field, snapshots, SMTP acceptance and attempt history, campaign/execution rows, contact dates and both assets. Integrity **OK**, foreign-key errors **0**. Re-analysis of identical input for all six campaigns proposes no contact/send changes or new persisted evidence.

Real SQLite eligibility readback excludes all 1148 invalid/unsubscribed contacts and finds 4528 eligible active contacts. Existing source gates and isolated tests cover explicit recipient Add, new-campaign preparation, existing queue exclusions, reimport persistence, unsubscribe precedence and cross-source deduplication; no operational campaign was created to test this.

**119 isolated tests passed** in 133.689s, using synthetic SQLite/fake SMTP/IMAP. Compileall app passed. No real SMTP call, application startup, restart, recovery, migration or QA server was needed. Test output mentioning an operational launcher is from isolated mocked launcher tests, not live activation.

## Context, publication and limitations

AGENTS and README were reviewed; the application contract did not change, so neither was edited by this task. PROJECT_BRIEF contains one new task register and exactly one appended dated Change Log entry. The public change comprises that brief and this aggregate report only. Private operational evidence stays ignored under output/backups/data/uploads. Source publication does not deploy or start the local application. The source/publication baseline SHA is above; actual resulting main SHA and remote readback are recorded in the final chat and private Git receipt after commit/push.

224 ambiguous reports remain unresolved, including unverified recipient/source/history cases. 196 delayed and 89 policy reports do not establish invalid addresses. Automatic info-mailbox unsubscribe coverage remains incomplete; this one-shot Gmail scan supplies the accessible verified evidence. The two existing pending admin notifications remain for a separate operator decision. No SMTP/IMAP access, forwarding, external unsubscribe endpoint, credentials or provider configuration was changed. 8000 remains stopped; no process was stopped or started by this task.
