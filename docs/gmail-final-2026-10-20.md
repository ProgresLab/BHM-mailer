# Final Gmail reconciliation and previous campaign closure

Task `BHM-GMAIL-FINAL-CLOSE-2026-10-20`. Operational result: **DONE, offline**, 2026-10-20. This report contains aggregate results only. SQLite, contacts, MIME/RAW, recipient decisions, backups and manifests remain private under ignored output/backups/data/uploads paths.

## Verified source and runtime

Canonical root: C:\Users\info\AGENTS\BHM Mailer; branch main; origin ProgresLab/BHM-mailer. Local HEAD and fresh GitHub main both matched `f17890e9013804fa1ef89cb276c0d1143904c262` before changes. Git identity is ProgresLab with its GitHub noreply address. Earlier local activation documentation in PROJECT_BRIEF/README and an untracked activation report were preserved and excluded from this task's publication.

Configuration resolved to data/bhm_mailer.sqlite3 and uploads/campaign_assets. OS process inspection found no BHM operator process or listener on8000. Canonical port and SMTP/IMAP OS-lock fences passed before maintenance and independent readback. SMTP and IMAP were stopped at entry and remain stopped. No process was stopped or started by this task.

SQLite identified campaigns17/18/28/44 as the remaining interrupted/manually paused executions, with account reservation44, no in-flight or uncertain attempts, and two unchanged pending admin notifications. The user's follow-up explicitly authorized permanently ending all previous campaigns. Draft/approved campaigns without a started queue were left intact.

## Read-only Gmail coverage

Four BHM-scoped, full-history `in:anywhere` searches covered delivery failure/delay/DSN, mailer-daemon/postmaster, structured recipient/diagnostic fields and info/marketing unsubscribe notifications. All73 pages were exhausted, yielding2596 unique candidate IDs. Of these,339 irrelevant candidates were excluded from reconciliation using metadata; newsletters with unsubscribe links do not constitute a BHM unsubscribe notification. One incomplete/rejected bulk export was excluded; selected evidence was assembled separately without overwriting the originals.

The reconciliation input contained **2257 relevant complete MIME messages**:2175 preserved complete exports for unchanged Gmail IDs from the previous scan and82 newly fetched reports/notifications. Four attachment-backed reports used their preserved complete RAW representation. No unresolved text/report attachment remained.1047 relevant messages were received since2026-10-18 00:00 CEST. Relevant message receipt dates span2026-10-08 17:04:18 through2026-10-20 05:04:24 CEST, so late reports concerning older campaigns are included.

Additional newest-result checks for all four queries at08:14:58 and **08:20:15 CEST on2026-10-20** found0 additional IDs. The full pagination applies to initial discovery; these later checks inspect the newest100 results per query. Scope is the accessible results of these searches at that cutoff, not access to an unconnected mailbox or future mail. Gmail messages, labels, folders and read state were not modified.

The existing app/reconciliation.py and tools/close_and_reconcile.py performed deterministic classification across all campaigns with immutable accepted SMTP attempts:36/37/38/40/41/42/43/44. Decisions required exact recipient/original Message-ID/accepted attempt/time, structured DSN fields, trusted outer receiver authentication and routing. Unsubscribe required the established info notification identity, campaign, token, signed snapshot timestamp and receipt ordering. Legacy history lacking an exact accepted-attempt ledger was not reconstructed by assumption. ensure_idle and ensure_paused_history were unchanged.

| Contact status | Before | Net change | After |
| --- | ---: | ---: | ---: |
| active |4152|−12|4140|
| invalid |1490|+1|1491|
| unsubscribed |34|+11|45|

Twelve distinct contacts changed. Existing unsubscribed always won. One verified hard bounce updated a historical send projection to bounced_later; its original SMTP acceptance and all attempt records stayed intact.79 append-only Gmail evidence audits were recorded. No contact was deleted or restored to active; no real send/contact date was changed.

| Report category | All records | New records |
| --- | ---: | ---: |
| Verified invalid-address/domain |1490|1|
| Verified unsubscribe |61|22|
| Delayed |313|51|
| Sender policy/reputation |105|1|
| Review required |285|16|
| No action |3|3|

2163 previously reconciled report records were skipped:1584 from IMAP and579 from Gmail, with mutually exclusive attribution. These duplicates are included in the category totals, not additional messages. There were94 new report decisions. Of22 new verified unsubscribe records,11 changed contact status; the remaining contacts were already unsubscribed. Review, delay, policy/reputation and R6/R7 reports never changed contact status or projected a new bounce. No broad parser policy projection was applied.

## Permanent closure of all previous started queues

| Campaign | Unattempted pending cancelled | Additional handling | Final execution |
| --- | ---: | --- | --- |
|17|299|640 historical sent rows preserved|completed_with_errors|
|18|827|93 historical accepted rows preserved|completed_with_errors|
|28|266|47 accepted rows and2 legacy rate_limited rows preserved|completed_with_errors|
|44|472|27 acceptances preserved;1 complete definite451/R7 refusal→smtp_failed|completed_with_errors|

Total: **1864 unattempted pending rows cancelled**, four closure audits, account reservation released. All existing executions are terminal; no pending/sending/uncertain send remains. Existing terminal resume rejection applies to every closed queue. Eligible cancelled contacts remain available for explicit future selection, subject to their independently reconciled contact status.

