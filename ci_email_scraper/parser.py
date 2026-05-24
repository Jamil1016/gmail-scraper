"""Email parser — HTML body to ParsedEmail.

Holds:
  - _clean_html: BeautifulSoup-based HTML normalization
  - parse_email: top-level entry — dispatches to per-vendor extractors
  - Vendor extractors: GitHubActionsExtractor, CircleCIExtractor, JenkinsExtractor
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup

from ci_email_scraper.patterns import match_vendor
from ci_email_scraper.types import ParsedEmail, ParseError

_TRACKING_SPAN_STYLE = re.compile(r"font-size:\s*[01](pt|px|p?)?\b", re.IGNORECASE)
_WORD_REJOIN = re.compile(r"\b([A-Z])\s([a-z])")


def _clean_html(html: str) -> str:
    """Normalize raw email HTML into searchable plain text."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["script", "style"]):
        tag.decompose()
    for span in soup.find_all("span", style=_TRACKING_SPAN_STYLE):
        span.decompose()
    text = soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    text = _WORD_REJOIN.sub(r"\1\2", text)
    return text


def _stable_id(subject: str, build_id: str, received_at: datetime) -> str:
    """16-char hex digest, stable across re-runs of the same fixture."""
    raw = f"{subject}|{build_id}|{received_at.isoformat()}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


# --- Vendor extractors ---

def _extract_after_label(text: str, label: str) -> str:
    """Pull the substring immediately after 'Label:' up to the next two-space gap.

    Designed for simple key: value lines. Whitespace tolerant.
    """
    pattern = re.compile(re.escape(label) + r"\s*([^\s].*?)(?=\s{2,}|$|[A-Z][a-z]+:)")
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def _parse_duration_to_seconds(s: str) -> int | None:
    """Parse 'Xm Ys' / 'X min Y sec' / 'X minutes Y seconds' → seconds. None if unparseable."""
    s = s.lower()
    m_minutes = re.search(r"(\d+)\s*(?:m|min(?:ute)?s?)\b", s)
    m_seconds = re.search(r"(\d+)\s*(?:s|sec(?:ond)?s?)\b", s)
    if not (m_minutes or m_seconds):
        return None
    minutes = int(m_minutes.group(1)) if m_minutes else 0
    seconds = int(m_seconds.group(1)) if m_seconds else 0
    return minutes * 60 + seconds


def _parse_github_actions(subject: str, text: str) -> dict[str, Any]:
    # Subject: "[owner/repo] Build #N — status"
    m = re.search(
        r"\[([\w.-]+/[\w.-]+)\]\s+Build\s+#(\d+)\s+[—–-]\s+(\w+)",
        subject,
    )
    if not m:
        raise ParseError(f"github_actions subject pattern not matched: {subject!r}")

    fields: dict[str, Any] = {
        "build_id": m.group(2),
        "status": m.group(3).lower(),
        "repo": m.group(1),
    }
    # Common labeled fields
    for label, key in [
        ("Branch:", "branch"),
        ("Commit:", "commit_sha"),
        ("Triggered by:", "actor"),
        ("Workflow:", "workflow"),
        ("Pull request:", "pull_request"),
        ("Reason:", "reason"),
        ("Failed tests:", "failed_tests_count"),
        ("Failure stage:", "failure_stage"),
        ("Matrix jobs:", "matrix_jobs"),
        ("Matrix passed:", "matrix_passed"),
        ("Matrix failed:", "matrix_failed"),
    ]:
        value = _extract_after_label(text, label)
        if value:
            fields[key] = value

    duration_raw = _extract_after_label(text, "Duration:")
    if duration_raw:
        seconds = _parse_duration_to_seconds(duration_raw)
        if seconds is not None:
            fields["duration_seconds"] = seconds

    return fields


