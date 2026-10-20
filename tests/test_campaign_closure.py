"""Closure and overnight continuation: isolated SQLite and fake transport only."""
import smtplib
import unittest
from unittest.mock import patch

from app import campaign_closure as close,db,worker,reconciliation as rec,mailer
from tools.reconcile_gmail import snapshot
import test_campaigns as fixtures
import test_reconciliation as rf


class Case(unittest.TestCase):
    setUp=fixtures.Case.setUp
    tearDown=fixtures.Case.tearDown
    contacts=fixtures.Case.contacts
    campaign=fixtures.Case.campaign
    prepare=fixtures.Case.prepare
    fake_send=fixtures.Case.fake_send
    row=fixtures.Case.row
    dsn=rf.ReconciliationCase.dsn

    def test_close_312_preserves_661_acceptances_snapshots_and_contact_history(self):
        cid,ids=self.prepare(973)
        with db.get_connection() as c:
            for s in c.execute('SELECT * FROM email_sends ORDER BY id LIMIT 661').fetchall():
                mid=f'<closure-{s["id"]}@example.test>';accepted=worker.stamp(self.clock()-20)
                c.execute("UPDATE email_sends SET status='accepted_by_smtp',accepted_at=?,sent_at=?,message_id=?,attempt_count=1 WHERE id=?",(accepted,accepted,mid,s['id']))
                c.execute("INSERT INTO send_attempt_history(send_id,attempt_number,mode,started,finished,status,message_id) VALUES(?,1,'smtp',?,?,'accepted_by_smtp',?)",(s['id'],self.clock()-21,self.clock()-20,mid))
            c.execute("UPDATE campaign_execution SET state='manual_paused',manual_pause=1")
            c.execute("UPDATE contacts SET last_sent_at='2020-01-01T00:00:00+00:00' WHERE id=?",(ids[-1],))
            before=snapshot(c);p=close.plan(c,cid,312)
            self.assertTrue(close.apply(c,p,worker.stamp(self.clock())))
            close.validate_delta(before,snapshot(c),p)
            after=snapshot(c)
            self.assertFalse(close.apply(c,p,worker.stamp(self.clock())))
            self.assertEqual(snapshot(c),after)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM email_sends WHERE status='cancelled' AND sent_at IS NULL AND accepted_at IS NULL").fetchone()[0],312)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM send_attempt_history').fetchone()[0],661)
        with self.assertRaises(ValueError):worker.resume(cid,self.clock())
        self.engine.tick();self.assertFalse(self.starts)
        with db.get_connection() as c:self.assertIsNone(c.execute('SELECT campaign_id FROM smtp_control').fetchone()[0])
        # Cancelled unattempted contacts can be explicitly selected again;
        # closure is not evidence that their addresses are invalid or sent.
        new=self.campaign()
        from app.selection import update_selection,selected_ids
        self.assertEqual(update_selection(new,ids[-2:],ids[-2:]),2)
        with db.get_connection() as c:self.assertEqual(selected_ids(c,new,eligible=True),ids[-2:])
        self.assertTrue(mailer.prepare_campaign_send(new,ids[-1:],'dry_run')['started'])

    def test_closure_refuses_inflight_unknown_wrong_count_and_prior_attempt(self):
        cid,_=self.prepare(2)
        with db.get_connection() as c:
            with self.assertRaises(ValueError):close.plan(c,cid,2)
            c.execute("UPDATE campaign_execution SET state='manual_paused',manual_pause=1")
            before=snapshot(c)
            with self.assertRaises(ValueError):close.plan(c,cid,312)
            self.assertEqual(snapshot(c),before)
            for status in ('sending','delivery_unknown','rate_limited'):
                c.execute('UPDATE email_sends SET status=? WHERE id=(SELECT MIN(id) FROM email_sends)',(status,))
                with self.assertRaises(ValueError):close.plan(c,cid,1)
            c.execute("UPDATE email_sends SET status='pending',attempt_count=1 WHERE id=(SELECT MIN(id) FROM email_sends)")
            with self.assertRaises(ValueError):close.plan(c,cid,2)

    def test_late_verified_gmail_after_closure_preserves_cancelled_rows(self):
        cid,ids=self.prepare(3);self.engine.tick();worker.pause(cid,self.clock())
        self.send=self.row('SELECT * FROM email_sends ORDER BY id');self.clock.advance(20)
        with db.get_connection() as c:
            p=close.plan(c,cid,2);close.apply(c,p,worker.stamp(self.clock()))
            closed=snapshot(c)
            proposal=rec.plan(c,cid,[self.dsn()],paused_history=True)
            rec.apply(c,proposal,worker.stamp(self.clock()))
            self.assertEqual(c.execute("SELECT COUNT(*) FROM email_sends WHERE status='cancelled'").fetchone()[0],2)
            self.assertEqual(c.execute('SELECT status FROM campaigns WHERE id=?',(cid,)).fetchone()[0],'completed_with_errors')
            self.assertEqual(snapshot(c)['send_attempt_history'],closed['send_attempt_history'])
            self.assertFalse(rec.plan(c,cid,[self.dsn()],paused_history=True)['contacts'])

    def test_close_definite_r7_refusal_preserves_attempt_and_unsent_dates(self):
        cid,ids=self.prepare(3)
        self.engine.tick();self.clock.advance(20)
        def refused(*a,**kw):
            raise smtplib.SMTPDataError(451,b'4.7.1 [R7] You have more than 30 messages in queue, try later')
        self.engine.sender=refused;self.engine.tick()
        with db.get_connection() as c:
            before=snapshot(c)
            with self.assertRaises(ValueError):close.plan(c,cid,1)
            p=close.plan(c,cid,1,1)
            close.apply(c,p,worker.stamp(self.clock()))
            close.validate_delta(before,snapshot(c),p)
            self.assertEqual(snapshot(c)['send_attempt_history'],before['send_attempt_history'])
            self.assertEqual(snapshot(c)['contacts'],before['contacts'])
            failed=c.execute("SELECT * FROM email_sends WHERE status='smtp_failed'").fetchone()
            self.assertIsNone(failed['accepted_at']);self.assertIsNone(failed['sent_at'])
            self.assertIn('[R7]',failed['last_error'])
            self.assertEqual(c.execute("SELECT COUNT(*) FROM email_sends WHERE accepted_at IS NOT NULL").fetchone()[0],1)
            after=snapshot(c)
            self.assertFalse(close.apply(c,p,worker.stamp(self.clock())))
            self.assertEqual(snapshot(c),after)
        with self.assertRaises(ValueError):worker.resume(cid,self.clock()+3601)
        self.engine.tick();self.assertEqual(len(self.starts),1)

    def test_refusal_closure_rejects_unknown_unfinished_or_conflicting_history(self):
        cid,_=self.prepare(2)
        def refused(*a,**kw):raise smtplib.SMTPDataError(451,b'4.7.1 [R7] queue')
        self.engine.sender=refused;self.engine.tick()
        with db.get_connection() as c:
            for column,value in [('status','delivery_unknown'),('finished',None),('smtp_code','250')]:
                with self.subTest(column=column):
                    c.execute('SAVEPOINT bad')
                    c.execute('UPDATE send_attempt_history SET '+column+'=?',(value,))
                    with self.assertRaises(ValueError):close.plan(c,cid,1,1)
                    c.execute('ROLLBACK TO bad');c.execute('RELEASE bad')

    def test_explicit_legacy_refusal_preservation_closes_without_inventing_history(self):
        cid,_=self.prepare(3)
        with db.get_connection() as c:
            sid=c.execute('SELECT MIN(id) FROM email_sends').fetchone()[0]
            c.execute("UPDATE campaign_execution SET state='manual_paused',manual_pause=1")
            c.execute("UPDATE email_sends SET status='rate_limited',attempt_count=1,smtp_code='451',last_error='Legacy 451 refusal; no immutable ledger' WHERE id=?",(sid,))
            before=snapshot(c)
            with self.assertRaises(ValueError):close.plan(c,cid,2,1)
            with self.assertRaises(ValueError):close.plan(c,cid,2,0,2)
            p=close.plan(c,cid,2,0,1)
            self.assertEqual(p['preserved_refused_ids'],[sid])
            close.apply(c,p,worker.stamp(self.clock()))
            close.validate_delta(before,snapshot(c),p)
            after=snapshot(c)
            self.assertEqual(next(r for r in after['email_sends'] if r['id']==sid),
                             next(r for r in before['email_sends'] if r['id']==sid))
            self.assertEqual(after['contacts'],before['contacts'])
            self.assertEqual(after['send_attempt_history'],before['send_attempt_history'])
            self.assertFalse(close.apply(c,p,worker.stamp(self.clock())))
            self.assertEqual(snapshot(c),after)
        with self.assertRaises(ValueError):worker.resume(cid,self.clock())
        self.engine.tick();self.assertFalse(self.starts)

    def test_preserved_refusal_rejects_ledger_acceptance_unknown_and_non4xx(self):
        cid,_=self.prepare(2)
        with db.get_connection() as c:
            sid=c.execute('SELECT MIN(id) FROM email_sends').fetchone()[0]
            c.execute("UPDATE campaign_execution SET state='manual_paused',manual_pause=1")
            c.execute("UPDATE email_sends SET status='rate_limited',attempt_count=1,smtp_code='451' WHERE id=?",(sid,))
            for column,value in [('accepted_at','2020-01-01'),('sent_at','2020-01-01'),
                                 ('outcome_uncertain',1),('smtp_code','250'),('smtp_code','unknown')]:
                with self.subTest(column=column):
                    c.execute('SAVEPOINT bad')
                    c.execute('UPDATE email_sends SET '+column+'=? WHERE id=?',(value,sid))
                    with self.assertRaises(ValueError):close.plan(c,cid,1,0,1)
                    c.execute('ROLLBACK TO bad');c.execute('RELEASE bad')
            c.execute("INSERT INTO send_attempt_history(send_id,attempt_number,mode,started,finished,status,smtp_code,message_id) VALUES(?,1,'smtp',?,?,'rate_limited','451','<legacy-test@example.test>')",(sid,self.clock()-1,self.clock()))
            with self.assertRaises(ValueError):close.plan(c,cid,1,0,1)
            # Complete definite history still uses the pre-existing refusal path.
            close.plan(c,cid,1,1)
            with self.assertRaises(ValueError):close.plan(c,cid,1,1,1)

    def test_1000_temporary_failures_continue_without_manual_resume(self):
        cid,_=self.prepare(1000);calls={};starts=[]
        def sender(*a,**kw):
            email=a[1];calls[email]=calls.get(email,0)+1;starts.append(self.clock())
            number=int(email[2:7]);attempt=calls[email]
            if number in {2,200,600,800} and attempt==1:
                raise smtplib.SMTPDataError(451,b'4.3.0 temporary server busy')
            if number==7 and attempt<3:
                raise smtplib.SMTPRecipientsRefused({email:(450,b'4.2.0 temporary mailbox busy')})
            return self.fake_send(*a,**kw)
        self.engine.sender=sender
        with patch.object(worker,'resume',side_effect=AssertionError('No manual resume allowed')) as resume:
            for _ in range(5000):
                self.engine.tick()
                row=self.row('SELECT * FROM campaign_execution')
                self.assertNotIn(row['state'],{'problem','manual_paused','interrupted'})
                if row['state']=='completed':break
                self.clock.advance(20)
            else:self.fail('Autonomous synthetic campaign did not finish')
            resume.assert_not_called()
        self.assertEqual(len(calls),1000);self.assertEqual(len(starts),1006)
        self.assertGreaterEqual(min(b-a for a,b in zip(starts,starts[1:])),20)
        with db.get_connection() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM email_sends WHERE status='accepted_by_smtp' AND accepted_at IS NOT NULL").fetchone()[0],1000)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM email_sends WHERE status IN ('pending','sending','delivery_unknown','rate_limited')").fetchone()[0],0)
            self.assertGreater(c.execute("SELECT COUNT(*) FROM execution_events WHERE message LIKE 'Automatyczna przerwa 5%'").fetchone()[0],0)
        print({'autonomous_contacts':1000,'calls':len(starts),'accepted':1000,'manual_resumes':0,'virtual_seconds':self.clock()-1000000})


if __name__=='__main__':unittest.main()