Campaign28's two legacy4xx rows have no immutable attempt ledger. The existing closure mechanism gained the explicit exact-count option `--expected-preserved-refused`: it leaves every field of those rows unchanged while closing the campaign. It does not infer smtp_failed, SMTP acceptance, invalidity or new attempts. The ordinary refusal-finalization path still requires complete finished definite4xx history; default validation remains strict. Tests cover no-ledger preservation, no-op replay, terminal resume rejection and rejection of acceptance, uncertain outcomes, non4xx codes, conflicting counts or existing ledgers. Only unattempted pending rows are cancelled.

## Backup, simulation and independent validation

Each closure used a fresh SQLite backup API snapshot including committed WAL, a complete hash-verified copy of both immutable assets, a copied simulation, exact delta validation and independent committed readback. Campaign44's prepare/apply included the full verified Gmail input; later closures used an explicit empty Gmail input after that reconciliation was committed. No schema migration or application startup ran.

An independent read-only audit compared every table and field through all four backup/simulation pairs and the final operational database. It confirmed all contact send dates, historical sent/accepted timestamps, HTML/text snapshots, immutable SMTP attempts, admin notifications, selection and unrelated tables preserved. The precise combined delta is12 contacts,1866 send projections/cancellations,4 campaign rows,4 execution rows,83 appended audits and release of reservation44. Both assets match the original hashes. SQLite integrity **OK**, foreign-key errors **0**, schema unchanged.

A second complete Gmail import and all four closure replays on a fresh memory copy of final SQLite produced **zero changes**. Actual eligibility SQL finds4140 eligible active contacts and excludes all1536 invalid/unsubscribed contacts. No operational campaign was created to test eligibility.128 isolated tests passed with synthetic SQLite/fake SMTP/IMAP; compileall app passed. No UI changed and no operational browser/SMTP test was needed. No own QA server or listener remains.

## Context, publication and remaining limits

AGENTS, PROJECT_BRIEF and README were reviewed and updated for the actual result and exact-count legacy preservation contract. PROJECT_BRIEF contains one new Requirements & Acceptance register and exactly one new dated task Change Log entry. Publication consists of seven source/test/aggregate-document files; prior local activation changes remain outside the task commit. The resulting commit and remote SHA are recorded separately in the final Git receipt; source publication does not deploy or activate the app.

285 ambiguous reports remain review-only, including16 new reports.313 delayed and105 policy/reputation records do not prove invalid addresses. Two legacy campaign28 rows retain their original rate_limited projections and missing-ledger limitation; their campaign is terminal. The two pending admin notifications remain unchanged and unsent. Automatic info-mailbox unsubscribe coverage is still incomplete; this one-shot Gmail scan supplements available evidence. No forwarding, provider credentials/configuration, SMTP send, new campaign, resume, recovery, restart or deploy was performed.


## Incremental refresh at 14:10 CEST

Follow-up task `BHM-GMAIL-REFRESH-2026-10-20-1410`, 2026-10-20: the operator was still absent, port8000 and SMTP/IMAP locks were free, all previous executions remained terminal, and canonical SQLite retained4140 active/1491 invalid/45 unsubscribed contacts. Source HEAD was c74292feb4646734326597611360b928ec80ef12. Prior local documentation changes were preserved.

Four scoped Gmail searches covered08:00 through14:10:23 CEST, overlapping the previous08:20 cutoff. All four result pages were exhausted:28 unique candidate IDs. Metadata inspection excluded two unrelated newsletters without fetching their bodies. Complete MIME was fetched for all26 relevant reports; no missing report attachment or RAW fallback was needed. Their receipt timestamps span09:17:55–12:19:48 CEST. A temporary Gmail rate limit cleared after backoff; all subsequent queries completed. Checks at14:08:57 and14:10:23 found no new IDs.

**Correction on2026-10-21:** these26 reports had Action:failed and were incorrectly classified as delayed:25 final network/transport failures and1 relay-policy failure. Their fresh MIME matches the original export. The original import recorded no later-bounce projections because of this classifier bug;the [subsequent correction](gmail-recheck-2026-10-21.md) repairs the history without inferring invalid addresses. There were **0 new invalid, 0 unsubscribed, 0 later-bounce projections, 0 duplicates and 0 new review cases**. The existing reconciliation workflow appended26 evidence audits and changed no contact, send, campaign, execution, selection, sync or admin-notification row. Final contacts remain **4140 active /1491 invalid /45 unsubscribed**. Delays do not establish invalid addresses.

A fresh SQLite backup API snapshot including committed WAL and both hash-verified campaign assets preceded copied simulation and apply behind the stopped-runtime fence. Independent full-row readback matched simulation; integrityOK, foreign-key errors0, schema/attempts/snapshots/real send dates and all closures unchanged. Re-analysis across accepted-attempt campaigns36/37/38/40/41/42/43/44 proposed zero further mutations. Actual eligibility still excludes all1536 invalid/unsubscribed contacts.128 isolated tests and compileall passed. No SMTP, Gmail mutation, new campaign, resume, restart, recovery, migration or deployment occurred; operator and QA ports remain free. Only aggregate documentation is published; complete private evidence and backups stay ignored locally.
