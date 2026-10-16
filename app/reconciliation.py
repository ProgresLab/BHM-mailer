"""Offline Gmail MIME reconciliation. No network, SMTP, startup or migration.

Evidence is appended to the existing execution_events ledger. SMTP acceptance
and immutable attempt history remain intact; later DSNs use trace_* columns.
"""
from __future__ import annotations

import base64
from collections import Counter
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser, Parser
from email.utils import parseaddr
import hashlib
import html
import json
import re
import sqlite3

PREFIX = 'gmail-reconciliation-v1:'
ADDRESS = re.compile(r'[A-Z0-9.!#$%&\x27*+/=?^_`{|}~-]+@[A-Z0-9.-]+', re.I)


def walk(part):
    yield part
    for child in part.get('parts') or []:
        yield from walk(child)


def headers(part, name):
    return [h['value'] for h in part.get('headers', []) if h['name'].lower() == name.lower()]


def header(part, name):
    return next(iter(headers(part, name)), '')


def text(part):
    body = part.get('body') or {}
    if body.get('content') is not None:
        return body['content']
    value = body.get('base64_url_content')
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4)).decode('utf-8', 'replace') if value else ''


def raw_payload(encoded):
    def convert(msg):
        node = dict(mime_type=msg.get_content_type(), filename=msg.get_filename() or '',
                    headers=[dict(name=k, value=str(v)) for k, v in msg.items()])
        payload = msg.get_payload()
        # Some MTAs incorrectly base64-encode message/delivery-status. Python's
        # email parser leaves the encoded block inside a child Message.
        if msg.get_content_type() == 'message/delivery-status' and str(msg.get('Content-Transfer-Encoding','')).lower() == 'base64' and isinstance(payload,list):
            encoded = ''.join(child.get_payload() for child in payload if isinstance(child.get_payload(),str))
            decoded = base64.b64decode(encoded).decode('utf-8','replace')
            node['parts'] = [convert(Parser(policy=policy.default).parsestr(block))
                             for block in re.split(r'\r?\n\s*\r?\n', decoded) if block.strip()]
            return node
        if isinstance(payload, list):
            node['parts'] = [convert(child) for child in payload]
        else:
            body = msg.get_payload(decode=True) or b''
            node['body'] = dict(content=body.decode(msg.get_content_charset() or 'utf-8', 'replace'))
        return node
    raw = encoded if isinstance(encoded, bytes) else base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4))
    return convert(BytesParser(policy=policy.default).parsebytes(raw))


def imap_authenticated(part, mailbox):
    """Trust only the inspected one.com receiver segment, never forwarded verdicts.

    The top storage Received and the next ingress Received delimit the server's
    Authentication-Results. A sender-supplied verdict below ingress is ignored.
    Unknown routing/layout/domain fails closed. This adapter is one.com specific.
    """
    hs = part.get('headers', [])
    received = [(i, h['value'].lower()) for i,h in enumerate(hs) if h['name'].lower() == 'received']
    if len(received) < 2:
        return False
    (start, storage), (end, ingress) = received[:2]
    route = re.search(r'\bfrom (mx\d+)\.cst\.(mailpod[\w-]+\.one\.com)\b', storage)
    if not route or not re.search(r'\bby mailstorage\d+\.cst\.' + re.escape(route[2]) + r'\b', storage):
        return False
    receiver = route[1] + '.pub.' + route[2]
    if not re.search(r'\bby ' + re.escape(receiver) + r'\b', ingress):
        return False
    verdicts = [h['value'].lower() for h in hs[start+1:end] if h['name'].lower() == 'authentication-results']
    if len(verdicts) != 1 or verdicts[0].split(';',1)[0].strip() != receiver:
        return False
    if headers(part,'Delivered-To') != [mailbox]:
        return False
    sender = parseaddr(header(part,'From'))[1].lower()
    domain = sender.rsplit('@',1)[-1]
    # Only verified provider DSNs or the established notification identity.
    if domain != 'one.com' and sender != 'info@bhm-chemicals.com':
        return False
    if domain == 'one.com' and headers(part,'Return-Path') != ['<>']:
        return False
    return any(re.search(r'\bdkim=pass\b[^;]*\bheader\.d=' + re.escape(domain) + r'(?:\s|;|$)', clause)
               for clause in verdicts[0].split(';'))


