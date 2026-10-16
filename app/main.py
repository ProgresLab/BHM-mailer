from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr
import io
import os
from pathlib import Path
import re
from urllib.parse import urlencode, urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import BackgroundTasks, FastAPI, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse, FileResponse
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware
from . import worker, imap_sync
from .assets import MAX_UPLOAD, store_banner, asset_path, banner_cid
from .rich_text import sanitize_html, html_to_text, legacy_to_html, safe_url
from .selection import PAGE_SIZE, selected_ids, selection_fingerprint, update_selection
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
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1','localhost','[::1]','testserver'])
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
    value = re.sub(r"cid:bhm-banner-([a-f0-9]{64}\.(?:jpg|png))", r"/campaign-assets/\1", str(value or ""))
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
templates.env.filters['epoch_utc'] = lambda value: datetime.fromtimestamp(float(value),timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC') if value else '—'


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    worker.manager.start()
    imap_sync.manager.start()


@app.on_event("shutdown")
def on_shutdown():
    imap_sync.manager.shutdown()
    worker.manager.shutdown()


@app.middleware("http")
async def local_state_guard(request, call_next):
    if request.method == 'POST':
        origin = request.headers.get('origin')
        if request.headers.get('sec-fetch-site') == 'cross-site' or (origin and urlsplit(origin).netloc != request.headers.get('host')):
            return JSONResponse({'error': 'Odrzucono żądanie z innej witryny.'}, status_code=403)
    return await call_next(request)


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
            LIMIT 8
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
        "pending",
        "sending",
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
        if send['status'] in {'pending','sending','dry_run','cancelled'}:
            continue
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
            if is_final and match['status'] not in {'pending','sending','dry_run'}:
                conn.execute('UPDATE email_sends SET outcome_uncertain=0 WHERE id=?', (match['id'],))
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


@app.get('/mail-sync/status.json')
def mail_sync_status():
    return JSONResponse(imap_sync.payload(),headers={'Cache-Control':'no-store'})


@app.post('/mail-sync/check')
def mail_sync_check():
    try:
        started=imap_sync.request_scan()
        return JSONResponse(dict(queued=started),status_code=202 if started else 409)
    except ValueError as exc:
        return JSONResponse(dict(error=str(exc)),status_code=400)


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


@app.get('/contacts/{contact_id}/history')
def contact_history(request: Request,contact_id: int,page: int=1):
    page=max(1,page)
    with get_connection() as conn:
        contact=conn.execute('SELECT * FROM contacts WHERE id=?',(contact_id,)).fetchone()
        if not contact:
            return redirect_to('/contacts',message='Nie znaleziono kontaktu.')
        total=conn.execute('SELECT COUNT(*) FROM email_sends WHERE contact_id=?',(contact_id,)).fetchone()[0]
        sends=conn.execute("""SELECT s.*,c.name AS campaign_name FROM email_sends s JOIN campaigns c ON c.id=s.campaign_id
            WHERE s.contact_id=? ORDER BY s.id DESC LIMIT 100 OFFSET ?""",(contact_id,(page-1)*100)).fetchall()
    return render_template(request,'contact_history.html',dict(contact=contact,sends=sends,page=page,total=total))


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
    return render_template(request, "campaign_new.html", {"form": {}})


@app.get("/campaigns/{campaign_id}/edit")
def campaign_edit_form(request: Request, campaign_id: int):
    campaign = fetch_one_dict('SELECT * FROM campaigns WHERE id=?', (campaign_id,))
    if not campaign or campaign['status'] != 'draft':
        return redirect_to(f'/campaigns/{campaign_id}/preview', message='Edycja jest dostępna tylko dla draftu.')
    campaign['body_html'] = sanitize_html(campaign.get('body_html') or legacy_to_html(campaign.get('body')))
    return render_template(request, 'campaign_new.html', {'form': campaign})


@app.post("/campaigns/new")
async def campaign_create(request: Request):
    return await save_draft(request)


@app.post("/campaigns/{campaign_id}/edit")
async def campaign_update(request: Request, campaign_id: int):
    return await save_draft(request, campaign_id)


async def save_draft(request, campaign_id=None):
    data = await request.form()
    fields = {k: str(data.get(k) or '').strip() for k in ('name','subject','language','headline','cta_label','cta_url')}
    fields['body_html'] = sanitize_html(str(data.get('body_html') or legacy_to_html(str(data.get('body') or ''))))
    try:
        if not fields['name'] or not fields['subject'] or not fields['headline'] or not html_to_text(fields['body_html']):
            raise ValueError('Wypełnij nazwę wewnętrzną, Subject, nagłówek oraz treść.')
        if fields['language'] not in VALID_LANGUAGES:
            raise ValueError('Wybierz jeden język: polski lub angielski.')
        if any(len(fields[k]) > 250 or '\r' in fields[k] or '\n' in fields[k] for k in ('name','subject','headline','cta_label')):
            raise ValueError('Nagłówki: maksymalnie 250 znaków, bez podziałów linii.')
        if len(fields['body_html']) > 100000:
            raise ValueError('Treść jest zbyt długa (maksymalnie 100 000 znaków).')
        if bool(fields['cta_label']) != bool(fields['cta_url']) or (fields['cta_url'] and not safe_url(fields['cta_url'])):
            raise ValueError('CTA wymaga etykiety i poprawnego URL http/https lub obu pustych pól.')
        old = fetch_one_dict('SELECT * FROM campaigns WHERE id=?', (campaign_id,)) if campaign_id else {}
        if campaign_id and (not old or old['status'] != 'draft'):
            raise ValueError('Kampania została zatwierdzona. Treści nie można zmienić.')
        banner = old.get('banner_asset')
        if data.get('remove_banner') == '1':
            banner = None
        upload = data.get('banner')
        if upload and getattr(upload, 'filename', ''):
            try:
                banner = await run_in_threadpool(store_banner, await upload.read(MAX_UPLOAD + 1))
            finally:
                await upload.close()
        fields['banner_asset'] = banner
        def persist():
            rendered = render_campaign_single(fields['language'], fields['subject'], None,
                body_html=fields['body_html'], headline=fields['headline'], cta_label=fields['cta_label'],
                cta_url=fields['cta_url'], banner_asset=banner)
            values = (fields['name'], fields['language'], fields['subject'], html_to_text(fields['body_html']),
                      rendered['html'], rendered['text'], fields['body_html'], fields['headline'],
                      fields['cta_label'], fields['cta_url'], banner)
            with get_connection() as conn:
                conn.execute('BEGIN IMMEDIATE')
                if campaign_id:
                    changed = conn.execute("""UPDATE campaigns SET name=?,language=?,subject=?,body=?,html=?,text=?,
                        body_html=?,headline=?,cta_label=?,cta_url=?,banner_asset=? WHERE id=? AND status='draft'""", (*values,campaign_id))
                    if changed.rowcount != 1:
                        raise ValueError('Status kampanii zmienił się. Zapis zablokowany.')
                    return campaign_id
                cursor = conn.execute("""INSERT INTO campaigns(name,language,subject,body,html,text,body_html,headline,
                    cta_label,cta_url,banner_asset,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,'draft',?)""", (*values,utc_now()))
                return cursor.lastrowid
        saved = await run_in_threadpool(persist)
    except ValueError as exc:
        fields['id'] = campaign_id
        return render_template(request, 'campaign_new.html', {'form': fields, 'error': str(exc)}, status_code=400)
    return redirect_to(f'/campaigns/{saved}/preview', message='Draft zapisany.')


@app.get('/campaign-assets/{asset_id}')
def private_campaign_asset(asset_id: str):
    try:
        path = asset_path(asset_id)
    except ValueError:
        return JSONResponse({'error':'Nie znaleziono grafiki.'}, status_code=404)
    with get_connection() as conn:
        bound = conn.execute('SELECT 1 FROM campaigns WHERE banner_asset=? UNION SELECT 1 FROM email_sends WHERE banner_asset=? LIMIT 1', (asset_id,asset_id)).fetchone()
    if not bound or not path.is_file():
        return JSONResponse({'error':'Nie znaleziono grafiki.'}, status_code=404)
    return FileResponse(path, headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})


