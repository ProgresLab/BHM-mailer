"""One sequential local worker, durable queue and conservative recovery.

SQLite transactions end before SMTP or waiting. The OS file lock lives for the
entire owner process: an expired timestamp can never cause a second SMTP worker.
"""
from datetime import datetime, timezone
import math
import hashlib
import json
import os
import re
import smtplib
import ssl
import threading
import time

from . import db, mailer, reconciliation
from .assets import asset_path

INTERVAL = 20
ACTIVE_PERIOD = 1800
BREAK_SECONDS = 300
MAX_AUTO_RESUMES = 3
# Headroom for unrelated account traffic. We cannot observe other mail clients.
WINDOW_LIMITS = ((300, 20), (3600, 200))


def recent_delivery_failures(conn, now):
    """List-quality signal by occurrence/receipt, NEVER reconciliation time.

    Legacy DSNs already carry Gmail internal_date/IMAP INTERNALDATE in the
    shared ledger. Unknown receipt dates cannot establish a fresh failure.
    """
    ids = {r[0] for r in conn.execute('''SELECT send_id FROM send_attempt_history
        WHERE mode='smtp' AND status='smtp_failed' AND started BETWEEN ? AND ?''', (now-3600,now))}
    for row in conn.execute('SELECT message FROM execution_events WHERE message LIKE ?', (reconciliation.PREFIX+'%',)):
        try:
            e = json.loads(row[0][len(reconciliation.PREFIX):])
            received = e.get('received_at') or int(e.get('date') or 0)/1000
            if e.get('bounce') and now-3600 <= received <= now and e.get('send_id'):
                ids.add(e['send_id'])
        except (ValueError, TypeError):
            continue
    return len(ids)


def warn_list_quality(conn, cid, now):
    count = recent_delivery_failures(conn, now)
    if count >= 50 and not conn.execute('''SELECT 1 FROM execution_events WHERE campaign_id=?
            AND created>? AND message LIKE 'Jakość listy:%' LIMIT 1''',(cid,now-3600)).fetchone():
        event(conn,cid,now,f'Jakość listy: {count} odrzuceń/zwrotów w godzinie. Ostrzeżenie; dalszy ruch zależy od odpowiedzi SMTP.')
    return count


def temporary_policy(exc, detail):
    """Only definite negative replies with a narrowly safe transient cause.

    Authentication/sender/policy/account failures always require an operator.
    A disconnect/timeout, even with a stray code attribute, is never retried.
    """
    code = getattr(exc,'smtp_code',None)
    if isinstance(exc,smtplib.SMTPRecipientsRefused):
        replies=list(exc.recipients.values())
        code=replies[0][0] if len(replies)==1 else None
    known = isinstance(exc,(smtplib.SMTPDataError,smtplib.SMTPRecipientsRefused,
                            smtplib.SMTPConnectError,smtplib.SMTPHeloError,
                            smtplib.SMTPAuthenticationError,smtplib.SMTPSenderRefused))
    definite = known and code is not None and 400 <= int(code) <= 599
    temporary = definite and int(code)<500
    unsafe = (isinstance(exc,(smtplib.SMTPAuthenticationError,smtplib.SMTPSenderRefused)) or
              bool(re.search(r'4\.7\.|\[R6\]|reputation|spam|blacklist|blocklist|\bblock(?:ed|ing)?\b|'
                             r'auth|credential|account|too many.*(?:fail|bounce)|undeliver|failed deliver|policy',detail,re.I)))
    safe = temporary and not unsafe and bool(re.search(
        r'\b4\.[234]\.[0-9]+\b|temporar|try (?:again )?later|greylist|graylist|rate limit|resources|server busy|service unavailable',detail,re.I))
    wait=900
    for match in re.finditer(r'(?:retry[- ]after\s*[:=]?|try (?:again )?in|cooldown\s*[:=]?)\s*(\d+)\s*(seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h)?\b',detail,re.I):
        unit=(match[2] or 's').lower()
        wait=max(wait,int(match[1])*(3600 if unit.startswith('h') else 60 if unit.startswith('m') else 1))
    return code,definite,temporary,safe,wait


def identity_fingerprint(settings):
    fields=('smtp_host','smtp_port','smtp_user','smtp_from_email','smtp_reply_to',
            'smtp_envelope_from','smtp_use_ssl','smtp_use_tls')
    return hashlib.sha256(json.dumps([getattr(settings,k) for k in fields]).encode()).hexdigest()


def stamp(now):
    return datetime.fromtimestamp(now, timezone.utc).isoformat()


def event(conn, campaign_id, now, message):
    conn.execute('INSERT INTO execution_events(campaign_id,created,message) VALUES(?,?,?)',
                 (campaign_id, now, message))