def canonical_key(e):
    identity = [normalize_id(e.get('report_id') or ''), e.get('recipient','').lower(),
                e.get('action'), e.get('status'), ' '.join((e.get('diagnostic') or '').split())]
    if not identity[0]:
        identity[0] = json.dumps([e.get('original_message_ids'),e.get('date')],sort_keys=True)
    key = hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    # Untrusted reports cannot suppress a later trusted copy of the same report.
    return key + (':review' if e.get('kind','').startswith('review') else '')


def authenticated(part):
    """Use the outer Gmail receiver verdict, never a nested/forwarded verdict."""
    sender = parseaddr(header(part, 'From'))[1].lower()
    domain = sender.rsplit('@', 1)[-1]
    verdict = next((v.lower() for v in headers(part, 'Authentication-Results')
                    if v.lower().startswith('mx.google.com;')), '')
    aligned = any(re.search(r'\bdkim=pass\b[^;]*\bheader\.(?:i|d)=@?' +
                           re.escape(domain) + r'(?:\s|;|$)', clause)
                  for clause in verdict.split(';'))
    return bool(aligned and '@' in sender)


def normalize_id(value):
    return value.strip().strip('<>').lower()


def message_ids(value):
    return {normalize_id(v) for v in re.findall(r'<?([^\s<>]+@[^\s<>]+)>?', value)}


def addresses(value):
    return {a.lower().rstrip('.') for a in ADDRESS.findall(value or '')}


def classify(action, status, diagnostic):
    detail = ' '.join(diagnostic.lower().split())
    if status.startswith(('4.7','5.7')) or re.search(r'\[r6\]|spam|blacklist|blocklist|sender.*blocked|reputation|relay access denied|policy reasons', detail):
        return 'sender_policy', None
    if action == 'delayed' or status.startswith('4'):
        return 'delayed', None
    if action != 'failed':
        return 'review', None
    # Policy/relay/authentication blocks never establish a nonexistent mailbox.
    if status.startswith('5.7') or re.search(r'5\.7\.\d|spam|blacklist|blocklist|sender.*blocked|reputation|relay access denied|policy reasons', detail):
        return 'sender_policy', None
    if status == '5.4.1':
        # Microsoft documents this exact DBEB response as invalid recipient.
        # Bare 5.4.1/access-denied strings are insufficient evidence.
        if re.search(r'550 5\.4\.1 recipient address rejected: access denied', detail) and \
                'https://aka.ms/exosmtperrors' in detail and re.search(r'\[[^\s\]]+\.prod\.outlook\.com\s', detail):
            return 'invalid_mailbox_microsoft', 'invalid'
        return 'review_microsoft_5.4.1', None
    if re.search(r'\bnxdomain\b|domain (?:does not exist|not found)|null mx', detail):
        return 'invalid_domain', 'invalid'
    if re.search(r'5\.1\.(?:1|10)\b', status + ' ' + detail) or re.search(
            r'no such user|user unknown|unknown user|mailbox (?:does not exist|not found)|'
            r'recipientnotfound|recipient (?:not found|does not exist)|no mailbox here|'
            r'address not found|invalid mailbox|not listed in .*directory', detail):
        return 'invalid_mailbox', 'invalid'
    if status in {'5.2.1', '5.1.6'}:
        return 'hard_bounce', 'bounced'
    return 'review', None


def dsn_records(root):
    records = []
    for part in walk(root):
        if part.get('mime_type') == 'message/delivery-status':
            for block in walk(part):
                fields = Parser(policy=policy.default).parsestr(text(block))
                for key in ('Final-Recipient', 'Original-Recipient', 'Action', 'Status', 'Diagnostic-Code'):
                    if not fields.get(key) and header(block, key):
                        fields[key] = header(block, key)
                if fields.get('Final-Recipient') or fields.get('Original-Recipient'):
                    records.append(fields)
        elif part.get('filename', '').lower() == 'details.txt':
            for block in re.split(r'\r?\n\s*\r?\n', text(part)):
                fields = Parser(policy=policy.default).parsestr(block)
                if fields.get('Final-Recipient') and fields.get('Action'):
                    records.append(fields)
    return records


