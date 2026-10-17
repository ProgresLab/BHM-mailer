from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, make_msgid
import hashlib
import hmac
import os
import re
import smtplib
import ssl
import sqlite3
import time
from urllib.parse import urlencode
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

from .db import ensure_unique_token, get_connection, utc_now
from .email_renderer import (
    EMAIL_LOGO_CID,
    EMAIL_LOGO_FILENAME,
    EMAIL_LOGO_PATH,
    EMAIL_LOGO_SRC,
    LEGACY_UNSUBSCRIBE_PLACEHOLDER,
    UNSUBSCRIBE_PLACEHOLDER,
)


load_dotenv()


LOCAL_UNSUBSCRIBE_WARNING = (
    "PUBLIC_UNSUBSCRIBE_BASE_URL points to a local address. Bulk sending is blocked; "
    "only a one-recipient SMTP test is allowed."
)
UNSUBSCRIBE_SECRET_REQUIRED_ERROR = (
    "UNSUBSCRIBE_SECRET is required when SMTP_ENABLED=true. Real sending is blocked "
    "until signed unsubscribe links can be generated."
)
LOCAL_UNSUBSCRIBE_MARKERS = ("127.0.0.1", "localhost", "0.0.0.0")
DEFAULT_PUBLIC_UNSUBSCRIBE_BASE_URL = "https://unsubscribe.mail.bhm-chemicals.com/unsubscribe"
ONE_COM_SMTP_HOST = "send.one.com"
ONE_COM_SMTP_PORT = 465
ONE_COM_SMTP_USER = "marketing@bhm-chemicals.com"
ONE_COM_FROM_EMAIL = "marketing@bhm-chemicals.com"
ONE_COM_ENVELOPE_FROM = "marketing@bhm-chemicals.com"
ONE_COM_REPLY_TO = "info@bhm-chemicals.com"
SUCCESS_SEND_STATUSES = {"accepted_by_smtp", "delivered_by_trace", "dry_run", "sent"}
ERROR_SEND_STATUSES = {
    "smtp_failed",
    "rate_limited",
    "failed_by_trace",
    "quarantined_by_trace",
    "bounced_later",
    "delivery_unknown",
    "failed",
    "bounced",
    "invalid",
    "skipped_invalid",
    "skipped_duplicate",
    "cancelled",
}
PENDING_SEND_STATUSES = {"pending", "sending"}


@dataclass
class MailSettings:
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_from_name: str
    smtp_from_email: str
    smtp_reply_to: str
    smtp_envelope_from: str
    smtp_use_tls: bool
    smtp_use_ssl: bool
    smtp_enabled: bool
    public_unsubscribe_base_url: str
    unsubscribe_secret: str
    admin_notification_email: str
    email_send_delay_seconds: float
    dry_run_skip_delay: bool


@dataclass
class SenderIdentity:
    smtp_user: str
    header_from: str
    reply_to: str
    envelope_from: str
    envelope_to: str
    message_id: str


