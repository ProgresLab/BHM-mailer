"""Synthetic SQLite, bounded fake IMAP and fake clock. Never uses a mailbox."""
from dataclasses import replace
from datetime import datetime,timezone
import copy
import json
import smtplib
import threading
import unittest
from unittest.mock import patch

from app import db, imap_sync, reconciliation as rec, worker
from app.selection import update_selection, selected_ids
import test_campaigns as fixtures
import test_reconciliation as reconciliation_fixtures


def wire(message, mailbox='marketing@bhm-chemicals.com'):
    root=copy.deepcopy(message['payload'])
    root['headers']=[h for h in root['headers'] if h['name']!='Authentication-Results']
    root['headers'][:0]=[
        dict(name='Return-Path',value='<>'),dict(name='Delivered-To',value=mailbox),
        dict(name='Received',value='from mx1.cst.mailpod10-cph3.one.com by mailstorage31.cst.mailpod10-cph3.one.com'),
        dict(name='Authentication-Results',value='mx1.pub.mailpod10-cph3.one.com; dkim=pass header.d='+
             ('bhm-chemicals.com' if 'Unsubscribe request' in root.get('body',{}).get('content','') else 'one.com')+' header.s=bounces1;'),
        dict(name='Received',value='from mailrelay3.pub.mailoutpod2-cph3.one.com by mx1.pub.mailpod10-cph3.one.com')]
    hs='\r\n'.join(h['name']+': '+h['value'] for h in root['headers'])
    if root['mime_type']=='multipart/report':
        body='Content-Type: multipart/report; boundary=qa; report-type=delivery-status\r\n\r\n--qa\r\nContent-Type: message/delivery-status\r\n\r\n'+root['parts'][0]['body']['content']+'\r\n--qa--\r\n'
    else:body='Content-Type: text/plain\r\n\r\n'+root['body']['content']
    return (hs+'\r\n'+body).encode()


class FakeIMAP:
    def __init__(self,messages=None,validity='123',received=1000020):
        self.messages=messages or {}
        self.validity=validity
        self.received=received
        self.calls=[]
        self.fail=False
    def login(self,*args):self.calls.append('login');return 'OK',[]
    def select(self,folder,readonly=False):
        assert readonly
        self.calls.append('EXAMINE');return 'OK',[]
    def response(self,key):
        return key,[(self.validity if key=='UIDVALIDITY' else str(max(self.messages,default=0)+1)).encode()]
    def uid(self,command,*args):
        self.calls.append((command,args))
        if self.fail:raise imap_sync.imaplib.IMAP4.abort('secret and arbitrary provider text')
        if command=='SEARCH':
            low,high=map(int,args[-1].split(':'))
            return 'OK',[b' '.join(str(uid).encode() for uid in self.messages if low<=uid<=high)]
        assert command=='FETCH' and 'BODY.PEEK[]' in args[-1]
        raw=self.messages[int(args[0])]
        date=datetime.fromtimestamp(self.received,timezone.utc).strftime('%d-%b-%Y %H:%M:%S +0000')
        return 'OK',[(f'1 (UID {args[0]} INTERNALDATE "{date}" RFC822.SIZE {len(raw)} BODY[] {{{len(raw)}}}'.encode(),raw),b')']
    def logout(self):self.calls.append('logout')