def ensure_idle(conn, campaign_id):
    campaign = conn.execute('SELECT * FROM campaigns WHERE id=?', (campaign_id,)).fetchone()
    execution = conn.execute('SELECT * FROM campaign_execution WHERE campaign_id=?', (campaign_id,)).fetchone()
    if not campaign or campaign['status'] not in {'completed', 'completed_with_errors'} or not execution or execution['state'] not in {'completed', 'completed_with_errors'}:
        raise ValueError('Campaign queue is not completed')
    if conn.execute("SELECT 1 FROM email_sends WHERE campaign_id=? AND status IN ('pending','sending','rate_limited') LIMIT 1", (campaign_id,)).fetchone():
        raise ValueError('Campaign still has open queue rows')
    if conn.execute("SELECT 1 FROM send_attempt_history WHERE status='sending' AND finished IS NULL LIMIT 1").fetchone():
        raise ValueError('An SMTP attempt is in flight')
    if conn.execute("SELECT 1 FROM email_sends WHERE status='sending' LIMIT 1").fetchone() or conn.execute("SELECT 1 FROM unsubscribe_events WHERE notification_status IN ('sending','queued') LIMIT 1").fetchone():
        raise ValueError('SMTP work remains active or queued')
    if conn.execute('SELECT 1 FROM smtp_control WHERE campaign_id IS NOT NULL LIMIT 1').fetchone():
        raise ValueError('SMTP account is reserved')
    return campaign


