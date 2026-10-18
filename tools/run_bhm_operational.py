"""Explicit local IMAP+SMTP mode. Bind before imports; never start a queue.

Startup is checked on an in-memory SQLite backup. Already safely paused queues
require no recovery writes or acknowledgement. Material recovery still requires
an exact operator acknowledgement. No secret is logged.
"""
import argparse
from contextlib import closing, contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import sqlite3
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def configure():
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    os.environ.update(IMAP_ENABLED='true', SMTP_ENABLED='true',
        SMTP_USE_SSL='true', SMTP_USE_TLS='false',
        IMAP_USER='marketing@bhm-chemicals.com', IMAP_FOLDER='INBOX',
        BHM_DB_PATH=str(ROOT/'data'/'bhm_mailer.sqlite3'),
        BHM_ASSET_DIR=str(ROOT/'uploads'/'campaign_assets'))


def configuration_ok(mailer, imap_sync):
    settings = mailer.get_mail_settings()
    imap = imap_sync.settings()
    return bool(settings.smtp_enabled and mailer.smtp_is_configured(settings)
        and not mailer.smtp_configuration_warnings(settings)
        and not mailer.public_unsubscribe_url_warning(settings)
        and settings.public_unsubscribe_base_url.startswith('https://')
        and imap.enabled and imap.configured
        and imap.user.lower() == mailer.ONE_COM_SMTP_USER)


def rows(conn):
    return {r[0]: [dict(v) for v in conn.execute('SELECT * FROM "'+r[0]+'" ORDER BY rowid')]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}


