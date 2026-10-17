# Gmail reconciliation, SMTP continuity and IMAP — 2026-10-17

Task: `BHM-CONTROLLED-2026-10-17`. Source baseline `2965d80ae8d3276226b5df976339ef259dd5205b`, canonical BHM Mailer root, public `ProgresLab/BHM-mailer`, main. This report contains aggregate evidence only. Private MIME, recipient identities, tokens, databases, backups, raw reports and logs remain ignored.

## Operational evidence

Campaign **40** has **973** snapshots: **661** historical SMTP acceptances, **312 pending**, zero sending/uncertain/unfinished attempts. Before this import: 469 accepted_by_smtp and 192 bounced_later. After import: **462 accepted_by_smtp, 199 bounced_later, 312 pending**. The 199 bounces are a subset of the 661 acceptances, not additional sends. Other status counts are zero. Execution remains manual_paused, manual_pause=1; campaign remains sending, not completed. Its SMTP reservation remains intact.

Every pending row is identical to the fresh backup, with no accepted_at/sent_at and no attempted send. All contacts.last_sent_at and all 661 immutable accepted attempt records are preserved. Older genuine send history in other campaigns is preserved too. No real send, new campaign, resume, unsubscribe notification or Gmail mutation was performed.

Port 8000 initially still belonged to the previous operational PID25844. Sandbox process enumeration concealed this; elevated read-only inspection established the actual listener, command and owner. After the user confirmed closing the app and authorized closing occupied application ports, only this identified BHM instance was stopped. SMTP/IMAP activity was checked idle before stopping. Initial and fresh pre-apply backups used SQLite backup API (committed WAL included) and preserved both immutable campaign assets. Integrity OK, foreign keys 0, asset SHA256 matches.

Fresh apply backup: `backups/reconciliation-20261017T085213243858Z/`, database SHA256 `f7249ce15ebe9f83e55f345597322848f7a63e55bfd045aecb30d407d249b4b8`. The private manifest records input hashes and asset hashes, exact before/after changes, simulation and independent readback.

## Gmail window and counts

Fixed scan window, Europe/Warsaw: **2026-10-16 22:34:38 CEST to 2026-10-17 10:34:38 CEST**. UTC: **2026-10-16 20:34:38 to 2026-10-17 08:34:38**. Main in:anywhere search exhausted three pages (289 IDs); supplementary notification/source search added one ordinary response. All **290** MIME messages were processed deterministically locally, without model classification of the full mailbox. No relevant MIME body/DSN attachment was missing from the exports; RAW fallback was unnecessary.

| Evidence category | Unique events/reports | Meaning |
| --- | ---: | --- |
| Structured DSN | 286 | Distinct report Message-IDs |
| Verified hard bounce / invalid address | 196 | 192 previously reconciled by IMAP, 4 new contact changes |
| Verified unsubscribe | 3 | 3 distinct contacts, source/token/campaign/snapshot timestamp verified |
| Delayed | 42 | No contact changes |
| Policy / reputation | 14 | 11 prior IMAP events, 3 new later-failure evidence updates; no invalid classification |
| Review required | 34 | Unverified, ambiguous or unmatched reports; no speculative contact updates |
| Ordinary response | 1 | No action |
| Already reconciled evidence | 277 | Overlaps categories above; never add to them |

Contact mutations: **4 active → invalid, 3 active → unsubscribed**. Separately, **7 email_sends rows** gained verified bounced_later evidence and **10 execution_events** were appended. No other table or schema changed. Existing mail_evidence plus the shared execution_events ledger deduplicate Gmail/IMAP; replay produces zero changes. Final totals: 5104 active, 551 invalid, 21 unsubscribed, 0 bounced. Unsubscribe wins over bounce classification.

## SMTP behavior