def plan(conn, campaign_id, messages, *, source='gmail', mailbox='marketing@bhm-chemicals.com'):
    if source == 'gmail':
        ensure_idle(conn, campaign_id)
    sends = [dict(r) for r in conn.execute('''SELECT s.*,c.status contact_status,c.unsubscribe_token
        FROM email_sends s JOIN contacts c ON c.id=s.contact_id WHERE campaign_id=?''', (campaign_id,))]
    by_email = {s['email'].lower(): s for s in sends}
    by_mid = {}
    for s in sends:
        attempts = list(conn.execute("SELECT message_id,started FROM send_attempt_history WHERE send_id=? AND mode='smtp' AND status='accepted_by_smtp'", (s['id'],)))
        for a in attempts:
            by_mid[normalize_id(a['message_id'])] = (s, a['started'])
    prior = set()
    for r in conn.execute('SELECT message FROM execution_events WHERE campaign_id=?', (campaign_id,)):
        if r[0].startswith(PREFIX):
            saved = json.loads(r[0][len(PREFIX):])
            prior.update((saved['key'], canonical_key(saved)))
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='mail_evidence'").fetchone():
        prior.update(r[0] for r in conn.execute('SELECT event_key FROM mail_evidence WHERE campaign_id=?',(campaign_id,)))
    events, seen = [], set()
    for message in messages:
        root = message.get('payload') or {}
        trusted = authenticated(root) if source == 'gmail' else imap_authenticated(root, mailbox)
        base = dict(gmail_id=message['id'], date=message.get('internal_date'),
                    report_id=header(root, 'Message-ID'), source=header(root, 'From'))
        report_time = int(message.get('internal_date') or 0) / 1000
        refs = set()
        for name in ('References', 'In-Reply-To'):
            refs |= message_ids(header(root, name))
        for part in walk(root):
            if part.get('mime_type') == 'text/rfc822-headers':
                original = Parser(policy=policy.default).parsestr(text(part))
                refs |= message_ids(original.get('Message-ID', ''))
            if part.get('mime_type') == 'message/rfc822':
                for child in part.get('parts') or []:
                    refs |= message_ids(header(child, 'Message-ID'))
        records = dsn_records(root)
        # Notifications go to info@ and are separate from forwarded marketing DSNs.
        body = next((text(p) for p in walk(root) if text(p).startswith('Unsubscribe request')), text(root))
        if body.startswith('Unsubscribe request'):
            fields = dict(re.findall(r'^([^\r\n:]+):\s*([^\r\n]*)', body, re.M))
            recipient = fields.get('Email', '').strip().lower()
            s = by_email.get(recipient)
            valid = (s and trusted and
                parseaddr(header(root, 'From'))[1].lower() == 'info@bhm-chemicals.com' and
                fields.get('Source') == 'unsubscribe.mail.bhm-chemicals.com' and
                fields.get('Campaign ID') == str(campaign_id) and
                fields.get('Token') == s['unsubscribe_token'] and
                fields.get('Timestamp', '').isdigit() and
                ('ts=' + fields['Timestamp'] + '&') in html.unescape(s['html_snapshot']) and
                s['accepted_at'] and report_time >= datetime.fromisoformat(s['accepted_at']).timestamp())
            events.append(dict(base, recipient=recipient, send_id=s['id'] if s else None,
                               kind='unsubscribe' if valid else 'review_unsubscribe',
                               target='unsubscribed' if valid else None, bounce=False,
                               reason='Authenticated notification; campaign, token and snapshot timestamp match' if valid else 'Unverified notification fields/source/time'))
        elif records:
            for record in records:
                recipient_set = addresses(record.get('Original-Recipient', '')) or addresses(record.get('Final-Recipient', ''))
                candidates = [by_mid[mid] for mid in refs if mid in by_mid and by_mid[mid][0]['email'].lower() in recipient_set]
                unique = {s['id']: (s, started) for s, started in candidates}
                action = str(record.get('Action', '')).strip().lower()
                status = str(record.get('Status', '')).strip()
                diagnostic = ' '.join(str(record.get('Diagnostic-Code', '')).split())
                kind, target = classify(action, status, diagnostic)
                s, started = next(iter(unique.values())) if len(unique) == 1 else (None, None)
                routed = 'marketing@bhm-chemicals.com' in ' '.join(header(root, k).lower() for k in ('To', 'X-Forwarded-for', 'X-HalOne-Forwarded-For'))
                verified = s is not None and trusted and routed and report_time >= started
                events.append(dict(base, recipient=next(iter(sorted(recipient_set)), ''),
                    send_id=s['id'] if s else None,
                    kind=kind if verified else 'review_unverified_dsn', target=target if verified else None,
                    bounce=bool(verified and action == 'failed' and (source == 'gmail' or target is not None)), action=action, status=status,
                    original_recipient=str(record.get('Original-Recipient', '')),
                    final_recipient=str(record.get('Final-Recipient', '')),
                    original_message_ids=sorted(refs), diagnostic=diagnostic,
                    reason=diagnostic if verified else 'Missing authenticated source, exact accepted Message-ID/recipient, routing or time'))
        else:
            report_like = root.get('mime_type') == 'multipart/report' or re.search(
                r'delivery (?:failure|status notification)|undeliver|returned mail', header(root,'Subject'), re.I)
            events.append(dict(base, recipient='', send_id=None, kind='review_text_report' if report_like else 'no_action', target=None,
                               bounce=False, reason='No structured DSN or verified unsubscribe notification'))
    for e in events:
        identity = [e['report_id'] or e['gmail_id'], e['recipient'], e.get('action'), e.get('status'), e.get('diagnostic'), e['kind']]
        e['key'] = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        e['canonical_key'] = canonical_key(e)
        e['duplicate'] = e['key'] in seen or e['key'] in prior or e['canonical_key'] in prior or e['canonical_key'] in seen
        # Unrelated messages/unknown recipients stay only in the private report.
        e['persist'] = e['send_id'] is not None
        seen.add(e['key'])
        seen.add(e['canonical_key'])
    changes, bounce_sends = {}, {}
    for e in events:
        if e['duplicate'] or e['send_id'] is None:
            continue
        s = next(s for s in sends if s['id'] == e['send_id'])
        if source == 'imap' and e['bounce'] and s['status'] not in {'accepted_by_smtp','sent','bounced_later'}:
            e.update(kind='review_conflicting_history',target=None,bounce=False,
                     reason='Conflicting historical evidence; operator review required')
            e['canonical_key']=canonical_key(e)
            e['duplicate']=e['canonical_key'] in prior or e['canonical_key'] in seen
            seen.add(e['canonical_key'])
            continue
        if e['target']:
            new = e['target']
            old = s['contact_status']
            prior_change = changes.get(s['contact_id'])
            if old == 'unsubscribed' or (prior_change and prior_change['new_status'] == 'unsubscribed'):
                new = 'unsubscribed'
            if old != new and not (prior_change and prior_change['new_status'] == 'unsubscribed'):
                changes[s['contact_id']] = dict(contact_id=s['contact_id'], email=s['email'],
                    old_status=old, new_status=new, reason=e['reason'], evidence_key=e['key'], gmail_id=e['gmail_id'])
        if e['bounce']:
            if s['status'] not in {'accepted_by_smtp', 'sent', 'bounced_later'}:
                raise ValueError('Conflicting historical send status; review before changing')
            bounce_sends[s['id']] = dict(send_id=s['id'], old_status=s['status'],
                old_trace=[s[k] for k in ('trace_status','trace_detail','trace_source','final_status_at','last_checked_at')],
                new_status='bounced_later', evidence_key=e['key'], gmail_id=e['gmail_id'], diagnostic=e['reason'])
    return dict(campaign_id=campaign_id, source=source, message_count=len(messages), events=events,
                contacts=list(changes.values()), sends=list(bounce_sends.values()),
                counts=dict(Counter(e['kind'] for e in events if not e['duplicate'])))


