from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr
import io
import os
from pathlib import Path
import re
from urllib.parse import urlencode
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import BackgroundTasks, FastAPI, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .db import BASE_DIR, UPLOADS_DIR, get_connection, init_db, utc_now
from .email_renderer import (
    EMAIL_LOGO_SRC,
    LEGACY_UNSUBSCRIBE_PLACEHOLDER,
    UNSUBSCRIBE_PLACEHOLDER,
    render_campaign_single,
)
from .importer import import_from_paste, import_from_xlsx
from .mailer import (
    ONE_COM_ENVELOPE_FROM,
    ONE_COM_FROM_EMAIL,
    ONE_COM_REPLY_TO,
    ONE_COM_SMTP_USER,
    finalize_campaign_status,
    get_mail_settings,
    maybe_send_unsubscribe_notification,
    prepare_campaign_send,
    public_unsubscribe_url_warning,
    send_pending_campaign,
    smtp_configuration_warnings,
    smtp_identity_diagnostics,
    smtp_mode_label,
    smtp_provider_label,
    smtp_send_configuration_error,
)
from .models import VALID_CONTACT_STATUSES, VALID_COUNTRY_GROUPS, VALID_LANGUAGES, normalize_email


app = FastAPI(title="BHM Chemicals Mailing Tool")
app.mount("/static", StaticFiles(directory=BASE_DIR / "app" / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")


def format_datetime_short(value: object) -> str:
    if not value:
        return "—"
    text = str(value).replace("T", " ")
    text = text.split("+", 1)[0].split(".", 1)[0]
    return text[:16]


def format_dt_warsaw(value: object) -> str:
    if not value:
        return "—"
    text = str(value).strip()
    if not text:
        return "—"
    parsed: datetime | None = None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        for date_format in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                parsed = datetime.strptime(text.replace("T", " ")[:19], date_format)
                break
            except ValueError:
                continue
    if parsed is None:
        return text[:16]
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    try:
        parsed = parsed.astimezone(ZoneInfo("Europe/Warsaw"))
    except ZoneInfoNotFoundError:
        parsed = parsed.astimezone()
    return parsed.strftime("%Y-%m-%d %H:%M")


def format_datetime_short(value: object) -> str:
    return format_dt_warsaw(value)


def display_send_status(status: object) -> str:
    value = str(status or "")
    if value == "accepted_by_smtp":
        return "Accepted by SMTP - provider accepted the message, not final delivery."
    if value == "delivered_by_trace":
        return "Delivered by Trace - trace confirms delivery."
    if value == "failed_by_trace":
        return "Failed by Trace - trace confirms failure."
    if value == "sent":
        return "Accepted by SMTP - legacy SMTP acceptance, not final delivery."
    if value == "failed":
        return "smtp_failed (legacy)"
    return value or "—"


def redact_sensitive(value: object) -> str:
    text = str(value or "")
    for env_name in ("SMTP_PASSWORD", "UNSUBSCRIBE_SECRET"):
        secret = os.getenv(env_name, "")
        if secret and len(secret) >= 4:
            text = text.replace(secret, "[redacted]")
    return text


def truncate_text(value: object, limit: int = 140) -> str:
    text = re.sub(r"\s+", " ", redact_sensitive(value)).strip()
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1]}…"


def unsubscribe_preview(value: object) -> str:
    return (
        str(value or "")
        .replace(LEGACY_UNSUBSCRIBE_PLACEHOLDER, UNSUBSCRIBE_PLACEHOLDER)
        .replace(EMAIL_LOGO_SRC, "/static/assets/bhm-chemicals-logo.png")
    )


def current_smtp_diagnostics(to_email: str = "test@example.com") -> dict[str, object]:
    settings = get_mail_settings()
    return {
        "provider": smtp_provider_label(settings),
        "mode": smtp_mode_label(settings),
        "warnings": smtp_configuration_warnings(settings),
        **smtp_identity_diagnostics(settings, to_email),
    }


def send_row_value(send: object, key: str) -> str:
    if send is None or key not in send.keys():
        return ""
    value = send[key]
    return str(value) if value is not None else ""


def email_from_header(value: object) -> str:
    parsed = parseaddr(str(value or ""))[1]
    return parsed.strip().lower()


def actual_send_smtp_identity(send: object | None) -> dict[str, object] | None:
    if send is None:
        return None

    header_from = send_row_value(send, "header_from")
    message_id = send_row_value(send, "message_id") or send_row_value(send, "smtp_message_id")
    identity = {
        "send_id": send_row_value(send, "id"),
        "smtp_user": send_row_value(send, "smtp_user"),
        "header_from": header_from,
        "reply_to": send_row_value(send, "reply_to"),
        "envelope_from": send_row_value(send, "envelope_from"),
        "envelope_to": send_row_value(send, "envelope_to"),
        "message_id": message_id,
    }
    is_one_com = (
        str(identity["smtp_user"]).strip().lower() == ONE_COM_SMTP_USER
        and email_from_header(header_from) == ONE_COM_FROM_EMAIL
        and str(identity["reply_to"]).strip().lower() == ONE_COM_REPLY_TO
        and str(identity["envelope_from"]).strip().lower() == ONE_COM_ENVELOPE_FROM
    )
    identity["provider"] = "one.com" if is_one_com else "previous SMTP settings"
    identity["previous_settings"] = not is_one_com
    return identity


templates.env.filters["datetime_short"] = format_datetime_short
templates.env.filters["unsubscribe_preview"] = unsubscribe_preview
templates.env.filters["send_status_label"] = display_send_status
templates.env.filters["short_text"] = truncate_text


