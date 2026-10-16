"""One-shot offline reconciliation with backup, simulation and independent readback.

Run prepare first. apply requires the resulting private manifest, unchanged DB
and the same mailbox input. This tool never imports app.main or starts a worker.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import reconciliation as rec


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def connect(path, readonly=False):
    c = sqlite3.connect(path.resolve().as_uri() + ('?mode=ro' if readonly else '?mode=rw'), uri=True)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    return c


def snapshot(conn):
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    return {t: [dict(r) for r in conn.execute('SELECT * FROM "' + t + '" ORDER BY rowid')] for t in tables}


def schema(conn):
    return [tuple(r) for r in conn.execute('SELECT type,name,sql FROM sqlite_master ORDER BY type,name')]


def validate_delta(before, after, proposal):
    if before.keys() != after.keys():
        raise ValueError('Unexpected tables')
    contacts = {c['contact_id']: c for c in proposal['contacts']}
    sends = {s['send_id']: s for s in proposal['sends']}
    counts = {}
    for table, old in before.items():
        new = after[table]
        if table == 'execution_events':
            if new[:len(old)] != old or len(new)-len(old) != sum(e['persist'] and not e['duplicate'] for e in proposal['events']):
                raise ValueError('Unexpected event changes')
            if any(not r['message'].startswith(rec.PREFIX) or r['campaign_id'] != proposal['campaign_id'] for r in new[len(old):]):
                raise ValueError('Unexpected event scope')
            counts[table] = len(new)-len(old)
            continue
        if len(old) != len(new):
            raise ValueError('Unexpected row additions/deletions: ' + table)
        changed = []
        for a, b in zip(old, new):
            if a == b:
                continue
            columns = {k for k in a if a[k] != b[k]}
            if table == 'contacts' and a['id'] in contacts:
                change=contacts[a['id']]
                if columns - {'status','updated_at'} or b['status'] != change['new_status'] or a['status'] != change['old_status']:
                    raise ValueError('Unexpected contact changes')
            elif table == 'email_sends' and a['id'] in sends:
                change=sends[a['id']]
                if columns - {'status','trace_status','trace_detail','trace_source','final_status_at','last_checked_at'} or b['status'] != 'bounced_later' or b['trace_detail'] != change['diagnostic'] or b['trace_source'] != 'gmail:' + change['gmail_id']:
                    raise ValueError('Unexpected send changes')
            else:
                raise ValueError('Unexpected changed row: ' + table)
            changed.append(a['id'])
        counts[table] = len(changed)
    if counts.get('contacts', 0) != len(contacts) or counts.get('email_sends', 0) != len(sends):
        raise ValueError('Missing expected mutations')
    return counts


def checks(conn):
    if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or list(conn.execute('PRAGMA foreign_key_check')):
        raise ValueError('SQLite integrity/foreign-key failure')


def load_messages(paths):
    messages, raw, files = {}, {}, {}
    for path in paths:
        data = json.loads(path.read_text(encoding='utf-8'))
        files[str(path.resolve())] = digest(path)
        if isinstance(data, list):
            raw.update({m['id']:m for m in data})
        else:
            for m in data['messages']:
                if not m.get('payload'):
                    raise ValueError('Incomplete MIME: ' + m['id'])
                messages[m['id']] = m
    for mid, m in raw.items():
        if mid not in messages or not m.get('raw'):
            raise ValueError('Unexpected/incomplete raw input')
        messages[mid]['payload'] = rec.raw_payload(m['raw'])
    # Missing text/report parts require RAW. Image bytes are irrelevant to DSN.
    for m in messages.values():
        for part in rec.walk(m['payload']):
            if part.get('body',{}).get('attachment_id') and not part.get('parts') and part.get('mime_type','').startswith(('text/', 'message/')) and not rec.text(part):
                raise ValueError('Unread report attachment: ' + m['id'])
    return list(messages.values()), files


def write(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding='utf-8')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=['prepare','apply'])
    p.add_argument('--database', type=Path, required=True)
    p.add_argument('--campaign', type=int, required=True)
    p.add_argument('--input', type=Path, nargs='+', required=True)
    p.add_argument('--manifest', type=Path, required=True)
    a=p.parse_args()
    messages, inputs=load_messages(a.input)
    if a.mode == 'prepare':
        if a.manifest.exists():
            raise ValueError('Manifest already exists; never overwrite evidence')
        with connect(a.database, True) as source:
            rec.ensure_idle(source,a.campaign)
            backup_dir=ROOT/'backups'/('reconciliation-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
            backup_dir.mkdir(parents=True,exist_ok=False)
            backup=backup_dir/'bhm_mailer.sqlite3'
            with sqlite3.connect(backup) as destination:
                source.backup(destination)
            with connect(backup,True) as saved:
                checks(saved)
                before=snapshot(saved)
                original_schema=schema(saved)
                if snapshot(source) != before:
                    raise ValueError('Source changed during backup')
                proposal=rec.plan(saved,a.campaign,messages)
        assets=ROOT/'uploads'/'campaign_assets'
        manifest_assets={}
        if assets.exists():
            shutil.copytree(assets,backup_dir/'campaign_assets')
            for src in assets.rglob('*'):
                if src.is_file():
                    relative=str(src.relative_to(assets))
                    if digest(src) != digest(backup_dir/'campaign_assets'/relative):
                        raise ValueError('Asset backup mismatch')
                    manifest_assets[relative]=digest(src)
        simulation=backup_dir/'simulation.sqlite3'
        shutil.copy2(backup, simulation)
        timestamp=datetime.now(timezone.utc).isoformat()
        with connect(simulation) as sim:
            sim.execute('BEGIN IMMEDIATE')
            rec.apply(sim,proposal,timestamp)
            checks(sim)
            if schema(sim) != original_schema:
                raise ValueError('Unexpected schema change')
            delta=validate_delta(before,snapshot(sim),proposal)
        # New connection, committed copy, replay must be a no-op.
        with connect(simulation, True) as readback:
            checks(readback)
            validate_delta(before,snapshot(readback),proposal)
            replay=rec.plan(readback,a.campaign,messages)
            if replay['contacts'] or replay['sends'] or any(e['persist'] and not e['duplicate'] for e in replay['events']):
                raise ValueError('Replay is not idempotent')
        a.manifest.parent.mkdir(parents=True, exist_ok=True)
        write(a.manifest,dict(database=str(a.database.resolve()),backup=str(backup),backup_sha256=digest(backup),
            simulation=str(simulation),inputs=inputs,assets=manifest_assets,timestamp=timestamp,
            proposal=proposal,delta=delta,phase='simulated'))
        print(json.dumps(dict(phase='simulated',messages=len(messages),counts=proposal['counts'],
            contacts=len(proposal['contacts']),sends=len(proposal['sends']),delta=delta)))
    else:
        manifest=json.loads(a.manifest.read_text(encoding='utf-8'))
        if manifest['phase'] != 'simulated' or manifest['database'] != str(a.database.resolve()) or inputs != manifest['inputs'] or manifest['proposal']['campaign_id'] != a.campaign:
            raise ValueError('Manifest/input mismatch')
        backup=Path(manifest['backup'])
        if digest(backup) != manifest['backup_sha256']:
            raise ValueError('Backup changed')
        with connect(backup,True) as saved:
            before=snapshot(saved); original_schema=schema(saved)
        assets=ROOT/'uploads'/'campaign_assets'
        current_assets={str(f.relative_to(assets)):digest(f) for f in assets.rglob('*') if f.is_file()}
        if current_assets != manifest['assets']:
            raise ValueError('Assets changed after preflight')
        with connect(a.database) as live:
            live.execute('BEGIN IMMEDIATE')
            if snapshot(live) != before or schema(live) != original_schema:
                raise ValueError('Operational data changed after backup; replan')
            current=rec.plan(live,a.campaign,messages)
            if current != manifest['proposal']:
                raise ValueError('Plan changed')
            rec.apply(live,current,manifest['timestamp'])
            checks(live)
            delta=validate_delta(before,snapshot(live),current)
            if schema(live) != original_schema:
                raise ValueError('Unexpected schema change')
        with connect(a.database,True) as readback, connect(Path(manifest['simulation']),True) as sim:
            checks(readback)
            if snapshot(readback) != snapshot(sim) or schema(readback) != original_schema:
                raise ValueError('Independent readback differs from simulation')
            validate_delta(before,snapshot(readback),current)
        write(a.manifest.with_name('applied-readback.json'),dict(phase='applied',delta=delta,
              matches_simulation=True,integrity='ok',foreign_keys=0,backup=str(backup),backup_sha256=digest(backup)))
        print(json.dumps(dict(phase='applied',delta=delta,matches_simulation=True)))


if __name__ == '__main__':
    main()