class Case(unittest.TestCase):
    setUp=fixtures.Case.setUp
    tearDown=fixtures.Case.tearDown
    contacts=fixtures.Case.contacts
    campaign=fixtures.Case.campaign
    prepare=fixtures.Case.prepare
    fake_send=fixtures.Case.fake_send
    row=fixtures.Case.row
    completed=reconciliation_fixtures.ReconciliationCase.completed
    dsn=reconciliation_fixtures.ReconciliationCase.dsn
    unsubscribe=reconciliation_fixtures.ReconciliationCase.unsubscribe
    propose=reconciliation_fixtures.ReconciliationCase.propose
    apply=reconciliation_fixtures.ReconciliationCase.apply

    def scanner(self,messages=None):
        self.config=imap_sync.Settings(True,password='synthetic')
        self.imap=FakeIMAP(messages,received=self.clock())
        self.scanner_engine=imap_sync.Engine(self.clock,lambda config:self.imap,self.config)
        return self.scanner_engine

    def ingest(self,raw):
        with db.get_connection() as c:
            c.execute('BEGIN IMMEDIATE')
            return imap_sync.process_message(c,raw,self.clock(),imap_sync.Settings(True,password='qa'),self.clock())

    def test_interval_incremental_late_date_and_restart(self):
        self.completed();engine=self.scanner({1:wire(self.dsn())})
        engine.tick()
        self.assertEqual(self.row('SELECT status FROM contacts')['status'],'invalid')
        self.assertEqual(self.row('SELECT last_uid FROM mail_sync_state')['last_uid'],1)
        count=len(self.imap.calls)
        self.imap.messages[2]=b'Date: Sat, 1 Jan 2000 00:00:00 +0000\r\nSubject: old delayed arrival\r\n\r\nHello'
        self.clock.advance(899);engine.tick();self.assertEqual(len(self.imap.calls),count)
        self.clock.advance(1)
        imap_sync.Engine(self.clock,lambda c:self.imap,self.config).tick()
        self.assertEqual(self.row('SELECT last_uid FROM mail_sync_state')['last_uid'],2)
        self.assertEqual(self.row('SELECT COUNT(*) n FROM mail_sync_messages')['n'],2)
        self.assertEqual(self.row('SELECT contact_changes FROM mail_sync_state')['contact_changes'],1)

    def test_uidvalidity_replay_and_gmail_imap_idempotence(self):
        self.completed();self.apply(self.propose([self.dsn()]))
        before=self.row('SELECT COUNT(*) n FROM execution_events')['n']
        e=self.scanner({10:wire(self.dsn())});e.tick()
        self.assertEqual(self.row('SELECT contact_changes FROM mail_sync_state')['contact_changes'],0)
        self.imap.validity='456';self.imap.messages={1:wire(self.dsn())}
        self.clock.advance(900);e.tick()
        self.assertEqual(self.row('SELECT uidvalidity,last_uid FROM mail_sync_state'),dict(uidvalidity='456',last_uid=1))
        self.assertEqual(self.row('SELECT COUNT(*) n FROM execution_events')['n'],before)

    def test_prior_legacy_gmail_ledger_without_new_table_entries(self):
        self.completed();self.apply(self.propose([self.dsn()]))
        with db.get_connection() as c:c.execute('DELETE FROM mail_evidence')
        result=self.ingest(wire(self.dsn()))
        self.assertEqual(result['contact_changes'],0)
        self.assertEqual(result['hard_bounces'],0)

    def test_existing_offline_gmail_delta_validator_still_accepts_import(self):
        from tools.reconcile_gmail import snapshot,validate_delta
        self.completed()
        with db.get_connection() as c:
            before=snapshot(c);proposal=rec.plan(c,self.cid,[self.dsn()]);rec.apply(c,proposal)
            result=validate_delta(before,snapshot(c),proposal)
        self.assertEqual(result['contacts'],1)
        self.assertEqual(result['mail_evidence'],0)

    def test_final_failed_4xx_is_projected_without_contact_change_and_deduped_with_gmail(self):
        self.completed();msg=self.dsn('4.0.0','failed','x-error; Network error')
        result=self.ingest(wire(msg))
        self.assertEqual(result['hard_bounces'],0);self.assertEqual(result['contact_changes'],0)
        self.assertEqual(self.row('SELECT status FROM contacts')['status'],'active')
        self.assertEqual(self.row('SELECT status FROM email_sends')['status'],'bounced_later')
        with db.get_connection() as c:
            p=rec.plan(c,self.cid,[msg]);self.assertTrue(p['events'][0]['duplicate'])
            self.assertFalse(p['contacts']);self.assertFalse(p['sends'])

    def test_operator_gmail_exclusion_deduplicates_subsequent_automatic_imap(self):
        self.completed();msg=self.dsn('4.0.0','failed','x-error; Network error')
        with db.get_connection() as c:
            rec.apply(c,rec.plan(c,self.cid,[msg],exclude_final_failures=True))
        count=self.row('SELECT COUNT(*) n FROM execution_events')['n']
        result=self.ingest(wire(msg))
        self.assertEqual(result['contact_changes'],0);self.assertEqual(result['hard_bounces'],0)
        self.assertEqual(self.row('SELECT status FROM contacts')['status'],'invalid')
        self.assertEqual(self.row('SELECT COUNT(*) n FROM execution_events')['n'],count)

    def test_disconnect_no_cursor_loss_or_secret_leak(self):
        self.completed();e=self.scanner({1:wire(self.dsn())});self.imap.fail=True;e.tick()
        row=self.row('SELECT * FROM mail_sync_state');self.assertEqual(row['last_uid'],0)
        self.assertNotIn('secret',row['last_error'])
        self.imap.fail=False;self.clock.advance(900);e.tick()
        self.assertEqual(self.row('SELECT last_uid FROM mail_sync_state')['last_uid'],1)

    def test_verified_unsubscribe_hard_bounce_no_reactivation(self):
        self.completed()
        self.assertEqual(self.ingest(wire(self.unsubscribe()))['unsubscribes'],1)
        self.assertEqual(self.row('SELECT status FROM contacts')['status'],'unsubscribed')
        self.assertEqual(self.ingest(wire(self.dsn()))['hard_bounces'],1)
        self.assertEqual(self.row('SELECT status FROM contacts')['status'],'unsubscribed')
        self.assertEqual(self.row('SELECT status FROM send_attempt_history')['status'],'accepted_by_smtp')

    def test_fake_boundary_forged_verdict_no_match_and_autoresponder(self):
        self.completed()
        raw=wire(self.dsn())
        fake=raw.replace(b'by mx1.pub.mailpod10',b'by evil.invalid mx1.pub.mailpod10')
        self.assertEqual(self.ingest(fake)['contact_changes'],0)
        # Forged header below genuine ingress cannot replace receiver verdict.
        fake=raw.replace(b'Authentication-Results:',b'X-Untrusted:').replace(b'From:',b'Authentication-Results: mx1.pub.mailpod10-cph3.one.com; dkim=pass header.d=one.com;\r\nFrom:')
        self.assertEqual(self.ingest(fake)['contact_changes'],0)
        self.assertEqual(self.ingest(wire(self.dsn(mid='<no-match@example.test>')))['reviews'],1)
        self.assertEqual(self.ingest(b'Auto-Submitted: auto-replied\r\nSubject: vacation\r\n\r\nAway')['contact_changes'],0)
        self.assertEqual(self.row('SELECT status FROM contacts')['status'],'active')
        # Earlier untrusted copy must not poison a subsequent trusted report.
        self.assertEqual(self.ingest(raw)['contact_changes'],1)

    def test_delay_reputation_and_ambiguous_review(self):
        self.completed()
        for status,action,diag,key in [('4.2.0','delayed','450 delay','alerts'),('5.7.1','failed','550 spam reputation','alerts'),('5.0.0','failed','550 unknown reason','reviews')]:
            msg=self.dsn(status,action,diag);msg['payload']['headers'][2]['value']=f'<{status}@example.test>'
            result=self.ingest(wire(msg));self.assertEqual(result['contact_changes'],0)
            if status!='4.2.0':self.assertEqual(result[key],1)

    def test_conflicting_trace_requires_review_without_poisoning_scan(self):
        self.completed()
        with db.get_connection() as c:c.execute("UPDATE email_sends SET status='delivered_by_trace'")
        result=self.ingest(wire(self.dsn()))
        self.assertEqual(result['reviews'],1)
        self.assertEqual(self.row('SELECT status FROM contacts')['status'],'active')
        self.assertEqual(self.row('SELECT status FROM email_sends')['status'],'delivered_by_trace')
        self.assertEqual(self.ingest(wire(self.dsn()))['reviews'],0)

    def test_live_pending_queue_rechecks_new_contact_status(self):
        cid,ids=self.prepare(2);self.engine.tick()
        self.send=self.row('SELECT * FROM email_sends ORDER BY id');self.cid=cid;self.contact=ids[0]
        self.ingest(wire(self.dsn()))
        # Existing accepted contact can still have a separate unsent campaign row.
        with db.get_connection() as c:
            c.execute("UPDATE contacts SET status='unsubscribed' WHERE id=?",(ids[1],))
        self.clock.advance(20);self.engine.tick()
        self.assertEqual(len(self.starts),1)
        self.assertEqual(self.row('SELECT status FROM email_sends WHERE contact_id=?',(ids[1],))['status'],'skipped_unsubscribed')

    def test_scan_button_durable_and_parallel_gate(self):
        self.scanner()
        self.assertTrue(imap_sync.request_scan(self.config))
        self.assertFalse(imap_sync.request_scan(self.config))
        self.scanner_engine.guard.acquire()
        self.scanner_engine.tick();self.assertEqual(self.imap.calls,[])
        self.scanner_engine.guard.release();self.scanner_engine.tick()
        self.assertEqual(self.row('SELECT requested,scanning FROM mail_sync_state'),dict(requested=0,scanning=0))

    def test_bounded_fetch_large_message_and_uid_windows(self):
        e=self.scanner({3000:b'x'*(imap_sync.MAX_BYTES+1)});e.tick()
        self.assertEqual(self.row('SELECT reviews FROM mail_sync_state')['reviews'],1)
        searches=[call for call in self.imap.calls if isinstance(call,tuple) and call[0]=='SEARCH']
        self.assertEqual(len(searches),3)
        self.assertEqual(self.row('SELECT last_uid FROM mail_sync_state')['last_uid'],3000)

    def test_config_only_reuses_same_account_secret(self):
        with patch.dict('os.environ',dict(IMAP_ENABLED='true',IMAP_PASSWORD='',SMTP_PASSWORD='private-test',SMTP_USER='same@example.test',IMAP_USER='same@example.test')):
            self.assertTrue(imap_sync.settings().configured)
            self.assertNotIn('private-test',repr(imap_sync.settings()))
            with patch.dict('os.environ',dict(IMAP_USER='other@example.test')):
                self.assertFalse(imap_sync.settings().configured)

    def test_imap_failure_does_not_stop_smtp(self):
        cid,ids=self.prepare(2);e=self.scanner({1:b'bad'});self.imap.fail=True;e.tick()
        self.engine.tick();self.assertEqual(len(self.starts),1)

    def test_os_singleton_lock_and_second_instance_request(self):
        self.scanner()
        entered=threading.Event()
        class StubEngine:
            def __init__(self,**kwargs):pass
            def tick(self):entered.set()
        a,b=imap_sync.Manager(),imap_sync.Manager()
        with patch.object(imap_sync,'settings',return_value=self.config),patch.object(imap_sync,'Engine',StubEngine):
            try:
                a.start();self.assertTrue(entered.wait(2));b.start()
                self.assertIsNone(b.thread)
                self.assertTrue(imap_sync.request_scan(self.config))
            finally:a.shutdown();b.shutdown()
            b.start();b.shutdown() # owner death releases the OS lock

    def test_failure_after_first_message_preserves_committed_cursor_counts(self):
        self.completed();e=self.scanner({1:wire(self.dsn()),2:b'Subject: ordinary\r\n\r\nhi'})
        original=self.imap.uid
        def fail(command,*args):
            if command=='FETCH' and args[0]=='2':raise OSError('lost socket')
            return original(command,*args)
        self.imap.uid=fail;e.tick()
        row=self.row('SELECT * FROM mail_sync_state')
        self.assertEqual(row['last_uid'],1);self.assertEqual(row['contact_changes'],1)
        self.imap.uid=original;self.clock.advance(900);e.tick()
        row=self.row('SELECT * FROM mail_sync_state')
        self.assertEqual(row['last_uid'],2);self.assertEqual(row['contact_changes'],1)
        self.assertEqual(row['new_messages'],2)