@app.on_event("startup")
def on_startup() -> None:
    init_db()


def render_template(
    request: Request,
    name: str,
    context: dict | None = None,
    status_code: int = 200,
):
    template_context = dict(context or {})
    template_context.setdefault("request", request)
    return templates.TemplateResponse(
        request=request,
        name=name,
        context=template_context,
        status_code=status_code,
    )


def redirect_to(path: str, **params: object) -> RedirectResponse:
    query = urlencode({key: value for key, value in params.items() if value is not None})
    url = f"{path}?{query}" if query else path
    return RedirectResponse(url=url, status_code=303)


def fetch_one_dict(query: str, params: tuple = ()) -> dict:
    with get_connection() as conn:
        row = conn.execute(query, params).fetchone()
    return dict(row) if row else {}


def chunk_ids(ids: list[int], size: int = 500) -> list[list[int]]:
    return [ids[index : index + size] for index in range(0, len(ids), size)]


def fetch_active_contact_ids(contact_ids: list[int]) -> list[int]:
    unique_ids = list(dict.fromkeys(contact_ids))
    if not unique_ids:
        return []
    active_ids: set[int] = set()
    with get_connection() as conn:
        for batch in chunk_ids(unique_ids):
            placeholders = ",".join("?" for _ in batch)
            rows = conn.execute(
                f"SELECT id FROM contacts WHERE status = 'active' AND id IN ({placeholders})",
                tuple(batch),
            ).fetchall()
            active_ids.update(int(row["id"]) for row in rows)
    return [contact_id for contact_id in unique_ids if contact_id in active_ids]


