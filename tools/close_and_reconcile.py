"""Authorized offline campaign closure + all-matched-campaign Gmail import.

Prepare makes a consistent DB/assets backup and validates a private copy. Apply
requires identical source/input/assets and independently compares committed data.
No app.main, schema initialization, worker startup or network SMTP is imported.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import shutil
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app import campaign_closure as closure,reconciliation as rec
from tools.reconcile_gmail import connect,snapshot,schema,checks,digest,load_messages,write,validate_delta
from tools.stopped_runtime import stopped_runtime


def reconcile(conn,messages,timestamp,expected=None):
    # Every campaign with an immutable accepted attempt is considered; never
    # infer a campaign from subject or apply a report to an unaccepted attempt.
    cids=[r[0] for r in conn.execute("""SELECT DISTINCT s.campaign_id FROM send_attempt_history a
        JOIN email_sends s ON s.id=a.send_id WHERE a.mode='smtp' AND a.status='accepted_by_smtp'
        ORDER BY s.campaign_id""")]
    plans=[]
    for cid in cids:
        proposal=rec.plan(conn,cid,messages,paused_history=True)
        proposal['contacts']=[c for c in proposal['contacts'] if c['new_status'] in {'invalid','unsubscribed'}]
        if expected is not None and (len(plans)>=len(expected) or proposal!=expected[len(plans)]):
            raise ValueError('Gmail proposal changed after simulation')
        before=snapshot(conn)
        rec.apply(conn,proposal,timestamp)
        validate_delta(before,snapshot(conn),proposal)
        plans.append(proposal)
    if expected is not None and len(expected)!=len(plans):raise ValueError('Campaign evidence scope changed')
    return plans


def assets():
    root=ROOT/'uploads'/'campaign_assets'
    return {str(p.relative_to(root)):digest(p) for p in root.rglob('*') if p.is_file()}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=['prepare','apply'])
    p.add_argument('--database',type=Path,required=True)
    p.add_argument('--campaign',type=int,required=True)
    p.add_argument('--expected-pending',type=int,required=True)
    p.add_argument('--input',type=Path,nargs='+',required=True)
    p.add_argument('--manifest',type=Path,required=True)
    a=p.parse_args()
    messages,inputs=load_messages(a.input)
    with stopped_runtime(a.database):
        if a.mode=='prepare':
            if a.manifest.exists():raise ValueError('Never overwrite a prior manifest')
            target=ROOT/'backups'/('close-reconcile-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
            target.mkdir(parents=True)
            backup=target/'database.sqlite3'
            with connect(a.database,True) as live:
                rec.ensure_paused_history(live,a.campaign)
                with sqlite3.connect(backup) as dest:live.backup(dest)
                with connect(backup,True) as saved:
                    checks(saved);before=snapshot(saved);original_schema=schema(saved)
                    if before!=snapshot(live):raise ValueError('Source changed during backup')
            hashes=assets()
            shutil.copytree(ROOT/'uploads'/'campaign_assets',target/'campaign_assets')
            if hashes!={str(f.relative_to(target/'campaign_assets')):digest(f) for f in (target/'campaign_assets').rglob('*') if f.is_file()}:
                raise ValueError('Asset backup mismatch')
            sim=target/'simulation.sqlite3';shutil.copy2(backup,sim)
            timestamp=datetime.now(timezone.utc).isoformat()
            with connect(sim) as conn:
                conn.execute('BEGIN IMMEDIATE')
                plans=reconcile(conn,messages,timestamp)
                before_close=snapshot(conn)
                proposal=closure.plan(conn,a.campaign,a.expected_pending)
                closure.apply(conn,proposal,timestamp)
                delta=closure.validate_delta(before_close,snapshot(conn),proposal)
                checks(conn)
                if schema(conn)!=original_schema:raise ValueError('Schema changed')
            with connect(sim,True) as conn:
                after=snapshot(conn)
                for cid in (x['campaign_id'] for x in plans):
                    replay=rec.plan(conn,cid,messages,paused_history=True)
                    if replay['contacts'] or replay['sends'] or any(e['persist'] and not e['duplicate'] for e in replay['events']):
                        raise ValueError('Gmail replay is not a no-op')
            with connect(sim) as conn:
                if closure.apply(conn,proposal,timestamp) or snapshot(conn)!=after:raise ValueError('Closure replay not idempotent')
            manifest=dict(phase='simulated',database=str(a.database.resolve()),backup=str(backup),sha256=digest(backup),
                simulation=str(sim),inputs=inputs,assets=hashes,timestamp=timestamp,gmail=plans,closure=proposal,closure_delta=delta)
            a.manifest.parent.mkdir(parents=True,exist_ok=True);write(a.manifest,manifest)
            print(json.dumps(dict(phase='simulated',messages=len(messages),examined_campaigns=[p['campaign_id'] for p in plans],
                contact_changes=sum(len(p['contacts']) for p in plans),closure_delta=delta,backup=str(backup))))
        else:
            m=json.loads(a.manifest.read_text(encoding='utf-8'))
            if m['phase']!='simulated' or m['database']!=str(a.database.resolve()) or m['inputs']!=inputs or m['assets']!=assets() or m['closure']['campaign_id']!=a.campaign or len(m['closure']['pending_ids'])!=a.expected_pending:
                raise ValueError('Manifest/scope/input/assets changed')
            backup=Path(m['backup'])
            if digest(backup)!=m['sha256']:raise ValueError('Backup changed')
            with connect(backup,True) as saved:before=snapshot(saved);original_schema=schema(saved)
            with connect(Path(m['simulation']),True) as sim:expected=snapshot(sim)
            with connect(a.database) as conn:
                conn.execute('BEGIN IMMEDIATE')
                if snapshot(conn)!=before or schema(conn)!=original_schema:raise ValueError('Operational data changed; replan')
                reconcile(conn,messages,m['timestamp'],m['gmail'])
                before_close=snapshot(conn)
                closure.apply(conn,m['closure'],m['timestamp'])
                closure.validate_delta(before_close,snapshot(conn),m['closure'])
                checks(conn)
                if snapshot(conn)!=expected or schema(conn)!=original_schema:raise ValueError('Apply differs from simulation')
            with connect(a.database,True) as readback:
                checks(readback)
                if snapshot(readback)!=expected or schema(readback)!=original_schema:raise ValueError('Independent readback mismatch')
            write(a.manifest.with_name('applied-readback.json'),dict(phase='applied',matches_simulation=True,
                cancelled=a.expected_pending,campaign=a.campaign,integrity='ok',foreign_keys=0,backup=m['backup'],sha256=m['sha256']))
            print(json.dumps(dict(phase='applied',cancelled=a.expected_pending,matches_simulation=True)))


if __name__=='__main__':main()
