"""Idempotent recovery and R7 diagnostics: synthetic SQLite/fake SMTP only."""
import smtplib
import unittest
from unittest.mock import patch
from app import db,worker
from tools import run_bhm_operational as launcher
import test_campaigns as fixtures
from tools.reconcile_gmail import snapshot


class Case(unittest.TestCase):
    setUp=fixtures.Case.setUp
    tearDown=fixtures.Case.tearDown
    contacts=fixtures.Case.contacts
    campaign=fixtures.Case.campaign
    prepare=fixtures.Case.prepare
    fake_send=fixtures.Case.fake_send
    row=fixtures.Case.row

    def test_real_crash_recovery_once_then_unknown_is_still_gated(self):
        cid,_=self.prepare(2)
        with db.get_connection() as c:
            sid=c.execute('SELECT MIN(id) FROM email_sends').fetchone()[0]
            c.execute("UPDATE email_sends SET status='sending',attempt_count=1 WHERE id=?",(sid,))
            c.execute("INSERT INTO send_attempt_history(send_id,attempt_number,mode,started,status,message_id) VALUES(?,1,'smtp',?,'sending','<crash@example.test>')",(sid,self.clock()))
        with self.assertRaisesRegex(ValueError,'inflight'):launcher.startup_preflight(db,worker,self.clock())
        worker.recover(self.clock())
        with db.get_connection() as c:
            before=snapshot(c)
            self.assertEqual(c.execute('SELECT status FROM send_attempt_history').fetchone()[0],'delivery_unknown')
        for _ in range(3):
            self.clock.advance(20);worker.recover(self.clock());self.engine.tick()
            with db.get_connection() as c:self.assertEqual(snapshot(c),before)
            with self.assertRaisesRegex(ValueError,'uncertain'):launcher.startup_preflight(db,worker,self.clock())
        self.assertFalse(self.starts)

    def test_r7_manual_cooldown_exact_provider_diagnostic_and_no_auto_probe(self):
        cid,_=self.prepare(2)
        calls=[]
        def refused(*a,**kw):
            calls.append(self.clock())
            raise smtplib.SMTPDataError(451,b'4.7.1 [R7] You have more than 30 messages in queue, try later')
        self.engine.sender=refused;self.engine.tick()
        status=self.client.get(f'/campaigns/{cid}/status.json').json()
        # HTTP uses real time, so use the fake clock for the deadline assertions.
        status=worker.execution_payload(cid,self.clock())
        self.assertEqual(status['execution_state'],'problem')
        self.assertIn('SMTPDataError: 451 4.7.1 [R7]',status['failure_detail'])
        self.assertIn('30 wiadomości',status['problem'])
        self.assertIsNotNone(status['resume_at'])
        self.assertGreaterEqual(status['next_attempt_seconds'],3600)
        with self.assertRaisesRegex(ValueError,'Cooldown'):worker.resume(cid,self.clock()+3599)
        for _ in range(200):self.clock.advance(20);self.engine.tick()
        self.assertEqual(len(calls),1)
        worker.resume(cid,self.clock());self.engine.tick()
        self.assertEqual(len(calls),2)
        self.assertEqual(self.row('SELECT state FROM campaign_execution')['state'],'problem')
        self.assertEqual(self.row('SELECT status FROM contacts ORDER BY id')['status'],'active')

    def test_closed_queue_remains_closed_across_recovery(self):
        from app import campaign_closure as close
        cid,_=self.prepare(1);worker.pause(cid,self.clock())
        with db.get_connection() as c:
            close.apply(c,close.plan(c,cid,1),worker.stamp(self.clock()))
            before=snapshot(c)
        for _ in range(3):
            self.clock.advance(60);worker.recover(self.clock());self.engine.tick()
            self.assertEqual(launcher.startup_preflight(db,worker,self.clock()),[])
            with db.get_connection() as c:self.assertEqual(snapshot(c),before)
        self.assertFalse(self.starts)
