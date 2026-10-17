"""Operational iteration: synthetic DB, fake SMTP/MIME/IMAP and virtual hours."""
import copy
import json
import smtplib
import sqlite3
import unittest
from unittest.mock import patch

from app import db, worker, reconciliation as rec, imap_sync
from tools.reconcile_gmail import snapshot, validate_delta
import test_campaigns as fixtures
import test_reconciliation as rf
import test_imap_sync as imf


class Case(unittest.TestCase):
    setUp=fixtures.Case.setUp
    tearDown=fixtures.Case.tearDown
    contacts=fixtures.Case.contacts
    campaign=fixtures.Case.campaign
    prepare=fixtures.Case.prepare
    fake_send=fixtures.Case.fake_send
    row=fixtures.Case.row
    completed=rf.ReconciliationCase.completed
    dsn=rf.ReconciliationCase.dsn
    unsubscribe=rf.ReconciliationCase.unsubscribe

    def test_661_accepted_312_pending_history_reconciliation_and_replay(self):
        cid,ids=self.prepare(973)
        with db.get_connection() as c:
            sends=c.execute('SELECT * FROM email_sends ORDER BY id LIMIT 661').fetchall()
            for s in sends:
                mid=f'<synthetic-{s["id"]}@example.test>'
                c.execute("UPDATE email_sends SET status='accepted_by_smtp',accepted_at=?,sent_at=?,message_id=?,attempt_count=1 WHERE id=?",(worker.stamp(self.clock()-20),worker.stamp(self.clock()-20),mid,s['id']))
                c.execute("INSERT INTO send_attempt_history(send_id,attempt_number,mode,started,finished,status,message_id) VALUES(?,1,'smtp',?,?,'accepted_by_smtp',?)",(s['id'],self.clock()-21,self.clock()-20,mid))
            c.execute("UPDATE campaign_execution SET state='manual_paused',manual_pause=1")
            c.execute('UPDATE contacts SET last_sent_at=? WHERE id=?',('2020-01-01T00:00:00+00:00',ids[-1]))
            self.send=dict(c.execute('SELECT * FROM email_sends ORDER BY id').fetchone())
            self.cid,self.contact=cid,ids[0]
            c.commit()  # fixture helper reads through an independent connection
            messages=[self.dsn(),self.unsubscribe()]
            before=snapshot(c)
            with self.assertRaises(ValueError):rec.plan(c,cid,messages)
            p=rec.plan(c,cid,messages,paused_history=True)
            rec.apply(c,p,worker.stamp(self.clock()))
            validate_delta(before,snapshot(c),p)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM email_sends WHERE status='pending' AND accepted_at IS NULL AND sent_at IS NULL").fetchone()[0],312)
            self.assertEqual(c.execute('SELECT last_sent_at FROM contacts WHERE id=?',(ids[-1],)).fetchone()[0],'2020-01-01T00:00:00+00:00')
            self.assertEqual(c.execute('SELECT campaign_id FROM smtp_control').fetchone()[0],cid)
            self.assertEqual(c.execute('SELECT status FROM campaigns WHERE id=?',(cid,)).fetchone()[0],'sending')
            after=snapshot(c);replay=rec.plan(c,cid,messages,paused_history=True);rec.apply(c,replay)
            self.assertEqual(snapshot(c),after)
            raw=imf.wire(self.dsn())
            result=imap_sync.process_message(c,raw,self.clock(),imap_sync.Settings(True,password='qa'),self.clock())
            self.assertEqual(result['contact_changes'],0)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM send_attempt_history').fetchone()[0],661)

    def test_history_guard_refuses_running_and_inflight(self):
        cid,_=self.prepare(2)
        with db.get_connection() as c:
            with self.assertRaises(ValueError):rec.ensure_paused_history(c,cid)
            c.execute("UPDATE campaign_execution SET state='manual_paused',manual_pause=1")
            rec.ensure_paused_history(c,cid)
            c.execute("UPDATE email_sends SET status='sending' WHERE id=(SELECT MIN(id) FROM email_sends)")
            with self.assertRaises(ValueError):rec.ensure_paused_history(c,cid)

    def test_offline_fence_releases_port_when_worker_lock_is_owned(self):
        from tools.stopped_runtime import stopped_runtime
        # No real port access in unit tests. The real synthetic worker file lock
        # still proves that a maintenance importer cannot race its owner.
        self.engine.tick()
        owner=worker.Manager()
        with patch.object(worker,'Engine'):
            owner.start()
        try:
            with patch('tools.stopped_runtime.socket.socket') as factory:
                with self.assertRaises(OSError):
                    with stopped_runtime(db.DB_PATH):self.fail('Worker lock was bypassed')
                factory.return_value.close.assert_called_once()
        finally:
            owner.shutdown()

    def test_historical_bulk_import_is_not_fresh_failure(self):
        cid,_=self.prepare(60)
        with db.get_connection() as c:
            for (sid,) in c.execute('SELECT id FROM email_sends').fetchall():
                c.execute("UPDATE email_sends SET status='bounced_later',final_status_at=? WHERE id=?",(worker.stamp(self.clock()),sid))
                c.execute('INSERT INTO execution_events(campaign_id,created,message) VALUES(?,?,?)',(cid,self.clock(),rec.PREFIX+json.dumps(dict(bounce=True,send_id=sid,date=str(int((self.clock()-7200)*1000))))))
            self.assertEqual(worker.recent_delivery_failures(c,self.clock()),0)

    def test_r6_single_hour_probe_then_operator_if_still_blocked(self):
        cid,_=self.prepare(2)
        calls=[]
        def reject(*a,**kw):
            calls.append(self.clock())
            raise smtplib.SMTPDataError(451,b'4.7.1 [R6] too many failed deliveries Retry-After: 2 hours')
        self.engine.sender=reject;self.engine.tick()
        state=self.row('SELECT * FROM campaign_execution')
        self.assertEqual(state['smtp_cooldown_until'],self.clock()+7200)
        p=worker.execution_payload(cid,self.clock());self.assertTrue(p['provider_wait']);self.assertIsNone(p['eta_seconds'])
        self.clock.advance(7199);self.engine.tick();self.assertEqual(len(calls),1)
        self.clock.advance(1);self.engine.tick();self.assertEqual(len(calls),2)
        self.assertEqual(self.row('SELECT state FROM campaign_execution')['state'],'problem')
        self.clock.advance(10000);self.engine.tick();self.assertEqual(len(calls),2)

    def test_recipient_temporary_backoff_bounded_then_next_address(self):
        cid,_=self.prepare(2);calls=[]
        def reject(*a,**kw):
            calls.append(self.clock())
            raise smtplib.SMTPRecipientsRefused({a[1]:(450,b'4.2.0 temporary mailbox busy')})
        self.engine.sender=reject;self.engine.tick()
        self.clock.advance(900);self.engine.tick()
        self.assertEqual(self.row('SELECT smtp_cooldown_until FROM campaign_execution')['smtp_cooldown_until'],self.clock()+1800)
        self.clock.advance(1800);self.engine.tick()
        s=self.row('SELECT * FROM email_sends ORDER BY id')
        self.assertEqual(s['status'],'smtp_failed');self.assertIsNone(s['accepted_at']);self.assertIsNone(s['sent_at'])
        self.engine.sender=self.fake_send;self.clock.advance(20);self.engine.tick()
        self.assertEqual(len(self.starts),1);self.assertEqual(len(calls),3)

    def test_uncertain_continues_other_recipient_without_retry_and_completes_errors(self):
        cid,_=self.prepare(2)
        self.engine.sender=lambda *a,**kw: (_ for _ in ()).throw(TimeoutError('after DATA'))
        self.engine.tick();unknown=self.row('SELECT * FROM email_sends ORDER BY id')
        self.assertEqual(unknown['status'],'delivery_unknown');self.assertIsNone(unknown['accepted_at'])
        self.engine.sender=self.fake_send;self.clock.advance(20);self.engine.tick();self.clock.advance(20);self.engine.tick()
        self.assertEqual(self.row('SELECT state FROM campaign_execution')['state'],'completed_with_errors')
        self.assertEqual(self.row('SELECT attempt_count FROM email_sends WHERE id=?',(unknown['id'],))['attempt_count'],1)
        self.assertEqual(len(self.starts),1)
        with self.assertRaises(ValueError):worker.resolve_uncertain(unknown['id'],'retry_not_accepted','No acceptance evidence supplied',False,self.clock())

    def test_three_consecutive_transport_uncertainties_stop_account(self):
        self.prepare(5)
        self.engine.sender=lambda *a,**kw: (_ for _ in ()).throw(TimeoutError('transport'))
        for _ in range(3):self.engine.tick();self.clock.advance(20)
        self.assertEqual(self.row('SELECT state FROM campaign_execution')['state'],'problem')
        self.assertEqual(self.row("SELECT COUNT(*) n FROM email_sends WHERE status='pending'")['n'],2)

    def test_data_recipient_rejection_and_configuration_error_are_distinct(self):
        cid,_=self.prepare(3)
        self.engine.sender=lambda *a,**kw: (_ for _ in ()).throw(smtplib.SMTPDataError(550,b'5.1.1 user unknown'))
        self.engine.tick()
        self.assertEqual(self.row('SELECT status FROM contacts ORDER BY id')['status'],'invalid')
        self.assertEqual(self.row('SELECT state FROM campaign_execution')['state'],'running')
        self.clock.advance(20)
        self.engine.sender=lambda *a,**kw: (_ for _ in ()).throw(ValueError('invalid sender configuration'))
        self.engine.tick()
        self.assertEqual(self.row('SELECT state FROM campaign_execution')['state'],'problem')

    def test_recipient_tls_configuration_refusal_stops_account_without_invalid(self):
        self.prepare(2)
        self.engine.sender=lambda *a,**kw: (_ for _ in ()).throw(smtplib.SMTPRecipientsRefused({a[1]:(553,b'This route requires TLS 1.2')}))
        self.engine.tick()
        self.assertEqual(self.row('SELECT state FROM campaign_execution')['state'],'problem')
        self.assertEqual(self.row('SELECT status FROM contacts ORDER BY id')['status'],'active')
        self.assertEqual(rec.classify('failed','5.1.1','TLS certificate invalid recipient')[1],None)

    def test_new_campaign_cannot_retry_previous_unknown_even_after_cancel(self):
        from app import mailer
        from app.selection import update_selection,selected_ids
        cid,ids=self.prepare(2)
        self.engine.sender=lambda *a,**kw: (_ for _ in ()).throw(TimeoutError('after DATA'))
        self.engine.tick();unknown=self.row('SELECT * FROM email_sends ORDER BY id')
        self.engine.sender=self.fake_send;self.clock.advance(20);self.engine.tick();self.clock.advance(20);self.engine.tick()
        new=self.campaign()
        self.assertEqual(update_selection(new,ids,ids),1)
        with db.get_connection() as c:self.assertEqual(selected_ids(c,new,eligible=True),ids[1:])
        response=self.client.get(f'/campaigns/{new}/recipients?active_only=0')
        self.assertIn('Niepewna próba',response.text)
        worker.resolve_uncertain(unknown['id'],'cancel','Operator chooses no retry',now=self.clock())
        # Direct API callers cannot bypass selection's eligibility protection.
        result=mailer.prepare_campaign_send(new,[ids[0]],'smtp')
        self.assertFalse(result['started'])

    def test_large_imap_report_reanalysis_no_partial_mime_or_cursor_reset(self):
        self.completed();config=imap_sync.Settings(True,password='qa')
        raw=imf.wire(self.dsn())+b'\r\n'+b' '*(imap_sync.MAX_BYTES+20)
        fake=imf.FakeIMAP({1:raw},received=self.clock())
        full,received,oversized=imap_sync.fetch_report(fake,1)
        self.assertFalse(oversized);self.assertEqual(full,raw)
        self.assertEqual(len([c for c in fake.calls if c[0]=='FETCH']),2)
        with db.get_connection() as c:
            imap_sync.ensure_state(c,config)
            c.execute("UPDATE mail_sync_state SET uidvalidity='123',last_uid=2")
            c.execute("INSERT INTO mail_sync_messages VALUES(?,'123',1,?,'review_required: message exceeds 1 MiB')",(config.key,self.clock()))
            result=imap_sync.reanalyse_review(c,config,'123',1,raw,received,self.clock())
            self.assertEqual(result['contact_changes'],1)
            self.assertEqual(c.execute('SELECT last_uid FROM mail_sync_state').fetchone()[0],2)
            with self.assertRaises(ValueError):imap_sync.reanalyse_review(c,config,'456',1,raw,received,self.clock())
        class Partial(imf.FakeIMAP):
            def uid(self,*a):
                typ,data=super().uid(*a)
                meta,body=data[0];return typ,[(meta,body[:-10]),data[1]]
        with self.assertRaisesRegex(ValueError,'Incomplete'):
            imap_sync.fetch_report(Partial({1:imf.wire(self.dsn())},received=self.clock()),1)

    def test_1000_virtual_hours_mixed_failures_no_duplicate_acceptance(self):
        cid,_=self.prepare(1000);calls={};starts=[];paused=False;restarted=False
        def sender(*a,**kw):
            email=a[1];calls[email]=calls.get(email,0)+1;starts.append(self.clock())
            num=int(email[2:7]);n=calls[email]
            if num==2:raise smtplib.SMTPRecipientsRefused({email:(550,b'5.1.1 user unknown')})
            if num==3 and n<3:raise smtplib.SMTPRecipientsRefused({email:(450,b'4.2.0 temporarily busy')})
            if num==5 and n==1:raise smtplib.SMTPDataError(451,b'4.7.1 [R6] too many failed deliveries')
            if num==7:raise TimeoutError('after DATA')
            if num==9 and n==1:raise smtplib.SMTPAuthenticationError(535,b'bad credentials')
            return self.fake_send(*a,**kw)
        self.engine.sender=sender
        for _ in range(5000):
            self.engine.tick();row=self.row('SELECT * FROM campaign_execution')
            if row['state']=='auto_cooldown' and not paused:
                worker.pause(cid,self.clock());self.clock.advance(1000);self.engine.tick()
                self.assertEqual(self.row('SELECT state FROM campaign_execution')['state'],'manual_paused')
                worker.resume(cid,self.clock());paused=True
            if len(calls)>300 and not restarted:
                worker.recover(self.clock());self.engine.tick();self.assertEqual(self.row('SELECT state FROM campaign_execution')['state'],'interrupted')
                worker.resume(cid,self.clock());restarted=True
            if row['state']=='problem':
                self.assertIn('535',row['failure_kind']);self.clock.advance(300);worker.resume(cid,self.clock())
            if row['state']=='completed_with_errors':break
            self.clock.advance(20)
        else:self.fail('Virtual campaign did not finish')
        self.assertTrue(paused and restarted)
        self.assertGreater(self.clock()-1000000,6*3600)
        self.assertGreaterEqual(min(b-a for a,b in zip(starts,starts[1:])),20)
        self.assertEqual(len(calls),1000);self.assertEqual(calls['qa00007@example.test'],1)
        with db.get_connection() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM send_attempt_history WHERE status='accepted_by_smtp'").fetchone()[0],997)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM email_sends WHERE accepted_at IS NOT NULL").fetchone()[0],997)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM email_sends WHERE status IN ('pending','sending','rate_limited')").fetchone()[0],0)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM email_sends WHERE status='delivery_unknown'").fetchone()[0],1)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM (SELECT send_id FROM send_attempt_history WHERE status='accepted_by_smtp' GROUP BY send_id HAVING COUNT(*)>1)").fetchone()[0],0)
        print(json.dumps(dict(simulation='1000 mixed failures',virtual_seconds=self.clock()-1000000,smtp_calls=len(starts),accepted=997,uncertain=1,failed=2)))


if __name__=='__main__':unittest.main()
