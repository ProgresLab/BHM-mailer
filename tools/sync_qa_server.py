"""Synthetic browser acceptance on 8019. Fake IMAP, SMTP forced OFF."""
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
QA=ROOT/'output'/'sync-qa'
QA.mkdir(parents=True,exist_ok=True)
os.environ.update(BHM_DB_PATH=str(QA/'synthetic.sqlite3'),BHM_ASSET_DIR=str(QA/'assets'),
    SMTP_ENABLED='false',SMTP_PASSWORD='',SMTP_USER='qa@example.test',ADMIN_NOTIFICATION_EMAIL='',
    IMAP_ENABLED='true',IMAP_USER='qa@example.test',IMAP_PASSWORD='synthetic',UNSUBSCRIBE_SECRET='qa-synthetic')
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from app import db, imap_sync, main, worker
from test_imap_sync import FakeIMAP


def seed():
    db.init_db()
    with db.get_connection() as c:
        if c.execute('SELECT COUNT(*) FROM campaigns').fetchone()[0]:return
        now=db.utc_now()
        c.executemany('''INSERT INTO contacts(email,company_name,country_group,language,status,unsubscribe_token,created_at,updated_at)
            VALUES(?,?,'PL','pl','active',?,?,?)''',[(f'qa{i:05}@example.test',f'Firma QA {i%7}',f'qa{i}',now,now) for i in range(1100)])
        for cid,status in [(32,'approved'),(33,'sending'),(34,'completed')]:
            c.execute('''INSERT INTO campaigns(id,name,subject,language,body,body_html,html,text,status,created_at)
                VALUES(?,?,'Syntetyczny temat','pl','QA','<p>QA</p>','<p>QA</p>','QA',?,?)''',
                (cid,'QA — '+('sortowanie odbiorców' if cid==32 else 'monitor SMTP' if cid==33 else 'historia akceptacji'),status,now))
        for contact,mode,accepted in [(1,'smtp','2026-10-15T09:00:00+00:00'),(1100,'smtp','2026-10-16T09:00:00+00:00'),(2,'dry_run',None)]:
            sid=c.execute('''INSERT INTO email_sends(campaign_id,contact_id,email,language,subject,html_snapshot,text_snapshot,status,created_at,accepted_at,message_id)
                SELECT 34,id,email,'pl','QA','<p>QA</p>','QA',?,?,?,? FROM contacts WHERE id=?''',
                ('accepted_by_smtp' if mode=='smtp' else 'dry_run',now,accepted,f'<qa{contact}@example.test>',contact)).lastrowid
            c.execute('''INSERT INTO send_attempt_history(send_id,attempt_number,mode,started,finished,status,message_id)
                VALUES(?,1,?,1,2,?,?)''',(sid,mode,'accepted_by_smtp' if mode=='smtp' else 'dry_run',f'<qa{contact}@example.test>'))
        c.execute('''INSERT INTO campaign_execution(campaign_id,state,mode,started,updated,manual_pause,smtp_cooldown_until,problem,failure_kind)
            VALUES(33,'auto_cooldown','dry_run',?,?,0,?,'Tymczasowa odmowa — automatyczne wznowienie','451 4.3.0 temporary server busy')''',
            (time.time(),time.time(),time.time()+900))
    # No actual queue reservation; preserve the monitor fixture across startup.
    with db.get_connection() as c:c.execute("UPDATE campaigns SET status='approved' WHERE id=33")


def seed_iteration():
    """Separate synthetic states; no reservation means no automatic attempt."""
    with db.get_connection() as c:
        now=time.time()
        c.execute('UPDATE campaign_execution SET started=?,updated=?,smtp_cooldown_until=? WHERE campaign_id=33',(now,now,now+900))
        for cid,state in ((35,'auto_cooldown'),(36,'completed_with_errors')):
            c.execute('''INSERT OR IGNORE INTO campaigns(id,name,subject,language,body,html,text,status,created_at)
                VALUES(?,?,'QA','pl','QA','<p>QA</p>','QA','approved',?)''',(cid,'QA R6' if cid==35 else 'QA niepewna próba',db.utc_now()))
            c.execute('''INSERT OR REPLACE INTO campaign_execution(campaign_id,state,mode,started,updated,smtp_cooldown_until,problem,failure_kind)
                VALUES(?,?,'smtp',?,?,?,?,?)''',(cid,state,now,now,now+3600 if cid==35 else 0,
                'Provider R6: jedna ograniczona próba po cooldownie; bez gwarancji odblokowania.' if cid==35 else '',
                '451 4.7.1 [R6] too many failed deliveries' if cid==35 else ''))
        if not c.execute('SELECT 1 FROM email_sends WHERE campaign_id=36').fetchone():
            c.execute('''INSERT INTO email_sends(campaign_id,contact_id,email,language,subject,html_snapshot,text_snapshot,status,created_at,outcome_uncertain)
                SELECT 36,id,email,'pl','QA','<p>QA</p>','QA','delivery_unknown',?,1 FROM contacts WHERE id=3''',(db.utc_now(),))
        c.execute("UPDATE campaigns SET status='completed_with_errors' WHERE id=36")
        c.execute('''INSERT OR IGNORE INTO campaigns(id,name,subject,language,body,html,text,status,created_at)
            VALUES(37,'QA R7','QA','pl','QA','<p>QA</p>','QA','approved',?)''',(db.utc_now(),))
        c.execute('''INSERT OR REPLACE INTO campaign_execution(campaign_id,state,mode,started,updated,problem,failure_kind)
            VALUES(37,'problem','smtp',?,?,?,?)''',(now,now,
            'Provider R7: ponad 30 wiadomości w kolejce one.com. Minimum 60 minut bez prób; potem kontrola operatora. Odblokowanie nie jest gwarantowane.',
            'SMTPDataError: 451 4.7.1 [R7] You have more than 30 messages in queue, try later'))
        c.execute('UPDATE smtp_control SET blocked_until=? WHERE id=1',(now+3600,))


if __name__=='__main__':
    seed()
    seed_iteration()
    imap_sync.manager=imap_sync.Manager(factory=lambda config:FakeIMAP({1:b'Subject: QA\r\n\r\nSynthetic only'}))
    (QA/'server.pid').write_text(str(os.getpid()))
    import uvicorn
    uvicorn.run(main.app,host='127.0.0.1',port=8019,log_level='warning')
