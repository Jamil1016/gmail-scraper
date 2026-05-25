"""Vendor detection from email subject + From-header.

Patterns are evaluated in ORDER. Longer/more-specific patterns are checked
first to avoid prefix collisions (the production bug this guards against).
"""

from __future__ import annotations

import re

# Subject patterns per vendor.
# Order matters: more specific patterns first.
_SUBJECT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # GitHub Actions: "[owner/repo] Build #N — status"
    ("github_actions", re.compile(r"\[[\w.-]+/[\w.-]+\]\s+Build\s+#\d+", re.IGNORECASE)),
    # CircleCI: "Project X: build #N [status]"
    ("circleci", re.compile(r"Project\s+\S+:\s+build\s+#\d+", re.IGNORECASE)),
    # Jenkins: "Build #N — project/branch — STATUS"
    ("jenkins", re.compile(r"Build\s+#\d+\s+[—–-]\s+\S+", re.IGNORECASE)),  # noqa: RUF001
]

# Fallback: From-header domain → vendor
_FROM_HEADERS: dict[str, str] = {
    "noreply@github.com": "github_actions",
    "noreply@circleci.com": "circleci",
    "jenkins@": "jenkins",  # substring match — many Jenkins installs vary the domain
}


def match_vendor(subject: str, from_addr: str, body_html: str) -> str:
    """Return the vendor name, or "unknown" if no pattern matches.

    Inspects subject first (most discriminating in practice), then falls back
    to From-header domain if subject is ambiguous.

    body_html is accepted for future heuristics but unused in v1.
    """
    _ = body_html  # reserved for future use; explicit no-op

    for vendor, pattern in _SUBJECT_PATTERNS:
        if pattern.search(subject):
            return vendor

    for needle, vendor in _FROM_HEADERS.items():
        if needle in from_addr.lower():
            return vendor

    return "unknown"