def startup_preflight(db, worker, now=None):
    """Read-only live connection; init/recover exclusively in memory."""
    now = time.time() if now is None else now
    memory = sqlite3.connect(':memory:')
    memory.row_factory = sqlite3.Row
    try:
        with closing(sqlite3.connect(db.DB_PATH.resolve().as_uri()+'?mode=ro', uri=True)) as live:
            live.backup(memory)
        if memory.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or memory.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Integralnosc SQLite wymaga przegladu.')
        blockers = {
            'inflight_sends': memory.execute("SELECT COUNT(*) FROM email_sends WHERE status='sending'").fetchone()[0],
            'inflight_attempts': memory.execute("SELECT COUNT(*) FROM send_attempt_history WHERE status='sending'").fetchone()[0],
            'uncertain': memory.execute('SELECT COUNT(*) FROM email_sends WHERE outcome_uncertain=1').fetchone()[0],
            'reserved': memory.execute('''SELECT COUNT(*) FROM smtp_control c WHERE c.campaign_id IS NOT NULL
                AND NOT EXISTS(SELECT 1 FROM campaign_execution e WHERE e.campaign_id=c.campaign_id
                    AND e.manual_pause=1 AND e.state IN ('manual_paused','interrupted'))''').fetchone()[0],
            'admin_notifications': memory.execute("SELECT COUNT(*) FROM unsubscribe_events WHERE notification_sent=0 OR notification_status IN ('queued','sending','uncertain')").fetchone()[0],
            'active_execution': memory.execute("SELECT COUNT(*) FROM campaign_execution WHERE state NOT IN ('completed','completed_with_errors','interrupted','manual_paused') OR (state IN ('interrupted','manual_paused') AND manual_pause<>1)").fetchone()[0],
            'account_cooldown': memory.execute('SELECT COUNT(*) FROM smtp_control WHERE blocked_until>?', (now,)).fetchone()[0],
        }
        if any(blockers.values()):
            raise ValueError('Aktywacja zablokowana; zachowano dane: '+json.dumps(blockers))
        original = rows(memory)
        from app import assets
        for table in ('campaigns', 'email_sends'):
            for row in original[table]:
                if row.get('banner_asset') and not assets.asset_path(row['banner_asset']).is_file():
                    raise ValueError('Brak assetu draftu lub snapshotu; przywroc komplet backupu przed startem.')
        schema = list(memory.execute('SELECT type,name,sql FROM sqlite_master ORDER BY type,name'))

        @contextmanager
        def connection():
            with memory:
                yield memory

        with patch.object(db, 'get_connection', connection):
            db.init_db()
            if original != rows(memory) or schema != list(memory.execute('SELECT type,name,sql FROM sqlite_master ORDER BY type,name')):
                raise ValueError('Startup wymaga migracji; potrzebny osobny backup/preflight i zgoda.')
            worker.recover(now)
        recovered = rows(memory)
        changed = {t for t in original if original[t] != recovered[t]}
        if changed - {'campaign_execution', 'execution_events'}:
            raise ValueError('Recovery wymaga zmian innych danych; potrzebny osobny przeglad i zgoda.')
        approved_ids = []
        if len(original['campaign_execution']) != len(recovered['campaign_execution']):
            raise ValueError('Recovery tworzy kolejke; potrzebna osobna zgoda.')
        for old, new in zip(original['campaign_execution'], recovered['campaign_execution']):
            if old == new:
                continue
            allowed={'updated'} if old['state']=='interrupted' else {'updated','state','problem'}
            if old['state'] not in {'interrupted','manual_paused'} or old['manual_pause'] != 1 or new['state']!='interrupted' or any(
                    new[k] != v for k, v in old.items() if k not in allowed):
                raise ValueError('Recovery zmienia stan kolejki; potrzebna osobna zgoda.')
            approved_ids.append(old['campaign_id'])
        old_events = original['execution_events']
        events = recovered['execution_events']
        if events[:len(old_events)] != old_events:
            raise ValueError('Recovery zmienia historie; potrzebna osobna zgoda.')
        added = events[len(old_events):]
        if sorted(e['campaign_id'] for e in added) != sorted(approved_ids) or any(
                e['message'] != 'Restart: wysyłka wstrzymana; nierozstrzygnięte próby wymagają weryfikacji.' for e in added):
            raise ValueError('Nieoczekiwane zdarzenia recovery; potrzebna osobna zgoda.')
        return sorted(approved_ids)
    finally:
        memory.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approve-recovery-for', nargs='+', type=int, default=[], metavar='CAMPAIGN_ID',
        help='Exact operator approval: recovery timestamps/events; manual-paused queues become interrupted, still paused. No send.')
    args = parser.parse_args(argv)
    configure()
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # No reuse/reload/multiple workers. Duplicate launch cannot import app.main.
        listener.bind(('127.0.0.1', 8000))
        listener.listen(2048)
        listener.set_inheritable(True)
    except OSError:
        listener.close()
        print('Port 8000 zajety. Bez drugiej instancji, migracji lub recovery.', file=sys.stderr)
        from tools.process_owner import port_owner
        print(json.dumps(port_owner(8000),ensure_ascii=True),file=sys.stderr)
        return 1
    try:
        from app import db, imap_sync, mailer, worker
        if not configuration_ok(mailer, imap_sync):
            raise ValueError('Niepelna lub niespojna konfiguracja one.com / podpisu unsubscribe / IMAP. Bez startupu.')
        recovery_ids = startup_preflight(db, worker)
        if recovery_ids != sorted(args.approve_recovery_for):
            if args.approve_recovery_for or not sys.stdin.isatty():
                raise ValueError('Potrzebna dokladna zgoda na recovery: '+str(recovery_ids))
            expected = 'RECOVERY '+','.join(map(str, recovery_ids))
            print('Startup zapisze updated i po 1 zdarzeniu recovery; reczne pauzy przejda w interrupted bez wznowienia: '+str(recovery_ids))
            print('Nie wznowi kolejek. Zatwierdz tylko po backupie i preflight kopii.')
            if input('Wpisz '+expected+' aby zatwierdzic: ').strip() != expected:
                raise ValueError('Recovery niezatwierdzone; aplikacja nieuruchomiona.')
        output = ROOT/'output'/'operational-activation'
        output.mkdir(parents=True, exist_ok=True)
        import hashlib
        import subprocess
        runtime = dict(pid=os.getpid(), cwd=str(Path.cwd()), source=str(ROOT),
            database=str(db.DB_PATH.resolve()), assets=str(ROOT/'uploads'/'campaign_assets'),
            smtp_enabled=True, imap_enabled=True, imap_configured=True,
            host='127.0.0.1', port=8000, launcher='tools/run_bhm_operational.py',
            started_at=datetime.now(timezone.utc).isoformat(), approved_recovery_ids=recovery_ids,
            source_commit=subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
            source_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (ROOT/'app').glob('*.py')})
        (output/'runtime.json').write_text(json.dumps(runtime, indent=2), encoding='utf-8')
        print('BHM Mailer: IMAP ON + SMTP ON, http://127.0.0.1:8000')
        print('SMTP dostepne. Start/wznowienie kampanii wymaga osobnego zatwierdzenia w aplikacji.')
        import uvicorn
        server = uvicorn.Server(uvicorn.Config('app.main:app', host='127.0.0.1', port=8000,
            workers=1, log_level='info'))
        server.run(sockets=[listener])
    except (ValueError, sqlite3.Error) as exc:
        # Only our bounded errors / SQLite diagnostics, never mail settings.
        print(str(exc) if isinstance(exc, ValueError) else 'SQLite preflight failed.', file=sys.stderr)
        return 1
    finally:
        listener.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