def apply(conn, proposal, now=None):
    """Caller owns transaction; abort on any optimistic conflict. Never migrate."""
    cid = proposal['campaign_id']
    if proposal.get('source','gmail') == 'gmail':
        ensure_idle(conn, cid)
    for event in proposal['events']:
        if event['persist'] and not event['duplicate'] and conn.execute('SELECT 1 FROM execution_events WHERE campaign_id=? AND message LIKE ? LIMIT 1',
                (cid, PREFIX + '%"key": "' + event['key'] + '"%')).fetchone():
            raise ValueError('Evidence was imported after planning; replan')
    now = now or datetime.now(timezone.utc).isoformat()
    for change in proposal['contacts']:
        exists = conn.execute('SELECT 1 FROM email_sends WHERE campaign_id=? AND contact_id=? AND lower(email)=?',
                              (cid, change['contact_id'], change['email'].lower())).fetchone()
        if not exists:
            raise ValueError('Contact outside campaign')
        changed = conn.execute('UPDATE contacts SET status=?,updated_at=? WHERE id=? AND status=?',
            (change['new_status'], now, change['contact_id'], change['old_status']))
        if changed.rowcount != 1:
            raise ValueError('Contact changed after planning')
    for change in proposal['sends']:
        row=conn.execute('SELECT * FROM email_sends WHERE id=? AND campaign_id=?', (change['send_id'],cid)).fetchone()
        if not row or row['status'] != change['old_status'] or [row[k] for k in ('trace_status','trace_detail','trace_source','final_status_at','last_checked_at')] != change['old_trace']:
            raise ValueError('Send evidence changed after planning')
        conn.execute('''UPDATE email_sends SET status='bounced_later',trace_status='failed',trace_detail=?,
            trace_source=?,final_status_at=?,last_checked_at=? WHERE id=?''',
            (change['diagnostic'], proposal.get('source','gmail') + ':' + change['gmail_id'], now, now, change['send_id']))
    for event in proposal['events']:
        if event['duplicate'] or not event['persist']:
            continue
        audit = dict(event, source_transport=proposal.get('source','gmail'), contact_changes=[c for c in proposal['contacts'] if c['evidence_key']==event['key']],
                     send_changes=[s for s in proposal['sends'] if s['evidence_key']==event['key']])
        conn.execute('INSERT INTO execution_events(campaign_id,created,message) VALUES(?,?,?)',
                     (cid, datetime.fromisoformat(now).timestamp(), PREFIX + json.dumps(audit, sort_keys=True)))
        if proposal.get('source','gmail') == 'imap' and conn.execute("SELECT 1 FROM sqlite_master WHERE name='mail_evidence'").fetchone():
            conn.execute('''INSERT INTO mail_evidence(event_key,campaign_id,send_id,source,kind,created,evidence)
                VALUES(?,?,?,?,?,?,?)''',(event['canonical_key'],cid,event['send_id'],proposal.get('source','gmail'),
                event['kind'],datetime.fromisoformat(now).timestamp(),json.dumps(audit,sort_keys=True)))