def account_time(conn, row, now):
    elapsed = max(0, now - row['updated'])
    if row['state'] == 'running' and not row['manual_pause']:
        conn.execute('''UPDATE campaign_execution SET active_seconds=active_seconds+?,
                        cycle_seconds=cycle_seconds+? WHERE campaign_id=?''',
                     (elapsed, elapsed, row['campaign_id']))
    conn.execute('UPDATE campaign_execution SET updated=? WHERE campaign_id=?', (now, row['campaign_id']))


def recover(now=None):
    """Only call after acquiring the process lock. Never starts delivery."""
    now = time.time() if now is None else now
    with db.get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        interrupted_attempts={r[0] for r in conn.execute('''SELECT DISTINCT s.campaign_id
            FROM email_sends s LEFT JOIN send_attempt_history a ON a.send_id=s.id
            WHERE s.status='sending' OR a.status='sending' ''')}
        conn.execute("UPDATE unsubscribe_events SET notification_status='uncertain' WHERE notification_status='sending'")
        conn.execute("""UPDATE send_attempt_history SET status='delivery_unknown',recovered_at=?,
                        detail='Proces przerwany podczas próby; wynik nieznany.' WHERE status='sending'""",(now,))
        campaigns = conn.execute("SELECT * FROM campaigns WHERE status='sending'").fetchall()
        for campaign in campaigns:
            cid = campaign['id']
            conn.execute('''INSERT OR IGNORE INTO campaign_execution(campaign_id,state,mode,started,updated)
                            VALUES(?,'interrupted','smtp',?,?)''', (cid, now, now))
            conn.execute("""UPDATE email_sends SET status='delivery_unknown', outcome_uncertain=1,
                            last_error='Proces przerwany podczas próby. Sprawdź Message Trace; bez automatycznej ponownej próby.'
                            WHERE campaign_id=? AND status='sending'""", (cid,))
            execution=conn.execute('SELECT * FROM campaign_execution WHERE campaign_id=?',(cid,)).fetchone()
            if execution['state'] in {'completed','completed_with_errors'}:
                continue
            if (execution['state'] in {'interrupted','manual_paused'} and execution['manual_pause']
                    and cid not in interrupted_attempts):
                continue  # Already safe: no timestamp churn, audit spam or resume.
            conn.execute("""UPDATE campaign_execution SET state='interrupted',manual_pause=1,updated=?,
                            problem='Proces został przerwany. Wymagana kontrola kolejki i jawne wznowienie.'
                            WHERE campaign_id=? AND state NOT IN ('completed','completed_with_errors')""", (now, cid))
            event(conn, cid, now, 'Restart: wysyłka wstrzymana; nierozstrzygnięte próby wymagają weryfikacji.')


def pause(campaign_id, now=None):
    now = time.time() if now is None else now
    with db.get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT * FROM campaign_execution WHERE campaign_id=?', (campaign_id,)).fetchone()
        if not row or row['state'] in {'completed', 'completed_with_errors'}:
            raise ValueError('Kampania nie ma aktywnej kolejki.')
        account_time(conn, row, now)
        conn.execute("UPDATE campaign_execution SET manual_pause=1,state='manual_paused' WHERE campaign_id=?", (campaign_id,))
        event(conn, campaign_id, now, 'Ręczna pauza. Rozpoczęta próba może się jeszcze kończyć.')
    manager.wake.set()


