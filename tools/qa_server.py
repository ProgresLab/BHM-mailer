"""Isolated synthetic visual QA. Never uses operational SQLite or real SMTP.

Run: .venv/Scripts/python.exe tools/qa_server.py
Open http://127.0.0.1:8017 . Existing QA fixtures are reused, never reset.
"""
import io
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
QA = ROOT / 'output' / 'qa'
QA.mkdir(parents=True, exist_ok=True)
(QA/'server.pid').write_text(str(os.getpid()),encoding='ascii')
os.environ.update(BHM_DB_PATH=str(QA/'synthetic.sqlite3'), BHM_ASSET_DIR=str(QA/'assets'),
                 SMTP_ENABLED='false', ADMIN_NOTIFICATION_EMAIL='', UNSUBSCRIBE_SECRET='synthetic-qa-only')
sys.path.insert(0,str(ROOT))

from PIL import Image, ImageDraw
from app import db, mailer
from app.assets import store_banner
from app.email_renderer import render_campaign_single
from app.rich_text import html_to_text


def seed():
    db.init_db()
    with db.get_connection() as conn:
        if conn.execute('SELECT COUNT(*) FROM campaigns').fetchone()[0]:
            return
        conn.executemany("""INSERT INTO contacts(email,company_name,country_group,language,status,unsubscribe_token,created_at,updated_at)
            VALUES(?,?,'PL','pl',?,?,?,?)""",[(f'qa{i:05}@example.test','Syntetyczny kontakt',
            'active' if i<5673 else ('unsubscribed','invalid','bounced')[i-5673],f'qa-token-{i}',db.utc_now(),db.utc_now()) for i in range(5676)])
    image=Image.new('RGB',(1200,400),'#11263a')
    draw=ImageDraw.Draw(image)
    draw.rectangle((0,380,1200,400),fill='#0a6b3d')
    draw.text((70,130),'BHM CHEMICALS',fill='white',font_size=60)
    draw.text((74,220),'SYNTETYCZNY BANER / VISUAL QA',fill='#d9e1e8',font_size=25)
    stream=io.BytesIO();image.save(stream,'PNG');banner=store_banner(stream.getvalue())
    body='''<p>Dzień dobry,</p><p>To <strong>syntetyczny podgląd</strong> korespondencji BHM Chemicals.
        Sprawdzamy czytelność treści, <em>wyróżnienia</em> oraz <u>formatowanie</u>.</p>
        <h2>Zakres przykładowej wiadomości</h2><ul data-list="check"><li>Pierwsza pozycja testowa</li>
        <li>Druga pozycja testowa</li><li>Informacja bez deklaracji handlowych</li></ul>
        <p style="font-size:18px">Porozmawiajmy o szczegółach.</p><p><a href="https://bhm-chemicals.com/">Strona BHM Chemicals</a></p>'''
    for name,asset,status in [('QA — kampania z banerem',banner,'draft'),('QA — oryginalne logo',None,'draft'),
                              ('QA — wybór odbiorców',None,'approved'),('QA — monitor 1000 dry-run',banner,'approved')]:
        rendered=render_campaign_single('pl','BHM Chemicals — wiadomość testowa',None,body_html=body,
            headline='Bezpośredni kontakt. Czytelna informacja.',cta_label='Zobacz produkty',
            cta_url='https://bhm-chemicals.com/pl/produkty/',banner_asset=asset)
        with db.get_connection() as conn:
            conn.execute('''INSERT INTO campaigns(name,subject,language,body,body_html,headline,cta_label,cta_url,banner_asset,html,text,status,created_at)
                VALUES(?,'BHM Chemicals — wiadomość testowa','pl',?,?,'Bezpośredni kontakt. Czytelna informacja.',
                'Zobacz produkty','https://bhm-chemicals.com/pl/produkty/',?,?,?,?,?)''',
                (name,html_to_text(body),body,asset,rendered['html'],rendered['text'],status,db.utc_now()))
    mailer.prepare_campaign_send(4,list(range(1,1001)),mode='dry_run')


if __name__=='__main__':
    seed()
    import uvicorn
    uvicorn.run('app.main:app',host='127.0.0.1',port=8017,log_level='warning')
