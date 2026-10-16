# BHM Mailer — operational preparation, 2026-10-16

Task: `BHM-OPERATIONAL-2026-10-16`. Result: **PARTIAL — source ready; controlled activation awaits exact recovery approval**. No mail sent, campaign started/resumed, contact imported/reactivated, operational migration, deployment or `.env` edit.

## Runtime and activation boundary

Verified root/CWD/source: `C:\Users\info\AGENTS\BHM Mailer`, `main`, origin `ProgresLab/BHM-mailer`, local and freshly checked remote baseline `e4df57fbe8910cbca1c891035451e4e5eb530fd4`. Git identity is the existing ProgresLab noreply identity. Earlier local README/brief edits and untracked activation report were preserved separately from this task's source publication.

Actual listener: <http://127.0.0.1:8000>, PID18152 (venv bootstrap9152), owned by the current Windows operator, command `tools/run_imap_safe.py`, created21:56:40 CEST. Runtime metadata independently identifies canonical `data/bhm_mailer.sqlite3` and `uploads/campaign_assets`. IMAP ON/configured/active, SMTP forced OFF. Existing Python process predates this launcher delta; it has not been restarted. Operator can prepare drafts; real SMTP is not yet available in that process. Read-only browser confirms SMTP disabled, default dry-run and unchecked separate SMTP acknowledgement.

New recommended normal launcher: **`start-bhm-operational.bat`**. Its helper binds8000 before importing application modules, forces IMAP/SMTP ON and SSL transport for this process only, validates complete one.com identity, Reply-To, envelope sender, HTTPS unsubscribe and local signature availability. It uses one Uvicorn instance without reload and the existing independently locked SMTP/IMAP managers. A second invocation against the current occupied8000 was rejected without recovery. Safe `start-imap-safe.bat` remains unchanged; legacy `start.bat` is explicitly documented as setup-only because its old Uvicorn command lacks prebind protection.

## SQLite, assets and startup effects

Fresh consistent SQLite API backup: private `backups/imap-sync-20261016T205328Z/`, with both immutable campaign assets. The API includes committed WAL contents; no WAL file existed at inspection. Backup SHA256 `d3182b0d1026394da474003624acb3f5e28e069ae5d0ebd546cc5d690fe157b8`. Copied integrity `ok`, foreign keys0, asset hashes match. All draft/snapshot asset references exist.

Copied `init_db()` is a schema/data no-op. Existing `recover()` changes **only `campaign_execution.updated` for17/18/28 and appends3 `execution_events`** (one “Restart: wysyłka wstrzymana…” each). States remain `interrupted`, `manual_pause=1`; no automatic resume. The launcher checks this exact shape on an in-memory copy and requires a matching explicit acknowledgement. Any migration, changed queue state, unexpected audit, unresolved/inflight work or notification stops activation before `app.main` import. No attempt was made to fix/repeat the known recovery mechanism in this task.

Normal IMAP manager startup also resets its persisted `scanning=0,next_sync=0` to catch up immediately; ordinary scheduled scans then update cursor/scheduling/evidence under the existing authorized IMAP rules. This is distinct from the six recovery writes. While the original instance continued running, comparison against the fresh backup found only normal `mail_sync_state` scheduling changes; all other tables, SMTP attempts, contacts, history, selections and assets were preserved. This task did not write operational SQLite. Fresh backup/readiness must be repeated immediately before a later approved switch if state has changed.

## Queue and SMTP readiness

- 17/18/28: interrupted/manual pause; pending299/827/268 respectively. No other interrupted execution, active attempt, unresolved SMTP outcome or account reservation. Completed36/37/38 stay completed.
- No unsent administrative notification or notification attempt. Two legacy records have status `pending` **but `notification_sent=1`**; they must not be counted as pending deliveries or requeued. The operational launcher blocks any unsent/queued/sending/uncertain admin record and preserves it for operator review.
- Stored account cooldown has expired. No current local50-failure/hour guard. Historical four451/R6 refusals remain in the ledger; no claim that an expired timer clears an external provider restriction.
- Existing marketing identity matches one.com `send.one.com:465`, SSL, From/envelope marketing, Reply-To info, complete password and unsubscribe-signature configuration. The existing465 transport already selected SSL even though the explicit flag was false; the new process pins `SMTP_USE_SSL=true` / `SMTP_USE_TLS=false`, without editing `.env`.
- Optional live readiness: certificate-verified SSL, EHLO250, AUTH235, NOOP250, QUIT. **No MAIL FROM, RCPT TO, DATA or message.** This proves connectivity/login only, not deliverability or clearance of recipient-stage R6. Worker activity in SMTP+IMAP mode is covered by synthetic tests; operational SMTP worker remains in OFF mode until approval.

