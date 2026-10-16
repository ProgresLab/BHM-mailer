from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import re
import sqlite3
from contextlib import contextmanager
from uuid import uuid4

from .models import VALID_CAMPAIGN_STATUSES, VALID_SEND_STATUSES


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = BASE_DIR / "uploads"
DB_PATH = Path(os.getenv("BHM_DB_PATH", DATA_DIR / "bhm_mailer.sqlite3"))


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@contextmanager
def get_connection():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                company_name TEXT NULL,
                contact_name TEXT NULL,
                industry TEXT NULL,
                country_group TEXT NOT NULL CHECK(country_group IN ('PL', 'INTERNATIONAL')),
                language TEXT NOT NULL CHECK(language IN ('pl', 'en')),
                status TEXT NOT NULL CHECK(status IN ('active', 'unsubscribed', 'bounced', 'invalid')),
                source TEXT NULL,
                source_sheet TEXT NULL,
                consent_status TEXT NULL,
                notes TEXT NULL,
                unsubscribe_token TEXT UNIQUE,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_sent_at TEXT NULL
            );

            CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                language TEXT NULL CHECK(language IN ('pl', 'en')),
                subject TEXT NULL,
                body TEXT NULL,
                html TEXT NULL,
                text TEXT NULL,
                subject_pl TEXT NULL,
                subject_en TEXT NULL,
                body_pl TEXT NULL,
                body_en TEXT NULL,
                html_pl TEXT NULL,
                html_en TEXT NULL,
                text_pl TEXT NULL,
                text_en TEXT NULL,
                status TEXT NOT NULL CHECK(status IN (
                    'draft', 'approved', 'sending', 'completed',
                    'completed_with_errors', 'stopped'
                )),
                created_at TEXT NOT NULL,
                approved_at TEXT NULL,
                completed_at TEXT NULL
            );

            CREATE TABLE IF NOT EXISTS email_sends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER NOT NULL,
                contact_id INTEGER NOT NULL,
                email TEXT NOT NULL,
                language TEXT NOT NULL,
                subject TEXT NOT NULL,
                html_snapshot TEXT NOT NULL,
                text_snapshot TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN (
                    'pending', 'sending', 'accepted_by_smtp', 'smtp_failed',
                    'rate_limited', 'delivery_pending', 'delivered_by_trace',
                    'failed_by_trace', 'quarantined_by_trace', 'bounced_later',
                    'delivery_unknown', 'skipped_unsubscribed', 'skipped_invalid',
                    'skipped_duplicate', 'cancelled', 'dry_run', 'sent', 'failed',
                    'bounced', 'invalid'
                )),
                smtp_response TEXT NULL,
                error_message TEXT NULL,
                smtp_user TEXT NULL,
                header_from TEXT NULL,
                reply_to TEXT NULL,
                envelope_from TEXT NULL,
                envelope_to TEXT NULL,
                message_id TEXT NULL,
                sent_at TEXT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(campaign_id) REFERENCES campaigns(id),
                FOREIGN KEY(contact_id) REFERENCES contacts(id)
            );

            CREATE TABLE IF NOT EXISTS unsubscribe_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_id INTEGER NOT NULL,
                email TEXT NOT NULL,
                token TEXT NOT NULL,
                source_campaign_id INTEGER NULL,
                created_at TEXT NOT NULL,
                notification_sent INTEGER DEFAULT 0,
                FOREIGN KEY(contact_id) REFERENCES contacts(id),
                FOREIGN KEY(source_campaign_id) REFERENCES campaigns(id)
            );

            CREATE INDEX IF NOT EXISTS idx_contacts_status ON contacts(status);
            CREATE INDEX IF NOT EXISTS idx_contacts_group ON contacts(country_group);
            CREATE INDEX IF NOT EXISTS idx_contacts_language ON contacts(language);
            CREATE INDEX IF NOT EXISTS idx_email_sends_campaign ON email_sends(campaign_id);
            CREATE INDEX IF NOT EXISTS idx_unsubscribe_token ON contacts(unsubscribe_token);
            """
        )
        ensure_v11_schema(conn)
        ensure_v13_schema(conn)
        ensure_campaign_execution_schema(conn)
        ensure_mail_sync_schema(conn)
        conn.commit()


def new_unsubscribe_token() -> str:
    return uuid4().hex + uuid4().hex[:8]


def ensure_campaign_execution_schema(conn):
    for name in ('body_html', 'headline', 'cta_label', 'cta_url', 'banner_asset'):
        ensure_column(conn, 'campaigns', name, 'TEXT NULL')
    ensure_column(conn, 'email_sends', 'banner_asset', 'TEXT NULL')
    ensure_column(conn, 'email_sends', 'outcome_uncertain', 'INTEGER NOT NULL DEFAULT 0')
    ensure_column(conn, 'unsubscribe_events', 'notification_status', "TEXT NOT NULL DEFAULT 'pending'")
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS campaign_selection (
            campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
            contact_id INTEGER NOT NULL REFERENCES contacts(id),
            PRIMARY KEY(campaign_id, contact_id)
        );
        CREATE TABLE IF NOT EXISTS campaign_execution (
            campaign_id INTEGER PRIMARY KEY REFERENCES campaigns(id),
            state TEXT NOT NULL DEFAULT 'ready',
            mode TEXT NOT NULL CHECK(mode IN ('dry_run', 'smtp')),
            manual_pause INTEGER NOT NULL DEFAULT 0,
            started REAL NOT NULL, updated REAL NOT NULL,
            active_seconds REAL NOT NULL DEFAULT 0,
            cycle_seconds REAL NOT NULL DEFAULT 0,
            cooldown_until REAL NOT NULL DEFAULT 0,
            next_attempt REAL NOT NULL DEFAULT 0,
            smtp_seconds REAL NOT NULL DEFAULT 0,
            smtp_attempts INTEGER NOT NULL DEFAULT 0,
            problem TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS smtp_control (
            id INTEGER PRIMARY KEY CHECK(id=1),
            campaign_id INTEGER NULL REFERENCES campaigns(id),
            next_attempt REAL NOT NULL DEFAULT 0,
            blocked_until REAL NOT NULL DEFAULT 0
        );
        INSERT OR IGNORE INTO smtp_control(id) VALUES(1);
        CREATE TABLE IF NOT EXISTS smtp_attempts (
            id INTEGER PRIMARY KEY, send_id INTEGER NOT NULL REFERENCES email_sends(id),
            started REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_smtp_attempts_time ON smtp_attempts(started);
        CREATE TABLE IF NOT EXISTS notification_attempts (
            id INTEGER PRIMARY KEY, event_id INTEGER NOT NULL REFERENCES unsubscribe_events(id),
            started REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_sends_queue ON email_sends(campaign_id,status,id);
        CREATE TABLE IF NOT EXISTS execution_events (
            id INTEGER PRIMARY KEY, campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
            created REAL NOT NULL, message TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS recovery_decisions (
            id INTEGER PRIMARY KEY, send_id INTEGER NOT NULL REFERENCES email_sends(id),
            created REAL NOT NULL, decision TEXT NOT NULL, note TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS send_attempt_history (
            id INTEGER PRIMARY KEY, send_id INTEGER NOT NULL REFERENCES email_sends(id),
            attempt_number INTEGER NOT NULL, mode TEXT NOT NULL, started REAL NOT NULL,
            finished REAL NULL, recovered_at REAL NULL, status TEXT NOT NULL,
            message_id TEXT NOT NULL, smtp_code TEXT NULL, detail TEXT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_attempt_history_send ON send_attempt_history(send_id,id);
    ''')
    ensure_column(conn,'campaign_execution','identity_fingerprint','TEXT NULL')
    ensure_column(conn,'campaign_execution','smtp_cooldown_until','REAL NOT NULL DEFAULT 0')
    ensure_column(conn,'campaign_execution','auto_resume_count','INTEGER NOT NULL DEFAULT 0')
    ensure_column(conn,'campaign_execution','failure_kind',"TEXT NOT NULL DEFAULT ''")


def ensure_mail_sync_schema(conn):
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS mail_sync_state (
            mailbox TEXT PRIMARY KEY, uidvalidity TEXT NOT NULL DEFAULT '',
            last_uid INTEGER NOT NULL DEFAULT 0, last_success REAL,
            next_sync REAL NOT NULL DEFAULT 0, scanning INTEGER NOT NULL DEFAULT 0,
            requested INTEGER NOT NULL DEFAULT 0, last_error TEXT NOT NULL DEFAULT '',
            new_messages INTEGER NOT NULL DEFAULT 0, hard_bounces INTEGER NOT NULL DEFAULT 0,
            unsubscribes INTEGER NOT NULL DEFAULT 0, reviews INTEGER NOT NULL DEFAULT 0,
            alerts INTEGER NOT NULL DEFAULT 0, contact_changes INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS mail_sync_messages (
            mailbox TEXT NOT NULL, uidvalidity TEXT NOT NULL, uid INTEGER NOT NULL,
            processed REAL NOT NULL, disposition TEXT NOT NULL,
            PRIMARY KEY(mailbox,uidvalidity,uid)
        );
        CREATE TABLE IF NOT EXISTS mail_evidence (
            event_key TEXT PRIMARY KEY, campaign_id INTEGER, send_id INTEGER,
            source TEXT NOT NULL, kind TEXT NOT NULL, created REAL NOT NULL,
            evidence TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_mail_evidence_campaign ON mail_evidence(campaign_id);
        CREATE INDEX IF NOT EXISTS idx_accepted_contact ON email_sends(contact_id,accepted_at);
        CREATE INDEX IF NOT EXISTS idx_accepted_message ON send_attempt_history(message_id,mode,status);
    ''')


def ensure_unique_token(conn: sqlite3.Connection) -> str:
    while True:
        token = new_unsubscribe_token()
        exists = conn.execute(
            "SELECT 1 FROM contacts WHERE unsubscribe_token = ?", (token,)
        ).fetchone()
        if not exists:
            return token


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return dict(row)


def table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}


def ensure_column(
    conn: sqlite3.Connection,
    table_name: str,
    column_name: str,
    definition: str,
) -> None:
    if column_name in table_columns(conn, table_name):
        return
    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def ensure_v11_schema(conn: sqlite3.Connection) -> None:
    ensure_column(conn, "contacts", "last_sent_at", "TEXT NULL")

    campaign_columns = {
        "language": "TEXT NULL",
        "subject": "TEXT NULL",
        "body": "TEXT NULL",
        "html": "TEXT NULL",
        "text": "TEXT NULL",
    }
    for column_name, definition in campaign_columns.items():
        ensure_column(conn, "campaigns", column_name, definition)

    conn.execute(
        """
        UPDATE campaigns
        SET language = COALESCE(
                language,
                CASE
                    WHEN COALESCE(NULLIF(subject_pl, ''), NULLIF(body_pl, ''), NULLIF(html_pl, ''), NULLIF(text_pl, '')) IS NOT NULL
                    THEN 'pl'
                    ELSE 'en'
                END
            ),
            subject = COALESCE(subject, NULLIF(subject_pl, ''), NULLIF(subject_en, ''), name),
            body = COALESCE(body, NULLIF(body_pl, ''), NULLIF(body_en, '')),
            html = COALESCE(html, NULLIF(html_pl, ''), NULLIF(html_en, '')),
            text = COALESCE(text, NULLIF(text_pl, ''), NULLIF(text_en, ''))
        WHERE language IS NULL
           OR subject IS NULL
           OR body IS NULL
           OR html IS NULL
           OR text IS NULL
        """
    )


def ensure_v13_schema(conn: sqlite3.Connection) -> None:
    email_send_columns = {
        "smtp_code": "TEXT NULL",
        "smtp_response": "TEXT NULL",
        "smtp_message_id": "TEXT NULL",
        "provider_message_id": "TEXT NULL",
        "attempt_count": "INTEGER DEFAULT 0",
        "started_at": "TEXT NULL",
        "accepted_at": "TEXT NULL",
        "final_status_at": "TEXT NULL",
        "last_checked_at": "TEXT NULL",
        "trace_status": "TEXT NULL",
        "trace_detail": "TEXT NULL",
        "trace_source": "TEXT NULL",
        "last_error": "TEXT NULL",
        "smtp_user": "TEXT NULL",
        "header_from": "TEXT NULL",
        "reply_to": "TEXT NULL",
        "envelope_from": "TEXT NULL",
        "envelope_to": "TEXT NULL",
        "message_id": "TEXT NULL",
    }
    for column_name, definition in email_send_columns.items():
        ensure_column(conn, "email_sends", column_name, definition)

    ensure_text_check_values(conn, "campaigns", "status", VALID_CAMPAIGN_STATUSES)
    ensure_text_check_values(conn, "email_sends", "status", VALID_SEND_STATUSES)


def ensure_text_check_values(
    conn: sqlite3.Connection,
    table_name: str,
    column_name: str,
    allowed_values: tuple[str, ...],
) -> None:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    if not row or not row["sql"]:
        return

    sql = str(row["sql"])
    if all(f"'{value}'" in sql for value in allowed_values):
        return

    pattern = re.compile(
        rf"({re.escape(column_name)}\s+TEXT\s+NOT\s+NULL\s+CHECK\s*\(\s*"
        rf"{re.escape(column_name)}\s+IN\s*\()(?P<values>[^)]*)(\)\s*\))",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(sql)
    if not match:
        return

    values_sql = ", ".join(f"'{value}'" for value in allowed_values)
    new_sql = f"{sql[: match.start(2)]}{values_sql}{sql[match.end(2) :]}"
    if new_sql == sql:
        return

    try:
        conn.execute("PRAGMA writable_schema = ON")
        conn.execute(
            "UPDATE sqlite_master SET sql = ? WHERE type = 'table' AND name = ?",
            (new_sql, table_name),
        )
        schema_version = conn.execute("PRAGMA schema_version").fetchone()[0]
        conn.execute(f"PRAGMA schema_version = {int(schema_version) + 1}")
    finally:
        conn.execute("PRAGMA writable_schema = OFF")
