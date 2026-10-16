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


if __name__=='__main__':
    seed()
    imap_sync.manager=imap_sync.Manager(factory=lambda config:FakeIMAP({1:b'Subject: QA\r\n\r\nSynthetic only'}))
    (QA/'server.pid').write_text(str(os.getpid()))
    import uvicorn
    uvicorn.run(main.app,host='127.0.0.1',port=8019,log_level='warning')
