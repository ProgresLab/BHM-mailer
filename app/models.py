from __future__ import annotations

from dataclasses import dataclass, field
import re


VALID_COUNTRY_GROUPS = ("PL", "INTERNATIONAL")
VALID_LANGUAGES = ("pl", "en")
VALID_CONTACT_STATUSES = ("active", "unsubscribed", "bounced", "invalid")
VALID_CAMPAIGN_STATUSES = (
    "draft",
    "approved",
    "sending",
    "completed",
    "completed_with_errors",
    "stopped",
)
VALID_SEND_STATUSES = (
    "pending",
    "sending",
    "accepted_by_smtp",
    "smtp_failed",
    "rate_limited",
    "delivery_pending",
    "delivered_by_trace",
    "failed_by_trace",
    "quarantined_by_trace",
    "bounced_later",
    "delivery_unknown",
    "skipped_unsubscribed",
    "skipped_invalid",
    "skipped_duplicate",
    "cancelled",
    "dry_run",
    "sent",
    "failed",
    "bounced",
    "invalid",
)

EMAIL_RE = re.compile(r"^[A-Z0-9._%+\-']+@[A-Z0-9.\-]+\.[A-Z]{2,}$", re.IGNORECASE)


def normalize_email(value: object) -> str | None:
    if value is None:
        return None
    email = str(value).strip().lower().strip("<>\"'()[]{}.,;:")
    if not email or not EMAIL_RE.match(email):
        return None
    return email


def normalize_group(value: str | None) -> str:
    value = (value or "AUTO").strip().upper()
    if value in {"POLSKA", "PL"}:
        return "PL"
    if value in {"POZA POLSKA", "POZA POLSKĄ", "INTERNATIONAL", "EN"}:
        return "INTERNATIONAL"
    return "AUTO"


@dataclass
class ImportCandidate:
    email: str
    country_group: str
    language: str
    company_name: str | None = None
    contact_name: str | None = None
    industry: str | None = None
    source: str | None = None
    source_sheet: str | None = None
    consent_status: str | None = None
    notes: str | None = None
    last_sent_at: str | None = None


@dataclass
class ImportReport:
    added: int = 0
    updated: int = 0
    duplicates: int = 0
    invalid_emails: list[str] = field(default_factory=list)
    skipped_unsubscribed: int = 0
    skipped_invalid_or_bounced: int = 0

    def merge(self, other: "ImportReport") -> "ImportReport":
        self.added += other.added
        self.updated += other.updated
        self.duplicates += other.duplicates
        self.invalid_emails.extend(other.invalid_emails)
        self.skipped_unsubscribed += other.skipped_unsubscribed
        self.skipped_invalid_or_bounced += other.skipped_invalid_or_bounced
        return self

    @property
    def invalid_count(self) -> int:
        return len(self.invalid_emails)
