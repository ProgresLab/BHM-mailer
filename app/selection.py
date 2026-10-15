import hashlib
from .db import get_connection

PAGE_SIZE = 500
MAX_RECIPIENTS = 1000


def selected_ids(conn, campaign_id, eligible=False):
    active = " AND c.status='active'" if eligible else ''
    return [r[0] for r in conn.execute(f'''SELECT s.contact_id FROM campaign_selection s
        JOIN contacts c ON c.id=s.contact_id WHERE s.campaign_id=? {active} ORDER BY s.contact_id''', (campaign_id,))]


def selection_fingerprint(ids):
    return hashlib.sha256(','.join(map(str, ids)).encode()).hexdigest()


def update_selection(campaign_id, visible, checked, clear=False, remove=False):
    visible, checked = set(visible), set(checked)
    if len(visible) > PAGE_SIZE or not checked <= visible:
        raise ValueError('Nieprawidłowa strona selekcji (maksymalnie 500 rekordów).')
    with get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        campaign = conn.execute('SELECT status FROM campaigns WHERE id=?', (campaign_id,)).fetchone()
        if not campaign or campaign['status'] != 'approved':
            raise ValueError('Selekcja wymaga zatwierdzonej kampanii.')
        if clear:
            conn.execute('DELETE FROM campaign_selection WHERE campaign_id=?', (campaign_id,))
            return 0
        existing = set(selected_ids(conn, campaign_id))
        eligible = set()
        if checked:
            eligible = {r[0] for r in conn.execute(f"SELECT id FROM contacts WHERE status='active' AND id IN ({','.join('?' for _ in checked)})", tuple(checked))}
        # An add never replaces a page snapshot: another page/tab may have saved
        # recipients since it was rendered. Only explicit remove/clear can delete.
        target = existing - visible if remove else existing | eligible
        if len(target) > MAX_RECIPIENTS:
            raise ValueError('Limit wynosi 1000 odbiorców. Usuń dodane kontakty lub zaznacz mniej nowych.')
        conn.executemany('DELETE FROM campaign_selection WHERE campaign_id=? AND contact_id=?',
                         [(campaign_id, cid) for cid in existing - target])
        conn.executemany('INSERT OR IGNORE INTO campaign_selection(campaign_id,contact_id) VALUES(?,?)',
                         [(campaign_id, cid) for cid in target - existing])
        return len(target)
