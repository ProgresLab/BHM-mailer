"""Explicit offline closure of unattempted pending rows. No SMTP or startup.

The maintenance caller must hold the stopped-runtime fence and transaction,
provide a verified backup, simulate and independently validate the exact delta.
"""
from datetime import datetime
import hashlib
import json

from . import reconciliation as rec

PREFIX='operator-close-v1:'


def plan(conn, campaign_id, expected_pending, expected_refused=0, expected_preserved_refused=0):
    rec.ensure_paused_history(conn,campaign_id)
    campaign=dict(conn.execute('SELECT * FROM campaigns WHERE id=?',(campaign_id,)).fetchone())
    execution=dict(conn.execute('SELECT * FROM campaign_execution WHERE campaign_id=?',(campaign_id,)).fetchone())
    control=dict(conn.execute('SELECT * FROM smtp_control WHERE id=1').fetchone())
    if campaign['status'] not in {'sending','stopped'} or execution['state'] not in {'manual_paused','interrupted','problem'}:
        raise ValueError('Only a durably stopped unfinished campaign can be closed')
    if control['campaign_id'] not in {None,campaign_id}:
        raise ValueError('Another campaign owns the SMTP reservation')
    rows=[dict(r) for r in conn.execute('SELECT * FROM email_sends WHERE campaign_id=? ORDER BY id',(campaign_id,))]
    pending=[r for r in rows if r['status']=='pending']
    refused=[r for r in rows if r['status']=='rate_limited']
    if len(pending)!=expected_pending or expected_pending<1:
        raise ValueError('Pending count differs from exact operator approval')
    if (len(refused)!=expected_refused+expected_preserved_refused or expected_refused<0
            or expected_preserved_refused<0 or (expected_refused and expected_preserved_refused)):
        raise ValueError('Refused count differs from exact operator approval')
    if any(r['status'] in {'sending','delivery_unknown'} or r['outcome_uncertain'] for r in rows):
        raise ValueError('In-flight, deferred or uncertain rows require a separate decision')
    for row in refused:
        attempts=conn.execute('SELECT * FROM send_attempt_history WHERE send_id=? ORDER BY id',(row['id'],)).fetchall()
        if expected_preserved_refused:
            # Legacy rows lack the immutable attempt ledger. Closure may leave
            # them byte-for-byte unchanged; never infer a final SMTP outcome.
            if (row['accepted_at'] or row['sent_at'] or attempts
                    or not str(row['smtp_code']).isdigit()
                    or not 400<=int(row['smtp_code'])<500):
                raise ValueError('Only legacy unaccepted 4xx rows without a ledger may be preserved')
            continue
        if (row['accepted_at'] or row['sent_at'] or not attempts or row['attempt_count']!=len(attempts)
                or any(a['mode']!='smtp' or a['status']!='rate_limited' or a['finished'] is None
                    or not str(a['smtp_code']).isdigit() or not 400<=int(a['smtp_code'])<500 for a in attempts)
                or str(row['smtp_code'])!=str(attempts[-1]['smtp_code'])):
            raise ValueError('Deferred row lacks complete definite SMTP refusal history')
    for row in pending:
        if row['accepted_at'] or row['sent_at'] or row['attempt_count'] or conn.execute(
                'SELECT 1 FROM send_attempt_history WHERE send_id=?',(row['id'],)).fetchone():
            raise ValueError('Pending row has attempt/acceptance history; separate review required')
    result=dict(campaign_id=campaign_id,campaign=campaign,execution=execution,control=control,
        pending_ids=[r['id'] for r in pending],total=len(rows),
        accepted=sum(bool(r['accepted_at']) for r in rows))
    if expected_preserved_refused:
        result['preserved_refused_ids']=[r['id'] for r in refused]
    elif refused:
        result['refused_ids']=[r['id'] for r in refused]
    result['key']=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()
    return result