@app.get('/campaigns/{campaign_id}/preview')
def campaign_preview(request: Request, campaign_id: int):
    campaign = fetch_one_dict('SELECT * FROM campaigns WHERE id=?', (campaign_id,))
    if not campaign:
        return redirect_to('/history', message='Nie znaleziono kampanii.')
    return render_template(request, 'campaign_preview.html', {'campaign':campaign})


@app.post('/campaigns/{campaign_id}/approve')
def campaign_approve(campaign_id: int):
    with get_connection() as conn:
        conn.execute("UPDATE campaigns SET status='approved',approved_at=? WHERE id=? AND status='draft'", (utc_now(),campaign_id))
    return redirect_to(f'/campaigns/{campaign_id}/recipients', message='Kampania zatwierdzona. Treść została zablokowana.')


@app.post('/campaigns/{campaign_id}/reopen')
def campaign_reopen(campaign_id: int):
    with get_connection() as conn:
        conn.execute("""UPDATE campaigns SET status='draft',approved_at=NULL WHERE id=? AND status='approved'
                        AND NOT EXISTS(SELECT 1 FROM email_sends WHERE campaign_id=?)""", (campaign_id,campaign_id))
    return redirect_to(f'/campaigns/{campaign_id}/edit')


@app.get('/campaigns/{campaign_id}/recipients')
def campaign_recipients(request: Request, campaign_id: int, country_group: str='', language: str='',
                        active_only: str='1', search: str='', page: int=1, selected_only: str='0',
                        sort: str='email', direction: str='asc'):
    # SQL fragments come exclusively from this allowlist; id is the stable tie breaker.
    ordering={'email':'c.email COLLATE NOCASE','company':'COALESCE(c.company_name,\'\') COLLATE NOCASE',
              'last_sent':'julianday(last_smtp_at)'}
    sort = sort if sort in ordering else 'email'
    direction = direction if direction in {'asc','desc'} else 'asc'
    with get_connection() as conn:
        campaign = conn.execute('SELECT * FROM campaigns WHERE id=?', (campaign_id,)).fetchone()
        if not campaign:
            return redirect_to('/history', message='Nie znaleziono kampanii.')
        if 'language' not in request.query_params:
            language = campaign['language'] or ''
        where, params = [], []
        for key,value in (('country_group',country_group),('language',language)):
            if value:
                where.append(f'c.{key}=?')
                params.append(value)
        if active_only == '1':
            where.append("c.status='active'")
        if search:
            where.append('(c.email LIKE ? OR c.company_name LIKE ? OR c.notes LIKE ?)')
            params.extend([f'%{search}%']*3)
        if selected_only == '1':
            where.append('EXISTS(SELECT 1 FROM campaign_selection s WHERE s.contact_id=c.id AND s.campaign_id=?)')
            params.append(campaign_id)
        sql = ' WHERE ' + ' AND '.join(where) if where else ''
        total = conn.execute('SELECT COUNT(*) FROM contacts c'+sql,tuple(params)).fetchone()[0]
        pages = max(1,(total+PAGE_SIZE-1)//PAGE_SIZE)
        page = min(max(1,page),pages)
        contacts = conn.execute('''SELECT c.*,
            (SELECT COALESCE(s.accepted_at,s.sent_at) FROM email_sends s WHERE s.contact_id=c.id
             AND s.status<>'dry_run' AND (s.accepted_at IS NOT NULL OR (s.status='sent' AND s.sent_at IS NOT NULL))
             AND NOT EXISTS(SELECT 1 FROM send_attempt_history a WHERE a.send_id=s.id AND a.mode='dry_run')
             ORDER BY julianday(COALESCE(s.accepted_at,s.sent_at)) DESC,s.id DESC LIMIT 1) AS last_smtp_at,
            (SELECT s.campaign_id FROM email_sends s WHERE s.contact_id=c.id
             AND s.status<>'dry_run' AND (s.accepted_at IS NOT NULL OR (s.status='sent' AND s.sent_at IS NOT NULL))
             AND NOT EXISTS(SELECT 1 FROM send_attempt_history a WHERE a.send_id=s.id AND a.mode='dry_run')
             ORDER BY julianday(COALESCE(s.accepted_at,s.sent_at)) DESC,s.id DESC LIMIT 1) AS last_smtp_campaign
            FROM contacts c'''+sql+f' ORDER BY {ordering[sort]} {direction.upper()},c.id ASC LIMIT ? OFFSET ?',(*params,PAGE_SIZE,(page-1)*PAGE_SIZE)).fetchall()
        selected = selected_ids(conn,campaign_id)
        eligible_count = len(selected_ids(conn,campaign_id,eligible=True))
    filters = dict(country_group=country_group,language=language,active_only=active_only,search=search,selected_only=selected_only,sort=sort,direction=direction)
    sort_links={key:'?'+urlencode(dict(filters,sort=key,direction='desc' if sort==key and direction=='asc' else 'asc',page=1)) for key in ordering}
    links = [(p,'?'+urlencode(dict(filters,page=p))) for p in range(1,pages+1)]
    return render_template(request,'campaign_recipients.html',dict(campaign=campaign,contacts=contacts,filters=filters,
        selected=selected,selected_count=len(selected),eligible_count=eligible_count,page=page,pages=pages,page_links=links,total=total,sort_links=sort_links))


def parse_ids(value):
    values = str(value or '').split(',')
    if len(values)>500 or any(v and not v.isdigit() for v in values):
        raise ValueError('Nieprawidłowa selekcja.')
    return [int(v) for v in values if v]


def selection_state(campaign_id):
    with get_connection() as conn:
        campaign = conn.execute('SELECT status FROM campaigns WHERE id=?', (campaign_id,)).fetchone()
        if not campaign:
            return JSONResponse({'error':'Nie znaleziono kampanii.'}, status_code=404)
        ids = selected_ids(conn, campaign_id)
        return {'selected_count':len(ids), 'selected_ids':ids,
                'eligible_count':len(selected_ids(conn, campaign_id, eligible=True)),
                'editable':campaign['status'] == 'approved', 'workflow':'explicit_add_v1'}


@app.get('/campaigns/{campaign_id}/selection')
def campaign_selection_state(campaign_id: int):
    result = selection_state(campaign_id)
    return JSONResponse(result, headers={'Cache-Control':'no-store'}) if isinstance(result, dict) else result


@app.post('/campaigns/{campaign_id}/selection')
async def campaign_selection_save(request: Request,campaign_id: int):
    form = await request.form()
    try:
        action = str(form.get('action') or 'add')
        clear = form.get('clear') == '1' or action == 'clear'
        if action not in ('add','clear') or (clear and form.get('confirm_clear') != '1'):
            raise ValueError('Wyczyszczenie listy wymaga jawnego potwierdzenia.')
        await run_in_threadpool(update_selection,campaign_id,parse_ids(form.get('visible')),parse_ids(form.get('checked')),clear)
        return selection_state(campaign_id)
    except ValueError as exc:
        return JSONResponse({'error':str(exc)},status_code=400)


@app.post('/campaigns/{campaign_id}/selection/remove')
async def campaign_selection_remove(request: Request, campaign_id: int):
    form = await request.form()
    try:
        ids = parse_ids(form.get('contact_id'))
        if len(ids) != 1:
            raise ValueError('Wskaż jednego odbiorcę do usunięcia z kampanii.')
        await run_in_threadpool(update_selection, campaign_id, ids, [], remove=True)
    except ValueError as exc:
        return redirect_to(f'/campaigns/{campaign_id}/summary', message=str(exc))
    return redirect_to(f'/campaigns/{campaign_id}/summary', message='Usunięto odbiorcę z kampanii.')


@app.get('/campaigns/{campaign_id}/summary')
def campaign_summary(request: Request, campaign_id: int):
    with get_connection() as conn:
        campaign = conn.execute('SELECT * FROM campaigns WHERE id=?', (campaign_id,)).fetchone()
        recipients = conn.execute('''SELECT c.* FROM contacts c JOIN campaign_selection s ON s.contact_id=c.id
            WHERE s.campaign_id=? ORDER BY c.id''', (campaign_id,)).fetchall()
    if not campaign or campaign['status'] != 'approved':
        return redirect_to(f'/campaigns/{campaign_id}/recipients', message='Selekcja wymaga zatwierdzonej kampanii.')
    ids = [r['id'] for r in recipients if r['status'] == 'active']
    seconds = max(0,len(ids)-1)*20
    seconds += (max(0,seconds-1)//worker.ACTIVE_PERIOD)*worker.BREAK_SECONDS
    return render_template(request,'campaign_confirm.html',dict(campaign=campaign,count=len(ids),
        selected_count=len(recipients),recipients=recipients,excluded=len(recipients)-len(ids),
        fingerprint=selection_fingerprint(ids),estimate_minutes=round(seconds/60),settings=get_mail_settings()))


@app.post('/editor/sanitize')
async def editor_sanitize(request: Request):
    form = await request.form()
    value = str(form.get('html') or '')
    if len(value) > 200000:
        return JSONResponse({'error':'Wklejana treść jest zbyt długa.'}, status_code=400)
    return {'html':sanitize_html(value)}


@app.post('/campaigns/{campaign_id}/recipients')
async def campaign_send(request: Request,campaign_id: int):
    form = await request.form()
    with get_connection() as conn:
        campaign = conn.execute('SELECT * FROM campaigns WHERE id=?',(campaign_id,)).fetchone()
        ids = selected_ids(conn,campaign_id,eligible=True)
        selected_count = len(selected_ids(conn,campaign_id))
    if not campaign or campaign['status'] != 'approved' or not ids or len(ids)>1000:
        return redirect_to(f'/campaigns/{campaign_id}/recipients',message='Wybierz 1–1000 aktywnych odbiorców zatwierdzonej kampanii.')
    fingerprint = selection_fingerprint(ids)
    if form.get('confirmed') != '1':
        return campaign_summary(request, campaign_id)
    if form.get('fingerprint') != fingerprint:
        return redirect_to(f'/campaigns/{campaign_id}/recipients',message='Selekcja lub kwalifikowalność zmieniła się. Potwierdź ponownie.')
    if not worker.manager.available:
        return redirect_to(f'/campaigns/{campaign_id}/recipients',message='Worker niedostępny w tym procesie. Użyj jednej instancji aplikacji.')
    mode = str(form.get('mode') or '')
    if mode == 'smtp' and form.get('smtp_ack') != '1':
        return redirect_to(f'/campaigns/{campaign_id}/recipients',message='Realny SMTP wymaga osobnego jawnego potwierdzenia operatora.')
    try:
        result = await run_in_threadpool(prepare_campaign_send,campaign_id,ids,mode)
        if not result['started']:
            raise ValueError(result['message'])
    except ValueError as exc:
        return redirect_to(f'/campaigns/{campaign_id}/recipients',message=str(exc))
    worker.manager.wake.set()
    return redirect_to(f'/campaigns/{campaign_id}/monitor')


@app.get('/campaigns/{campaign_id}/monitor')
def campaign_monitor(request: Request,campaign_id: int):
    campaign = fetch_one_dict('SELECT * FROM campaigns WHERE id=?',(campaign_id,))
    if not campaign:
        return redirect_to('/history')
    return render_template(request,'campaign_monitor.html',dict(campaign=campaign,status_data=worker.execution_payload(campaign_id)))


@app.post('/campaigns/{campaign_id}/pause')
def campaign_pause(campaign_id: int):
    try:
        worker.pause(campaign_id)
        return {'ok':True}
    except ValueError as exc:
        return JSONResponse({'error':str(exc)},status_code=400)


@app.post('/campaigns/{campaign_id}/resume')
def campaign_resume(campaign_id: int):
    if not worker.manager.available:
        return JSONResponse({'error':'Worker niedostępny w tym procesie.'},status_code=409)
    try:
        worker.resume(campaign_id)
        return {'ok':True}
    except ValueError as exc:
        return JSONResponse({'error':str(exc)},status_code=400)


@app.post('/sends/{send_id}/resolve')
async def campaign_resolve(request: Request,send_id: int):
    form = await request.form()
    send = fetch_one_dict('SELECT campaign_id FROM email_sends WHERE id=?',(send_id,))
    try:
        await run_in_threadpool(worker.resolve_uncertain,send_id,str(form.get('decision') or ''),str(form.get('note') or ''),form.get('confirmed')=='1')
        message='Decyzja zapisana. Wznowienie pozostaje ręczne.'
    except ValueError as exc:
        message=str(exc)
    return redirect_to('/history/'+str(send.get('campaign_id','')),message=message)


@app.get("/campaigns/{campaign_id}/status.json")
def campaign_status_json(campaign_id: int):
    payload = campaign_status_payload(campaign_id)
    if payload is None:
        return JSONResponse({"error": "Campaign not found."}, status_code=404)
    payload.update(worker.execution_payload(campaign_id))
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
def history_detail(request: Request, campaign_id: int, send_id: int | None = None, attempt_page: int = 1):
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
    with get_connection() as conn:
        attempts=conn.execute("""SELECT a.*,s.email FROM send_attempt_history a JOIN email_sends s ON s.id=a.send_id
            WHERE s.campaign_id=? ORDER BY a.id DESC LIMIT 100 OFFSET ?""",(campaign_id,(max(1,attempt_page)-1)*100)).fetchall()
        decisions=conn.execute("""SELECT d.*,s.email FROM recovery_decisions d JOIN email_sends s ON s.id=d.send_id
            WHERE s.campaign_id=? ORDER BY d.id DESC""",(campaign_id,)).fetchall()
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
            "attempts": attempts, "attempt_page": max(1,attempt_page), "decisions": decisions,
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
