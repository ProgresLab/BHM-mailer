"""Read operational SQLite only; run init/recover on an in-memory backup.

Does not stop/start servers, initialize the live DB, or send mail.
Report contains IDs/changed column names only, never contact or message content.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output' / 'recipient-runtime'
OUT.mkdir(parents=True, exist_ok=True)
os.environ['SMTP_ENABLED'] = 'false'
sys.path.insert(0, str(ROOT))
from app import db, worker


def files():
    paths = list((ROOT / 'data').glob('bhm_mailer.sqlite3*'))
    paths += list((ROOT / 'uploads' / 'campaign_assets').rglob('*'))
    return {str(p.relative_to(ROOT)): dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
            size=p.stat().st_size, mtime_ns=p.stat().st_mtime_ns)
            for p in paths if p.is_file() and not p.name.endswith('.worker.lock')}


def main():
    before_files = files()
    source = sqlite3.connect((ROOT / 'data' / 'bhm_mailer.sqlite3').as_uri() + '?mode=ro', uri=True)
    copy = sqlite3.connect(':memory:')
    try:
        source.backup(copy)
    finally:
        source.close()
    copy.row_factory = sqlite3.Row
    copy.execute('PRAGMA foreign_keys=ON')
    tables = [r[0] for r in copy.execute("SELECT name FROM sqlite_master WHERE type='table'")]

    def snapshot():
        return {t: [dict(r) for r in copy.execute(f'SELECT * FROM "{t}" ORDER BY rowid')] for t in tables}

    @contextmanager
    def connection():
        with copy:
            yield copy

    original = snapshot()
    schema = [tuple(r) for r in copy.execute('SELECT type,name,sql FROM sqlite_master ORDER BY type,name')]
    state = dict(campaign_32_status=copy.execute('SELECT status FROM campaigns WHERE id=32').fetchone()[0],
        in_flight_sends=copy.execute("SELECT COUNT(*) FROM email_sends WHERE status='sending'").fetchone()[0],
        in_flight_attempts=copy.execute("SELECT COUNT(*) FROM send_attempt_history WHERE status='sending'").fetchone()[0],
        in_flight_notifications=copy.execute("SELECT COUNT(*) FROM unsubscribe_events WHERE notification_status='sending'").fetchone()[0],
        executions=[dict(r) for r in copy.execute('SELECT campaign_id,state,mode,manual_pause FROM campaign_execution')])
    with patch.object(db, 'get_connection', connection), patch.object(db, 'DATA_DIR', OUT), patch.object(db, 'UPLOADS_DIR', OUT):
        db.init_db()
        initialized = snapshot()
        after_schema = [tuple(r) for r in copy.execute('SELECT type,name,sql FROM sqlite_master ORDER BY type,name')]
        worker.recover()
        recovered = snapshot()
    changes = {}
    for table in tables:
        a, b = initialized[table], recovered[table]
        if a == b:
            continue
        changes[table] = dict(added=len(b)-len(a), changed_existing=[
            dict(key={k: row[k] for k in ('id','campaign_id') if k in row},
                 columns=[k for k in row if row[k] != other[k]])
            for row, other in zip(a,b) if row != other])
    after_files = files()
    result = dict(operational_before=before_files, operational_after=after_files,
        operational_files_unchanged=before_files == after_files, state=state,
        initialization_noop=original == initialized and schema == after_schema,
        restart_recovery_changes=changes, integrity_check=copy.execute('PRAGMA integrity_check').fetchone()[0],
        foreign_key_errors=len(copy.execute('PRAGMA foreign_key_check').fetchall()))
    copy.close()
    (OUT / 'activation-preflight.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('operational_before','operational_after')}, indent=2))
    assert result['operational_files_unchanged'] and result['initialization_noop']
    assert result['integrity_check'] == 'ok' and result['foreign_key_errors'] == 0


if __name__ == '__main__':
    main()