## Contacts and unsubscribe evidence

| Unit / scope | Count |
| --- | ---: |
| All contacts / active |5303 |
| All contacts / invalid |355 |
| All contacts / unsubscribed |18 |
| All contacts / bounced |0 |
| Campaign38 contacts / invalid |354 |
| Campaign38 contacts / unsubscribed |10 |
| Campaign38 contacts / active |636 |
| Campaign38 historical send records / bounced_later |430 |
| Campaign38 historical send records / accepted_by_smtp projection |570 |
| Campaign38 historical accepted attempts / total attempts |1000 /1004 |
| Active contacts linked to a historical bounced_later send |76 |

Counts of contacts, send records and evidence events are different units. Do not add them. All430 later-bounce records retain original acceptance history;354 link to invalid contacts,76 remain active because the evidence did not justify invalidating them. Prior72 ambiguous reports remain for manual review; this task does not resolve or equate them to72 distinct contacts. IMAP still shows263 review dispositions from its initial2173 messages, a different scope including oversized/unmatched evidence. Review these before including affected active recipients in another campaign. No contact was restored to active due to absence of a bounce.

Contact statuses invalid/bounced/unsubscribed are excluded by selection, final confirmation and per-attempt worker eligibility; tests include status changes after preparation. A new campaign has an empty separate selection. Global last-acceptance ASC puts “Nigdy” then oldest first;500/page and maximum1000 verified in browser/SQLite. Historical bounced_later alone is not a contact-status exclusion: the76 active contacts above remain selectable pending review.

Read-only Gmail follow-up: complete searches (no next page token) for established info unsubscribe notifications and the prior broad BHM unsubscribe query. The info-source search returns11 existing messages (10 from campaign38 plus the earlier self-test); none after the prior reconciliation cutoff18:40:27 UTC. The one broad post-cutoff candidate was an unrelated newsletter, not an unsubscribe. **0 new matching info unsubscribe found; no import or Gmail mutation.** Coverage remains limited to connected Gmail/forwarded info and the existing marketing IMAP folder; the source project's documented incomplete automatic info coverage is unchanged. New confirmed notifications require a separate controlled offline reconciliation before campaign start.

## Validation, cleanup and Git

**101 tests passed** in57.711s on synthetic SQLite/fake SMTP/fake IMAP. They cover mode/paths/identity, duplicate bind, exact/no/mismatched recovery approval, preserved pending notifications, reserved/active/cooldown gates, independent IMAP progress during blocked SMTP, empty cross-campaign selection,20-second spacing,1800/300 breaks,>=900 cooldown/max3 auto-resumes and manual/restart/R6/uncertainty protections. The1000 fake-message simulation had minimum gap20s and automatic breaks. Compileall and JS syntax checks passed.

Browser:14 recipient scenarios on8018 and5 sorting/sync/monitor scenarios on8019 passed, including500+500/1001 rejection, persistence/reload/summary, filters/exclusions and mobile. The legacy JS reproduction now pins the actual initial commit instead of evolving HEAD. Recipient QA explicitly forces IMAP OFF. Target8000 read-only browser passes dashboard/editor/contacts/history/monitor, historical counters1000 accepted/430 errors, paused queues, selection handshake, never-first sorting and mobile; zero JS errors or mutation requests. Screenshots/private manifests stay ignored under output/backups. No operational campaign was altered for QA.

Cleanup: both owned synthetic servers were stopped with console Ctrl+C after verifying their command/owner and exclusive console membership. Ports8017/8018/8019 are free; only the original approved operator18152 remains on8000. No forced termination or additional operational startup.

Context Pack Closeout: local AGENTS/README/brief reviewed, operational mode responsibilities recorded, exactly one O01–O08 Requirements & Acceptance task register and one dated task Change Log entry. Source publication excludes secrets, contact data, SQLite/assets backups, logs and prior local activation work. Git commit/push and fresh remote SHA are reported separately; deployment is not requested.
