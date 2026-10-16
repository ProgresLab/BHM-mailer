"""Operator launcher: canonical local DB, IMAP ON, SMTP always OFF.

Bind the port before loading the application so a second launch cannot execute
migration/recovery against an already running instance. No secret is written.
"""
import json
import os
from pathlib import Path
import socket
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]


def main():
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    os.environ.update(SMTP_ENABLED='false', IMAP_ENABLED='true',
        IMAP_USER='marketing@bhm-chemicals.com', IMAP_FOLDER='INBOX',
        BHM_DB_PATH=str(ROOT/'data'/'bhm_mailer.sqlite3'),
        BHM_ASSET_DIR=str(ROOT/'uploads'/'campaign_assets'))
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # No SO_REUSEADDR: a second launch must fail before app startup.
        listener.bind(('127.0.0.1', 8000))
        listener.listen(2048)
        listener.set_inheritable(True)
    except OSError:
        listener.close()
        print('Port 8000 jest zajety. Nie uruchomiono drugiej instancji ani recovery.', file=sys.stderr)
        return 1
    try:
        from app import db, imap_sync, mailer
        smtp = mailer.get_mail_settings()
        imap = imap_sync.settings()
        if smtp.smtp_enabled or not imap.configured:
            print('Bezpieczny start zablokowany: wymagane SMTP OFF i konfiguracja IMAP.', file=sys.stderr)
            return 1
        output=ROOT/'output'/'imap-activation'
        output.mkdir(parents=True, exist_ok=True)
        runtime=dict(pid=os.getpid(), cwd=str(Path.cwd()), source=str(ROOT),
            database=str(db.DB_PATH.resolve()), assets=str(ROOT/'uploads'/'campaign_assets'),
            smtp_enabled=smtp.smtp_enabled, imap_enabled=imap.enabled,
            imap_configured=imap.configured, host='127.0.0.1', port=8000,
            started_at=datetime.now(timezone.utc).isoformat(), launcher='tools/run_imap_safe.py')
        (output/'runtime.json').write_text(json.dumps(runtime,indent=2),encoding='utf-8')
        import uvicorn
        server=uvicorn.Server(uvicorn.Config('app.main:app',host='127.0.0.1',port=8000,
                                            workers=1,log_level='info'))
        server.run(sockets=[listener])
    finally:
        listener.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
