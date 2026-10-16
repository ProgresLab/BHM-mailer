"""Synthetic MIME, isolated SQLite and fake SMTP only."""
import copy
from datetime import datetime, timezone
import json
import smtplib
import unittest
from app import db, importer, mailer, reconciliation as rec
from app.models import ImportCandidate, ImportReport
from app.selection import selected_ids
import test_campaigns as fixtures


def node(mime='text/plain', body='', **fields):
    return dict(mime_type=mime, body=dict(content=body), headers=[dict(name=k.replace('_','-'), value=v) for k,v in fields.items()])


class ReconciliationCase(unittest.TestCase):
    setUp=fixtures.Case.setUp
    tearDown=fixtures.Case.tearDown
    contacts=fixtures.Case.contacts
    campaign=fixtures.Case.campaign
    prepare=fixtures.Case.prepare
    fake_send=fixtures.Case.fake_send
    row=fixtures.Case.row

    def completed(self):
        cid,ids=self.prepare(1)
        self.engine.tick()
        self.clock.advance(20)
        self.engine.tick()
        self.send=self.row('SELECT * FROM email_sends WHERE campaign_id=?',(cid,))
        self.cid,self.contact=cid,ids[0]
        return cid

    def dsn(self, status='5.1.1', action='failed', diagnostic='smtp; 550 5.1.1 User unknown', recipient=None, mid=None):
        root=node('multipart/report', From='Postmaster <support@one.com>', To='marketing@bhm-chemicals.com',
            Message_ID='<report@example.test>', In_Reply_To=mid or self.send['message_id'],
            Authentication_Results='mx.google.com; dkim=pass header.i=@one.com header.s=bounces1')
        root['parts']=[node('message/delivery-status',
            'Final-Recipient: rfc822; '+(recipient or self.send['email'])+'\r\nAction: '+action+'\r\nStatus: '+status+'\r\nDiagnostic-Code: '+diagnostic+'\r\n')]
        return dict(id='gmail-synthetic',internal_date=str(int(self.clock()*1000)),payload=root)

    def unsubscribe(self):
        contact=self.row('SELECT * FROM contacts WHERE id=?',(self.contact,))
        import re
        timestamp=re.search(r'ts=(\d+)',self.send['html_snapshot']).group(1)
        body=f"Unsubscribe request\r\nEmail: {self.send['email']}\r\nToken: {contact['unsubscribe_token']}\r\nCampaign ID: {self.cid}\r\nTimestamp: {timestamp}\r\nSource: unsubscribe.mail.bhm-chemicals.com\r\n"
        return dict(id='gmail-unsubscribe',internal_date=str(int(self.clock()*1000)),payload=node(body=body,
            From='BHM Chemicals Unsubscribe <info@bhm-chemicals.com>', Message_ID='<unsub@example.test>',
            Authentication_Results='mx.google.com; dkim=pass header.i=@bhm-chemicals.com'))

    def propose(self,messages):
        with db.get_connection() as c:return rec.plan(c,self.cid,messages)

    def apply(self,p):
        with db.get_connection() as c:
            c.execute('BEGIN IMMEDIATE');rec.apply(c,p)

    def test_permanent_bounce_preserves_acceptance_and_attempts(self):
        self.completed(); msg=self.dsn(); p=self.propose([msg]);self.apply(p)
        s=self.row('SELECT * FROM email_sends WHERE id=?',(self.send['id'],))
        self.assertEqual(s['status'],'bounced_later')
        for field in ('smtp_response','smtp_code','accepted_at','message_id','sent_at'):
            self.assertEqual(s[field],self.send[field])
        self.assertEqual(self.row('SELECT status FROM contacts WHERE id=?',(self.contact,))['status'],'invalid')
        self.assertEqual(self.row('SELECT status FROM send_attempt_history')['status'],'accepted_by_smtp')

    def test_delay_and_policy_never_disable_contact(self):
        self.completed()
        for status,action,diag in [('4.0.0','delayed','smtp; 450 try later'),('5.7.1','failed','smtp; 550 spam policy')]:
            p=self.propose([self.dsn(status,action,diag)])
            self.assertEqual(p['contacts'],[])
        self.assertEqual(rec.classify('failed','5.0.0','x-error; DNS error NXDOMAIN'),('invalid_domain','invalid'))
        self.assertEqual(rec.classify('failed','5.4.1','smtp; 550 access denied'),('review_microsoft_5.4.1',None))
        self.assertEqual(rec.classify('failed','5.4.1','smtp; 550 5.4.1 Recipient address rejected: Access denied. https://aka.ms/EXOSmtpErrors [MX.prod.outlook.com 2026-10-16]'),('invalid_mailbox_microsoft','invalid'))

    def test_unsubscribe_priority_and_no_notification_send(self):
        self.completed();p=self.propose([self.unsubscribe(),self.dsn()]);self.apply(p)
        evidence=next(e for e in p['events'] if e['key']==p['contacts'][0]['evidence_key'])
        self.assertEqual(evidence['kind'],'unsubscribe')
        self.assertEqual(self.row('SELECT status FROM contacts WHERE id=?',(self.contact,))['status'],'unsubscribed')
        self.assertEqual(self.row('SELECT COUNT(*) n FROM unsubscribe_events')['n'],0)
        later=self.dsn();later['payload']['headers'].append(dict(name='Message-ID',value='<later@example.test>'))
        self.assertEqual(self.propose([later])['contacts'],[])

    def test_false_report_unknown_recipient_campaign_mismatch_and_autoresponder(self):
        self.completed()
        false=self.dsn();false['payload']['headers']=[h for h in false['payload']['headers'] if h['name']!='Authentication-Results']
        unknown=self.dsn(recipient='unknown@example.test')
        wrong=self.dsn(mid='<other-campaign@example.test>')
        auto=dict(id='auto',payload=node(body='Out of office',Subject='Unsubscribe'))
        for msg in [false,unknown,wrong,auto]:
            p=self.propose([msg]);self.assertEqual(p['contacts'],[]);self.assertEqual(p['sends'],[])
        bad=self.unsubscribe();bad['payload']['body']['content']=bad['payload']['body']['content'].replace('Campaign ID: '+str(self.cid),'Campaign ID: 999')
        self.assertEqual(self.propose([bad])['contacts'],[])

    def test_duplicate_replay_and_other_gmail_copy_are_noops(self):
        self.completed();m=self.dsn();duplicate=copy.deepcopy(m);duplicate['id']='other-gmail-id'
        p=self.propose([m,duplicate]);self.assertEqual(sum(e['duplicate'] for e in p['events']),1)
        self.apply(p)
        before=self.row('SELECT COUNT(*) n FROM execution_events')['n']
        replay=self.propose([m,duplicate]);self.apply(replay)
        self.assertEqual(replay['contacts'],[]);self.assertEqual(replay['sends'],[])
        self.assertEqual(self.row('SELECT COUNT(*) n FROM execution_events')['n'],before)

    def test_reimport_and_new_campaign_exclude_both_statuses(self):
        self.completed()
        for status in ('invalid','unsubscribed'):
            with db.get_connection() as c:
                c.execute('UPDATE contacts SET status=? WHERE id=?',(status,self.contact))
                importer.upsert_one(c,ImportCandidate(email=self.send['email'],country_group='PL',language='pl'),ImportReport())
                self.assertEqual(c.execute('SELECT status FROM contacts WHERE id=?',(self.contact,)).fetchone()[0],status)
            cid=self.campaign()
            result=mailer.prepare_campaign_send(cid,[self.contact],'dry_run')
            self.assertFalse(result['started'])

    def test_existing_queue_skips_both_statuses(self):
        cid,ids=self.prepare(2);self.cid=cid
        with db.get_connection() as c:
            c.execute("UPDATE contacts SET status='invalid' WHERE id=?",(ids[0],))
            c.execute("UPDATE contacts SET status='unsubscribed' WHERE id=?",(ids[1],))
        self.engine.tick();self.engine.tick()
        with db.get_connection() as c:
            self.assertEqual([r[0] for r in c.execute('SELECT status FROM email_sends ORDER BY id')],['skipped_invalid','skipped_unsubscribed'])
        self.assertEqual(self.starts,[])

    def test_inflight_recipient_rejection_cannot_overwrite_unsubscribe(self):
        cid,ids=self.prepare(1)
        def reject(*args,**kwargs):
            with db.get_connection() as c:c.execute("UPDATE contacts SET status='unsubscribed' WHERE id=?",(ids[0],))
            raise smtplib.SMTPRecipientsRefused({args[1]:(550,b'5.1.1 User unknown')})
        self.engine.sender=reject;self.engine.tick()
        self.assertEqual(self.row('SELECT status FROM contacts WHERE id=?',(ids[0],))['status'],'unsubscribed')

    def test_busy_queue_and_optimistic_conflict_block_writes(self):
        cid,ids=self.prepare(1)
        with db.get_connection() as c:
            with self.assertRaises(ValueError):rec.ensure_idle(c,cid)
        self.engine.tick();self.clock.advance(20);self.engine.tick()
        self.cid,self.contact=cid,ids[0];self.send=self.row('SELECT * FROM email_sends')
        p=self.propose([self.dsn()])
        with db.get_connection() as c:c.execute("UPDATE contacts SET status='unsubscribed' WHERE id=?",(self.contact,))
        with self.assertRaises(ValueError):self.apply(p)
        self.assertEqual(self.row('SELECT status FROM email_sends')['status'],'accepted_by_smtp')

    def test_details_attachment_and_raw_mime(self):
        self.completed();m=self.dsn()
        m['payload']['parts'][0]['mime_type']='text/plain';m['payload']['parts'][0]['filename']='details.txt'
        self.assertEqual(len(self.propose([m])['contacts']),1)
        import base64
        raw=b'From: support@one.com\r\nContent-Type: multipart/report; boundary=x; report-type=delivery-status\r\n\r\n--x\r\nContent-Type: message/delivery-status\r\n\r\nReporting-MTA: dns; send.one.com\r\n\r\nFinal-Recipient: rfc822; qa@example.test\r\nAction: failed\r\nStatus: 5.1.1\r\nDiagnostic-Code: smtp; 550 user unknown\r\n\r\n--x--\r\n'
        parsed=rec.raw_payload(base64.urlsafe_b64encode(raw).decode())
        self.assertEqual(str(rec.dsn_records(parsed)[0]['Status']),'5.1.1')
        block=b'Final-Recipient: rfc822; qa@example.test\r\nAction: failed\r\nStatus: 5.1.1\r\n'
        encoded=b'Content-Type: message/delivery-status\r\nContent-Transfer-Encoding: base64\r\n\r\n'+base64.b64encode(block)+b'\r\n'
        parsed=rec.raw_payload(base64.urlsafe_b64encode(encoded).decode())
        self.assertEqual(str(rec.dsn_records(parsed)[0]['Status']),'5.1.1')


if __name__=='__main__':unittest.main()
