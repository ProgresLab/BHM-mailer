"""Consistent private backup and copied DB migration/recovery/optional IMAP QA.

Never initializes the operational database or starts workers. Outputs counts,
IDs and hashes only. All backup/assets/reports stay in ignored directories.
"""
import argparse
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app import db, worker, imap_sync


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(conn):
    conn.row_factory=sqlite3.Row
    return {r[0]:[dict(v) for v in conn.execute('SELECT * FROM "'+r[0]+'" ORDER BY rowid')]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--scan',action='store_true')
    args=parser.parse_args()
    timestamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    target=ROOT/'backups'/('imap-sync-'+timestamp)
    target.mkdir(parents=True)
    database=db.DB_PATH.resolve()
    before=digest(database)
    with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True) as live:
        active=dict(inflight=live.execute("SELECT COUNT(*) FROM email_sends WHERE status='sending'").fetchone()[0],
                    attempts=live.execute("SELECT COUNT(*) FROM send_attempt_history WHERE status='sending'").fetchone()[0],
                    reserved=live.execute('SELECT COUNT(*) FROM smtp_control WHERE campaign_id IS NOT NULL').fetchone()[0],
                    notifications=live.execute("SELECT COUNT(*) FROM unsubscribe_events WHERE notification_status IN ('queued','sending')").fetchone()[0])
        if any(active.values()):raise RuntimeError('Operational work reserved/in flight; no activation')
        with sqlite3.connect(target/'database.sqlite3') as saved:live.backup(saved)
    assets=ROOT/'uploads'/'campaign_assets'
    asset_hashes={str(f.relative_to(assets)):digest(f) for f in assets.rglob('*') if f.is_file()}
    if assets.exists():shutil.copytree(assets,target/'campaign_assets')
    assert asset_hashes=={str(f.relative_to(target/'campaign_assets')):digest(f) for f in (target/'campaign_assets').rglob('*') if f.is_file()}
    simulation=target/'simulation.sqlite3'
    shutil.copy2(target/'database.sqlite3',simulation)
    with sqlite3.connect(simulation) as c:original=rows(c)
    with patch.object(db,'DB_PATH',simulation):
        db.init_db()
        with sqlite3.connect(simulation) as c:
            initialized=rows(c)
            migration={t:dict(added_rows=len(v)-len(original.get(t,[])),
                added_columns=sorted(set(v[0] if v else [])-set(original[t][0] if t in original and original[t] else [])))
                for t,v in initialized.items() if t not in original or v!=original[t]}
            for table,values in original.items():
                for old,new in zip(values,initialized[table]):
                    assert all(new[k]==v for k,v in old.items()),table
        worker.recover()
        with sqlite3.connect(simulation) as c:
            recovered=rows(c)
            recovery={t:dict(added=len(v)-len(initialized[t]),changed_ids=[row.get('campaign_id',row.get('id'))
                for row,new in zip(initialized[t],v) if row!=new]) for t,v in recovered.items() if v!=initialized[t]}
        if args.scan:
            engine=imap_sync.Engine(config=replace(imap_sync.settings(),enabled=True))
            for _ in range(100):
                engine.tick()
                state=imap_sync.payload(engine.config)
                if state.get('last_error'):raise RuntimeError(state['last_error'])
                if state.get('last_success'):break
                time.sleep(1)
            else:raise RuntimeError('Scan did not complete in bounded batches')
        with sqlite3.connect(simulation) as c:
            final=rows(c)
            integrity=c.execute('PRAGMA integrity_check').fetchone()[0]
            foreign_keys=len(c.execute('PRAGMA foreign_key_check').fetchall())
            scan=imap_sync.payload(engine.config) if args.scan else None
            # Reconciliation may only alter contact status/time, later evidence
            # columns and append audits. Immutable SMTP/history/assets stay exact.
            for table in ('send_attempt_history','smtp_attempts','campaigns','campaign_selection','unsubscribe_events'):
                assert original[table]==final[table],table
            for old,new in zip(original['email_sends'],final['email_sends']):
                allowed={'status','trace_status','trace_detail','trace_source','final_status_at','last_checked_at'}
                assert all(new[k]==v for k,v in old.items() if k not in allowed)
    assert digest(database)==before,'Operational database changed'
    assert asset_hashes=={str(f.relative_to(assets)):digest(f) for f in assets.rglob('*') if f.is_file()}
    result=dict(timestamp=timestamp,database=str(database),backup=str(target),backup_sha256=digest(target/'database.sqlite3'),
                operational_unchanged=True,assets_verified=len(asset_hashes),active=active,migration=migration,
                recovery=recovery,integrity=integrity,foreign_key_errors=foreign_keys,scan=scan)
    (target/'preflight.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    (ROOT/'output'/'imap-preflight'/'latest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
