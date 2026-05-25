from ci_email_scraper.patterns import match_vendor


class TestGitHubActionsDetection:
    def test_matches_standard_subject(self) -> None:
        subject = "[acme-corp/widget-api] Build #42 — success"
        assert match_vendor(subject, "noreply@github.com", "") == "github_actions"

    def test_matches_failure_subject(self) -> None:
        subject = "[acme-corp/widget-api] Build #43 — failure"
        assert match_vendor(subject, "noreply@github.com", "") == "github_actions"

    def test_falls_back_to_from_header(self) -> None:
        # Subject alone is ambiguous; from-address resolves it
        subject = "Build report"
        assert match_vendor(subject, "noreply@github.com", "") == "github_actions"


class TestCircleCIDetection:
    def test_matches_standard_subject(self) -> None:
        subject = "Project widget-api: build #42 [success]"
        assert match_vendor(subject, "noreply@circleci.com", "") == "circleci"

    def test_matches_failure_subject(self) -> None:
        subject = "Project widget-api: build #43 [failed]"
        assert match_vendor(subject, "noreply@circleci.com", "") == "circleci"


class TestJenkinsDetection:
    def test_matches_standard_subject(self) -> None:
        subject = "Build #142 — widget-api/main — SUCCESS"
        assert match_vendor(subject, "jenkins@example.com", "") == "jenkins"

    def test_matches_failure_subject(self) -> None:
        subject = "Build #143 — widget-api/main — FAILURE"
        assert match_vendor(subject, "jenkins@example.com", "") == "jenkins"


class TestUnknownDetection:
    def test_returns_unknown_for_unrelated_emails(self) -> None:
        assert match_vendor("Your weekly digest", "newsletter@example.com", "") == "unknown"

    def test_returns_unknown_for_empty_input(self) -> None:
        assert match_vendor("", "", "") == "unknown"


class TestPrefixDisambiguation:
    """Critical: longer/more-specific patterns must win over shorter ones.

    This is the production bug we're guarding against — substring matches
    creating false positives across vendors.
    """

    def test_github_subject_does_not_match_circleci_pattern(self) -> None:
        # GitHub Actions subject contains 'build #' but should NOT match CircleCI
        subject = "[acme/widget] Build #42 — success"
        assert match_vendor(subject, "noreply@github.com", "") == "github_actions"

    def test_jenkins_subject_does_not_match_github_pattern(self) -> None:
        subject = "Build #42 — widget-api/main — SUCCESS"
        assert match_vendor(subject, "jenkins@example.com", "") == "jenkins"
