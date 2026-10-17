"""Read-only IMAP diagnosis into a PRIVATE copy; never imports app.main.

Fetch only reports previously marked for review (plus recent unmatched reports),
using EXAMINE/PEEK and the existing local credential. No SMTP or live DB writes.
"""
from dataclasses import replace
import argparse
import imaplib
import json
from pathlib import Path
import re
import sqlite3
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app import db, imap_sync, mailer, reconciliation as rec


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--max-reviews',type=int,default=100,help='Maximum explicit review UIDs to re-analyse on the copy (1..1000).')
    args=parser.parse_args()
    if not 1<=args.max_reviews<=1000:raise ValueError('max-reviews must be 1..1000')
    out=ROOT/'output'/'repair-2026-10-17'/'imap'
    out.mkdir(parents=True,exist_ok=True)
    # mailer loads existing local configuration without displaying credentials.
    mailer.get_mail_settings()
    config=replace(imap_sync.settings(),enabled=True)
    if not config.configured:
        raise ValueError('Existing matching IMAP credential unavailable')
    copy=out/'diagnostic.sqlite3'
    with sqlite3.connect(db.DB_PATH.resolve().as_uri()+'?mode=ro',uri=True) as live, sqlite3.connect(copy) as dest:
        live.backup(dest)
    with sqlite3.connect(copy) as c:
        c.row_factory=sqlite3.Row
        state=dict(c.execute('SELECT * FROM mail_sync_state WHERE mailbox=?',(config.key,)).fetchone())
        # Re-analysis is explicit and bounded. No cursor reset/UIDVALIDITY guess.
        reviewed=[dict(r) for r in c.execute('SELECT * FROM mail_sync_messages WHERE mailbox=? AND uidvalidity=? ORDER BY uid DESC',(config.key,state['uidvalidity']))
            if 'review_required' in r['disposition'] or json.loads(r['disposition']).get('reviews',0)]
        selected=reviewed[:args.max_reviews]
    results=[]
    client=imap_sync.connection(config)
    try:
        client.login(config.user,config.password)
        if client.select(config.folder,readonly=True)[0]!='OK':
            raise ValueError('EXAMINE failed')
        validity=client.response('UIDVALIDITY')[1][0].decode()
        if validity!=state['uidvalidity']:
            raise ValueError('UIDVALIDITY changed; no historical UID reuse')
        folders=client.list()[1]
        for row in selected:
            uid=row['uid']
            typ,data=client.uid('FETCH',str(uid),'(INTERNALDATE RFC822.SIZE BODY.PEEK[]<0.8388609>)')
            if typ!='OK':raise ValueError('PEEK failed')
            parts=[v for v in data if isinstance(v,tuple)]
            if not parts:continue
            meta,raw=parts[0]
            size=int(re.search(rb'RFC822.SIZE (\d+)',meta)[1])
            if size>8*1024*1024 or len(raw)!=size:
                results.append(dict(uid=uid,size=size,incomplete=True));continue
            received=time.mktime(imaplib.Internaldate2tuple(meta))
            (out/f'uid-{uid}.eml').write_bytes(raw)
            root=rec.raw_payload(raw)
            with patch.object(db,'DB_PATH',copy), db.get_connection() as c:
                counts=imap_sync.reanalyse_review(c,config,validity,uid,raw,received,time.time())
            results.append(dict(uid=uid,size=size,authenticated=rec.imap_authenticated(root,config.user),
                from_domain=rec.header(root,'From').rsplit('@',1)[-1].strip('>'),
                structured=bool(rec.dsn_records(root)),counts=counts))
        report=dict(connection='OK',read_only=True,uidvalidity=validity,uidnext=client.response('UIDNEXT')[1][0].decode(),
            state=state,review_messages=len(reviewed),selected=len(selected),folders=[v.decode(errors='replace') for v in folders],results=results)
        (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(dict(connection='OK',read_only=True,review_messages=len(reviewed),selected=len(selected),
            authenticated=sum(r.get('authenticated',False) for r in results),new_changes=sum(r.get('counts',{}).get('contact_changes',0) for r in results),
            oversized=sum(r['size']>1024*1024 for r in results)),indent=2))
    finally:
        client.logout()


if __name__=='__main__':main()