def parse_datetime_utc(value: object) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        parsed = None
        formats = (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%m/%d/%Y %I:%M:%S %p",
            "%m/%d/%Y %I:%M %p",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
        )
        for date_format in formats:
            try:
                parsed = datetime.strptime(text[:22].strip(), date_format)
                break
            except ValueError:
                continue
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalized_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def normalized_subject(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def row_get(row: dict[str, str], candidates: tuple[str, ...]) -> str:
    normalized = {normalized_header(key): value for key, value in row.items()}
    for candidate in candidates:
        value = normalized.get(normalized_header(candidate))
        if value is not None:
            return str(value).strip()
    return ""


def normalized_email_address(value: object) -> str | None:
    parsed = parseaddr(str(value or ""))[1]
    return normalize_email(parsed) or normalize_email(value)


def trace_sender_candidates(send: dict, settings: object) -> set[str]:
    raw_candidates = (
        getattr(settings, "smtp_from_email", ""),
        getattr(settings, "smtp_user", ""),
        getattr(settings, "smtp_envelope_from", ""),
        send.get("smtp_user"),
        send.get("envelope_from"),
        send.get("header_from"),
    )
    return {
        email
        for email in (normalized_email_address(candidate) for candidate in raw_candidates)
        if email
    }


def campaign_status_payload(campaign_id: int) -> dict | None:
    with get_connection() as conn:
        campaign = conn.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
        if not campaign:
            return None
        counts = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                COALESCE(SUM(status = 'pending'), 0) AS pending,
                COALESCE(SUM(status = 'sending'), 0) AS sending,
                COALESCE(SUM(status IN ('accepted_by_smtp', 'sent')), 0) AS accepted_by_smtp,
                COALESCE(SUM(status IN ('smtp_failed', 'failed')), 0) AS smtp_failed,
                COALESCE(SUM(status = 'rate_limited'), 0) AS rate_limited,
                COALESCE(SUM(status = 'delivery_pending'), 0) AS delivery_pending,
                COALESCE(SUM(status = 'delivered_by_trace'), 0) AS delivered_by_trace,
                COALESCE(SUM(status = 'failed_by_trace'), 0) AS failed_by_trace,
                COALESCE(SUM(status = 'quarantined_by_trace'), 0) AS quarantined_by_trace,
                COALESCE(SUM(status IN ('bounced_later', 'bounced', 'invalid')), 0) AS bounced_later,
                COALESCE(SUM(status LIKE 'skipped_%'), 0) AS skipped,
                COALESCE(SUM(status = 'dry_run'), 0) AS dry_run,
                MIN(started_at) AS started_at,
                MAX(COALESCE(final_status_at, accepted_at, started_at, sent_at, created_at)) AS updated_at
            FROM email_sends
            WHERE campaign_id = ?
            """,
            (campaign_id,),
        ).fetchone()
        current = conn.execute(
            """
            SELECT id, email, status,
                   COALESCE(final_status_at, accepted_at, started_at, sent_at, created_at) AS timestamp,
                   COALESCE(last_error, error_message, '') AS error
            FROM email_sends
            WHERE campaign_id = ?
            ORDER BY status = 'sending' DESC, id DESC
            LIMIT 1
            """,
            (campaign_id,),
        ).fetchone()
        events = conn.execute(
            """
            SELECT id, email, status,
                   COALESCE(final_status_at, accepted_at, started_at, sent_at, created_at) AS timestamp,
                   COALESCE(last_error, error_message, '') AS error
            FROM email_sends
            WHERE campaign_id = ?
            ORDER BY id DESC
            LIMIT 20
            """,
            (campaign_id,),
        ).fetchall()

    data = dict(counts) if counts else {}
    total = int(data.get("total") or 0)
    pending = int(data.get("pending") or 0)
    sending = int(data.get("sending") or 0)
    processed = max(total - pending - sending, 0)
    percent = round((processed / total) * 100, 1) if total else 0
    last_error = ""
    event_payload = []
    for event in events:
        error = truncate_text(event["error"], 160)
        if error and not last_error:
            last_error = error
        event_payload.append(
            {
                "id": event["id"],
                "email": event["email"],
                "status": event["status"],
                "status_label": display_send_status(event["status"]),
                "timestamp": format_dt_warsaw(event["timestamp"]),
                "error": error,
            }
        )
    return {
        "campaign_id": campaign_id,
        "campaign_status": campaign["status"],
        "total": total,
        "processed": processed,
        "percent": percent,
        "pending": pending,
        "sending": sending,
        "accepted_by_smtp": int(data.get("accepted_by_smtp") or 0),
        "smtp_failed": int(data.get("smtp_failed") or 0),
        "rate_limited": int(data.get("rate_limited") or 0),
        "delivery_pending": int(data.get("delivery_pending") or 0),
        "delivered_by_trace": int(data.get("delivered_by_trace") or 0),
        "failed_by_trace": int(data.get("failed_by_trace") or 0),
        "quarantined_by_trace": int(data.get("quarantined_by_trace") or 0),
        "bounced_later": int(data.get("bounced_later") or 0),
        "skipped": int(data.get("skipped") or 0),
        "dry_run": int(data.get("dry_run") or 0),
        "current_email": current["email"] if current else "",
        "current_status": display_send_status(current["status"]) if current else "",
        "started_at": format_dt_warsaw(data.get("started_at")),
        "updated_at": format_dt_warsaw(data.get("updated_at")),
        "completed_at": format_dt_warsaw(campaign["completed_at"]),
        "last_error": last_error,
        "last_20_events": event_payload,
    }


def trace_detail_from_row(row: dict[str, str]) -> str:
    allowed_fragments = []
    for key, value in row.items():
        text = str(value or "").strip()
        if not text:
            continue
        label = re.sub(r"\s+", " ", str(key or "")).strip()
        if normalized_header(label) in {"recipientaddress", "recipient", "to"}:
            continue
        allowed_fragments.append(f"{label}: {text}")
    return truncate_text("; ".join(allowed_fragments), 1000)


def trace_status_to_send_status(raw_status: str, current_status: str) -> tuple[str, bool, str]:
    status = raw_status.strip()
    lowered = status.lower()
    protected = current_status in {
        "smtp_failed",
        "failed",
        "skipped_unsubscribed",
        "skipped_invalid",
        "skipped_duplicate",
        "cancelled",
        "dry_run",
    }
    if protected:
        return current_status, lowered in {"delivered", "failed", "quarantined"}, status
    if lowered == "delivered":
        return "delivered_by_trace", True, status
    if lowered == "failed":
        return "failed_by_trace", True, status
    if lowered == "quarantined":
        return "quarantined_by_trace", True, status
    if lowered in {"pending", "expanded"}:
        return "delivery_pending", False, status
    if current_status in {"accepted_by_smtp", "sent"}:
        return current_status, False, status
    return "delivery_unknown", False, status


def best_trace_match(
    sends_by_email: dict[str, list[dict]],
    recipient: str,
    subject: str,
    trace_time: datetime | None,
    sender: str | None,
    settings: object,
) -> dict | None:
    candidates = sends_by_email.get(recipient, [])
    best_send = None
    best_score = float("inf")
    for send in candidates:
        if subject and normalized_subject(send["subject"]) != subject:
            continue
        if sender and sender not in trace_sender_candidates(send, settings):
            continue
        send_time = (
            parse_datetime_utc(send.get("accepted_at"))
            or parse_datetime_utc(send.get("started_at"))
            or parse_datetime_utc(send.get("sent_at"))
            or parse_datetime_utc(send.get("created_at"))
        )
        if trace_time and send_time:
            delta = abs((send_time - trace_time).total_seconds())
            if delta > timedelta(hours=24).total_seconds():
                continue
        else:
            delta = 0
        if delta < best_score:
            best_score = delta
            best_send = send
    return best_send


def import_message_trace_csv(campaign_id: int, csv_text: str) -> dict[str, int]:
    report = {
        "matched": 0,
        "updated": 0,
        "not_matched": 0,
        "delivered": 0,
        "failed": 0,
        "quarantined": 0,
        "pending": 0,
        "unknown": 0,
    }
    sample = csv_text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(csv_text), dialect=dialect)
    settings = get_mail_settings()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM email_sends
            WHERE campaign_id = ?
            ORDER BY id ASC
            """,
            (campaign_id,),
        ).fetchall()
        sends_by_email: dict[str, list[dict]] = {}
        for row in rows:
            send = dict(row)
            email = normalize_email(send["email"])
            if email:
                sends_by_email.setdefault(email, []).append(send)

        for trace_row in reader:
            recipient = normalize_email(
                row_get(
                    trace_row,
                    (
                        "recipient address",
                        "recipient",
                        "recipient email",
                        "recipient email address",
                        "to",
                        "email",
                    ),
                )
            )
            raw_sender = row_get(trace_row, ("sender address", "sender", "from", "sender email"))
            sender = normalized_email_address(raw_sender)
            if not recipient:
                report["not_matched"] += 1
                continue
            subject = normalized_subject(
                row_get(trace_row, ("subject", "message subject", "original subject"))
            )
            trace_time = parse_datetime_utc(
                row_get(
                    trace_row,
                    (
                        "date",
                        "date/time",
                        "received",
                        "received time",
                        "origin timestamp",
                        "timestamp",
                    ),
                )
            )
            match = best_trace_match(sends_by_email, recipient, subject, trace_time, sender, settings)
            if not match:
                report["not_matched"] += 1
                continue

            raw_status = row_get(trace_row, ("status", "delivery status", "event", "action"))
            if not raw_status:
                raw_status = "unknown"
            lowered = raw_status.strip().lower()
            if lowered == "delivered":
                report["delivered"] += 1
            elif lowered == "failed":
                report["failed"] += 1
            elif lowered == "quarantined":
                report["quarantined"] += 1
            elif lowered in {"pending", "expanded"}:
                report["pending"] += 1
            else:
                report["unknown"] += 1

            report["matched"] += 1
            new_status, is_final, trace_status = trace_status_to_send_status(raw_status, match["status"])
            now = utc_now()
            final_status_at = now if is_final else match.get("final_status_at")
            conn.execute(
                """
                UPDATE email_sends
                SET status = ?,
                    trace_status = ?,
                    trace_detail = ?,
                    trace_source = 'message_trace_csv',
                    last_checked_at = ?,
                    final_status_at = ?
                WHERE id = ?
                """,
                (
                    new_status,
                    trace_status,
                    trace_detail_from_row(trace_row),
                    now,
                    final_status_at,
                    match["id"],
                ),
            )
            report["updated"] += 1

        finalize_campaign_status(conn, campaign_id)
        conn.commit()
    return report