@dataclass
class SmtpSendResult:
    smtp_code: str
    smtp_response: str
    smtp_message_id: str
    smtp_user: str
    header_from: str
    reply_to: str
    envelope_from: str
    envelope_to: str
    message_id: str
    provider_message_id: str | None = None


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        parsed = float(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def env_int(name: str, default: int = 0) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError:
        return default


def get_mail_settings() -> MailSettings:
    return MailSettings(
        smtp_host=os.getenv("SMTP_HOST", "").strip(),
        smtp_port=env_int("SMTP_PORT", 0),
        smtp_user=os.getenv("SMTP_USER", "").strip(),
        smtp_password=os.getenv("SMTP_PASSWORD", "").strip(),
        smtp_from_name=os.getenv("SMTP_FROM_NAME", "BHM Chemicals").strip(),
        smtp_from_email=os.getenv("SMTP_FROM_EMAIL", "").strip(),
        smtp_reply_to=os.getenv("SMTP_REPLY_TO", "").strip(),
        smtp_envelope_from=os.getenv("SMTP_ENVELOPE_FROM", "").strip(),
        smtp_use_tls=env_bool("SMTP_USE_TLS", True),
        smtp_use_ssl=env_bool("SMTP_USE_SSL", False),
        smtp_enabled=env_bool("SMTP_ENABLED", False),
        public_unsubscribe_base_url=os.getenv("PUBLIC_UNSUBSCRIBE_BASE_URL", "").strip().rstrip("/"),
        unsubscribe_secret=os.getenv("UNSUBSCRIBE_SECRET", "").strip(),
        admin_notification_email=os.getenv("ADMIN_NOTIFICATION_EMAIL", "").strip(),
        email_send_delay_seconds=20.0,
        dry_run_skip_delay=env_bool("DRY_RUN_SKIP_DELAY", False),
    )


def smtp_is_configured(settings: MailSettings) -> bool:
    return bool(settings.smtp_enabled and smtp_send_configuration_error(settings) is None)


def is_local_unsubscribe_base_url(base_url: str) -> bool:
    value = (base_url or "").lower()
    return any(marker in value for marker in LOCAL_UNSUBSCRIBE_MARKERS)


def public_unsubscribe_url_warning(settings: MailSettings) -> str | None:
    if settings.smtp_enabled and is_local_unsubscribe_base_url(settings.public_unsubscribe_base_url):
        return LOCAL_UNSUBSCRIBE_WARNING
    return None


def smtp_send_configuration_error(settings: MailSettings) -> str | None:
    if not settings.smtp_enabled:
        return None

    errors: list[str] = []
    if not settings.unsubscribe_secret:
        errors.append(UNSUBSCRIBE_SECRET_REQUIRED_ERROR)
    errors.extend(sender_identity_configuration_errors(settings))
    return " ".join(errors) if errors else None


def sender_identity_configuration_errors(
    settings: MailSettings, identity: SenderIdentity | None = None
) -> list[str]:
    if not settings.smtp_enabled:
        return []

    errors: list[str] = []
    if not settings.smtp_host:
        errors.append("SMTP_HOST is required before real SMTP sending.")
    if not settings.smtp_port:
        errors.append("SMTP_PORT is required before real SMTP sending.")
    if not settings.smtp_from_email:
        errors.append("SMTP_FROM_EMAIL is required before real SMTP sending.")
    if not settings.smtp_user:
        errors.append("SMTP_USER is required before real SMTP sending.")
    if not settings.smtp_password:
        errors.append("SMTP_PASSWORD is required before real SMTP sending.")
    if not settings.smtp_reply_to:
        errors.append("SMTP_REPLY_TO is empty; configure it before real SMTP sending.")
    if not settings.smtp_envelope_from:
        errors.append("SMTP_ENVELOPE_FROM is required before real SMTP sending.")
    if not settings.public_unsubscribe_base_url:
        errors.append("PUBLIC_UNSUBSCRIBE_BASE_URL is required before real SMTP sending.")
    return errors


def smtp_provider_label(settings: MailSettings) -> str:
    host = (settings.smtp_host or "").strip().lower()
    if host == ONE_COM_SMTP_HOST:
        return "one.com"
    return settings.smtp_host or "not configured"


def smtp_uses_ssl(settings: MailSettings) -> bool:
    return bool(settings.smtp_use_ssl or settings.smtp_port == 465)


def smtp_mode_label(settings: MailSettings) -> str:
    port = settings.smtp_port
    if smtp_uses_ssl(settings):
        return f"SSL {port}" if port else "SSL"
    if settings.smtp_use_tls:
        return f"STARTTLS {port}" if port else "STARTTLS"
    return f"plain SMTP {port}" if port else "not configured"


def smtp_configuration_warnings(settings: MailSettings) -> list[str]:
    warnings: list[str] = []
    if (settings.smtp_host or "").strip().lower() != ONE_COM_SMTP_HOST:
        warnings.append("SMTP_HOST should be send.one.com for one.com campaign SMTP.")
    if settings.smtp_port != ONE_COM_SMTP_PORT:
        warnings.append("SMTP_PORT should be 465 for one.com campaign SMTP.")
    if not settings.smtp_use_ssl:
        warnings.append("SMTP_USE_SSL should be true for one.com campaign SMTP.")
    if (settings.smtp_user or "").strip().lower() != ONE_COM_SMTP_USER:
        warnings.append("SMTP_USER should be marketing@bhm-chemicals.com for campaign sends.")
    if (settings.smtp_from_email or "").strip().lower() != ONE_COM_FROM_EMAIL:
        warnings.append("SMTP_FROM_EMAIL should be marketing@bhm-chemicals.com for campaign sends.")
    if (settings.smtp_envelope_from or "").strip().lower() != ONE_COM_ENVELOPE_FROM:
        warnings.append("SMTP_ENVELOPE_FROM should be marketing@bhm-chemicals.com for campaign sends.")
    if (settings.smtp_reply_to or "").strip().lower() != ONE_COM_REPLY_TO:
        warnings.append("SMTP_REPLY_TO should remain info@bhm-chemicals.com.")
    return warnings


def message_id_domain(settings: MailSettings) -> str:
    from_email = settings.smtp_from_email or ""
    if "@" in from_email:
        domain = from_email.rsplit("@", 1)[1].strip()
        if domain:
            return domain
    return "mail.bhm-chemicals.com"


def prepare_message_identity(settings: MailSettings, to_email: str) -> SenderIdentity:
    header_from_email = settings.smtp_from_email.strip()
    envelope_from = settings.smtp_envelope_from.strip() or settings.smtp_from_email.strip()
    return SenderIdentity(
        smtp_user=settings.smtp_user.strip(),
        header_from=formataddr((settings.smtp_from_name, header_from_email)),
        reply_to=settings.smtp_reply_to.strip(),
        envelope_from=envelope_from,
        envelope_to=to_email.strip(),
        message_id=make_msgid(domain=message_id_domain(settings)),
    )


def smtp_identity_diagnostics(settings: MailSettings, to_email: str) -> dict[str, str]:
    identity = prepare_message_identity(settings, to_email)
    return {
        "smtp_user": identity.smtp_user,
        "header_from": identity.header_from,
        "reply_to": identity.reply_to,
        "envelope_from": identity.envelope_from,
        "envelope_to": identity.envelope_to,
        "message_id": identity.message_id,
    }


def identity_update_kwargs(identity: SenderIdentity) -> dict[str, str]:
    return {
        "smtp_user": identity.smtp_user,
        "header_from": identity.header_from,
        "reply_to": identity.reply_to,
        "envelope_from": identity.envelope_from,
        "envelope_to": identity.envelope_to,
        "message_id": identity.message_id,
    }


def row_value(row: sqlite3.Row, key: str, default: str = "") -> str:
    if key not in row.keys():
        return default
    value = row[key]
    return str(value) if value is not None else default


def personalize_snapshot(snapshot: str, unsubscribe_url: str) -> str:
    return (
        (snapshot or "")
        .replace(LEGACY_UNSUBSCRIBE_PLACEHOLDER, unsubscribe_url)
        .replace(UNSUBSCRIBE_PLACEHOLDER, unsubscribe_url)
    )


def unsubscribe_signature(
    secret: str,
    email: str,
    token: str,
    language: str,
    campaign_id: int,
    timestamp: str,
) -> str:
    payload = f"{email}|{token}|{language}|{campaign_id}|{timestamp}"
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def build_public_unsubscribe_url(
    settings: MailSettings,
    email: str,
    token: str,
    language: str,
    campaign_id: int,
) -> str:
    timestamp = str(int(time.time()))
    params = {
        "email": email,
        "token": token,
        "lang": language,
        "campaign_id": str(campaign_id),
        "ts": timestamp,
    }
    params["sig"] = unsubscribe_signature(
        settings.unsubscribe_secret,
        email,
        token,
        language,
        campaign_id,
        timestamp,
    )
    base_url = settings.public_unsubscribe_base_url or DEFAULT_PUBLIC_UNSUBSCRIBE_BASE_URL
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}{urlencode(params)}"