class CooldownCase(unittest.TestCase):
    setUp=fixtures.Case.setUp
    tearDown=fixtures.Case.tearDown
    contacts=fixtures.Case.contacts
    campaign=fixtures.Case.campaign
    prepare=fixtures.Case.prepare
    fake_send=fixtures.Case.fake_send
    row=fixtures.Case.row

    def reject(self,reply=b'4.3.0 temporary server busy',code=451):
        self.engine.sender=lambda *a,**k: (_ for _ in ()).throw(smtplib.SMTPDataError(code,reply))
        self.engine.tick()

    def test_safe_auto_resume_900_seconds_and_active_time(self):
        cid,ids=self.prepare(2);self.reject()
        self.assertEqual(self.row('SELECT state FROM campaign_execution')['state'],'auto_cooldown')
        self.engine.sender=self.fake_send;self.clock.advance(899);self.engine.tick();self.assertEqual(len(self.starts),0)
        self.clock.advance(1);self.engine.tick();self.assertEqual(len(self.starts),1)
        self.assertEqual(self.row('SELECT cycle_seconds FROM campaign_execution')['cycle_seconds'],0)

    def test_provider_wait_and_manual_pause_during_cooldown(self):
        cid,ids=self.prepare(2);self.reject(b'4.3.0 temporary busy Retry-After: 30 minutes')
        self.assertEqual(self.row('SELECT smtp_cooldown_until FROM campaign_execution')['smtp_cooldown_until'],self.clock()+1800)
        worker.pause(cid,self.clock());self.clock.advance(1800);self.engine.sender=self.fake_send;self.engine.tick()
        self.assertFalse(self.starts);worker.resume(cid,self.clock());self.engine.tick();self.assertEqual(len(self.starts),1)

    def test_repeated_safe_rejections_are_bounded(self):
        cid,ids=self.prepare(1)
        for i in range(4):
            self.reject()
            self.assertEqual(self.row('SELECT state FROM campaign_execution')['state'],'auto_cooldown' if i<3 else 'problem')
            self.clock.advance(900)
        self.assertEqual(self.row('SELECT auto_resume_count FROM campaign_execution')['auto_resume_count'],3)
        self.engine.sender=self.fake_send;self.engine.tick();self.assertFalse(self.starts)

    def test_auth_policy_5xx_never_auto_resume(self):
        cid,ids=self.prepare(1)
        failures=[smtplib.SMTPAuthenticationError(454,b'temporary authentication failure'),
                  smtplib.SMTPDataError(451,b'temporary reputation issue'),
                  smtplib.SMTPDataError(550,b'5.7.1 rejected')]
        for failure in failures:
            with db.get_connection() as c:
                c.execute("UPDATE campaign_execution SET state='running',updated=?,manual_pause=0,smtp_cooldown_until=0",(self.clock(),))
                c.execute("UPDATE email_sends SET status='pending',outcome_uncertain=0")
                c.execute('UPDATE smtp_control SET blocked_until=0,next_attempt=0')
            self.engine.sender=lambda *a,**k: (_ for _ in ()).throw(failure);self.engine.tick()
            self.assertEqual(self.row('SELECT state FROM campaign_execution')['state'],'problem')
            self.assertEqual(self.row('SELECT smtp_cooldown_until FROM campaign_execution')['smtp_cooldown_until'],0)
            self.clock.advance(1000)

    def test_restart_cooldown_requires_explicit_operator(self):
        cid,ids=self.prepare(1);self.reject();worker.recover(self.clock())
        self.clock.advance(1000);self.engine.sender=self.fake_send;self.engine.tick()
        self.assertFalse(self.starts)
        self.assertEqual(self.row('SELECT state FROM campaign_execution')['state'],'interrupted')

    def test_sleep_during_cooldown_blocks_auto_resume(self):
        cid,ids=self.prepare(1);self.reject()
        self.engine.monotonic=self.clock;self.engine.last_observed=self.clock()
        self.clock.advance(1000);self.engine.sender=self.fake_send;self.engine.tick()
        self.assertFalse(self.starts)
        self.assertEqual(self.row('SELECT state FROM campaign_execution')['state'],'interrupted')

    def test_manual_pause_while_rejection_inflight_wins(self):
        cid,ids=self.prepare(1)
        def fail(*a,**kw):
            worker.pause(cid,self.clock())
            raise smtplib.SMTPDataError(451,b'4.3.0 temporary busy')
        self.engine.sender=fail;self.engine.tick()
        self.assertEqual(self.row('SELECT state FROM campaign_execution')['state'],'manual_paused')
        self.clock.advance(900);self.engine.sender=self.fake_send;self.engine.tick();self.assertFalse(self.starts)

    def test_smtp_failure_does_not_stop_imap_and_review_counts(self):
        self.prepare(1);self.reject(b'4.7.1 [R6] blocked')
        config=imap_sync.Settings(True,password='test')
        fake=FakeIMAP({1:b'Subject: ordinary\r\n\r\nHi'})
        imap_sync.Engine(self.clock,lambda c:fake,config).tick()
        self.assertEqual(self.row('SELECT last_uid FROM mail_sync_state')['last_uid'],1)

    def test_1800_active_break_and_eta(self):
        cid,ids=self.prepare(3)
        with db.get_connection() as c:c.execute('UPDATE campaign_execution SET cycle_seconds=1799')
        self.engine.tick();self.clock.advance(1);self.engine.tick()
        self.assertEqual(self.row('SELECT state FROM campaign_execution')['state'],'auto_break')
        p=worker.execution_payload(cid,self.clock())
        self.assertEqual(p['cooldown_seconds'],300)
        self.assertEqual(p['eta_seconds'],320)
        self.clock.advance(299);self.engine.tick();self.assertEqual(len(self.starts),1)
        self.clock.advance(1);self.engine.tick();self.assertEqual(len(self.starts),2)
        self.assertEqual(self.row('SELECT cycle_seconds FROM campaign_execution')['cycle_seconds'],0)

    def test_full_provider_reply_preserved(self):
        self.prepare(1);reply=b'4.3.0 temporary busy '+b'x'*1200;self.reject(reply)
        self.assertIn('x'*1200,self.row('SELECT detail FROM send_attempt_history')['detail'])

    def test_rolling_limits_apply_after_auto_cooldown(self):
        cid,ids=self.prepare(1);self.reject()
        self.clock.advance(900)
        with db.get_connection() as c:
            sid=c.execute('SELECT id FROM email_sends').fetchone()[0]
            c.executemany('INSERT INTO smtp_attempts(send_id,started) VALUES(?,?)',[(sid,self.clock()-1)]*20)
        self.engine.sender=self.fake_send;self.engine.tick();self.assertFalse(self.starts)
        self.assertGreater(worker.execution_payload(cid,self.clock())['next_attempt_seconds'],0)

    def test_many_distinct_failures_warn_without_resume_loop(self):
        cid,ids=self.prepare(51)
        with db.get_connection() as c:
            sends=c.execute('SELECT id FROM email_sends ORDER BY id LIMIT 50').fetchall()
            for (sid,) in sends:
                c.execute("UPDATE email_sends SET status='smtp_failed' WHERE id=?",(sid,))
                c.execute('''INSERT INTO send_attempt_history(send_id,attempt_number,mode,started,finished,status,message_id)
                    VALUES(?,1,'smtp',?,?,'smtp_failed','<failure@example.test>')''',(sid,self.clock()-10,self.clock()-9))
        self.engine.tick()
        self.assertEqual(len(self.starts),1)
        row=self.row('SELECT state,problem FROM campaign_execution')
        self.assertEqual(row['state'],'running')
        self.assertIn('50',worker.execution_payload(cid,self.clock())['quality_warning'])
        worker.pause(cid,self.clock());worker.resume(cid,self.clock());self.engine.tick()
        self.assertEqual(self.row("SELECT COUNT(*) n FROM execution_events WHERE message LIKE 'Jakość listy:%'")['n'],1)

    def test_verified_later_bounces_count_toward_failure_signal(self):
        cid,ids=self.prepare(2)
        with db.get_connection() as c:
            sid=c.execute('SELECT id FROM email_sends ORDER BY id LIMIT 1').fetchone()[0]
            c.execute("UPDATE email_sends SET status='bounced_later',final_status_at=? WHERE id=?",(worker.stamp(self.clock()),sid))
            c.execute('INSERT INTO execution_events(campaign_id,created,message) VALUES(?,?,?)',(cid,self.clock(),rec.PREFIX+json.dumps(dict(bounce=True,send_id=sid,date=str(int(self.clock()*1000))))))
            self.assertEqual(worker.recent_delivery_failures(c,self.clock()),1)
            self.assertEqual(worker.recent_delivery_failures(c,self.clock()+3601),0)