@app.get("/")
def dashboard(request: Request):
    with get_connection() as conn:
        stats = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                COALESCE(SUM(status = 'active'), 0) AS active,
                COALESCE(SUM(country_group = 'PL'), 0) AS pl_count,
                COALESCE(SUM(country_group = 'INTERNATIONAL'), 0) AS international_count,
                COALESCE(SUM(status = 'unsubscribed'), 0) AS unsubscribed,
                COALESCE(SUM(status IN ('bounced', 'invalid')), 0) AS bounced_invalid
            FROM contacts
            """
        ).fetchone()
        campaigns = conn.execute(
            """
            SELECT c.*,
                   COUNT(s.id) AS recipient_count,
                   COALESCE(SUM(s.status = 'pending'), 0) AS pending_count,
                   COALESCE(SUM(s.status = 'sending'), 0) AS sending_count,
                   COALESCE(SUM(s.status = 'dry_run'), 0) AS dry_run_count,
                   COALESCE(SUM(s.status IN ('accepted_by_smtp', 'sent')), 0) AS accepted_smtp_count,
                   COALESCE(SUM(s.status IN ('smtp_failed', 'failed')), 0) AS smtp_failed_count,
                   COALESCE(SUM(s.status = 'rate_limited'), 0) AS rate_limited_count,
                   COALESCE(SUM(s.status = 'delivery_pending'), 0) AS delivery_pending_count,
                   COALESCE(SUM(s.status = 'delivered_by_trace'), 0) AS delivered_trace_count,
                   COALESCE(SUM(s.status = 'failed_by_trace'), 0) AS failed_trace_count,
                   COALESCE(SUM(s.status = 'quarantined_by_trace'), 0) AS quarantined_count,
                   COALESCE(SUM(s.status IN ('bounced_later', 'bounced', 'invalid')), 0) AS bounced_later_count,
                   COALESCE(SUM(s.status LIKE 'skipped_%'), 0) AS skipped_count,
                   COALESCE(SUM(s.status IN ('accepted_by_smtp', 'sent')), 0) AS sent_count,
                   COALESCE(SUM(s.status IN ('smtp_failed', 'failed')), 0) AS failed_count,
                   COALESCE(SUM(s.status IN ('bounced_later', 'bounced', 'invalid')), 0) AS bounced_count,
                   0 AS invalid_count
            FROM campaigns c
            LEFT JOIN email_sends s ON s.campaign_id = c.id
            GROUP BY c.id
            ORDER BY c.created_at DESC
            LIMIT 8
            """
        ).fetchall()
    return render_template(request, "dashboard.html", {"stats": stats, "campaigns": campaigns})


@app.get("/contacts/import")
def contacts_import_form(request: Request):
    return render_template(request, "contacts_import.html", {"report": None})


@app.post("/contacts/import")
async def contacts_import(
    request: Request,
    paste_text: str = Form(""),
    country_group_mode: str = Form("AUTO"),
    xlsx_file: UploadFile | None = File(None),
):
    from .models import ImportReport

    report = ImportReport()
    error = None
    if paste_text.strip():
        report.merge(import_from_paste(paste_text, country_group_mode, "paste"))

    if xlsx_file and xlsx_file.filename:
        safe_name = Path(xlsx_file.filename).name
        target = UPLOADS_DIR / f"{utc_now().replace(':', '-')}_{safe_name}"
        target.write_bytes(await xlsx_file.read())
        try:
            report.merge(import_from_xlsx(target, country_group_mode, safe_name))
        except Exception as exc:  # noqa: BLE001 - surface import problems in the UI.
            error = str(exc)

    return render_template(request, "contacts_import.html", {"report": report, "error": error})


@app.get("/contacts")
def contacts_list(
    request: Request,
    country_group: str = "",
    language: str = "",
    status: str = "",
    industry: str = "",
    search: str = "",
):
    where: list[str] = []
    params: list[str] = []
    if country_group:
        where.append("country_group = ?")
        params.append(country_group)
    if language:
        where.append("language = ?")
        params.append(language)
    if status:
        where.append("status = ?")
        params.append(status)
    if industry:
        where.append("industry = ?")
        params.append(industry)
    if search:
        where.append("(email LIKE ? OR company_name LIKE ? OR contact_name LIKE ? OR notes LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like, like])
    where_sql = "WHERE " + " AND ".join(where) if where else ""

    with get_connection() as conn:
        contacts = conn.execute(
            f"""
            SELECT * FROM contacts
            {where_sql}
            ORDER BY created_at DESC, email ASC
            LIMIT 500
            """,
            tuple(params),
        ).fetchall()
        industries = conn.execute(
            "SELECT DISTINCT industry FROM contacts WHERE industry IS NOT NULL AND industry != '' ORDER BY industry"
        ).fetchall()

    return render_template(
        request,
        "contacts_list.html",
        {
            "contacts": contacts,
            "industries": industries,
            "filters": {
                "country_group": country_group,
                "language": language,
                "status": status,
                "industry": industry,
                "search": search,
            },
        },
    )


@app.get("/contacts/{contact_id}/edit")
def contact_edit_form(request: Request, contact_id: int):
    with get_connection() as conn:
        contact = conn.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,)).fetchone()
    if not contact:
        return redirect_to("/contacts", message="Nie znaleziono kontaktu.")
    return render_template(request, "contact_edit.html", {"contact": contact, "form": dict(contact)})


@app.post("/contacts/{contact_id}/edit")
async def contact_edit(request: Request, contact_id: int):
    form = await request.form()
    email = normalize_email(form.get("email"))
    country_group = str(form.get("country_group") or "").strip().upper()
    language = str(form.get("language") or "").strip().lower()
    status = str(form.get("status") or "").strip().lower()

    with get_connection() as conn:
        contact = conn.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,)).fetchone()
        if not contact:
            return redirect_to("/contacts", message="Nie znaleziono kontaktu.")

        error = None
        if not email:
            error = "Podaj poprawny adres email."
        elif country_group not in VALID_COUNTRY_GROUPS:
            error = "Nieprawidłowa grupa kraju."
        elif language not in VALID_LANGUAGES:
            error = "Nieprawidłowy język."
        elif status not in VALID_CONTACT_STATUSES:
            error = "Nieprawidłowy status."
        else:
            duplicate = conn.execute(
                "SELECT id FROM contacts WHERE email = ? AND id != ?",
                (email, contact_id),
            ).fetchone()
            if duplicate:
                error = "Ten email jest już przypisany do innego kontaktu."

        if error:
            return render_template(
                request,
                "contact_edit.html",
                {"contact": contact, "form": form, "error": error},
                status_code=400,
            )

        conn.execute(
            """
            UPDATE contacts
            SET email = ?,
                company_name = ?,
                contact_name = ?,
                industry = ?,
                country_group = ?,
                language = ?,
                status = ?,
                source = ?,
                notes = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                email,
                str(form.get("company_name") or "").strip() or None,
                str(form.get("contact_name") or "").strip() or None,
                str(form.get("industry") or "").strip() or None,
                country_group,
                language,
                status,
                str(form.get("source") or "").strip() or None,
                str(form.get("notes") or "").strip() or None,
                utc_now(),
                contact_id,
            ),
        )
        conn.commit()
    return redirect_to("/contacts", message="Kontakt zaktualizowany.")


