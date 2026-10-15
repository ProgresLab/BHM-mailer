"""Recipient regression sandbox: synthetic SQLite only, port 8018, SMTP OFF."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
QA = ROOT / 'output' / 'recipient-qa'
QA.mkdir(parents=True, exist_ok=True)
os.environ.update(BHM_DB_PATH=str(QA / 'synthetic.sqlite3'),
                  BHM_ASSET_DIR=str(QA / 'assets'), SMTP_ENABLED='false',
                  ADMIN_NOTIFICATION_EMAIL='', UNSUBSCRIBE_SECRET='synthetic-qa-only')
sys.path.insert(0, str(ROOT))
from app import db


def seed():
    db.init_db()
    with db.get_connection() as conn:
        if conn.execute('SELECT COUNT(*) FROM campaigns').fetchone()[0]:
            return
        now = db.utc_now()
        rows = [('marcin@example.test', 'active')] + [
            (f'qa{i:05}@example.test', 'active') for i in range(1500)] + [
            (f'zz-{status}@example.test', status) for status in ('unsubscribed', 'bounced', 'invalid')]
        conn.executemany('''INSERT INTO contacts(email,company_name,country_group,language,status,
            unsubscribe_token,created_at,updated_at) VALUES(?,'QA syntetyczny kontakt','PL','pl',?,?,?,?)''',
            [(email, status, f'qa-{i}', now, now) for i, (email, status) in enumerate(rows)])
        conn.execute('''INSERT INTO campaigns(id,name,subject,language,body,body_html,html,text,status,created_at)
            VALUES(32,'QA — wybór odbiorców','QA — syntetyczny temat','pl','Treść QA',
            '<p>Treść QA</p>','<p>Treść QA</p>','Treść QA','approved',?)''', (now,))


if __name__ == '__main__':
    seed()
    (QA / 'server.pid').write_text(str(os.getpid()), encoding='ascii')
    import uvicorn
    uvicorn.run('app.main:app', host='127.0.0.1', port=8018, log_level='warning')
