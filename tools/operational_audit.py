"""Read-only campaign audit and consistent private SQLite/assets backup. No startup."""
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import db


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(conn):
    def rows(sql, args=()):
        return [dict(r) for r in conn.execute(sql, args)]
    campaigns = rows('SELECT id,status,created_at,completed_at FROM campaigns ORDER BY id DESC LIMIT 12')
    for campaign in campaigns:
        cid = campaign['id']
        campaign['sends'] = rows('SELECT status,COUNT(*) count FROM email_sends WHERE campaign_id=? GROUP BY status', (cid,))
        campaign['execution'] = rows('SELECT * FROM campaign_execution WHERE campaign_id=?', (cid,))
        campaign['attempts'] = rows('''SELECT status,COUNT(*) count,SUM(finished IS NULL) unfinished
            FROM send_attempt_history WHERE send_id IN (SELECT id FROM email_sends WHERE campaign_id=?) GROUP BY status''', (cid,))
        campaign['acceptance_audit'] = rows('''SELECT COUNT(*) total,
            SUM(s.accepted_at IS NOT NULL) accepted_at,SUM(s.sent_at IS NOT NULL) sent_at,
            SUM(s.outcome_uncertain) uncertain,
            SUM((s.accepted_at IS NOT NULL OR s.sent_at IS NOT NULL) AND NOT EXISTS
                (SELECT 1 FROM send_attempt_history a WHERE a.send_id=s.id AND a.mode='smtp' AND a.status='accepted_by_smtp')) timestamps_without_ledger,
            SUM(s.status IN ('pending','rate_limited','smtp_failed') AND (s.accepted_at IS NOT NULL OR s.sent_at IS NOT NULL)) unsent_with_timestamps,
            SUM(s.status IN ('pending','rate_limited','smtp_failed') AND c.last_sent_at IS NOT NULL) unsent_contacts_with_history,
            SUM(s.status IN ('pending','rate_limited','smtp_failed') AND c.last_sent_at IS NOT NULL AND NOT EXISTS
                (SELECT 1 FROM email_sends older WHERE older.contact_id=c.id AND older.campaign_id<>s.campaign_id
                AND older.accepted_at=c.last_sent_at)) history_without_other_acceptance
            FROM email_sends s JOIN contacts c ON c.id=s.contact_id WHERE campaign_id=?''', (cid,))[0]
    return dict(campaigns=campaigns,contacts=rows('SELECT status,COUNT(*) count FROM contacts GROUP BY status'),
        control=rows('SELECT * FROM smtp_control'),sync=rows('SELECT * FROM mail_sync_state'),
        evidence=rows('SELECT source,kind,COUNT(*) count FROM mail_evidence GROUP BY source,kind'),
        integrity=conn.execute('PRAGMA integrity_check').fetchone()[0],foreign_keys=len(rows('PRAGMA foreign_key_check')))


def main():
    target = ROOT/'backups'/('repair-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    target.mkdir(parents=True, exist_ok=False)
    database = db.DB_PATH.resolve()
    with sqlite3.connect(database.as_uri()+'?mode=ro', uri=True) as live:
        live.row_factory = sqlite3.Row
        with sqlite3.connect(target/'database.sqlite3') as saved:
            live.backup(saved)
        report = audit(live)
        for suffix in ('-wal','-shm'):
            sidecar = Path(str(database)+suffix)
            if sidecar.exists():
                shutil.copy2(sidecar, target/sidecar.name)
    assets = ROOT/'uploads'/'campaign_assets'
    if assets.exists():
        shutil.copytree(assets, target/'campaign_assets')
    asset_hashes = {str(p.relative_to(assets)):digest(p) for p in assets.rglob('*') if p.is_file()}
    assert asset_hashes == {str(p.relative_to(target/'campaign_assets')):digest(p) for p in (target/'campaign_assets').rglob('*') if p.is_file()}
    with sqlite3.connect(target/'database.sqlite3') as saved:
        saved.row_factory = sqlite3.Row
        assert audit(saved) == report
    (target/'local-before.patch').write_bytes(subprocess.check_output(['git','diff'],cwd=ROOT))
    report.update(backup=str(target),database_sha256=digest(target/'database.sqlite3'),assets=asset_hashes)
    (target/'audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    output=ROOT/'output'/'repair-2026-10-17'
    output.mkdir(parents=True,exist_ok=True)
    (output/'audit-before.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