def _parse_circleci(subject: str, text: str) -> dict[str, Any]:
    # Subject: "Project X: build #N [status]"
    m = re.search(
        r"Project\s+(\S+):\s+build\s+#(\d+)\s+\[(\w+)\]",
        subject,
        re.IGNORECASE,
    )
    if not m:
        raise ParseError(f"circleci subject pattern not matched: {subject!r}")

    status_raw = m.group(3).lower()
    status = "failure" if status_raw == "failed" else status_raw

    fields: dict[str, Any] = {
        "build_id": m.group(2),
        "status": status,
        "project": m.group(1),
    }
    for label, key in [
        ("Branch:", "branch"),
        ("Commit:", "commit_sha"),
        ("Workflow:", "workflow"),
        ("Pull request:", "pull_request"),
        ("Failed step:", "failed_step"),
        ("Failed tests:", "failed_tests_count"),
        ("Cancelled by:", "cancelled_by"),
        ("Reason:", "reason"),
        ("Parallel jobs:", "parallel_jobs"),
        ("Parallel passed:", "parallel_passed"),
        ("Parallel failed:", "parallel_failed"),
    ]:
        value = _extract_after_label(text, label)
        if value:
            fields[key] = value

    duration_raw = _extract_after_label(text, "Duration:")
    if duration_raw:
        seconds = _parse_duration_to_seconds(duration_raw)
        if seconds is not None:
            fields["duration_seconds"] = seconds

    return fields


def _parse_jenkins(subject: str, text: str) -> dict[str, Any]:
    # Subject: "Build #N — project/branch — STATUS"
    m = re.search(
        r"Build\s+#(\d+)\s+[—–-]\s+(\S+)\s+[—–-]\s+(\w+)",
        subject,
    )
    if not m:
        raise ParseError(f"jenkins subject pattern not matched: {subject!r}")

    project_branch = m.group(2)
    project, _, branch = project_branch.partition("/")
    status_raw = m.group(3).lower()
    # Jenkins-specific: UNSTABLE and ABORTED both map to failure / cancelled
    status = {"unstable": "failure", "aborted": "cancelled"}.get(status_raw, status_raw)

    fields: dict[str, Any] = {
        "build_id": m.group(1),
        "status": status,
        "project": project,
        "branch": branch or "",
    }
    for label, key in [
        ("Commit:", "commit_sha"),
        ("Triggered:", "triggered"),
        ("Failed stage:", "failed_stage"),
        ("Error:", "error"),
        ("Workspace:", "workspace"),
        ("Artifacts:", "artifacts"),
        ("Stages:", "stages"),
        ("Stages passed:", "stages_passed"),
        ("Stages unstable:", "stages_unstable"),
        ("Unstable stage:", "unstable_stage"),
        ("Aborted by:", "aborted_by"),
    ]:
        value = _extract_after_label(text, label)
        if value:
            fields[key] = value

    duration_raw = _extract_after_label(text, "Duration:")
    if duration_raw:
        seconds = _parse_duration_to_seconds(duration_raw)
        if seconds is not None:
            fields["duration_seconds"] = seconds

    return fields


_EXTRACTORS = {
    "github_actions": _parse_github_actions,
    "circleci": _parse_circleci,
    "jenkins": _parse_jenkins,
}


def parse_email(
    subject: str,
    body_html: str,
    received_at: datetime,
    from_addr: str,
) -> ParsedEmail:
    """Parse a raw email into a ParsedEmail.

    Returns an "unknown" ParsedEmail if no vendor matches. Raises ParseError
    if the vendor is known but the email is malformed.
    """
    vendor = match_vendor(subject, from_addr, body_html)
    if vendor == "unknown":
        return ParsedEmail(
            vendor="unknown",
            message_id=_stable_id(subject, "", received_at),
            build_id="",
            status="unknown",
            received_at=received_at,
            fields={},
        )

    text = _clean_html(body_html)
    extractor = _EXTRACTORS[vendor]
    raw_fields = extractor(subject, text)

    build_id = raw_fields.pop("build_id")
    status = raw_fields.pop("status")

    return ParsedEmail(
        vendor=vendor,
        message_id=_stable_id(subject, build_id, received_at),
        build_id=build_id,
        status=status,
        received_at=received_at,
        fields=raw_fields,
    )