def apply(conn, proposal, timestamp):
    cid=proposal['campaign_id']
    detail=dict(key=proposal['key'],campaign_id=cid,
        action='permanently_close_unattempted_queue',cancelled_ids=proposal['pending_ids'],
        historical_acceptances_preserved=proposal['accepted'],
        reason='Explicit operator authorization; never send remaining pending messages.')
    if proposal.get('refused_ids'):
        detail['refused_ids']=proposal['refused_ids']
    if proposal.get('preserved_refused_ids'):
        detail['preserved_refused_ids']=proposal['preserved_refused_ids']
    audit=PREFIX+json.dumps(detail,sort_keys=True)
    if conn.execute('SELECT 1 FROM execution_events WHERE campaign_id=? AND message=?',(cid,audit)).fetchone():
        row=conn.execute('SELECT state FROM campaign_execution WHERE campaign_id=?',(cid,)).fetchone()
        if row and row['state']=='completed_with_errors':return False
        raise ValueError('Closure audit conflicts with execution state')
    if plan(conn,cid,len(proposal['pending_ids']),len(proposal.get('refused_ids',[])),
            len(proposal.get('preserved_refused_ids',[])))!=proposal:
        raise ValueError('Campaign changed after closure planning')
    for sid in proposal['pending_ids']:
        changed=conn.execute("""UPDATE email_sends SET status='cancelled',final_status_at=?,
            last_error='Operator trwale zakończył kampanię. Niewysłane; bez próby SMTP.' WHERE id=? AND status='pending'""",(timestamp,sid))
        if changed.rowcount!=1:raise ValueError('Pending row changed')
    for sid in proposal.get('refused_ids',[]):
        # Terminal projection only: the original negative reply, timestamps and
        # immutable attempt ledger remain intact. This is not invalidity proof.
        if conn.execute("UPDATE email_sends SET status='smtp_failed',final_status_at=? WHERE id=? AND status='rate_limited'",
                        (timestamp,sid)).rowcount!=1:
            raise ValueError('Refused row changed')
    conn.execute("UPDATE campaigns SET status='completed_with_errors',completed_at=? WHERE id=?",(timestamp,cid))
    conn.execute("""UPDATE campaign_execution SET state='completed_with_errors',manual_pause=1,
        updated=?,problem='Trwale zakończona przez operatora. Pozostałe wiadomości anulowane bez wysyłki.' WHERE campaign_id=?""",
        (datetime.fromisoformat(timestamp).timestamp(),cid))
    conn.execute('UPDATE smtp_control SET campaign_id=NULL WHERE id=1 AND campaign_id=?',(cid,))
    conn.execute('INSERT INTO execution_events(campaign_id,created,message) VALUES(?,?,?)',
        (cid,datetime.fromisoformat(timestamp).timestamp(),audit))
    return True


def validate_delta(before,after,proposal):
    """Every row, including all snapshots, contacts and old attempts, is checked."""
    cid=proposal['campaign_id'];pending=set(proposal['pending_ids']);refused=set(proposal.get('refused_ids',[]));counts={}
    if before.keys()!=after.keys():raise ValueError('Unexpected table changes')
    for table,old in before.items():
        new=after[table]
        if table=='execution_events':
            if new[:len(old)]!=old or len(new)!=len(old)+1 or not new[-1]['message'].startswith(PREFIX) or new[-1]['campaign_id']!=cid:
                raise ValueError('Unexpected closure audit delta')
            counts[table]=1;continue
        if len(old)!=len(new):raise ValueError('Unexpected row count: '+table)
        changed=0
        for a,b in zip(old,new):
            if a==b:continue
            keys={k for k in a if a[k]!=b[k]}
            if table=='email_sends' and a['id'] in pending:
                if keys-{'status','final_status_at','last_error'} or b['status']!='cancelled' or b['accepted_at'] or b['sent_at']:
                    raise ValueError('Unexpected cancelled-send changes')
            elif table=='email_sends' and a['id'] in refused:
                if keys-{'status','final_status_at'} or b['status']!='smtp_failed' or b['accepted_at'] or b['sent_at']:
                    raise ValueError('Unexpected refused-send changes')
            elif table=='campaigns' and a['id']==cid:
                if keys-{'status','completed_at'} or b['status']!='completed_with_errors':raise ValueError('Campaign delta')
            elif table=='campaign_execution' and a['campaign_id']==cid:
                if keys-{'state','manual_pause','updated','problem'} or b['state']!='completed_with_errors' or b['manual_pause']!=1:
                    raise ValueError('Execution delta')
            elif table=='smtp_control' and a['campaign_id']==cid:
                if keys!={'campaign_id'} or b['campaign_id'] is not None:raise ValueError('Reservation delta')
            else:raise ValueError('Unexpected closure mutation: '+table)
            changed+=1
        counts[table]=changed
    expected={'email_sends':len(pending)+len(refused),'campaigns':1,'campaign_execution':1,'execution_events':1,
        'smtp_control':int(proposal['control']['campaign_id']==cid)}
    if any(counts.get(t)!=n for t,n in expected.items()) or any(n for t,n in counts.items() if t not in expected):
        raise ValueError('Missing/excess closure changes')
    return counts