class SortCase(unittest.TestCase):
    setUp=fixtures.Case.setUp
    tearDown=fixtures.Case.tearDown
    contacts=fixtures.Case.contacts
    campaign=fixtures.Case.campaign
    prepare=fixtures.Case.prepare
    fake_send=fixtures.Case.fake_send
    row=fixtures.Case.row

    def test_global_sort_pagination_stable_filters_allowlist(self):
        ids=self.contacts(1100);cid=self.campaign()
        with db.get_connection() as c:
            c.executemany('UPDATE contacts SET company_name=? WHERE id=?',[(f'Company {1100-i:04}',i) for i in ids])
        for field in ('email','company','last_sent'):
            for direction in ('asc','desc'):
                all_ids=[]
                for page in (1,2,3):
                    r=self.client.get(f'/campaigns/{cid}/recipients?sort={field}&direction={direction}&page={page}')
                    self.assertEqual(r.status_code,200)
                    all_ids.extend(x['id'] for x in r.context['contacts'])
                self.assertEqual(len(all_ids),1100);self.assertEqual(len(set(all_ids)),1100)
                expected=ids if field=='last_sent' or (field=='email')==(direction=='asc') else ids[::-1]
                self.assertEqual(all_ids,expected)
        r=self.client.get(f'/campaigns/{cid}/recipients?sort=email;DROP%20TABLE%20contacts&direction=evil&search=qa00001')
        self.assertEqual(len(r.context['contacts']),1)

    def test_last_acceptance_no_dry_run_and_selection_survives_sort(self):
        cid,ids=self.prepare(3);self.engine.tick();self.clock.advance(20);self.engine.tick()
        target=self.campaign();update_selection(target,ids,ids)
        for direction,expected in [('asc',[ids[2],ids[0],ids[1]]),('desc',[ids[1],ids[0],ids[2]])]:
            r=self.client.get(f'/campaigns/{target}/recipients?sort=last_sent&direction={direction}')
            self.assertEqual([c['id'] for c in r.context['contacts']],expected)
            self.assertEqual(set(r.context['selected']),set(ids))
            self.assertIn('Nigdy',r.text);self.assertIn(f'Kampania #{cid}',r.text)
        # Historical real acceptance remains visible after a later bounce.
        with db.get_connection() as c:
            c.execute("UPDATE email_sends SET status='bounced_later' WHERE contact_id=?",(ids[0],))
        r=self.client.get(f'/campaigns/{target}/recipients?sort=last_sent')
        self.assertTrue(r.context['contacts'][1]['last_smtp_at'])
        self.clock.advance(20);self.engine.tick();self.clock.advance(20);self.engine.tick()
        dry=self.campaign();result=fixtures.mailer.prepare_campaign_send(dry,[ids[2]],'dry_run')
        self.assertTrue(result['started'])
        self.engine.tick()
        r=self.client.get(f'/campaigns/{target}/recipients?sort=last_sent&direction=desc')
        self.assertEqual(r.context['contacts'][0]['last_smtp_campaign'],cid)

    def test_legacy_acceptance_without_new_attempt_ledger(self):
        cid,ids=self.prepare(2);self.engine.tick();target=self.campaign()
        with db.get_connection() as c:
            c.execute('DELETE FROM send_attempt_history')
            c.execute("UPDATE email_sends SET accepted_at=NULL,status='sent' WHERE contact_id=?",(ids[0],))
        r=self.client.get(f'/campaigns/{target}/recipients?sort=last_sent&direction=desc')
        self.assertEqual(r.context['contacts'][0]['id'],ids[0])
        self.assertTrue(r.context['contacts'][0]['last_smtp_at'])


if __name__=='__main__':unittest.main()
