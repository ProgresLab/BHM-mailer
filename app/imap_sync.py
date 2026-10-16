"""Read-only one.com IMAP, durable UID cursor and independent singleton thread.

Network I/O never holds SQLite transactions. No STORE, CLOSE, EXPUNGE or SMTP.
Only bounded UID windows and bounded message bodies are fetched.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import imaplib
import json
import os
import re
import ssl
import threading
import time

from . import db, mailer, reconciliation as rec

INTERVAL = 900
MAX_BYTES = 1024 * 1024
MAX_MESSAGES = 200
TIMEOUT = 20


@dataclass(frozen=True)
class Settings:
    enabled: bool = False
    host: str = 'imap.one.com'
    port: int = 993
    user: str = 'marketing@bhm-chemicals.com'
    password: str = field(default='', repr=False)
    folder: str = 'INBOX'

    @property
    def key(self):
        return hashlib.sha256(json.dumps([self.host,self.port,self.user,self.folder]).encode()).hexdigest()

    @property
    def configured(self):
        return self.enabled and self.host == 'imap.one.com' and self.port == 993 and bool(self.password) and bool(self.user)


def settings():
    user = os.getenv('IMAP_USER','marketing@bhm-chemicals.com').strip().lower()
    password = os.getenv('IMAP_PASSWORD','')
    if not password and user == os.getenv('SMTP_USER','').strip().lower():
        password = os.getenv('SMTP_PASSWORD','')
    return Settings(os.getenv('IMAP_ENABLED','false').lower() == 'true',
                    user=user,password=password,folder=os.getenv('IMAP_FOLDER','INBOX'))


def connection(config):
    return imaplib.IMAP4_SSL(config.host,config.port,ssl_context=ssl.create_default_context(),timeout=TIMEOUT)


def ensure_state(conn, config):
    conn.execute('INSERT OR IGNORE INTO mail_sync_state(mailbox) VALUES(?)',(config.key,))


def payload(config=None):
    config = config or settings()
    with db.get_connection() as conn:
        row = conn.execute('SELECT * FROM mail_sync_state WHERE mailbox=?',(config.key,)).fetchone()
    data = dict(row) if row else {}
    data.update(connection='configuration_required' if not config.configured else 'error' if data.get('last_error') else
                'active' if data.get('last_success') else 'waiting',interval=INTERVAL,enabled=config.enabled,
                status_stale=bool(data.get('last_success') and time.time()-data['last_success']>INTERVAL+120),
                unsubscribe_coverage='Niepełne: INBOX marketing nie zawiera zweryfikowanego źródła info@. Wymagany osobny autoryzowany import Gmail lub druga skrzynka.')
    data.pop('mailbox',None)
    return data


def request_scan(config=None):
    config = config or settings()
    if not config.configured:
        raise ValueError('Konfiguracja IMAP wymagana (IMAP_ENABLED i hasło tej samej skrzynki).')
    with db.get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        ensure_state(conn,config)
        row = conn.execute('SELECT scanning,requested FROM mail_sync_state WHERE mailbox=?',(config.key,)).fetchone()
        if row['scanning'] or row['requested']:
            return False
        conn.execute('UPDATE mail_sync_state SET requested=1 WHERE mailbox=?',(config.key,))
    manager.wake.set()
    return True


def process_message(conn, raw, received, config, now):
    """Apply through the shared MIME/DSN rules, in the cursor transaction.

    Exact accepted attempt Message-ID/recipient, receiver trust boundary and
    receipt time are all required. Unrelated mail is not stored as raw content.
    """
    root = rec.raw_payload(raw)
    ids = set()
    for part in rec.walk(root):
        for name in ('Message-ID','In-Reply-To','References'):
            ids |= rec.message_ids(rec.header(part,name))
        if part.get('mime_type') == 'text/rfc822-headers':
            from email.parser import Parser
            ids |= rec.message_ids(Parser().parsestr(rec.text(part)).get('Message-ID',''))
    campaigns = set()
    for mid in ids:
        campaigns.update(r[0] for r in conn.execute('''SELECT DISTINCT s.campaign_id FROM send_attempt_history a
            JOIN email_sends s ON s.id=a.send_id WHERE lower(trim(a.message_id,'<>'))=?
            AND a.mode='smtp' AND a.status='accepted_by_smtp' ''',(mid,)))
    for part in rec.walk(root):
        if rec.text(part).startswith('Unsubscribe request'):
            match = re.search(r'^Campaign ID:\s*(\d+)\s*$',rec.text(part),re.M)
            if match and conn.execute('SELECT 1 FROM campaigns WHERE id=?',(int(match[1]),)).fetchone():
                campaigns.add(int(match[1]))
    counts = dict(hard_bounces=0,unsubscribes=0,reviews=0,alerts=0,contact_changes=0)
    message = dict(id=hashlib.sha256(raw).hexdigest(),internal_date=str(int(received*1000)),payload=root)
    for cid in sorted(campaigns):
        proposal = rec.plan(conn,cid,[message],source='imap',mailbox=config.user)
        rec.apply(conn,proposal,datetime.fromtimestamp(now,timezone.utc).isoformat())
        counts['contact_changes'] += len(proposal['contacts'])
        for e in proposal['events']:
            if e['duplicate']:
                continue
            if not e['persist'] and e['kind'].startswith('review'):
                added=conn.execute('''INSERT OR IGNORE INTO mail_evidence(event_key,campaign_id,source,kind,created,evidence)
                    VALUES(?,?,'imap','review_required',?,?)''',(e['canonical_key'],cid,now,json.dumps(e,sort_keys=True)))
                if not added.rowcount:continue
            counts['hard_bounces'] += int(e['target'] in {'invalid','bounced'})
            counts['unsubscribes'] += int(e['kind']=='unsubscribe')
            counts['reviews'] += int(e['kind'].startswith('review'))
            counts['alerts'] += int(e['kind']=='sender_policy')
    if not campaigns:
        report = rec.dsn_records(root) or root.get('mime_type') == 'multipart/report' or any(
            rec.text(p).startswith('Unsubscribe request') for p in rec.walk(root))
        if report:
            key = rec.canonical_key(dict(report_id=rec.header(root,'Message-ID'),date=message['internal_date'],original_message_ids=sorted(ids)))
            added = conn.execute('''INSERT OR IGNORE INTO mail_evidence(event_key,source,kind,created,evidence)
                VALUES(?,'imap','review_required',?,?)''',(key,now,json.dumps(dict(reason='No exact accepted attempt match',original_message_ids=sorted(ids)))))
            counts['reviews'] += int(added.rowcount == 1)
    return counts


class Engine:
    def __init__(self, clock=time.time, factory=connection, config=None, stop=None):
        self.clock,self.factory,self.config = clock,factory,config or settings()
        self.stop = stop or threading.Event()
        self.guard = threading.Lock()

    def tick(self):
        if not self.config.configured or not self.guard.acquire(False):
            return
        client = None
        try:
            now = self.clock()
            with db.get_connection() as conn:
                found=conn.execute('SELECT * FROM mail_sync_state WHERE mailbox=?',(self.config.key,)).fetchone()
                if not found:
                    ensure_state(conn,self.config)
                    found=conn.execute('SELECT * FROM mail_sync_state WHERE mailbox=?',(self.config.key,)).fetchone()
                row=dict(found)
                if not row['requested'] and now < row['next_sync']:
                    return
                conn.execute('UPDATE mail_sync_state SET scanning=1,requested=0 WHERE mailbox=?',(self.config.key,))
            client = self.factory(self.config)
            client.login(self.config.user,self.config.password)
            if client.select(self.config.folder,readonly=True)[0] != 'OK':
                raise ValueError('IMAP EXAMINE failed')
            validity = client.response('UIDVALIDITY')[1][0].decode('ascii')
            upper = int(client.response('UIDNEXT')[1][0])-1
            if not validity.isdigit():
                raise ValueError('Missing UIDVALIDITY')
            cursor = row['last_uid'] if row['uidvalidity'] == validity else 0
            totals = dict(new_messages=0,hard_bounces=0,unsubscribes=0,reviews=0,alerts=0,contact_changes=0)
            begin = self.clock()
            while cursor < upper and totals['new_messages'] < MAX_MESSAGES and self.clock()-begin < 60 and not self.stop.is_set():
                end = min(cursor+1000,upper)
                typ,data = client.uid('SEARCH',None,'UID',f'{cursor+1}:{end}')
                if typ != 'OK':
                    raise ValueError('IMAP UID SEARCH failed')
                uids = sorted({int(v) for v in data[0].split() if cursor < int(v) <= end})
                for uid in uids:
                    if totals['new_messages'] >= MAX_MESSAGES or self.clock()-begin >= 60 or self.stop.is_set():
                        break
                    with db.get_connection() as conn:
                        done = conn.execute('SELECT 1 FROM mail_sync_messages WHERE mailbox=? AND uidvalidity=? AND uid=?',
                                            (self.config.key,validity,uid)).fetchone()
                    counts = dict(hard_bounces=0,unsubscribes=0,reviews=0,alerts=0,contact_changes=0)
                    if not done:
                        typ,data = client.uid('FETCH',str(uid),'(INTERNALDATE RFC822.SIZE BODY.PEEK[]<0.'+str(MAX_BYTES+1)+'>)')
                        if typ != 'OK':
                            raise ValueError('IMAP UID FETCH failed')
                        parts = [p for p in data if isinstance(p,tuple)]
                        if not parts: # expunged between search and fetch
                            cursor=uid
                            continue
                        meta,raw = parts[0]
                        received = imaplib.Internaldate2tuple(meta)
                        if received is None:
                            raise ValueError('Missing IMAP INTERNALDATE')
                        received = time.mktime(received)
                        oversized = len(raw)>MAX_BYTES or int(re.search(rb'RFC822.SIZE (\d+)',meta)[1])>MAX_BYTES
                        with db.get_connection() as conn:
                            conn.execute('BEGIN IMMEDIATE')
                            if oversized:
                                counts['reviews']=1
                                disposition='review_required: message exceeds 1 MiB'
                            else:
                                counts=process_message(conn,raw,received,self.config,self.clock())
                                disposition=json.dumps(counts)
                            conn.execute('INSERT INTO mail_sync_messages VALUES(?,?,?,?,?)',
                                (self.config.key,validity,uid,self.clock(),disposition))
                            conn.execute('''UPDATE mail_sync_state SET uidvalidity=?,last_uid=?,new_messages=new_messages+1,
                                hard_bounces=hard_bounces+?,unsubscribes=unsubscribes+?,reviews=reviews+?,
                                alerts=alerts+?,contact_changes=contact_changes+? WHERE mailbox=?''',
                                (validity,uid,*counts.values(),self.config.key))
                        totals['new_messages']+=1
                        for key,value in counts.items():totals[key]+=value
                    cursor=uid
                if not uids or cursor == uids[-1]:cursor=end
            complete = cursor >= upper
            with db.get_connection() as conn:
                conn.execute('''UPDATE mail_sync_state SET uidvalidity=?,last_uid=?,scanning=0,last_error='',
                    last_success=?,next_sync=? WHERE mailbox=?''',
                    (validity,cursor,self.clock() if complete else row['last_success'],self.clock()+(INTERVAL if complete else 1),
                     self.config.key))
        except Exception as exc:
            # Provider responses may echo credentials or private mailbox content.
            # Public monitoring intentionally contains only an error category.
            safe = 'IMAP: '+type(exc).__name__+' — sprawdź połączenie i konfigurację; ponowienie za 15 minut.'
            with db.get_connection() as conn:
                conn.execute('UPDATE mail_sync_state SET scanning=0,last_error=?,next_sync=? WHERE mailbox=?',
                             (safe,self.clock()+INTERVAL,self.config.key))
        finally:
            if client:
                try:client.logout()
                except Exception:pass
            self.guard.release()


class Manager:
    def __init__(self, factory=connection):
        self.wake,self.stop = threading.Event(),threading.Event()
        self.guard=threading.Lock()
        self.thread=None
        self.factory=factory

    def start(self):
        with self.guard:
            if self.thread and self.thread.is_alive():return
            config=settings()
            if not config.configured:return
            # OS lock held throughout the thread lifetime, including network waits.
            path=db.DB_PATH.resolve().with_suffix('.imap-'+config.key[:16]+'.worker.lock')
            handle=open(path,'a+b')
            handle.seek(0)
            try:
                if os.name=='nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl
                    fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError:
                handle.close();return
            with db.get_connection() as conn:
                ensure_state(conn,config)
                # Reopen immediately to catch up after a restart. UID cursor and
                # evidence ledger remain durable; a second instance cannot own it.
                conn.execute('UPDATE mail_sync_state SET scanning=0,next_sync=0 WHERE mailbox=?',(config.key,))
            self.stop.clear()
            self.thread=threading.Thread(target=self.run,args=(config,handle),name='bhm-imap-sync',daemon=True)
            self.thread.start()

    def run(self,config,handle):
        try:
            engine=Engine(config=config,stop=self.stop,factory=self.factory)
            while not self.stop.is_set():
                engine.tick()
                self.wake.wait(1)
                self.wake.clear()
        finally:
            handle.close()

    def shutdown(self):
        self.stop.set();self.wake.set()
        if self.thread:self.thread.join(timeout=45)


manager=Manager()
