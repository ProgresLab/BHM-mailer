# Gmail reconciliation and operator exclusion — 2026-10-22

Applied to canonical operational SQLite with the operator runtime stopped. This run implements the current human instruction to exclude verified final failures as `invalid`, including final network errors. It preserves technical diagnoses and does not represent those transport errors as proof of nonexistent mailboxes. Default automatic IMAP/Gmail classification is unchanged.

## Scope and Gmail coverage

- Fresh received-time window:2026-10-21 00:00–2026-10-22 01:42:57 CEST, overlapping the previous21Oct09:52 cutoff.
- Four scoped searches,each fully paginated,then the same four fully paginated final searches:14 pages,171 unique candidates. A further4-page post-apply search with cutoff overlap found0 new IDs through01:42:57 CEST;18 pages total.
- 162 relevant full MIME messages,including1 report arriving during analysis;9 unrelated messages excluded at metadata stage without reading bodies. No relevant text/report attachments were missing.
- Combined2462 unique messages after merging2360 cached historical MIME messages;4 existing RAW fallbacks retained. Fresh messages overlap60 cached IDs;102 report IDs are new to the combined input. Complete evidence spans8Oct17:04:18–22Oct01:36:13 CEST. Late arrivals are matched to historical accepted attempts,not inferred from campaign subject or thread headline.
- No Gmail changes or Outlook operations. The screenshot's final BANNER failure matched an exact accepted historical attempt;independent SQLite readback confirms that contact invalid.

## Applied operational results

| Result | Count |
| --- | ---: |
| New contact invalid statuses |531 |
| New contact unsubscribed statuses |0 |
| Final active |3608 |
| Final invalid |2023 |
| Final unsubscribed |45 |
| Prior duplicate reports skipped |1912 |
| Duplicate attribution:IMAP / Gmail |1390 /522 |
| Linked operator exclusion decisions |532 |
| Updated later-failure send projections |96 |
| Appended evidence/decision audits |534 |

Fresh technical categories:150 final network/transport failures,8 sender-policy failures,2 verified unsubscribe notifications and2 unverified external DSNs. Both unsubscribe recipients were already unsubscribed,so no new contact transitions were necessary.532 new operator decisions comprise239 delivery_failed,179 technically ambiguous final diagnostics and114 sender-policy records across the complete historical input. Existing invalid/unsubscribed statuses and repeated recipients explain why decisions and new transitions differ.

All2462 technical records:254 genuine delayed,239 delivery_failed,128 sender_policy,1491 invalid-address/domain reports,63 unsubscribe,284 technical review records and3 no_action.179 technically ambiguous but authenticated/exactly matched final reports receive the explicit operator exclusion;105 unresolved records remain:98 unverified DSNs,6 text-only reports and1 unverified unsubscribe. Of those,2 are in the current fresh window and come from external Mail Delivery System senders whose original source cannot be authenticated by the existing gate. They are not the verified one.com Postmaster reports. Their contact statuses were not inferred from the subject. Technical categories are evidence classifications;they do not undo operator invalid or unsubscribe statuses.

## Preservation and validation

- Canonical data/bhm_mailer.sqlite3;consistent SQLite backup API includes committed WAL. Both referenced immutable campaign assets backed up and hash-verified. Exact simulation completed before live mutation.
- 139 isolated tests passed;python compileall app passed. No SMTP connection was made by QA. New regressions cover old-report exclusion,new final policy/unknown diagnostics,unsubscribe priority,true delays,trust/matching gates and subsequent automatic IMAP deduplication.
- Independent committed readback matches every simulation row and schema;integrity_check=ok,foreign_key_check=0. Repeat import with the explicit flag adds no contacts,send changes or evidence;ordinary copies also deduplicate.
- Only contacts.status/updated_at,96 later-failure projection rows and534 appended execution_events changed. All original events,attempts,SMTP acceptance columns,sent/contact dates,snapshots,selection,admin notifications,campaign and execution rows preserved. All previous queues remain terminal.
- 2068 invalid/unsubscribed contacts excluded from new active selection;3608 eligible active contacts. No contact deletion or reactivation.
- Operator stayed stopped;8000 and SMTP/IMAP locks free. No startup,recovery,resume,new campaign,real mail,Gmail mutation or deploy. QA processes finished;QA ports released.

## Context Pack Closeout and publication

AGENTS.md,PROJECT_BRIEF.md and README.md reviewed and updated for the explicit manual policy and actual results. One current task Requirements & Acceptance register and exactly one new Change Log entry. Prior local user edits remain unstaged. Public changes contain source,synthetic tests and aggregate documentation only;SQLite,contacts,RAW/MIME,backups and private reports remain ignored. Source publication to main does not deploy or start the application;actual commit and remote SHA are verified separately.