- The 50-failure local threshold is a visible list-quality warning, audited at most once per hour. It does not repeatedly stop a resumed queue. SMTP attempt timestamps, DSN receipt time (Gmail internal_date / IMAP INTERNALDATE), report Date and reconciliation processing time remain separate. Historical import time never fabricates a recent failure.
- Definite safe transient refusals wait at least 900 seconds, respecting longer numeric server instructions. Three consecutive account-level automatic resumes are allowed; acceptance resets the episode. Recipient-level transients have a maximum of three attempts, with 900/1800-second backoff, then remain smtp_failed without acceptance while other contacts continue.
- A permanent recipient refusal continues the queue. Only evidence of an invalid address changes contact status; generic permanent errors, reputation, TLS and authentication never establish an invalid mailbox.
- R6 is account-wide: one persisted, bounded probe per queue after at least 3600 seconds; a longer server instruction wins. A second R6 requires operator/provider review. One hour is a conservative local waiting policy, **not a verified promise that one.com clears R6 in an hour**. Provider refusal is never bypassed. Existing pacing and rolling headroom remain below [published one.com sending limits](https://help.one.com/hc/en-us/articles/115005594205-What-limitations-apply-to-email-size-and-sending).
- An ambiguous transport result remains delivery_unknown/outcome_uncertain, without accepted_at/sent_at, and is excluded from retries and new-campaign selection/preparation/worker execution. Other pending contacts may continue; three consecutive uncertainties stop the account. Authentication, certificate, identity/configuration and other policy failures stop automatically.
- Exhausted queues can complete_with_errors while retaining unknown/error/skipped counts. Unknown attempts are never counted as accepted. Restart and manual pause still require explicit control; no automatic real resume follows restart.
- The monitor separates ordinary breaks, SMTP cooldown, provider waiting, manual pause, warnings, errors and uncertainty. It withholds ETA during uncertain provider/cooldown states. New campaigns start with empty selection; sorting, filters, 500/page and maximum1000 remain. A history link and unfinished-queue/unknown warning prevent false "sent" claims.

## IMAP findings and repairs

Live read-only EXAMINE/PEEK connection succeeded. Persisted UIDVALIDITY was1598218349, last_uid2478, UIDNEXT2479, no recorded sync error. Current initial counts:2478 messages,192 hard bounces/contact changes,305 reviews,11 policy alerts,0 unsubscribe. INBOX and INBOX.Spam were listed. No source/forwarding/account configuration was changed.

All **305 previously unresolved messages** were fetched for explicit re-analysis on a private copy. **41 exceeded 1 MiB**. The new bounded fetch expands recognized reports once to at most8 MiB, rejects partial MIME without advancing the UID cursor, and leaves larger/non-report content for review. This fixes confirmed truncation coverage without trusting subjects as classification proof.

Two authenticated one.com reports use a permanent **550 Invalid Recipient** diagnostic that the earlier classifier did not recognize. This is distinct from the oversized reports. The documented [Mimecast recipient-validation response](https://mimecastsupport.zendesk.com/hc/en-us/articles/34000709564691-Policies-Mimecast-SMTP-Error-Codes) supports the address classification; authentication, accepted Message-ID, recipient and time checks remain mandatory. These two contacts are included in the four Gmail invalid changes above.

`reanalyse_review` requires full bounded MIME, a known review UID and matching UIDVALIDITY, preserves the cursor and reuses the same evidence ledger. The diagnostic CLI writes only a copy. Review totals are historical and do not silently decrement after later resolution. Unknown one.com receiver segments, unaligned sources, missing accepted attempts and conflicting evidence remain review cases. External DSNs that Gmail can authenticate may still remain untrusted under the stricter one.com IMAP adapter. Nonstandard reports without sufficient evidence remain unresolved. Automatic unsubscribe coverage is still incomplete because the marketing mailbox lacks the established info notification source; this task's three Gmail notifications are reconciled separately.

## Validation and activation boundary

Private evidence: `output/repair-2026-10-17/` (scan/input manifests, exact proposals, copy simulation, applied readback, independent operational readback, IMAP diagnosis and test logs); browser evidence under ignored output/sync-qa and output/playwright. Automated tests use synthetic SQLite, fake SMTP/Gmail MIME/IMAP and virtual time; no provider SMTP send.

The 1000-contact mixed-failure simulation covers30020 virtual seconds,1003 SMTP calls,997 accepted,2 definite failures and1 unknown, with no duplicate acceptance; a separate1000-contact normal run preserves20-second minimum starts and300-second breaks after1800 active seconds. Synthetic browser QA exercises recipient checkbox/Add/API/SQLite/reload/summary, sorting/pagination, cooldown/IMAP, R6 without guaranteed recovery, completed_with_errors and desktop/mobile layouts.

Activation requires separate exact approval under task section11 and AGENTS: copied initialization is a schema/data no-op; recovery changes updated for17/18/28, and state manual_paused→interrupted plus updated/problem for40; it appends one recovery event for each of17/18/28/40. manual_pause=1 and all312 pending rows stay unchanged; reservation40 is preserved. Normal launcher remains **start-bhm-operational.bat**, IMAP ON + SMTP ON; safe IMAP-only launcher remains separate. This approval does not authorize resuming40, a new campaign or a test send. Until approval,8000 stays stopped and validated source publication remains independent of runtime activation. After activation, creating a new campaign is allowed; sending it still respects the retained unfinished-queue reservation.
