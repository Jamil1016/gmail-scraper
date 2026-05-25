"""Load .eml fixture files from a directory tree.

Pure IO + decoding. No parsing. The output (RawEmail) feeds into parse_email.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from pathlib import Path

from ci_email_scraper.types import RawEmail


def load_fixture_dir(root: Path | str) -> Iterator[RawEmail]:
    """Yield every .eml file under `root` (recursively) as RawEmail.

    Skips files that can't be parsed as email messages — logs to stderr.
    """
    root_path = Path(root)
    for eml_path in sorted(root_path.rglob("*.eml")):
        try:
            yield _load_eml(eml_path)
        except (OSError, ValueError) as exc:
            print(f"warning: failed to load {eml_path}: {exc}", file=__import__("sys").stderr)


def _load_eml(path: Path) -> RawEmail:
    msg = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    subject = msg["Subject"] or ""
    from_addr = msg["From"] or ""

    body_html = ""
    if msg.is_multipart():
        for part in msg.iter_parts():
            if part.get_content_type() == "text/html":
                body_html = part.get_content()
                break
    elif msg.get_content_type() == "text/html":
        body_html = msg.get_content()

    received_at: datetime = datetime(2026, 1, 1, tzinfo=UTC)
    date_header = msg["Date"]
    if date_header:
        try:
            received_at = parsedate_to_datetime(date_header)
        except (TypeError, ValueError):
            pass

    return RawEmail(
        subject=subject,
        body_html=body_html,
        received_at=received_at,
        from_addr=from_addr,
    )
