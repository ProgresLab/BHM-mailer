from __future__ import annotations

from datetime import date, datetime, timezone
import re
import sqlite3
from pathlib import Path
from typing import Iterable

from .db import ensure_unique_token, get_connection, utc_now
from .models import ImportCandidate, ImportReport, normalize_email, normalize_group

try:
    import openpyxl
except ImportError:  # pragma: no cover - handled at runtime with a clear message.
    openpyxl = None


TOKEN_SPLIT_RE = re.compile(r"[\s,;]+")
HEADER_ALIASES = {
    "company_name": {"company name", "company name and country", "company name & country", "company"},
    "email": {"email", "email address", "e-mail", "e-mail address"},
    "industry": {"industry", "inudstry"},
    "last_sent_at": {"date sent", "sent date"},
    "notes": {"comments", "comment", "notes"},
}


def clean_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def split_product_like_cells(value: object) -> tuple[list[str], list[str]]:
    if value is None:
        return [], []
    valid: list[str] = []
    invalid: list[str] = []
    for token in TOKEN_SPLIT_RE.split(str(value)):
        token = token.strip().strip("<>\"'()[]{}.,;:")
        if not token:
            continue
        if "@" not in token:
            continue
        email = normalize_email(token)
        if email:
            valid.append(email)
        else:
            invalid.append(token.lower())
    return valid, invalid


def classify_group(mode: str | None, email: str, sheet_name: str | None = None) -> tuple[str, str]:
    normalized = normalize_group(mode)
    if normalized == "PL":
        return "PL", "pl"
    if normalized == "INTERNATIONAL":
        return "INTERNATIONAL", "en"
    if sheet_suggests_poland(sheet_name) or email.endswith(".pl"):
        return "PL", "pl"
    return "INTERNATIONAL", "en"


def sheet_suggests_poland(sheet_name: str | None) -> bool:
    sheet = (sheet_name or "").upper()
    return bool(
        re.search(r"(^|[^A-Z])PL([^A-Z]|$)", sheet)
        or "POLSK" in sheet
        or "POLAND" in sheet
    )


def normalize_header(value: object) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("&", " and ")
    text = re.sub(r"\s+", " ", text)
    return text


def detect_columns(row: Iterable[object]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for index, cell in enumerate(row):
        header = normalize_header(cell)
        for field, aliases in HEADER_ALIASES.items():
            if header in aliases and field not in mapping:
                mapping[field] = index
    return mapping


def format_date_value(value: object) -> str | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.replace(microsecond=0).isoformat()
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc).isoformat()
    text = clean_text(value)
    return text


def import_from_paste(text: str, mode: str | None = "AUTO", source: str = "paste") -> ImportReport:
    candidates: list[ImportCandidate] = []
    invalid: list[str] = []
    emails, bad_tokens = split_product_like_cells(text)
    invalid.extend(bad_tokens)
    for email in emails:
        group, language = classify_group(mode, email)
        candidates.append(
            ImportCandidate(
                email=email,
                country_group=group,
                language=language,
                source=source,
            )
        )
    return upsert_contacts(candidates, invalid)


def import_from_xlsx(path: Path, mode: str | None = "AUTO", source: str | None = None) -> ImportReport:
    if openpyxl is None:
        raise RuntimeError("openpyxl is not installed. Install requirements.txt first.")

    workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
    candidates: list[ImportCandidate] = []
    invalid: list[str] = []
    source_name = source or path.name

    for worksheet in workbook.worksheets:
        rows = worksheet.iter_rows(values_only=True)
        columns: dict[str, int] = {}
        for row in rows:
            if not any(cell is not None and str(cell).strip() for cell in row):
                continue
            possible_columns = detect_columns(row)
            if "email" in possible_columns:
                columns = possible_columns
                break
        if not columns:
            continue

        for row in rows:
            values = list(row)
            email_cell = values[columns["email"]] if columns["email"] < len(values) else None
            emails, bad_tokens = split_product_like_cells(email_cell)
            invalid.extend(bad_tokens)
            if not emails:
                continue

            company_name = get_column_value(values, columns, "company_name")
            industry = get_column_value(values, columns, "industry")
            notes = get_column_value(values, columns, "notes")
            last_sent_at = format_date_value(get_raw_column_value(values, columns, "last_sent_at"))

            for email in emails:
                group, language = classify_group(mode, email, worksheet.title)
                candidates.append(
                    ImportCandidate(
                        email=email,
                        company_name=company_name,
                        industry=industry,
                        country_group=group,
                        language=language,
                        source=source_name,
                        source_sheet=worksheet.title,
                        notes=notes,
                        last_sent_at=last_sent_at,
                    )
                )

    return upsert_contacts(candidates, invalid)


def get_column_value(values: list[object], columns: dict[str, int], field: str) -> str | None:
    return clean_text(get_raw_column_value(values, columns, field))


def get_raw_column_value(values: list[object], columns: dict[str, int], field: str) -> object | None:
    index = columns.get(field)
    if index is None or index >= len(values):
        return None
    return values[index]


def upsert_contacts(candidates: Iterable[ImportCandidate], invalid_emails: list[str] | None = None) -> ImportReport:
    report = ImportReport(invalid_emails=invalid_emails or [])
    seen: set[str] = set()
    with get_connection() as conn:
        for candidate in candidates:
            email = normalize_email(candidate.email)
            if not email:
                report.invalid_emails.append(str(candidate.email))
                continue
            if email in seen:
                report.duplicates += 1
                continue
            seen.add(email)
            candidate.email = email
            upsert_one(conn, candidate, report)
        conn.commit()
    return report


def upsert_one(conn: sqlite3.Connection, candidate: ImportCandidate, report: ImportReport) -> None:
    existing = conn.execute("SELECT * FROM contacts WHERE email = ?", (candidate.email,)).fetchone()
    now = utc_now()
    if existing is None:
        conn.execute(
            """
            INSERT INTO contacts (
                email, company_name, contact_name, industry, country_group, language, status,
                source, source_sheet, consent_status, notes, unsubscribe_token,
                created_at, updated_at, last_sent_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate.email,
                candidate.company_name,
                candidate.contact_name,
                candidate.industry,
                candidate.country_group,
                candidate.language,
                candidate.source,
                candidate.source_sheet,
                candidate.consent_status,
                candidate.notes,
                ensure_unique_token(conn),
                now,
                now,
                candidate.last_sent_at,
            ),
        )
        report.added += 1
        return

    if existing["status"] == "unsubscribed":
        report.skipped_unsubscribed += 1
    elif existing["status"] in {"bounced", "invalid"}:
        report.skipped_invalid_or_bounced += 1

    updates: dict[str, str] = {}
    for field in (
        "company_name",
        "contact_name",
        "industry",
        "source",
        "source_sheet",
        "consent_status",
        "notes",
        "last_sent_at",
    ):
        new_value = getattr(candidate, field)
        if new_value and not existing[field]:
            updates[field] = new_value

    if not existing["unsubscribe_token"]:
        updates["unsubscribe_token"] = ensure_unique_token(conn)

    if not updates:
        report.duplicates += 1
        return

    updates["updated_at"] = now
    assignments = ", ".join(f"{field} = ?" for field in updates)
    conn.execute(
        f"UPDATE contacts SET {assignments} WHERE id = ?",
        (*updates.values(), existing["id"]),
    )
    report.updated += 1