@app.post("/contacts/bulk")
async def contacts_bulk_update(request: Request):
    form = await request.form()
    ids = [int(value) for value in form.getlist("contact_ids") if str(value).isdigit()]
    action = str(form.get("bulk_action") or "")
    if not ids:
        return redirect_to("/contacts", message="Nie zaznaczono kontaktów.")

    now = utc_now()
    placeholders = ",".join("?" for _ in ids)
    with get_connection() as conn:
        if action == "set_pl":
            conn.execute(
                f"UPDATE contacts SET country_group = 'PL', language = 'pl', updated_at = ? WHERE id IN ({placeholders})",
                (now, *ids),
            )
        elif action == "set_international":
            conn.execute(
                f"UPDATE contacts SET country_group = 'INTERNATIONAL', language = 'en', updated_at = ? WHERE id IN ({placeholders})",
                (now, *ids),
            )
        elif action in {"active", "unsubscribed", "invalid"}:
            conn.execute(
                f"UPDATE contacts SET status = ?, updated_at = ? WHERE id IN ({placeholders})",
                (action, now, *ids),
            )
        else:
            return redirect_to("/contacts", message="Nieznana akcja masowa.")
        conn.commit()
    return redirect_to("/contacts", message=f"Zaktualizowano {len(ids)} kontaktów.")


@app.get("/campaigns/new")
def campaign_new_form(request: Request):
    return render_template(request, "campaign_new.html")


