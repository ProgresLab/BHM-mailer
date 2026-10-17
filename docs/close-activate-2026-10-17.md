# Permanent closure, fresh Gmail scan and operational activation

Task `BHM-CLOSE-ACTIVATE-2026-10-17`. **DONE: actual operator application is available on127.0.0.1:8000, IMAP ON / SMTP ON; no campaign was started or resumed.** Root/main/origin matched ProgresLab/BHM-mailer, starting SHA `de7ef9e8140389942c3c7b9e622f82d643639cdb`. User explicitly authorized permanent closure of40, fresh Gmail reconciliation and the unchanged recovery writes for17/18/28. Earlier local documentation edits were preserved outside the task commits.

## Campaign40 and database preservation

- Campaign and execution are **completed_with_errors**. All **312 unattempted pending rows are cancelled**, without accepted_at/sent_at. No contact was marked invalid/sent by cancellation. One operator-close-v1 audit records the decision and exact cancelled send IDs privately. SMTP reservation40 is released. Completed execution rejects resume, including a tested backend invocation; the actual monitor disables Resume and states permanent closure.
- **661 historical SMTP acceptances** remain:462 accepted_by_smtp and199 bounced_later. Bounces are a subset of accepted messages. No pending, sending, rate_limited or delivery_unknown remains in40. All973 snapshots, attempts, assets, contact statuses and contacts.last_sent_at are preserved. Cancelled unattempted contacts remain eligible for a separate future selection when their contact status/history permits.
- Closure changed only312 send status/final_status_at/last_error fields, campaign status/completed_at, execution state/updated/problem, the reservation and one audit. No rows were removed, no schema migration occurred, and no SMTP attempt or unsubscribe notification was added.
- Fresh consistent SQLite backup API captured committed WAL; both immutable assets were copied and hash-verified. Backup: `backups/close-reconcile-20261017T114416024648Z/`, database SHA256 `816d1035a3b074840879b31ffda473a78b3f27dfedfeab16f05de8897b20b884`. Full copy simulation, exact per-table delta, committed independent readback, Gmail replay and closure replay passed; integrity OK, foreign keys0.

## Fresh Gmail scan

Scan anchor: **2026-10-17 13:40:38 CEST**, window **17.10 01:40:38–13:40:38 Europe/Warsaw**; UTC **2026-10-16 23:40:38–2026-10-17 11:40:38**. Existing Gmail connector, in:anywhere, all pages: main search198 results on2 pages; supplementary unsubscribe/source search3 results on1 page; deduplicated **199 complete MIME messages**. No OAuth, Gmail mutation or model-based mass classification.

All campaigns with immutable accepted SMTP attempts were evaluated:36/37/38/40. All reliable matches belong to40; reports without accepted Message-ID/recipient/source/time proof remain unresolved. No campaign ID was inferred from a subject. No required report MIME attachment was missing.

| Category in current scan | Count | New operational changes |
| --- | ---: | --- |
| Structured DSN |196| Reports, not contacts |
| Verified invalid-address/hard-bounce evidence |136|0 invalid; already reconciled |
| Verified unsubscribe |2|0 unsubscribed; already reconciled |
| Delayed |31|0 contact changes |
| Policy/reputation |7|0 contact changes |
| Review/unverified |22|1 newly seen unmatched report; no mutation |
| Ordinary response |1|No action |
| Duplicate prior Gmail/IMAP evidence |197|Overlaps the categories above |

**Fresh Gmail contact changes:0 invalid,0 unsubscribed;0 new later-bounce updates;0 appended Gmail evidence events.** Previously applied4 invalid/3 unsubscribe were not repeated. Contact totals remain5104 active/551 invalid/21 unsubscribed/0 bounced. The new unmatched report and ordinary response are retained only in the private report; they do not fabricate campaign/contact history. Automatic info-mailbox unsubscribe coverage remains incomplete; this one-shot Gmail read does not configure background Gmail.

## Autonomous SMTP validation

**119 isolated tests passed**, including new strict closure/inflight/unknown/count-conflict checks, snapshot/contact-history preservation, no-resume after closure, late Gmail DSN, and eligibility of unattempted cancelled contacts for a synthetic new campaign.

An additional1000-contact virtual campaign handled four separate account transients and two recipient transients: **1006 fake SMTP calls,1000 acceptances,0 manual resumes**,29600 virtual seconds (8h13m20s), no duplicate acceptance.20-second minimum spacing and300-second breaks after1800 active seconds remain. Existing1000 normal and1000 mixed-failure simulations also passed;>=900s safe cooldown, backoff, R6 bounded probe, configuration stops and uncertainty safeguards remain intact. No real SMTP test or provider-stage acceptance was attempted.

Synthetic browser regression:8 monitor/selection scenarios passed on8019 (fake IMAP, SMTP OFF). Actual GET/HEAD-only Chromium acceptance passed on8000: dashboard/new editor/contacts/history/40 monitor,661 accepted/312 cancelled/zero pending/unknown, Resume disabled, terminal notice/ETA, existing approved39 selection empty,500/page and last-send sort, selection API explicit_add_v1, served JS SHA equal to source, default dry-run and separate unchecked SMTP acknowledgement, IMAP active, desktop/mobile and zero JS errors. No operational selection was changed and no campaign was created. Screenshots were inspected privately; the terminal notice was corrected to avoid suggesting manual resume of a permanently closed campaign.

## Activation and operating instructions

Fresh post-closure backup `backups/close-activation-20261017T114647318853Z/`, database SHA256 `44a313ef0ac8b52f4187aefbdf42e23c1b5efe3fb2f1b15666284a6b0b77b055`, both assets verified. Copied init is a no-op; copied recovery predicts only updated for17/18/28 and exactly3 appended recovery events.40 is unchanged. User authorization covered precisely this scope.

Actual start used **start-bhm-operational.bat --approve-recovery-for 17 18 28**, hidden server window, one bind-before-import instance on127.0.0.1:8000, actual PID **21732**, SMTP ON / IMAP ON. Runtime Python source commit is `38e16ef7a6c09d6e76b176a3bfd279270c092e9e`; subsequent changes are terminal UI/static copy and closeout documentation, served without a second startup. Runtime source hashes and served JS were independently verified. No recovery of40 occurred.17/18/28 remain interrupted/manual_pause=1; the account reservation is NULL.

First verified IMAP scan completed after startup with UID2478,2478 processed messages,192 historical hard-bounce/contact changes,305 historical review decisions, no error. IMAP thread runs independently of SMTP; no new mailbox UID was available at the verification point. Background scanning remains scheduled. Independent complete SQLite readback found only the approved3 recovery timestamps/events and normal IMAP schedule changes versus the fresh activation backup. Contacts, all snapshots, campaign selections, attempts, SMTP/admin ledgers,40 closure, assets and .env were unchanged. Integrity OK, FK0.

Open **http://127.0.0.1:8000/campaigns/new** to prepare your own next campaign, maximum1000, with a new empty selection. Existing campaign39 was used read-only to verify an empty selection and sorting; it was not created or modified in this task. Inactive/unsubscribed and unresolved-contact protections remain enforced. The312 cancelled records are not presented as sent. No old reservation blocks a new campaign.

The application and computer must remain running; closing the browser is safe. After a future shutdown use the standard launcher, review the fresh preflight and authorize that future recovery separately if required. Do not launch a second instance while8000 is occupied. Own QA processes were stopped and8017/8018/8019 released; only the operator instance was left running. Source publication does not deploy anything. Private input/proposals/backups/runtime evidence stay under ignored output/closure-2026-10-17 and backups directories.