def select_language_value(campaign: sqlite3.Row, language: str, field: str) -> str:
    primary_key = f"{field}_{language}"
    fallback_language = "en" if language == "pl" else "pl"
    fallback_key = f"{field}_{fallback_language}"
    return row_value(campaign, primary_key) or row_value(campaign, fallback_key)


def campaign_language(campaign: sqlite3.Row) -> str:
    language = row_value(campaign, "language", "en").lower()
    return language if language in {"pl", "en"} else "en"


def campaign_subject(campaign: sqlite3.Row) -> str:
    language = campaign_language(campaign)
    return (
        row_value(campaign, "subject")
        or select_language_value(campaign, language, "subject")
        or row_value(campaign, "name")
    )


def campaign_html(campaign: sqlite3.Row) -> str:
    language = campaign_language(campaign)
    return row_value(campaign, "html") or select_language_value(campaign, language, "html")


def campaign_text(campaign: sqlite3.Row) -> str:
    language = campaign_language(campaign)
    return row_value(campaign, "text") or select_language_value(campaign, language, "text")


def chunks(values: list[int], size: int = 500) -> list[list[int]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def fetch_contacts_by_ids(conn: sqlite3.Connection, contact_ids: list[int]) -> dict[int, sqlite3.Row]:
    contacts: dict[int, sqlite3.Row] = {}
    for batch in chunks(contact_ids):
        placeholders = ",".join("?" for _ in batch)
        rows = conn.execute(f"SELECT * FROM contacts WHERE id IN ({placeholders})", tuple(batch)).fetchall()
        contacts.update({int(row["id"]): row for row in rows})
    return contacts


def prepare_campaign_send(campaign_id: int, contact_ids: list[int], mode: str = "dry_run") -> dict[str, object]:
    if mode not in {"dry_run", "smtp"}:
        raise ValueError("Nieprawidłowy tryb wysyłki.")
    unique_ids = list(dict.fromkeys(contact_ids))
    if len(unique_ids) > 1000:
        raise ValueError("Limit kampanii wynosi 1000 odbiorców.")
    if not unique_ids:
        return {"started": False, "message": "No recipients selected.", "send_ids": [], "recipient_count": 0}

    settings = get_mail_settings()
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        owner = conn.execute("SELECT campaign_id FROM smtp_control WHERE id=1").fetchone()
        if owner["campaign_id"] is not None:
            raise ValueError("Konto jest zarezerwowane przez aktywną lub wstrzymaną kampanię.")
        if conn.execute("SELECT 1 FROM email_sends WHERE campaign_id=? LIMIT 1", (campaign_id,)).fetchone():
            raise ValueError("Ta kampania ma już snapshoty. Użyj panelu wznowienia.")
        campaign = conn.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
        if campaign is None:
            raise ValueError("Campaign not found.")
        if campaign["status"] == "sending":
            return {
                "started": False,
                "message": "Campaign is already sending.",
                "send_ids": [],
                "recipient_count": 0,
            }
        if campaign["status"] != "approved":
            raise ValueError("Campaign must be approved before sending.")

        contacts = fetch_contacts_by_ids(conn, unique_ids)
        from .selection import UNCERTAIN_CONTACT_SQL
        uncertain_ids={r[0] for r in conn.execute('SELECT c.id FROM contacts c WHERE '+UNCERTAIN_CONTACT_SQL)}
        active_contacts = [contacts[contact_id] for contact_id in unique_ids if contacts.get(contact_id) and contacts[contact_id]["status"] == "active" and contact_id not in uncertain_ids]
        if not active_contacts:
            return {
                "started": False,
                "message": "No active recipients selected.",
                "send_ids": [],
                "recipient_count": 0,
            }

        configuration_error = smtp_send_configuration_error(settings) if mode == "smtp" else None
        if configuration_error:
            return {
                "started": False,
                "message": configuration_error,
                "send_ids": [],
                "recipient_count": len(active_contacts),
            }

        if mode == "smtp" and not smtp_is_configured(settings):
            raise ValueError("SMTP nie jest włączone lub skonfigurowane.")
        warning = public_unsubscribe_url_warning(settings) if mode == "smtp" else None
        if warning and len(active_contacts) > 1:
            return {
                "started": False,
                "message": warning,
                "send_ids": [],
                "recipient_count": len(active_contacts),
            }

        cursor = conn.execute(
            "UPDATE campaigns SET status = 'sending' WHERE id = ? AND status = 'approved'",
            (campaign_id,),
        )
        if cursor.rowcount != 1:
            conn.commit()
            return {
                "started": False,
                "message": "Campaign could not be started because its status changed.",
                "send_ids": [],
                "recipient_count": 0,
            }

        from .assets import asset_path
        banner = row_value(campaign, 'banner_asset')
        if banner and not asset_path(banner).is_file():
            raise ValueError("Brak zapisanego banera kampanii.")
        language = campaign_language(campaign)
        subject = campaign_subject(campaign)
        html_template = campaign_html(campaign)
        text_template = campaign_text(campaign)
        send_ids: list[int] = []
        for contact in active_contacts:
            token = contact["unsubscribe_token"]
            if not token:
                token = ensure_unique_token(conn)
                conn.execute(
                    "UPDATE contacts SET unsubscribe_token = ?, updated_at = ? WHERE id = ?",
                    (token, utc_now(), contact["id"]),
                )
            unsubscribe_url = build_public_unsubscribe_url(
                settings,
                contact["email"],
                token,
                language,
                campaign_id,
            )
            send_ids.append(
                insert_send(
                    conn,
                    campaign_id,
                    contact,
                    language,
                    subject,
                    personalize_snapshot(html_template, unsubscribe_url),
                    personalize_snapshot(text_template, unsubscribe_url),
                    "pending",
                )
            )
        conn.execute("UPDATE email_sends SET banner_asset=? WHERE campaign_id=?", (banner or None, campaign_id))
        now_epoch = time.time()
        conn.execute("INSERT INTO campaign_execution(campaign_id,state,mode,started,updated) VALUES(?,'running',?,?,?)",
                     (campaign_id, mode, now_epoch, now_epoch))
        from .worker import identity_fingerprint
        conn.execute('UPDATE campaign_execution SET identity_fingerprint=? WHERE campaign_id=?',(identity_fingerprint(settings),campaign_id))
        conn.execute("UPDATE smtp_control SET campaign_id=? WHERE id=1", (campaign_id,))
        conn.commit()

    return {
        "started": True,
        "message": "Campaign sending started.",
        "send_ids": send_ids,
        "recipient_count": len(send_ids),
    }


def send_pending_campaign(campaign_id: int, send_ids: list[int] | None = None) -> None:
    # Compatibility entry point: delivery is owned exclusively by the singleton worker.
    from .worker import manager
    if not manager.available:
        raise ValueError("Worker niedostępny. Uruchom pojedynczy proces aplikacji.")
    manager.wake.set()


def mark_send_started(conn: sqlite3.Connection, send_id: int) -> None:
    conn.execute(
        """
        UPDATE email_sends
        SET status = 'sending',
            started_at = ?,
            attempt_count = COALESCE(attempt_count, 0) + 1,
            last_error = NULL,
            error_message = NULL
        WHERE id = ?
        """,
        (utc_now(), send_id),
    )


def finalize_campaign_status(conn: sqlite3.Connection, campaign_id: int) -> str:
    row = conn.execute(
        """
        SELECT
            COALESCE(SUM(status IN ('pending', 'sending')), 0) AS open_count,
            COALESCE(SUM(status IN (
                'smtp_failed', 'rate_limited', 'failed_by_trace',
                'quarantined_by_trace', 'bounced_later', 'delivery_unknown',
                'failed', 'bounced', 'invalid', 'skipped_invalid',
                  'skipped_duplicate', 'skipped_unsubscribed', 'cancelled'
            )), 0) AS error_count
        FROM email_sends
        WHERE campaign_id = ?
        """,
        (campaign_id,),
    ).fetchone()
    if not row:
        return "sending"
    if int(row["open_count"] or 0) > 0:
        current = conn.execute("SELECT status FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
        if current and current["status"] not in {"sending", "stopped"}:
            return current["status"]
        return "sending"

    status = "completed_with_errors" if int(row["error_count"] or 0) > 0 else "completed"
    conn.execute(
        """
        UPDATE campaigns
        SET status = ?, completed_at = COALESCE(completed_at, ?)
        WHERE id = ? AND status IN ('sending', 'completed', 'completed_with_errors')
        """,
        (status, utc_now(), campaign_id),
    )
    return status


def should_delay(settings: MailSettings, dry_run: bool) -> bool:
    if dry_run and settings.dry_run_skip_delay:
        return False
    return settings.email_send_delay_seconds > 0


def mark_contact_sent(conn: sqlite3.Connection, contact_id: int, sent_at: str) -> None:
    conn.execute(
        "UPDATE contacts SET last_sent_at = ?, updated_at = ? WHERE id = ?",
        (sent_at, sent_at, contact_id),
    )


def update_send_status(
    conn: sqlite3.Connection,
    send_id: int,
    status: str,
    error_message: str | None = None,
    smtp_response: str | None = None,
    smtp_code: str | None = None,
    smtp_message_id: str | None = None,
    provider_message_id: str | None = None,
    sent_at: str | None = None,
    accepted_at: str | None = None,
    final_status_at: str | None = None,
    last_error: str | None = None,
    smtp_user: str | None = None,
    header_from: str | None = None,
    reply_to: str | None = None,
    envelope_from: str | None = None,
    envelope_to: str | None = None,
    message_id: str | None = None,
) -> None:
    safe_error = sanitize_log_text(error_message)
    safe_last_error = sanitize_log_text(last_error if last_error is not None else error_message)
    safe_response = sanitize_log_text(smtp_response)
    conn.execute(
        """
        UPDATE email_sends
        SET status = ?,
            error_message = ?,
            last_error = ?,
            smtp_response = ?,
            smtp_code = ?,
            smtp_message_id = ?,
            provider_message_id = ?,
            smtp_user = ?,
            header_from = ?,
            reply_to = ?,
            envelope_from = ?,
            envelope_to = ?,
            message_id = ?,
            sent_at = ?,
            accepted_at = ?,
            final_status_at = ?
        WHERE id = ?
        """,
        (
            status,
            safe_error,
            safe_last_error,
            safe_response,
            smtp_code,
            smtp_message_id,
            provider_message_id,
            smtp_user,
            header_from,
            reply_to,
            envelope_from,
            envelope_to,
            message_id,
            sent_at,
            accepted_at,
            final_status_at,
            send_id,
        ),
    )


def coerce_send_status_for_db(conn: sqlite3.Connection, status: str) -> str:
    if status == "invalid" and not email_sends_supports_status(conn, "invalid"):
        return "bounced"
    return status


def email_sends_supports_status(conn: sqlite3.Connection, status: str) -> bool:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'email_sends'"
    ).fetchone()
    sql = row["sql"] if row else ""
    if "CHECK" not in sql:
        return True
    return f"'{status}'" in sql


def send_campaign_to_contacts(
    conn: sqlite3.Connection, campaign_id: int, contact_ids: list[int]
) -> dict[str, object]:
    result = prepare_campaign_send(campaign_id, contact_ids)
    if result["started"]:
        send_pending_campaign(campaign_id, result["send_ids"])
    counters = read_campaign_counters(campaign_id)
    return {"message": result["message"], "counters": counters, "requested": len(contact_ids)}


def read_campaign_counters(campaign_id: int) -> dict[str, int]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                COALESCE(SUM(status = 'pending'), 0) AS pending,
                COALESCE(SUM(status = 'sending'), 0) AS sending,
                COALESCE(SUM(status = 'dry_run'), 0) AS dry_run,
                COALESCE(SUM(status IN ('accepted_by_smtp', 'sent')), 0) AS accepted_by_smtp,
                COALESCE(SUM(status IN ('smtp_failed', 'failed')), 0) AS smtp_failed,
                COALESCE(SUM(status = 'rate_limited'), 0) AS rate_limited,
                COALESCE(SUM(status = 'delivery_pending'), 0) AS delivery_pending,
                COALESCE(SUM(status = 'delivered_by_trace'), 0) AS delivered_by_trace,
                COALESCE(SUM(status = 'failed_by_trace'), 0) AS failed_by_trace,
                COALESCE(SUM(status = 'quarantined_by_trace'), 0) AS quarantined_by_trace,
                COALESCE(SUM(status IN ('bounced_later', 'bounced', 'invalid')), 0) AS bounced_later,
                COALESCE(SUM(status LIKE 'skipped_%'), 0) AS skipped,
                COALESCE(SUM(status = 'delivery_unknown'), 0) AS delivery_unknown
            FROM email_sends
            WHERE campaign_id = ?
            """,
            (campaign_id,),
        ).fetchone()
    return dict(row) if row else {}


def insert_send(
    conn: sqlite3.Connection,
    campaign_id: int,
    contact: sqlite3.Row,
    language: str,
    subject: str,
    html_snapshot: str,
    text_snapshot: str,
    status: str,
    error_message: str | None = None,
    smtp_response: str | None = None,
    sent_at: str | None = None,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO email_sends (
            campaign_id, contact_id, email, language, subject, html_snapshot,
            text_snapshot, status, smtp_response, error_message, sent_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            campaign_id,
            contact["id"],
            contact["email"],
            language,
            subject,
            html_snapshot,
            text_snapshot,
            status,
            smtp_response,
            error_message,
            sent_at,
            utc_now(),
        ),
    )
    return int(cursor.lastrowid)


def send_one_email(
    settings: MailSettings,
    to_email: str,
    subject: str,
    text_content: str,
    html_content: str,
    identity: SenderIdentity | None = None,
    banner_asset: str | None = None,
) -> SmtpSendResult:
    identity = identity or prepare_message_identity(settings, to_email)
    configuration_error = smtp_send_configuration_error(settings)
    if configuration_error:
        raise ValueError("SMTP configuration error: " + configuration_error)
    message = MIMEMultipart("related")
    message["Subject"] = subject
    message["From"] = identity.header_from
    message["To"] = identity.envelope_to
    message["Message-ID"] = identity.message_id
    if identity.reply_to:
        message["Reply-To"] = identity.reply_to

    alternative = MIMEMultipart("alternative")
    alternative.attach(MIMEText(text_content, "plain", "utf-8"))
    alternative.attach(MIMEText(html_content, "html", "utf-8"))
    message.attach(alternative)
    attach_inline_logo(message, html_content)
    if banner_asset:
        from .assets import asset_path, banner_cid
        image = MIMEImage(asset_path(banner_asset).read_bytes())
        image.add_header('Content-ID', f'<{banner_cid(banner_asset)}>')
        image.add_header('Content-Disposition', 'inline', filename='campaign-banner.' + banner_asset.rsplit('.', 1)[1])
        message.attach(image)

    use_ssl = smtp_uses_ssl(settings)
    smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    tls_kwargs = {"context": ssl.create_default_context()} if use_ssl else {}
    with smtp_class(settings.smtp_host, settings.smtp_port, timeout=30, **tls_kwargs) as smtp:
        smtp.ehlo()
        if not use_ssl and settings.smtp_use_tls:
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
        if settings.smtp_user or settings.smtp_password:
            smtp.login(settings.smtp_user, settings.smtp_password)
        refused = smtp.sendmail(
            from_addr=identity.envelope_from,
            to_addrs=[identity.envelope_to],
            msg=message.as_string(),
        )
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)

    response_text = "Accepted by SMTP via sendmail; no refused recipients"
    return SmtpSendResult(
        smtp_code="250",
        smtp_response=f"250 {response_text}",
        smtp_message_id=identity.message_id,
        smtp_user=identity.smtp_user,
        header_from=identity.header_from,
        reply_to=identity.reply_to,
        envelope_from=identity.envelope_from,
        envelope_to=identity.envelope_to,
        message_id=identity.message_id,
        provider_message_id=None,
    )


def attach_inline_logo(message: MIMEMultipart, html_content: str) -> None:
    if EMAIL_LOGO_SRC not in (html_content or "") or not EMAIL_LOGO_PATH.exists():
        return
    image = MIMEImage(EMAIL_LOGO_PATH.read_bytes(), _subtype="png")
    image.add_header("Content-ID", f"<{EMAIL_LOGO_CID}>")
    image.add_header("Content-Disposition", "inline", filename=EMAIL_LOGO_FILENAME)
    message.attach(image)


def warsaw_datetime_text() -> str:
    try:
        now = datetime.now(ZoneInfo("Europe/Warsaw"))
    except ZoneInfoNotFoundError:
        now = datetime.now().astimezone()
    timezone_name = now.tzname() or "Europe/Warsaw"
    return f"{now:%Y-%m-%d %H:%M:%S} {timezone_name}"


def classify_smtp_failure(error_text: str) -> str:
    if looks_like_rate_limited(error_text):
        return "rate_limited"
    if looks_like_temporary_smtp_failure(error_text):
        return "delivery_pending"
    return "smtp_failed"


def sanitize_log_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    for env_name in ("SMTP_PASSWORD", "IMAP_PASSWORD", "UNSUBSCRIBE_SECRET"):
        secret = os.getenv(env_name, "")
        if secret and len(secret) >= 4:
            text = text.replace(secret, "[redacted]")
    return text


def decode_smtp_response(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip()
    return str(value).strip()


def smtp_exception_text(exc: Exception) -> str:
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return sanitize_log_text('; '.join(f'{code} {decode_smtp_response(reply)}'
            for code,reply in exc.recipients.values())) or ''
    smtp_code = getattr(exc, "smtp_code", None)
    smtp_error = getattr(exc, "smtp_error", None)
    response = decode_smtp_response(smtp_error)
    if smtp_code and response:
        return sanitize_log_text(f"{smtp_code} {response}") or ""
    if smtp_code:
        return sanitize_log_text(str(smtp_code)) or ""
    return sanitize_log_text(str(exc)) or ""


def extract_smtp_code(text: str | None) -> str | None:
    if not text:
        return None
    match = re.search(r"\b([245][0-9]{2}|[245]\.[0-9]\.[0-9])\b", text)
    return match.group(1) if match else None


def extract_provider_message_id(response_text: str) -> str | None:
    match = re.search(
        r"\b(?:message[-_ ]?id|internalid)\s*[=:]\s*<?([A-Z0-9._%+\-@]+)>?",
        response_text,
        re.IGNORECASE,
    )
    return match.group(1) if match else None


def looks_like_rate_limited(error_text: str) -> bool:
    return bool(
        re.search(
            r"(4\.7|4\.3|throttl|rate|limit|too many)",
            error_text or "",
            re.IGNORECASE,
        )
    )


def looks_like_temporary_smtp_failure(error_text: str) -> bool:
    return bool(
        re.search(
            r"(\b4[0-9]{2}\b|\b4\.[0-9]\.[0-9]\b|temporar|try again|defer)",
            error_text or "",
            re.IGNORECASE,
        )
    )


def looks_like_permanent_recipient_failure(error_text: str) -> bool:
    return bool(
        re.search(
            r"\b(550|551|553|5\.1\.1)\b|user unknown|mailbox unavailable|invalid recipient",
            error_text or "",
            re.IGNORECASE,
        )
    )


def looks_like_bounce(error_text: str) -> bool:
    return bool(
        re.search(
            r"\b(550|551)\b|mailbox unavailable|user unknown",
            error_text or "",
            re.IGNORECASE,
        )
    )


def looks_like_invalid_address(error_text: str) -> bool:
    return bool(
        re.search(
            r"\b(553|5\.1\.1)\b|user unknown|invalid recipient",
            error_text or "",
            re.IGNORECASE,
        )
    )


def maybe_send_unsubscribe_notification(
    conn: sqlite3.Connection,
    event_id: int,
    email: str,
    campaign_id: int | None,
) -> bool:
    settings = get_mail_settings()
    if not settings.admin_notification_email or not smtp_is_configured(settings):
        return False

    # Durable notification; only the singleton worker may use this SMTP account.
    conn.execute("UPDATE unsubscribe_events SET notification_status='queued' WHERE id=? AND notification_sent=0 AND notification_status='pending'", (event_id,))
    conn.commit()
    from .worker import manager
    manager.wake.set()
    return False  # queued, not yet accepted by SMTP