@app.post("/campaigns/new")
async def campaign_create(request: Request):
    form = await request.form()
    name = str(form.get("name") or "").strip()
    language = str(form.get("language") or "").strip().lower()
    body = str(form.get("body") or "").strip()
    if not name:
        return render_template(
            request,
            "campaign_new.html",
            {"error": "Nazwa kampanii jest wymagana.", "form": form},
            status_code=400,
        )
    if language not in VALID_LANGUAGES:
        return render_template(
            request,
            "campaign_new.html",
            {"error": "Wybierz język kampanii.", "form": form},
            status_code=400,
        )
    if not body:
        return render_template(
            request,
            "campaign_new.html",
            {"error": "Treść wiadomości jest wymagana.", "form": form},
            status_code=400,
        )

    subject = name
    rendered = render_campaign_single(language, subject, body)
    now = utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO campaigns (
                name, language, subject, body, html, text, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'draft', ?)
            """,
            (
                name,
                language,
                subject,
                body,
                rendered["html"],
                rendered["text"],
                now,
            ),
        )
        campaign_id = cursor.lastrowid
        conn.commit()
    return redirect_to(f"/campaigns/{campaign_id}/preview", message="Draft kampanii zapisany.")


@app.get("/campaigns/{campaign_id}/preview")
def campaign_preview(request: Request, campaign_id: int):
    with get_connection() as conn:
        campaign = conn.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
    if not campaign:
        return redirect_to("/history", message="Nie znaleziono kampanii.")
    return render_template(request, "campaign_preview.html", {"campaign": campaign})


@app.post("/campaigns/{campaign_id}/approve")
def campaign_approve(campaign_id: int):
    with get_connection() as conn:
        conn.execute(
            "UPDATE campaigns SET status = 'approved', approved_at = ? WHERE id = ? AND status = 'draft'",
            (utc_now(), campaign_id),
        )
        conn.commit()
    return redirect_to(f"/campaigns/{campaign_id}/recipients", message="Kampania zatwierdzona.")


@app.get("/campaigns/{campaign_id}/recipients")
def campaign_recipients(
    request: Request,
    campaign_id: int,
    country_group: str = "",
    language: str = "",
    active_only: str = "1",
    search: str = "",
):
    with get_connection() as conn:
        campaign = conn.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
    if not campaign:
        return redirect_to("/history", message="Nie znaleziono kampanii.")

    if "language" not in request.query_params:
        language = campaign["language"] or ""

    where: list[str] = []
    params: list[str] = []
    if country_group:
        where.append("country_group = ?")
        params.append(country_group)
    if language:
        where.append("language = ?")
        params.append(language)
    if active_only == "1":
        where.append("status = 'active'")
    if search:
        where.append("(email LIKE ? OR company_name LIKE ? OR notes LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like])
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    with get_connection() as conn:
        contacts = conn.execute(
            f"SELECT * FROM contacts {where_sql} ORDER BY language, country_group, email",
            tuple(params),
        ).fetchall()
    return render_template(
        request,
        "campaign_recipients.html",
        {
            "campaign": campaign,
            "contacts": contacts,
            "filters": {
                "country_group": country_group,
                "language": language,
                "active_only": active_only,
                "search": search,
            },
        },
    )


@app.post("/campaigns/{campaign_id}/recipients")
async def campaign_send(request: Request, campaign_id: int, background_tasks: BackgroundTasks):
    form = await request.form()
    ids = [int(value) for value in form.getlist("contact_ids") if str(value).isdigit()]
    if not ids:
        return redirect_to(f"/campaigns/{campaign_id}/recipients", message="Nie zaznaczono odbiorców.")

    with get_connection() as conn:
        campaign = conn.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
    if not campaign:
        return redirect_to("/history", message="Nie znaleziono kampanii.")
    if campaign["status"] == "sending":
        return redirect_to(f"/history/{campaign_id}", message="Kampania jest już w trakcie wysyłki.")
    if campaign["status"] != "approved":
        return redirect_to(
            f"/campaigns/{campaign_id}/recipients",
            message="Kampania musi mieć status approved przed wysyłką.",
        )

    active_ids = fetch_active_contact_ids(ids)
    if not active_ids:
        return redirect_to(
            f"/campaigns/{campaign_id}/recipients",
            message="Nie wybrano aktywnych odbiorców.",
        )

    settings = get_mail_settings()
    configuration_error = smtp_send_configuration_error(settings)
    if configuration_error:
        return redirect_to(f"/campaigns/{campaign_id}/recipients", message=configuration_error)

    warning = public_unsubscribe_url_warning(settings)
    if warning and len(active_ids) > 1:
        return redirect_to(f"/campaigns/{campaign_id}/recipients", message=warning)
    if warning and request.query_params.get("local_unsubscribe_warning_ack") != "1":
        return redirect_to(
            f"/campaigns/{campaign_id}/recipients",
            message=warning,
            local_unsubscribe_warning_ack="1",
        )

    large_campaign_warning = len(active_ids) > 100
    large_campaign_ack_required = len(active_ids) > 500
    missing_large_ack = (
        str(form.get("confirmed") or "") == "1"
        and large_campaign_ack_required
        and str(form.get("large_delivery_ack") or "") != "1"
    )

    if str(form.get("confirmed") or "") != "1" or missing_large_ack:
        language = campaign["language"] or ""
        with get_connection() as conn:
            contacts = conn.execute(
                """
                SELECT * FROM contacts
                WHERE status = 'active' AND (? = '' OR language = ?)
                ORDER BY language, country_group, email
                """,
                (language, language),
            ).fetchall()
        return render_template(
            request,
            "campaign_recipients.html",
            {
                "campaign": campaign,
                "contacts": contacts,
                "filters": {
                    "country_group": "",
                    "language": language,
                    "active_only": "1",
                    "search": "",
                },
                "confirm_count": len(active_ids),
                "confirm_contact_ids": active_ids,
                "large_campaign_warning": large_campaign_warning,
                "large_campaign_ack_required": large_campaign_ack_required,
                "confirm_error": (
                    "Confirm that accepted_by_smtp is not final delivery before sending this large campaign."
                    if missing_large_ack
                    else None
                ),
            },
        )

    with get_connection() as conn:
        current = conn.execute("SELECT status FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
    if current and current["status"] == "sending":
        return redirect_to(f"/history/{campaign_id}", message="Kampania jest już w trakcie wysyłki.")

    result = prepare_campaign_send(campaign_id, active_ids)
    if not result["started"]:
        return redirect_to(f"/history/{campaign_id}", message=result["message"])
    background_tasks.add_task(send_pending_campaign, campaign_id, result["send_ids"])
    message = f"Wysyłka rozpoczęta w tle. Odbiorcy: {result['recipient_count']}."
    return redirect_to(f"/history/{campaign_id}", message=message)


@app.get("/campaigns/{campaign_id}/status.json")
def campaign_status_json(campaign_id: int):
    payload = campaign_status_payload(campaign_id)
    if payload is None:
        return JSONResponse({"error": "Campaign not found."}, status_code=404)
    return payload


@app.get("/campaigns/{campaign_id}/export.csv")
def campaign_export_csv(campaign_id: int):
    with get_connection() as conn:
        campaign = conn.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
        if not campaign:
            return redirect_to("/history", message="Nie znaleziono kampanii.")
        rows = conn.execute(
            """
            SELECT s.*, c.company_name
            FROM email_sends s
            LEFT JOIN contacts c ON c.id = s.contact_id
            WHERE s.campaign_id = ?
            ORDER BY s.id ASC
            """,
            (campaign_id,),
        ).fetchall()

    output = io.StringIO()
    fieldnames = [
        "campaign_id",
        "email",
        "company_name",
        "language",
        "subject",
        "status",
        "smtp_code",
        "smtp_response",
        "last_error",
        "smtp_user",
        "header_from",
        "reply_to",
        "envelope_from",
        "envelope_to",
        "message_id",
        "started_at Europe/Warsaw",
        "accepted_at Europe/Warsaw",
        "final_status_at Europe/Warsaw",
        "trace_status",
        "trace_detail",
        "source",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "campaign_id": campaign_id,
                "email": row["email"],
                "company_name": row["company_name"] or "",
                "language": row["language"],
                "subject": row["subject"],
                "status": display_send_status(row["status"]),
                "smtp_code": row["smtp_code"] or "",
                "smtp_response": redact_sensitive(row["smtp_response"]),
                "last_error": redact_sensitive(row["last_error"] or row["error_message"]),
                "smtp_user": row["smtp_user"] or "",
                "header_from": row["header_from"] or "",
                "reply_to": row["reply_to"] or "",
                "envelope_from": row["envelope_from"] or "",
                "envelope_to": row["envelope_to"] or "",
                "message_id": row["message_id"] or "",
                "started_at Europe/Warsaw": format_dt_warsaw(row["started_at"]),
                "accepted_at Europe/Warsaw": format_dt_warsaw(row["accepted_at"]),
                "final_status_at Europe/Warsaw": format_dt_warsaw(row["final_status_at"]),
                "trace_status": row["trace_status"] or "",
                "trace_detail": redact_sensitive(row["trace_detail"]),
                "source": row["trace_source"] or "",
            }
        )
    filename = f"campaign-{campaign_id}-status.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/campaigns/{campaign_id}/message-trace/import")
async def campaign_import_message_trace(campaign_id: int, trace_csv: UploadFile = File(...)):
    raw = await trace_csv.read()
    try:
        csv_text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        csv_text = raw.decode("cp1250", errors="replace")
    report = import_message_trace_csv(campaign_id, csv_text)
    message = (
        "Message Trace CSV imported: "
        f"matched={report['matched']}, updated={report['updated']}, "
        f"not_matched={report['not_matched']}, delivered={report['delivered']}, "
        f"failed={report['failed']}, quarantined={report['quarantined']}, "
        f"pending={report['pending']}, unknown={report['unknown']}."
    )
    return redirect_to(f"/history/{campaign_id}", message=message)


@app.get("/history")
def history(request: Request):
    with get_connection() as conn:
        campaigns = conn.execute(
            """
            SELECT c.*,
                   COUNT(s.id) AS recipient_count,
                   COALESCE(SUM(s.status = 'pending'), 0) AS pending_count,
                   COALESCE(SUM(s.status = 'sending'), 0) AS sending_count,
                   COALESCE(SUM(s.status = 'dry_run'), 0) AS dry_run_count,
                   COALESCE(SUM(s.status IN ('accepted_by_smtp', 'sent')), 0) AS accepted_smtp_count,
                   COALESCE(SUM(s.status IN ('smtp_failed', 'failed')), 0) AS smtp_failed_count,
                   COALESCE(SUM(s.status = 'rate_limited'), 0) AS rate_limited_count,
                   COALESCE(SUM(s.status = 'delivery_pending'), 0) AS delivery_pending_count,
                   COALESCE(SUM(s.status = 'delivered_by_trace'), 0) AS delivered_trace_count,
                   COALESCE(SUM(s.status = 'failed_by_trace'), 0) AS failed_trace_count,
                   COALESCE(SUM(s.status = 'quarantined_by_trace'), 0) AS quarantined_count,
                   COALESCE(SUM(s.status IN ('bounced_later', 'bounced', 'invalid')), 0) AS bounced_later_count,
                   COALESCE(SUM(s.status LIKE 'skipped_%'), 0) AS skipped_count,
                   COALESCE(SUM(s.status IN ('accepted_by_smtp', 'sent')), 0) AS sent_count,
                   COALESCE(SUM(s.status IN ('smtp_failed', 'failed')), 0) AS failed_count,
                   COALESCE(SUM(s.status IN ('bounced_later', 'bounced', 'invalid')), 0) AS bounced_count,
                   0 AS invalid_count
            FROM campaigns c
            LEFT JOIN email_sends s ON s.campaign_id = c.id
            GROUP BY c.id
            ORDER BY c.created_at DESC
            """
        ).fetchall()
    return render_template(
        request,
        "history.html",
        {
            "campaigns": campaigns,
            "campaign": None,
            "sends": [],
            "current_smtp_config": current_smtp_diagnostics(),
            "actual_smtp_identity": None,
        },
    )


@app.get("/history/{campaign_id}")
def history_detail(request: Request, campaign_id: int, send_id: int | None = None):
    with get_connection() as conn:
        campaign = conn.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
        sends = conn.execute(
            """
            SELECT s.*, c.company_name, c.status AS contact_status
            FROM email_sends s
            LEFT JOIN contacts c ON c.id = s.contact_id
            WHERE s.campaign_id = ?
            ORDER BY s.id ASC
            """,
            (campaign_id,),
        ).fetchall()
        campaigns = conn.execute(
            """
            SELECT c.*,
                   COUNT(s.id) AS recipient_count,
                   COALESCE(SUM(s.status = 'pending'), 0) AS pending_count,
                   COALESCE(SUM(s.status = 'sending'), 0) AS sending_count,
                   COALESCE(SUM(s.status = 'dry_run'), 0) AS dry_run_count,
                   COALESCE(SUM(s.status IN ('accepted_by_smtp', 'sent')), 0) AS accepted_smtp_count,
                   COALESCE(SUM(s.status IN ('smtp_failed', 'failed')), 0) AS smtp_failed_count,
                   COALESCE(SUM(s.status = 'rate_limited'), 0) AS rate_limited_count,
                   COALESCE(SUM(s.status = 'delivery_pending'), 0) AS delivery_pending_count,
                   COALESCE(SUM(s.status = 'delivered_by_trace'), 0) AS delivered_trace_count,
                   COALESCE(SUM(s.status = 'failed_by_trace'), 0) AS failed_trace_count,
                   COALESCE(SUM(s.status = 'quarantined_by_trace'), 0) AS quarantined_count,
                   COALESCE(SUM(s.status IN ('bounced_later', 'bounced', 'invalid')), 0) AS bounced_later_count,
                   COALESCE(SUM(s.status LIKE 'skipped_%'), 0) AS skipped_count,
                   COALESCE(SUM(s.status IN ('accepted_by_smtp', 'sent')), 0) AS sent_count,
                   COALESCE(SUM(s.status IN ('smtp_failed', 'failed')), 0) AS failed_count,
                   COALESCE(SUM(s.status IN ('bounced_later', 'bounced', 'invalid')), 0) AS bounced_count,
                   0 AS invalid_count
            FROM campaigns c
            LEFT JOIN email_sends s ON s.campaign_id = c.id
            GROUP BY c.id
            ORDER BY c.created_at DESC
            """
        ).fetchall()
    if not campaign:
        return redirect_to("/history", message="Nie znaleziono kampanii.")
    selected_send = None
    if sends:
        selected_send = sends[0]
        if send_id is not None:
            for send in sends:
                if int(send["id"]) == send_id:
                    selected_send = send
                    break
    status_data = campaign_status_payload(campaign_id)
    diagnostic_recipient = selected_send["email"] if selected_send else "test@example.com"
    return render_template(
        request,
        "history.html",
        {
            "campaigns": campaigns,
            "campaign": campaign,
            "sends": sends,
            "selected_send": selected_send,
            "status_data": status_data,
            "current_smtp_config": current_smtp_diagnostics(diagnostic_recipient),
            "actual_smtp_identity": actual_send_smtp_identity(selected_send),
        },
    )


@app.get("/unsubscribe/{token}")
def unsubscribe(request: Request, token: str):
    campaign_id_raw = request.query_params.get("c")
    campaign_id = int(campaign_id_raw) if campaign_id_raw and campaign_id_raw.isdigit() else None
    with get_connection() as conn:
        contact = conn.execute("SELECT * FROM contacts WHERE unsubscribe_token = ?", (token,)).fetchone()
        if not contact:
            return render_template(
                request,
                "unsubscribe_confirmed.html",
                {
                    "message": "Unsubscribe link not found.",
                    "secondary_message": "Link wypisu nie został znaleziony.",
                    "is_error": True,
                },
                status_code=404,
            )
        now = utc_now()
        conn.execute(
            "UPDATE contacts SET status = 'unsubscribed', updated_at = ? WHERE id = ?",
            (now, contact["id"]),
        )
        cursor = conn.execute(
            """
            INSERT INTO unsubscribe_events (
                contact_id, email, token, source_campaign_id, created_at, notification_sent
            ) VALUES (?, ?, ?, ?, ?, 0)
            """,
            (contact["id"], contact["email"], token, campaign_id, now),
        )
        event_id = cursor.lastrowid
        conn.commit()
        maybe_send_unsubscribe_notification(conn, event_id, contact["email"], campaign_id)

    message_pl = "Zostałeś wypisany z listy mailingowej BHM Chemicals."
    message_en = "You have been unsubscribed from the BHM Chemicals mailing list."
    context = (
        {"message": message_pl, "secondary_message": message_en}
        if contact["language"] == "pl"
        else {"message": message_en, "secondary_message": message_pl}
    )
    return render_template(request, "unsubscribe_confirmed.html", context)