def resume(campaign_id, now=None):
    now = time.time() if now is None else now
    with db.get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT * FROM campaign_execution WHERE campaign_id=?', (campaign_id,)).fetchone()
        if not row or row['state'] in {'completed', 'completed_with_errors'}:
            raise ValueError('Brak kolejki do wznowienia.')
        if row['state'] == 'running' and not row['manual_pause']:
            return  # Idempotent double-click; do not reset the active-time anchor.
        # Uncertain rows remain excluded by the queue query. Resume authorizes
        # only other pending recipients; retry still requires resolve_uncertain.
        if conn.execute("SELECT 1 FROM email_sends WHERE campaign_id=? AND status='sending'", (campaign_id,)).fetchone():
            raise ValueError('Próba SMTP jest nadal w toku.')
        settings = mailer.get_mail_settings()
        if row['mode'] == 'smtp' and not mailer.smtp_is_configured(settings):
            raise ValueError('Konfiguracja SMTP nie pozwala bezpiecznie wznowić realnej kolejki.')
        if row['mode']=='smtp' and row['identity_fingerprint'] != identity_fingerprint(settings):
            raise ValueError('Tożsamość SMTP różni się od zapisanej kolejki lub pochodzi ze starego workera. Wymagana osobna kontrola zgodności.')
        owner = conn.execute('SELECT * FROM smtp_control WHERE id=1').fetchone()
        if owner['campaign_id'] not in {None, campaign_id}:
            raise ValueError('Inna kampania rezerwuje konto SMTP. Zakończ ją przed wznowieniem tej kolejki.')
        if owner['blocked_until'] > now and not row['smtp_cooldown_until']:
            raise ValueError(f"Cooldown SMTP: odczekaj jeszcze {math.ceil(owner['blocked_until']-now)} s, sprawdź problem i wznów ręcznie.")
        conn.execute('UPDATE smtp_control SET campaign_id=? WHERE id=1', (campaign_id,))
        # Only explicit operator resume retries a definite temporary rejection.
        conn.execute("UPDATE email_sends SET status='pending' WHERE campaign_id=? AND status='rate_limited' AND outcome_uncertain=0", (campaign_id,))
        state = 'auto_cooldown' if row['smtp_cooldown_until'] > now else 'auto_break' if row['cooldown_until'] > now else 'running'
        conn.execute('''UPDATE campaign_execution SET manual_pause=0,state=?,updated=?,problem=''
                        WHERE campaign_id=?''', (state, now, campaign_id))
        event(conn, campaign_id, now, 'Operator wznowił pozostałą kolejkę; zachowano odstęp i cooldown.')
    manager.wake.set()


def resolve_uncertain(send_id, decision, note, confirmed=False, now=None):
    if decision not in {'cancel', 'retry_not_accepted'} or len(note.strip()) < 12:
        raise ValueError('Wymagana decyzja i opis dowodu (minimum 12 znaków).')
    if decision == 'retry_not_accepted' and not confirmed:
        raise ValueError('Ponowienie wymaga potwierdzonego dowodu braku akceptacji SMTP.')
    now = time.time() if now is None else now
    with db.get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT * FROM email_sends WHERE id=? AND outcome_uncertain=1', (send_id,)).fetchone()
        if not row:
            raise ValueError('Próba nie wymaga już rozstrzygnięcia.')
        status = 'cancelled' if decision == 'cancel' else 'pending'
        conn.execute('UPDATE email_sends SET status=?,outcome_uncertain=0 WHERE id=?', (status, send_id))
        conn.execute('INSERT INTO recovery_decisions(send_id,created,decision,note) VALUES(?,?,?,?)',
                     (send_id, now, decision, mailer.sanitize_log_text(note.strip())))
        event(conn, row['campaign_id'], now, 'Zapisano decyzję operatora dla nierozstrzygniętej próby.')


