import contextlib
from datetime import UTC, datetime
from email import policy
from email.parser import BytesParser
from pathlib import Path

import pytest

from ci_email_scraper.parser import parse_email
from ci_email_scraper.types import ParseError


def _load_fixture(path: Path) -> tuple[str, str, datetime, str]:
    """Returns (subject, body_html, received_at, from_addr) from a .eml path."""
    msg = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    subject = msg["Subject"] or ""
    from_addr = msg["From"] or ""
    body_html = ""
    if msg.is_multipart():
        for part in msg.iter_parts():
            if part.get_content_type() == "text/html":
                body_html = part.get_content()
                break
    else:
        body_html = msg.get_content() if msg.get_content_type() == "text/html" else ""
    date_header = msg["Date"]
    received_at = datetime(2026, 1, 1, tzinfo=UTC)  # default if Date header malformed
    if date_header:
        from email.utils import parsedate_to_datetime

        with contextlib.suppress(TypeError, ValueError):
            received_at = parsedate_to_datetime(date_header)
    return subject, body_html, received_at, from_addr


class TestGitHubActionsParser:
    def test_success_main_deploy(self) -> None:
        path = Path("fixtures/github_actions/success-main-deploy.eml")
        subject, body, received_at, from_addr = _load_fixture(path)
        result = parse_email(subject, body, received_at, from_addr)
        assert result["vendor"] == "github_actions"
        assert result["build_id"] == "142"
        assert result["status"] == "success"
        assert result["fields"]["repo"] == "acme-corp/widget-api"
        assert result["fields"]["branch"] == "main"
        assert result["fields"]["actor"] == "alice-dev"

    def test_failure_with_failed_tests(self) -> None:
        path = Path("fixtures/github_actions/failure-broken-tests.eml")
        subject, body, received_at, from_addr = _load_fixture(path)
        result = parse_email(subject, body, received_at, from_addr)
        assert result["status"] == "failure"
        assert result["build_id"] == "144"

    def test_matrix_build_dynamic_fields(self) -> None:
        """Matrix build introduces fields not present in other GHA fixtures.
        Verifies dynamic JSONB absorption."""
        path = Path("fixtures/github_actions/matrix-build-mixed.eml")
        subject, body, received_at, from_addr = _load_fixture(path)
        result = parse_email(subject, body, received_at, from_addr)
        assert result["status"] == "failure"
        # 'matrix_jobs' or similar should appear in dynamic fields
        assert any("matrix" in k.lower() for k in result["fields"])


class TestCircleCIParser:
    def test_success_main(self) -> None:
        path = Path("fixtures/circleci/success-main.eml")
        subject, body, received_at, from_addr = _load_fixture(path)
        result = parse_email(subject, body, received_at, from_addr)
        assert result["vendor"] == "circleci"
        assert result["build_id"] == "1024"
        assert result["status"] == "success"
        assert result["fields"]["project"] == "widget-api"
        assert result["fields"]["branch"] == "main"

    def test_failure_linter(self) -> None:
        path = Path("fixtures/circleci/failure-linter.eml")
        subject, body, received_at, from_addr = _load_fixture(path)
        result = parse_email(subject, body, received_at, from_addr)
        assert result["status"] == "failure"
        assert result["build_id"] == "1026"


class TestJenkinsParser:
    def test_success_nightly(self) -> None:
        path = Path("fixtures/jenkins/success-nightly.eml")
        subject, body, received_at, from_addr = _load_fixture(path)
        result = parse_email(subject, body, received_at, from_addr)
        assert result["vendor"] == "jenkins"
        assert result["build_id"] == "2142"
        assert result["status"] == "success"
        assert result["fields"]["project"] == "widget-api"
        assert result["fields"]["branch"] == "main"

    def test_unstable_treated_as_failure(self) -> None:
        path = Path("fixtures/jenkins/multi-stage-partial.eml")
        subject, body, received_at, from_addr = _load_fixture(path)
        result = parse_email(subject, body, received_at, from_addr)
        # Jenkins 'UNSTABLE' should map to failure for our normalized status
        assert result["status"] == "failure"


class TestUnknownVendor:
    def test_returns_unknown_for_unrelated_email(self) -> None:
        result = parse_email(
            subject="Your weekly newsletter",
            body_html="<p>News!</p>",
            received_at=datetime(2026, 5, 1, tzinfo=UTC),
            from_addr="news@example.com",
        )
        assert result["vendor"] == "unknown"
        assert result["status"] == "unknown"
        assert result["build_id"] == ""


class TestMessageIdStability:
    def test_same_input_produces_same_id(self) -> None:
        path = Path("fixtures/github_actions/success-main-deploy.eml")
        subject, body, received_at, from_addr = _load_fixture(path)
        a = parse_email(subject, body, received_at, from_addr)
        b = parse_email(subject, body, received_at, from_addr)
        assert a["message_id"] == b["message_id"]

    def test_different_builds_produce_different_ids(self) -> None:
        a_path = Path("fixtures/github_actions/success-main-deploy.eml")
        b_path = Path("fixtures/github_actions/success-pr-merged.eml")
        a_args = _load_fixture(a_path)
        b_args = _load_fixture(b_path)
        a = parse_email(*a_args)
        b = parse_email(*b_args)
        assert a["message_id"] != b["message_id"]


class TestParseErrorOnMalformedKnownVendor:
    def test_raises_on_github_subject_without_build_id(self) -> None:
        # Recognized as GHA by from-header but subject lacks build_id
        with pytest.raises(ParseError):
            parse_email(
                subject="Build report",
                body_html="<p>some body</p>",
                received_at=datetime(2026, 5, 1, tzinfo=UTC),
                from_addr="noreply@github.com",
            )
