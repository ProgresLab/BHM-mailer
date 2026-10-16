"""Operational startup gates: synthetic SQLite only, no real sockets or mail."""
from dataclasses import replace
import os
import socket
from unittest.mock import Mock, patch
import unittest
import threading
import time

from app import db, imap_sync, mailer, worker
from tools import run_bhm_operational as launcher
import test_campaigns as fixtures


class OperationalCase(unittest.TestCase):
    setUp = fixtures.Case.setUp
    tearDown = fixtures.Case.tearDown
    contacts = fixtures.Case.contacts
    campaign = fixtures.Case.campaign
    prepare = fixtures.Case.prepare
    fake_send = fixtures.Case.fake_send
    row = fixtures.Case.row

    def snapshot(self):
        with db.get_connection() as conn:
            return launcher.rows(conn)

    def paused_legacy(self):
        self.contacts(1)
        with db.get_connection() as conn:
            for cid in (17,18,28):
                conn.execute("INSERT INTO campaigns(id,name,status,created_at,language,subject,body,html,text) VALUES(?,'Synthetic legacy','sending',?,'pl','QA','QA','<p>QA</p>','QA')",(cid,db.utc_now()))
                conn.execute('''INSERT INTO campaign_execution(campaign_id,state,mode,manual_pause,started,updated,problem)
                    VALUES(?,'interrupted','smtp',1,1,1,?)''',(cid,'Proces został przerwany. Wymagana kontrola kolejki i jawne wznowienie.'))

    def test_exact_recovery_on_copy_and_idle_engine_never_sends(self):
        self.paused_legacy()
        before = self.snapshot()
        self.assertEqual(launcher.startup_preflight(db, worker, self.clock()), [17,18,28])
        self.assertEqual(self.snapshot(), before)
        sender = Mock()
        worker.Engine(self.clock, sender, fixtures.settings).tick()
        sender.assert_not_called()
        self.assertEqual(self.snapshot(), before)

    def test_no_recovery_for_clean_database(self):
        self.assertEqual(launcher.startup_preflight(db, worker, self.clock()), [])

    def test_notifications_preserved_and_block_activation(self):
        ids = self.contacts(1)
        for status in ('pending','queued','sending','uncertain'):
            with self.subTest(status=status):
                with db.get_connection() as c:
                    c.execute('DELETE FROM unsubscribe_events')
                    c.execute('''INSERT INTO unsubscribe_events(contact_id,email,token,created_at,notification_sent,notification_status)
                        VALUES(?,'qa@example.test','synthetic-token',?,0,?)''',(ids[0],db.utc_now(),status))
                before = self.snapshot()
                with self.assertRaisesRegex(ValueError,'admin_notifications'):
                    launcher.startup_preflight(db, worker, self.clock())
                self.assertEqual(self.snapshot(), before)

    def test_active_and_reserved_work_blocks_without_recovery(self):
        self.prepare(1)
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError,'reserved'):
            launcher.startup_preflight(db, worker, self.clock())
        self.assertEqual(self.snapshot(), before)

    def test_cooldown_blocks_even_without_reservation(self):
        with db.get_connection() as c:
            c.execute('UPDATE smtp_control SET blocked_until=?',(self.clock()+900,))
        with self.assertRaisesRegex(ValueError,'account_cooldown'):
            launcher.startup_preflight(db, worker, self.clock())

    def test_duplicate_exits_before_import_preflight_or_server(self):
        sock = Mock()
        sock.bind.side_effect = OSError('occupied')
        with patch.object(launcher,'configure'), patch.object(launcher.socket,'socket',return_value=sock), patch.object(launcher,'startup_preflight') as preflight:
            self.assertEqual(launcher.main([]),1)
            preflight.assert_not_called()
        sock.close.assert_called_once()

    def test_modes_paths_and_identity_validation(self):
        with patch.dict(os.environ,{},clear=True), patch.object(launcher.os,'chdir'):
            launcher.configure()
            self.assertEqual(os.environ['SMTP_ENABLED'],'true')
            self.assertEqual(os.environ['IMAP_ENABLED'],'true')
            self.assertEqual(os.environ['BHM_DB_PATH'],str(launcher.ROOT/'data'/'bhm_mailer.sqlite3'))
            self.assertEqual(os.environ['BHM_ASSET_DIR'],str(launcher.ROOT/'uploads'/'campaign_assets'))
        config = replace(fixtures.settings(),smtp_host=mailer.ONE_COM_SMTP_HOST,
            smtp_user=mailer.ONE_COM_SMTP_USER,smtp_from_email=mailer.ONE_COM_FROM_EMAIL,
            smtp_envelope_from=mailer.ONE_COM_ENVELOPE_FROM,smtp_reply_to=mailer.ONE_COM_REPLY_TO)
        with patch.object(mailer,'get_mail_settings',return_value=config), patch.object(imap_sync,'settings',return_value=imap_sync.Settings(True,password='synthetic')):
            self.assertTrue(launcher.configuration_ok(mailer,imap_sync))
            for field,value in [('unsubscribe_secret',''),('smtp_reply_to','wrong@example.test'),('smtp_envelope_from','wrong@example.test'),('smtp_use_ssl',False),('smtp_host','fake.invalid'),('public_unsubscribe_base_url','http://localhost/unsubscribe')]:
                with self.subTest(field=field),patch.object(mailer,'get_mail_settings',return_value=replace(config,**{field:value})):
                    self.assertFalse(launcher.configuration_ok(mailer,imap_sync))

    def test_headless_no_approval_preserves_database_and_never_loads_uvicorn(self):
        self.paused_legacy()
        before = self.snapshot()
        with patch.object(launcher,'configure'),patch.object(launcher.socket,'socket'),patch.object(launcher,'configuration_ok',return_value=True),patch.object(launcher.sys.stdin,'isatty',return_value=False):
            self.assertEqual(launcher.main([]),1)
        self.assertEqual(self.snapshot(),before)

    def test_explicit_approval_uses_one_server_and_prebound_socket(self):
        self.paused_legacy()
        before = self.snapshot()
        import uvicorn
        sock = Mock()
        with patch.object(launcher,'configure'),patch.object(launcher.socket,'socket',return_value=sock),patch.object(launcher,'configuration_ok',return_value=True),patch.object(launcher,'ROOT',self.test_root),patch.object(uvicorn,'Server') as server:
            self.assertEqual(launcher.main(['--approve-recovery-for','17','18','28']),0)
            self.assertEqual(server.call_args.args[0].workers,1)
            self.assertFalse(server.call_args.args[0].reload)
            server.return_value.run.assert_called_once_with(sockets=[sock])
        self.assertEqual(self.snapshot(),before)

    def test_mismatched_approval_cannot_start_server(self):
        self.paused_legacy()
        import uvicorn
        with patch.object(launcher,'configure'),patch.object(launcher.socket,'socket'),patch.object(launcher,'configuration_ok',return_value=True),patch.object(uvicorn,'Server') as server:
            self.assertEqual(launcher.main(['--approve-recovery-for','17','18']),1)
            server.assert_not_called()

    def test_no_cross_campaign_automatic_selection(self):
        from app.selection import selected_ids, update_selection
        ids = self.contacts(2)
        first, second = self.campaign(), self.campaign()
        update_selection(first,ids,ids)
        with db.get_connection() as c:
            self.assertEqual(selected_ids(c,first),ids)
            self.assertEqual(selected_ids(c,second),[])

    def test_both_threads_run_and_imap_progresses_during_smtp(self):
        from test_imap_sync import FakeIMAP
        entered, release = threading.Event(), threading.Event()
        def blocked_sender(*args, **kwargs):
            entered.set()
            if not release.wait(5):
                raise RuntimeError('Synthetic sender timeout')
            return self.fake_send(*args, **kwargs)
        engine = worker.Engine(self.clock, blocked_sender, fixtures.settings)
        smtp = worker.Manager()
        imap = imap_sync.Manager(factory=lambda config:FakeIMAP({1:b'Subject: Synthetic\r\n\r\nQA'}))
        config = imap_sync.Settings(True,password='synthetic')
        with patch.object(worker,'Engine',return_value=engine),patch.object(imap_sync,'settings',return_value=config):
            try:
                smtp.start()
                self.prepare(1)
                smtp.wake.set()
                self.assertTrue(entered.wait(3))
                imap.start()
                deadline = time.monotonic()+3
                while time.monotonic()<deadline:
                    with db.get_connection() as c:
                        if c.execute('SELECT COUNT(*) FROM mail_sync_messages').fetchone()[0]:
                            break
                    time.sleep(.02)
                else:
                    self.fail('IMAP blocked by synthetic SMTP')
                self.assertTrue(smtp.available)
                self.assertTrue(imap.thread.is_alive())
                self.assertEqual(self.client.get('/').status_code,200)
            finally:
                release.set()
                imap.shutdown()
                smtp.shutdown()
