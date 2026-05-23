from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, TypedDict


class ParsedEmail(TypedDict):
    """Result of parsing a single email.

    `fields` holds vendor-specific dynamic fields that don't fit the
    fixed schema — this is what lands in the Postgres JSONB column.
    """

    vendor: str          # "github_actions" | "circleci" | "jenkins" | "unknown"
    message_id: str      # stable hash for dedup
    build_id: str        # "" if vendor == "unknown"
    status: str          # "success" | "failure" | "cancelled" | "unknown"
    received_at: datetime
    fields: dict[str, Any]


@dataclass(frozen=True)
class RawEmail:
    """Raw email loaded from a .eml fixture.

    Decoupled from ParsedEmail so the fixture loader and parser have
    independent test surfaces.
    """

    subject: str
    body_html: str
    received_at: datetime
    from_addr: str


class ParseError(Exception):
    """Raised when a recognized vendor email cannot be fully parsed.

    Distinguishes 'this email doesn't match any vendor we know' (returns
    unknown ParsedEmail) from 'we know the vendor but the body is malformed'
    (raises ParseError).
    """