class Engine:
    def __init__(self, clock=time.time, sender=None, settings=None, monotonic=time.monotonic):
        self.clock = clock
        self.sender = sender or mailer.send_one_email
        self.settings = settings or mailer.get_mail_settings
        self.tick_lock = threading.Lock()
        self.monotonic=monotonic
        self.last_observed=monotonic()

    def tick(self):
        # Also protects direct/reentrant invocation within the owner process.
        if not self.tick_lock.acquire(blocking=False):
            return
        try:
            self._tick()
            self._notify_idle()
        finally:
            self.tick_lock.release()

    def _tick(self):
        now = self.clock()
        observed=self.monotonic()
        slept=observed-self.last_observed>120
        self.last_observed=observed
        with db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            control = conn.execute('SELECT * FROM smtp_control WHERE id=1').fetchone()
            cid = control['campaign_id']
            if cid is None:
                return
            row = conn.execute('SELECT * FROM campaign_execution WHERE campaign_id=?', (cid,)).fetchone()
            if not row:
                return
            if row['manual_pause'] or row['state'] in {'problem','interrupted'}:
                return
            if slept:
                conn.execute("""UPDATE campaign_execution SET state='interrupted',manual_pause=1,updated=?,
                    problem='Uśpienie lub przerwa workera. Sprawdź kolejkę i wznów ręcznie.' WHERE campaign_id=?""",(now,cid))
                event(conn,cid,now,'Przerwa workera przekroczyła 120 sekund; automatyczne wznowienie zablokowane.')
                return
            if row['smtp_cooldown_until']:
                if now < max(row['smtp_cooldown_until'],control['blocked_until']):
                    return
                conn.execute("UPDATE email_sends SET status='pending' WHERE campaign_id=? AND status='rate_limited' AND outcome_uncertain=0",(cid,))
                conn.execute("UPDATE campaign_execution SET state='running',smtp_cooldown_until=0,updated=?,problem='' WHERE campaign_id=?",(now,cid))
                event(conn,cid,now,'Bezpieczny cooldown SMTP zakończony; automatyczne wznowienie pozostałej kolejki.')
                row=conn.execute('SELECT * FROM campaign_execution WHERE campaign_id=?',(cid,)).fetchone()
            if row['state']=='auto_break' and now < row['cooldown_until']:
                return
            if row['state'] == 'running' and now - row['updated'] > 120:
                conn.execute("""UPDATE campaign_execution SET state='interrupted',manual_pause=1,updated=?,
                                problem='Długa przerwa procesu lub uśpienie komputera. Sprawdź i wznów ręcznie.' WHERE campaign_id=?""", (now, cid))
                return
            account_time(conn, row, now)
            # Finish a persisted break even if it expired while manually paused.
            if row['cooldown_until']:
                if now < row['cooldown_until']:
                    return
                conn.execute("UPDATE campaign_execution SET state='running',cycle_seconds=0,cooldown_until=0 WHERE campaign_id=?", (cid,))
                event(conn, cid, now, 'Automatyczna przerwa zakończona.')
            row = conn.execute('SELECT * FROM campaign_execution WHERE campaign_id=?', (cid,)).fetchone()
            pending = conn.execute("""SELECT s.*, c.status AS contact_status FROM email_sends s
                                     JOIN contacts c ON c.id=s.contact_id
                                     WHERE s.campaign_id=? AND s.status='pending' AND s.outcome_uncertain=0 ORDER BY s.id LIMIT 1""", (cid,)).fetchone()
            if not pending:
                status = mailer.finalize_campaign_status(conn, cid)
                conn.execute('UPDATE campaign_execution SET state=? WHERE campaign_id=?', (status, cid))
                conn.execute('UPDATE smtp_control SET campaign_id=NULL WHERE id=1')
                event(conn, cid, now, 'Przetwarzanie kolejki zakończone.')
                return
            if row['cycle_seconds'] >= ACTIVE_PERIOD:
                conn.execute("UPDATE campaign_execution SET state='auto_break',cooldown_until=? WHERE campaign_id=?", (now + BREAK_SECONDS, cid))
                event(conn, cid, now, 'Automatyczna przerwa 5 minut po 30 minutach aktywnej pracy.')
                return
            if pending['contact_status'] != 'active':
                status = 'skipped_unsubscribed' if pending['contact_status'] == 'unsubscribed' else 'skipped_invalid'
                mailer.update_send_status(conn, pending['id'], status, final_status_at=stamp(now))
                return
            from .selection import UNCERTAIN_CONTACT_SQL
            if conn.execute('SELECT 1 FROM contacts c WHERE c.id=? AND '+UNCERTAIN_CONTACT_SQL,(pending['contact_id'],)).fetchone():
                mailer.update_send_status(conn,pending['id'],'skipped_duplicate',
                    error_message='Wcześniejsza próba tego kontaktu ma niepewny wynik. Bez ponowienia.',final_status_at=stamp(now))
                return
            # Belt-and-braces for historical duplicate rows: no repeat of a previous attempt.
            if conn.execute("""SELECT 1 FROM email_sends WHERE campaign_id=? AND contact_id=? AND id<>?
                               AND (attempt_count>0 OR status IN ('sending','accepted_by_smtp','sent','delivered_by_trace','dry_run')) LIMIT 1""",
                            (cid, pending['contact_id'], pending['id'])).fetchone():
                mailer.update_send_status(conn, pending['id'], 'skipped_duplicate', final_status_at=stamp(now))
                return
            allowed_at = max(row['next_attempt'], control['next_attempt'], control['blocked_until'])
            if row['mode'] == 'smtp':
                for window, limit in WINDOW_LIMITS:
                    starts = conn.execute('''SELECT started FROM smtp_attempts WHERE started>?
                        UNION ALL SELECT started FROM notification_attempts WHERE started>? ORDER BY started''', (now-window,now-window)).fetchall()
                    if len(starts) >= limit:
                        allowed_at = max(allowed_at, starts[-limit]['started'] + window)
            if now < allowed_at:
                conn.execute('UPDATE campaign_execution SET next_attempt=? WHERE campaign_id=?', (allowed_at, cid))
                return
            settings = self.settings()
            if row['mode'] == 'smtp' and not mailer.smtp_is_configured(settings):
                conn.execute("UPDATE campaign_execution SET state='problem',problem='Niekompletna konfiguracja SMTP.' WHERE campaign_id=?", (cid,))
                return
            if row['mode']=='smtp' and row['identity_fingerprint'] != identity_fingerprint(settings):
                conn.execute("UPDATE campaign_execution SET state='problem',problem='Zmieniła się tożsamość SMTP. Wysyłka zablokowana.' WHERE campaign_id=?",(cid,))
                return
            if row['mode']=='smtp':
                warn_list_quality(conn,cid,now)
            # A missing asset blocks the queue before any SMTP attempt.
            if pending['banner_asset'] and not asset_path(pending['banner_asset']).is_file():
                conn.execute("UPDATE campaign_execution SET state='problem',problem='Brak zapisanego banera. Przywróć asset z kopii.' WHERE campaign_id=?", (cid,))
                return
            identity = mailer.prepare_message_identity(settings, pending['email'])
            changed = conn.execute("UPDATE email_sends SET status='sending',started_at=?,attempt_count=attempt_count+1 WHERE id=? AND status='pending'", (stamp(now), pending['id']))
            if changed.rowcount != 1:
                return
            # Persist identity BEFORE network I/O, including Message-ID for crash verification.
            conn.execute('''UPDATE email_sends SET smtp_user=?,header_from=?,reply_to=?,envelope_from=?,envelope_to=?,
                            message_id=?,smtp_message_id=? WHERE id=?''',
                         (identity.smtp_user, identity.header_from, identity.reply_to, identity.envelope_from,
                          identity.envelope_to, identity.message_id, identity.message_id, pending['id']))
            conn.execute('UPDATE smtp_control SET next_attempt=? WHERE id=1', (now + INTERVAL,))
            conn.execute('UPDATE campaign_execution SET next_attempt=? WHERE campaign_id=?', (now + INTERVAL, cid))
            attempt_id=conn.execute('''INSERT INTO send_attempt_history(send_id,attempt_number,mode,started,status,message_id)
                VALUES(?,?,?,?,'sending',?)''',(pending['id'],(pending['attempt_count'] or 0)+1,row['mode'],now,identity.message_id)).lastrowid
            if row['mode'] == 'smtp':
                conn.execute('INSERT INTO smtp_attempts(send_id,started) VALUES(?,?)', (pending['id'], now))
        # No SQLite connection or transaction held during SMTP.
        result = None
        failure = None
        try:
            if row['mode'] == 'smtp':
                result = self.sender(settings, pending['email'], pending['subject'], pending['text_snapshot'],
                                     pending['html_snapshot'], identity=identity, banner_asset=pending['banner_asset'])
        except Exception as exc:
            failure = exc
        end = self.clock()
        with db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            current = conn.execute('SELECT * FROM campaign_execution WHERE campaign_id=?', (cid,)).fetchone()
            account_time(conn, current, end)
            common = dict(smtp_message_id=identity.message_id, **mailer.identity_update_kwargs(identity))
            if row['mode'] == 'dry_run':
                mailer.update_send_status(conn, pending['id'], 'dry_run', smtp_response='Symulacja. Bez połączenia SMTP.',
                                          final_status_at=stamp(end), **common)
            elif failure is None:
                mailer.update_send_status(conn, pending['id'], 'accepted_by_smtp', smtp_response=result.smtp_response,
                                          smtp_code=result.smtp_code, provider_message_id=result.provider_message_id,
                                          accepted_at=stamp(end), sent_at=stamp(end), **common)
                mailer.mark_contact_sent(conn, pending['contact_id'], stamp(end))
                # This counter bounds consecutive account-wide transients;
                # a successful acceptance ends that transient episode.
                conn.execute("UPDATE campaign_execution SET auto_resume_count=0,problem='',failure_kind='' WHERE campaign_id=?",(cid,))
            else:
                error = mailer.smtp_exception_text(failure)
                # Only explicit SMTP negative replies prove non-acceptance. A transport
                # timeout/disconnect may follow DATA acceptance and is never retried.
                code,definite,temporary,safe,wait = temporary_policy(failure,error)
                r7 = definite and temporary and bool(re.search(r'\[R7\]',error,re.I))
                if r7:
                    wait=max(wait,3600)  # Conservative local floor, not provider availability proof.
                enhanced = re.search(r'\b5\.\d+\.\d+\b',error)
                kind,target = reconciliation.classify('failed',enhanced[0] if enhanced else '',error)
                recipient_reply = ((isinstance(failure,smtplib.SMTPRecipientsRefused) and len(failure.recipients)==1) or
                    (isinstance(failure,smtplib.SMTPDataError) and definite and
                     ((not temporary and target=='invalid') or bool(re.search(r'\b4\.2\.\d+\b',error)))))
                policy_error = bool(re.search(r'auth|credential|account|reputation|spam|block|policy|\btls\b|certificate|encrypt|4\.7\.|5\.7\.|\[R6\]',error,re.I))
                recipient_failure = recipient_reply and definite and not temporary and kind != 'sender_policy' and not policy_error
                status = 'rate_limited' if temporary else 'smtp_failed' if definite else 'delivery_unknown'
                mailer.update_send_status(conn, pending['id'], status, error_message=error, smtp_code=str(code or ''),
                                          final_status_at=stamp(end), **common)
                if not definite:
                    conn.execute('UPDATE email_sends SET outcome_uncertain=1 WHERE id=?', (pending['id'],))
                if recipient_failure and target == 'invalid':
                    conn.execute("UPDATE contacts SET status='invalid',updated_at=? WHERE id=? AND status NOT IN ('unsubscribed','invalid')", (stamp(end),pending['contact_id']))
                if recipient_failure:
                    event(conn,cid,end,'Trwała odmowa odbiorcy; bez akceptacji SMTP. Kontynuacja pozostałych adresów.')
                else:
                    # R6 is account-wide. One conservative probe per queue,
                    # after at least one hour; an explicit longer wait wins.
                    r6 = definite and temporary and bool(re.search(r'\[R6\]',error,re.I)) and not isinstance(failure,(smtplib.SMTPAuthenticationError,smtplib.SMTPSenderRefused))
                    probed = conn.execute("SELECT 1 FROM execution_events WHERE campaign_id=? AND message LIKE 'Provider R6:%' LIMIT 1",(cid,)).fetchone()
                    if r6:
                        wait=max(wait,3600)
                    previous = conn.execute("SELECT COUNT(*) FROM send_attempt_history WHERE send_id=? AND status='rate_limited'",(pending['id'],)).fetchone()[0]
                    recipient_exhausted = safe and recipient_reply and previous >= 2
                    if safe and recipient_reply:
                        wait=max(wait,900*(2**min(previous,2)))
                    auto = (r6 and not probed) or (safe and not recipient_exhausted and current['auto_resume_count'] < MAX_AUTO_RESUMES)
                    uncertain = not definite and isinstance(failure,(TimeoutError,ConnectionError,smtplib.SMTPServerDisconnected)) and not isinstance(failure,ssl.SSLError)
                    unknowns = conn.execute('''SELECT status FROM send_attempt_history WHERE mode='smtp' ORDER BY id DESC LIMIT 3''').fetchall()
                    uncertain_continue = uncertain and not (len(unknowns)>=3 and all(a[0]=='delivery_unknown' for a in unknowns[1:]))
                    message = ('Provider R7: ponad 30 wiadomości w kolejce one.com. Minimum 60 minut bez prób; potem kontrola operatora. Odblokowanie nie jest gwarantowane.' if r7 else
                               'Provider R6: oczekiwanie minimum 60 minut; potem jedna ograniczona próba, bez gwarancji odblokowania.' if r6 and auto else
                               'Provider R6 nadal blokuje konto. Wymagana kontrola dostawcy/operatora.' if r6 else
                               'Limit prób tego odbiorcy; niewysłany. Kontynuacja pozostałych adresów.' if recipient_exhausted else
                               'Niepewna próba odłożona do weryfikacji; bez ponowienia. Kontynuacja innych adresów.' if uncertain_continue else
                               'Tymczasowa, potwierdzona odmowa SMTP; automatyczne wznowienie po cooldownie.' if auto else
                               'Problem SMTP / konfiguracji lub limit kolejnych prób. Sprawdź historię przed wznowieniem.')
                    if recipient_exhausted:
                        conn.execute("UPDATE email_sends SET status='smtp_failed' WHERE id=?",(pending['id'],))
                        conn.execute('UPDATE campaign_execution SET auto_resume_count=0 WHERE campaign_id=?',(cid,))
                    # A manual pause made while SMTP was in flight always wins.
                    state='manual_paused' if current['manual_pause'] else 'auto_cooldown' if auto else 'running' if recipient_exhausted or uncertain_continue else 'problem'
                    conn.execute('''UPDATE campaign_execution SET state=?,problem=?,smtp_cooldown_until=?,
                        auto_resume_count=auto_resume_count+?,failure_kind=? WHERE campaign_id=?''',
                        (state,message,end+wait if auto else 0,int(auto),type(failure).__name__+': '+error,cid))
                    if auto or state=='problem':
                        conn.execute('UPDATE smtp_control SET blocked_until=MAX(blocked_until,?) WHERE id=1', (end + (wait if temporary else 300),))
                    event(conn, cid, end, message)
            conn.execute('''UPDATE campaign_execution SET smtp_seconds=smtp_seconds+?,smtp_attempts=smtp_attempts+1
                            WHERE campaign_id=?''', (max(0, end-now), cid))
            outcome=conn.execute('SELECT status,smtp_code,last_error,smtp_response FROM email_sends WHERE id=?',(pending['id'],)).fetchone()
            conn.execute('UPDATE send_attempt_history SET finished=?,status=?,smtp_code=?,detail=? WHERE id=?',
                         (end,outcome['status'],outcome['smtp_code'],outcome['last_error'] or outcome['smtp_response'],attempt_id))

    def _notify_idle(self):
        """Admin notifications share this worker, account spacing and rolling limits.

        They wait for campaign completion. An ambiguous/crashed notification is
        preserved as uncertain and is never automatically retried.
        """
        now = self.clock()
        settings = self.settings()
        if not mailer.smtp_is_configured(settings) or not settings.admin_notification_email:
            return
        with db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            control = conn.execute('SELECT * FROM smtp_control WHERE id=1').fetchone()
            if control['campaign_id'] is not None or now < max(control['next_attempt'],control['blocked_until']):
                return
            for window,limit in WINDOW_LIMITS:
                count=conn.execute('''SELECT (SELECT COUNT(*) FROM smtp_attempts WHERE started>?) +
                    (SELECT COUNT(*) FROM notification_attempts WHERE started>?)''',(now-window,now-window)).fetchone()[0]
                if count>=limit:
                    return
            notification=conn.execute("""SELECT * FROM unsubscribe_events WHERE notification_sent=0
                AND notification_status='queued' ORDER BY id LIMIT 1""").fetchone()
            if not notification:
                return
            conn.execute("UPDATE unsubscribe_events SET notification_status='sending' WHERE id=?",(notification['id'],))
            conn.execute('INSERT INTO notification_attempts(event_id,started) VALUES(?,?)',(notification['id'],now))
            conn.execute('UPDATE smtp_control SET next_attempt=? WHERE id=1',(now+INTERVAL,))
        from html import escape
        body=(f"email: {notification['email']}\nDate/time UTC: {notification['created_at']}\n"
              f"campaign_id: {notification['source_campaign_id'] or ''}\n")
        try:
            identity=mailer.prepare_message_identity(settings,settings.admin_notification_email)
            self.sender(settings,settings.admin_notification_email,f"Unsubscribe: {notification['email']}",
                        body,f'<pre>{escape(body)}</pre>',identity=identity)
        except Exception:
            with db.get_connection() as conn:
                conn.execute("UPDATE unsubscribe_events SET notification_status='uncertain' WHERE id=?",(notification['id'],))
                conn.execute('UPDATE smtp_control SET blocked_until=MAX(blocked_until,?) WHERE id=1',(self.clock()+900,))
        else:
            with db.get_connection() as conn:
                conn.execute("UPDATE unsubscribe_events SET notification_sent=1,notification_status='accepted_by_smtp' WHERE id=?",(notification['id'],))


def execution_payload(campaign_id, now=None):
    now = time.time() if now is None else now
    with db.get_connection() as conn:
        row = conn.execute('SELECT * FROM campaign_execution WHERE campaign_id=?', (campaign_id,)).fetchone()
        if not row:
            return {}
        row = dict(row)
        control = conn.execute('SELECT * FROM smtp_control WHERE id=1').fetchone()
        counts = conn.execute('''SELECT COUNT(*) AS total, SUM(status='pending') AS pending,
            SUM(status='sending') AS sending, SUM(accepted_at IS NOT NULL OR status='sent') AS accepted,
            SUM(status='dry_run') AS dry_run, SUM(status LIKE 'skipped_%') AS skipped,
            SUM(status='cancelled') AS cancelled,
            SUM(status IN ('smtp_failed','rate_limited','delivery_unknown','failed_by_trace','bounced_later','quarantined_by_trace')) AS errors,
            SUM(outcome_uncertain=1) AS uncertain FROM email_sends WHERE campaign_id=?''', (campaign_id,)).fetchone()
        counts = {k: int(v or 0) for k, v in dict(counts).items()}
        current = conn.execute("SELECT email FROM email_sends WHERE campaign_id=? AND status='sending' ORDER BY id LIMIT 1", (campaign_id,)).fetchone()
        next_row = conn.execute("SELECT email FROM email_sends WHERE campaign_id=? AND status='pending' ORDER BY id LIMIT 1", (campaign_id,)).fetchone()
        counts['pending'] += conn.execute("SELECT COUNT(*) FROM email_sends WHERE campaign_id=? AND status='rate_limited' AND outcome_uncertain=0",(campaign_id,)).fetchone()[0]
        quality_failures = recent_delivery_failures(conn,now)
        events = conn.execute("SELECT created,message FROM execution_events WHERE campaign_id=? AND message NOT LIKE 'gmail-reconciliation-v1:%' ORDER BY id DESC LIMIT 8", (campaign_id,)).fetchall()
    active = row['active_seconds'] + (max(0, now-row['updated']) if row['state']=='running' and not row['manual_pause'] else 0)
    remaining = counts['pending'] + counts['sending']
    processed = counts['total'] - remaining
    cooldown = max(0, row['cooldown_until'] - now)
    smtp_cooldown = max(0,row['smtp_cooldown_until']-now)
    until_next = max(0, max(row['next_attempt'],control['next_attempt'],control['blocked_until'],row['smtp_cooldown_until'])-now)
    cycle = row['cycle_seconds'] + max(0, active-row['active_seconds'])
    mean = row['smtp_seconds']/max(1,row['smtp_attempts'])
    work = max(0, remaining-1)*max(INTERVAL,mean) + (mean if remaining else 0)
    future_cycle = 0 if row['cooldown_until'] else cycle
    breaks = max(0, math.floor((future_cycle+max(0,work-0.001))/ACTIVE_PERIOD)) if remaining else 0
    eta = work + breaks*BREAK_SECONDS + max(cooldown,smtp_cooldown,until_next)
    provider_wait = '[R6]' in row['failure_kind'] and row['state']=='auto_cooldown'
    paused = row['manual_pause'] or row['state'] in {'problem','interrupted'}
    eta_uncertain = bool(paused or row['state']=='auto_cooldown' or counts['uncertain'])
    finished = row['state'] in {'completed','completed_with_errors'}
    if finished:
        eta = 0
    return dict(execution_state=row['state'], mode=row['mode'], manual_pause=bool(row['manual_pause']),
                elapsed_seconds=round(max(0,(row['updated'] if finished else now)-row['started'])), active_seconds=round(active),
                cooldown_seconds=math.ceil(cooldown), next_attempt_seconds=math.ceil(until_next),
                smtp_cooldown_seconds=math.ceil(smtp_cooldown),
                resume_at=stamp(max(row['smtp_cooldown_until'],control['blocked_until'])) if not finished and max(row['smtp_cooldown_until'],control['blocked_until'])>now else None,
                failure_detail=row['failure_kind'], auto_resume_count=row['auto_resume_count'],
                next_break_seconds=max(0,math.ceil(ACTIVE_PERIOD-cycle)),
                eta_seconds=None if eta_uncertain else round(eta), eta_uncertain=eta_uncertain,
                eta_finish=None if eta_uncertain else stamp(now+eta), problem=row['problem'],
                provider_wait=provider_wait, quality_failures=quality_failures,
                quality_warning=f'Wysoka liczba zwrotów/odrzuceń: {quality_failures} w godzinie. Sprawdź jakość listy.' if quality_failures>=50 else '',
                current_email=current['email'] if current else '', next_email=next_row['email'] if next_row else '',
                counts=counts, processed=processed, percent=round(processed/max(1,counts['total'])*100,1),
                recent_events=[dict(e) for e in events], interval=INTERVAL)


class Manager:
    def __init__(self):
        self.wake = threading.Event()
        self.stop = threading.Event()
        self.thread = None
        self.lock_file = None
        self.guard = threading.Lock()

    @property
    def available(self):
        return self.thread is not None and self.thread.is_alive()

    def start(self):
        with self.guard:
            if self.available:
                return
            path = db.DB_PATH.with_suffix(db.DB_PATH.suffix + '.worker.lock')
            handle = open(path, 'a+b')
            handle.seek(0)
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                handle.close()
                return
            self.lock_file = handle
            try:
                recover()
            except Exception:
                handle.close()
                self.lock_file = None
                raise
            self.stop.clear()
            self.thread = threading.Thread(target=self.run, name='bhm-smtp-worker', daemon=True)
            self.thread.start()

    def run(self):
        engine = Engine()
        try:
            while not self.stop.is_set():
                try:
                    engine.tick()
                except Exception:
                    # Fail closed; in-flight row stays reserved for restart recovery.
                    with db.get_connection() as conn:
                        conn.execute("""UPDATE campaign_execution SET state='problem',manual_pause=1,
                            problem='Błąd workera. Wymagana kontrola i restart procesu.'
                            WHERE campaign_id=(SELECT campaign_id FROM smtp_control WHERE id=1)""")
                    return
                self.wake.wait(1)
                self.wake.clear()
        finally:
            self.lock_file.close()
            self.lock_file = None

    def shutdown(self):
        self.stop.set()
        self.wake.set()
        if self.thread:
            self.thread.join(timeout=35)


manager = Manager()
