# Clean-Room gmail-scraper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable open-source Python package that parses synthetic CI/CD build notification emails (GitHub Actions, CircleCI, Jenkins) into a Postgres JSONB column, with a CLI for ingesting + querying, full pytest coverage, and green GitHub Actions on the public repo.

**Architecture:** Single Python package `ci_email_scraper`. Sync parser (BeautifulSoup + ordered header patterns + vendor extractors), async DB layer (asyncpg pool). Fixture-driven (no real Gmail API in v1) — `.eml` files in `fixtures/<vendor>/` are the input. Postgres in docker for local dev; GHA service container for CI. Idempotent upsert by stable message-id hash so re-runs are free.

**Tech Stack:** Python 3.12, BeautifulSoup 4, asyncpg, Postgres 16, pytest + pytest-asyncio + pytest-cov + testcontainers-postgres, ruff, mypy, docker-compose, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-05-21-gmail-scraper-clean-room.md`

**Working directory:** `C:\Users\admin\Desktop\Projects\personal\gmail-scraper`

**Repo:** `Jamil1016/gmail-scraper` (currently has one commit — the placeholder README + the spec).

---

## File Structure Overview

```
gmail-scraper/
├── ci_email_scraper/
│   ├── __init__.py
│   ├── __main__.py                 # python -m ci_email_scraper entry
│   ├── cli.py                      # argparse: run / query / init-db
│   ├── parser.py                   # parse_email + per-vendor extractors
│   ├── patterns.py                 # ordered vendor-detection patterns
│   ├── fixtures.py                 # .eml loader
│   ├── db.py                       # asyncpg pool + upsert
│   ├── schema.sql                  # CREATE TABLE migration
│   └── types.py                    # ParsedEmail, RawEmail
├── fixtures/
│   ├── github_actions/             # 6 .eml files
│   ├── circleci/                   # 6 .eml files
│   └── jenkins/                    # 6 .eml files
├── tests/
│   ├── __init__.py
│   ├── conftest.py                 # pytest fixtures: postgres testcontainer
│   ├── test_patterns.py
│   ├── test_parser.py
│   ├── test_dirty_html.py
│   ├── test_upsert.py
│   └── test_cli.py
├── .github/
│   └── workflows/
│       ├── test.yml                # pytest + coverage
│       └── lint.yml                # ruff + mypy
├── .env.example
├── .gitignore
├── docker-compose.yml              # Postgres 16
├── pyproject.toml                  # PEP 621 + ruff/mypy config
├── README.md                       # story + Mermaid + quick-start
└── LICENSE                         # MIT
```

Each file has one clear responsibility:
- `patterns.py` — vendor detection only, no parsing
- `parser.py` — HTML → ParsedEmail, no IO
- `fixtures.py` — filesystem walk + .eml decode, no parsing
- `db.py` — asyncpg pool + upsert SQL, no parsing
- `cli.py` — glue between fixtures, parser, db. Sync wrapper around async.
- `types.py` — data contracts only

---

# Phase 0 — Project Scaffolding

### Task 1: Repo scaffolding (pyproject.toml, configs, docker-compose)

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `pyproject.toml`
- Create: `docker-compose.yml`
- Create: `LICENSE`
- Create: `ci_email_scraper/__init__.py`
- Create: `ci_email_scraper/schema.sql`

- [ ] **Step 1: Create `.gitignore`**

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
.eggs/
build/
dist/
.venv/
venv/

# Test / coverage
.pytest_cache/
.coverage
coverage.xml
htmlcov/

# Editor / OS
.vscode/
.idea/
.DS_Store
Thumbs.db

# Env
.env
.env.local

# Cache
/tmp_cache/
```

- [ ] **Step 2: Create `.env.example`**

```bash
# Postgres connection
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ci_emails
```

- [ ] **Step 3: Create `pyproject.toml`**

```toml
[project]
name = "ci-email-scraper"
version = "0.1.0"
description = "Parse CI/CD build notification emails into Postgres JSONB. Clean-room reference implementation of the HTML-email-to-structured-data pattern."
readme = "README.md"
requires-python = ">=3.12"
license = { text = "MIT" }
authors = [{ name = "Jamil Mendez" }]
dependencies = [
    "beautifulsoup4>=4.12",
    "asyncpg>=0.29",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=4.1",
    "testcontainers[postgres]>=4.0",
    "ruff>=0.5",
    "mypy>=1.10",
]

[project.scripts]
ci-email-scraper = "ci_email_scraper.cli:main"

[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["ci_email_scraper*"]
exclude = ["tests*", "fixtures*"]

[tool.setuptools.package-data]
ci_email_scraper = ["schema.sql"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = ["-v", "--strict-markers"]

[tool.coverage.run]
source = ["ci_email_scraper"]
omit = ["ci_email_scraper/__main__.py"]

[tool.coverage.report]
fail_under = 80
show_missing = true
skip_covered = false

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP", "SIM", "RUF"]
ignore = ["E501"]  # line length handled by formatter

[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
```

- [ ] **Step 4: Create `docker-compose.yml`**

```yaml
services:
  postgres:
    image: postgres:16
    container_name: ci-emails-postgres
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: ci_emails
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

- [ ] **Step 5: Create `LICENSE`** (MIT, year 2026)

```
MIT License

Copyright (c) 2026 Jamil Mendez

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 6: Create `ci_email_scraper/__init__.py`**

```python
"""ci_email_scraper — parse CI/CD build notification emails into Postgres JSONB."""

__version__ = "0.1.0"
```

- [ ] **Step 7: Create `ci_email_scraper/schema.sql`**

```sql
create table if not exists ci_builds (
  message_id    text primary key,
  vendor        text not null,
  build_id      text not null,
  status        text not null,
  fields        jsonb not null,
  received_at   timestamptz not null,
  created_at    timestamptz not null default now()
);

create index if not exists ci_builds_repo_idx
  on ci_builds ((fields->>'repo'));
create index if not exists ci_builds_vendor_received_idx
  on ci_builds (vendor, received_at desc);
create index if not exists ci_builds_status_idx
  on ci_builds (status);
```

- [ ] **Step 8: Install package + verify imports**

```bash
cd "C:\Users\admin\Desktop\Projects\personal\gmail-scraper"
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
python -c "import ci_email_scraper; print(ci_email_scraper.__version__)"
```

Expected: `0.1.0` printed.

- [ ] **Step 9: Commit**

```bash
git add .gitignore .env.example pyproject.toml docker-compose.yml LICENSE ci_email_scraper/
git commit -m "chore: project scaffolding (pyproject, docker, schema, license)"
```

---

# Phase 1 — Data Contracts

### Task 2: Create `types.py` (no logic, just types)

**Files:**
- Create: `ci_email_scraper/types.py`

- [ ] **Step 1: Implement `types.py`**

```python
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
```

- [ ] **Step 2: Verify imports**

```bash
python -c "from ci_email_scraper.types import ParsedEmail, RawEmail, ParseError; print('ok')"
```

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add ci_email_scraper/types.py
git commit -m "feat: add ParsedEmail, RawEmail, ParseError data contracts"
```

---

# Phase 2 — Vendor Detection (TDD)

### Task 3: `patterns.py` with vendor detection

**Files:**
- Create: `ci_email_scraper/patterns.py`
- Create: `tests/__init__.py`
- Create: `tests/test_patterns.py`

- [ ] **Step 1: Create empty `tests/__init__.py`**

```bash
echo. > tests\__init__.py
```

- [ ] **Step 2: Write failing tests at `tests/test_patterns.py`**

```python
import pytest

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
```

- [ ] **Step 3: Run, confirm fail**

```bash
pytest tests/test_patterns.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'ci_email_scraper.patterns'`.

- [ ] **Step 4: Implement `ci_email_scraper/patterns.py`**

```python
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
    ("jenkins", re.compile(r"Build\s+#\d+\s+[—–-]\s+\S+", re.IGNORECASE)),
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
```

- [ ] **Step 5: Run, confirm pass**

```bash
pytest tests/test_patterns.py -v
```
Expected: PASS, all 9 tests.

- [ ] **Step 6: Commit**

```bash
git add ci_email_scraper/patterns.py tests/__init__.py tests/test_patterns.py
git commit -m "feat: vendor detection with ordered subject patterns + From-header fallback"
```

---

# Phase 3 — HTML Cleaner (TDD)

### Task 4: `_clean_html` for hidden-span removal + word rejoin

**Files:**
- Create: `ci_email_scraper/parser.py` (skeleton with just `_clean_html` for now)
- Create: `tests/test_dirty_html.py`

- [ ] **Step 1: Write failing tests at `tests/test_dirty_html.py`**

```python
from ci_email_scraper.parser import _clean_html


class TestHiddenSpanRemoval:
    def test_strips_zero_width_tracking_span(self) -> None:
        html = """
        <p>Build status: <span style="font-size:0">tracker_abc123</span>success</p>
        """
        cleaned = _clean_html(html)
        assert "tracker_abc123" not in cleaned
        assert "success" in cleaned

    def test_strips_one_pt_tracking_span(self) -> None:
        html = '<p>Status: <span style="font-size: 1pt">hidden</span>success</p>'
        cleaned = _clean_html(html)
        assert "hidden" not in cleaned
        assert "success" in cleaned

    def test_keeps_normal_spans(self) -> None:
        html = '<p>Status: <span style="color: red">success</span></p>'
        cleaned = _clean_html(html)
        assert "success" in cleaned


class TestWordRejoin:
    def test_rejoins_split_uppercase_letter(self) -> None:
        # BeautifulSoup get_text(" ") splits "Construction" → "C onstruction"
        # when a tracking span sits between "C" and "onstruction".
        # _clean_html should rejoin them.
        html = '<p><span style="font-size:0">x</span>C<span style="font-size:0">y</span>onstruction Engineer</p>'
        cleaned = _clean_html(html)
        assert "Construction Engineer" in cleaned
        assert "C onstruction" not in cleaned

    def test_does_not_merge_unrelated_words(self) -> None:
        html = "<p>Hello World</p>"
        cleaned = _clean_html(html)
        assert "Hello World" in cleaned


class TestScriptStyleStripping:
    def test_strips_script_tags(self) -> None:
        html = "<p>Visible</p><script>alert('x')</script>"
        cleaned = _clean_html(html)
        assert "Visible" in cleaned
        assert "alert" not in cleaned

    def test_strips_style_tags(self) -> None:
        html = "<p>Visible</p><style>body { color: red; }</style>"
        cleaned = _clean_html(html)
        assert "Visible" in cleaned
        assert "color: red" not in cleaned
```

- [ ] **Step 2: Run, confirm fail**

```bash
pytest tests/test_dirty_html.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'ci_email_scraper.parser'`.

- [ ] **Step 3: Implement `ci_email_scraper/parser.py` (cleaner only)**

```python
"""Email parser — HTML body to ParsedEmail.

This file holds:
  - _clean_html: BeautifulSoup-based HTML normalization (Phase 3)
  - parse_email + vendor extractors (Phase 4)
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

_TRACKING_SPAN_STYLE = re.compile(r"font-size:\s*[01](pt|px|p?)?\b", re.IGNORECASE)
_WORD_REJOIN = re.compile(r"\b([A-Z])\s([a-z])")


def _clean_html(html: str) -> str:
    """Normalize raw email HTML into searchable plain text.

    Three steps:
      1. Strip <script> and <style> tags entirely.
      2. Strip zero-width / 1pt tracking spans (common email tracking technique
         that breaks plain-text extraction).
      3. Collapse whitespace and rejoin single uppercase letters that
         BeautifulSoup's get_text() splits apart.
    """
    soup = BeautifulSoup(html, "html.parser")

    # 1. Remove <script> and <style> entirely
    for tag in soup.find_all(["script", "style"]):
        tag.decompose()

    # 2. Remove zero-width tracking spans
    for span in soup.find_all("span", style=_TRACKING_SPAN_STYLE):
        span.decompose()

    # 3. Extract text + collapse whitespace
    text = soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)

    # Rejoin single uppercase letters BS split apart from following lowercase
    text = _WORD_REJOIN.sub(r"\1\2", text)

    return text
```

- [ ] **Step 4: Run, confirm pass**

```bash
pytest tests/test_dirty_html.py -v
```
Expected: PASS, all 7 tests.

- [ ] **Step 5: Commit**

```bash
git add ci_email_scraper/parser.py tests/test_dirty_html.py
git commit -m "feat: HTML cleaner with tracking-span removal and word rejoin"
```

---

# Phase 4 — Fixtures

### Task 5: GitHub Actions fixtures (6 .eml files)

**Files:**
- Create: `fixtures/github_actions/success-main-deploy.eml`
- Create: `fixtures/github_actions/success-pr-merged.eml`
- Create: `fixtures/github_actions/failure-broken-tests.eml`
- Create: `fixtures/github_actions/failure-build-error.eml`
- Create: `fixtures/github_actions/cancelled-superseded.eml`
- Create: `fixtures/github_actions/matrix-build-mixed.eml`

Each fixture is a valid RFC 822 .eml file with HTML body. The format must be parseable by Python's `email` module. Use this template, varying subject + fields:

- [ ] **Step 1: Create `fixtures/github_actions/success-main-deploy.eml`**

```
From: noreply@github.com
To: jamil@example.com
Subject: [acme-corp/widget-api] Build #142 — success
Date: Mon, 19 May 2026 14:23:18 +0000
Content-Type: text/html; charset=utf-8
MIME-Version: 1.0

<html><body>
<div style="font-family: sans-serif">
  <h2>Build #142 — success</h2>
  <table>
    <tr><td>Repository:</td><td>acme-corp/widget-api</td></tr>
    <tr><td>Branch:</td><td>main</td></tr>
    <tr><td>Commit:</td><td>a3f8c92d1b4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a</td></tr>
    <tr><td>Triggered by:</td><td>alice-dev</td></tr>
    <tr><td>Duration:</td><td>3m 42s</td></tr>
    <tr><td>Workflow:</td><td>deploy-prod.yml</td></tr>
  </table>
  <p><span style="font-size:0">tracker_xyz789</span>View build details on GitHub.</p>
</div>
</body></html>
```

- [ ] **Step 2: Create `fixtures/github_actions/success-pr-merged.eml`**

```
From: noreply@github.com
To: jamil@example.com
Subject: [acme-corp/widget-api] Build #143 — success
Date: Mon, 19 May 2026 15:11:02 +0000
Content-Type: text/html; charset=utf-8
MIME-Version: 1.0

<html><body>
<div style="font-family: sans-serif">
  <h2>Build #143 — success</h2>
  <table>
    <tr><td>Repository:</td><td>acme-corp/widget-api</td></tr>
    <tr><td>Branch:</td><td>feature/auth-rewrite</td></tr>
    <tr><td>Commit:</td><td>b7c9d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9</td></tr>
    <tr><td>Triggered by:</td><td>bob-eng</td></tr>
    <tr><td>Duration:</td><td>2m 18s</td></tr>
    <tr><td>Workflow:</td><td>pr-checks.yml</td></tr>
    <tr><td>Pull request:</td><td>#287</td></tr>
  </table>
</div>
</body></html>
```

- [ ] **Step 3: Create `fixtures/github_actions/failure-broken-tests.eml`**

```
From: noreply@github.com
To: jamil@example.com
Subject: [acme-corp/widget-api] Build #144 — failure
Date: Mon, 19 May 2026 16:44:51 +0000
Content-Type: text/html; charset=utf-8
MIME-Version: 1.0

<html><body>
<div style="font-family: sans-serif">
  <h2>Build #144 — failure</h2>
  <table>
    <tr><td>Repository:</td><td>acme-corp/widget-api</td></tr>
    <tr><td>Branch:</td><td>main</td></tr>
    <tr><td>Commit:</td><td>c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0</td></tr>
    <tr><td>Triggered by:</td><td>alice-dev</td></tr>
    <tr><td>Duration:</td><td>4m 12s</td></tr>
    <tr><td>Failed tests:</td><td>3</td></tr>
  </table>
  <h3>Failed tests</h3>
  <ul>
    <li>tests.api.test_auth::test_login_with_expired_token</li>
    <li>tests.api.test_auth::test_refresh_with_invalid_token</li>
    <li>tests.api.test_users::test_create_with_duplicate_email</li>
  </ul>
</div>
</body></html>
```

- [ ] **Step 4: Create `fixtures/github_actions/failure-build-error.eml`**

```
From: noreply@github.com
To: jamil@example.com
Subject: [acme-corp/widget-api] Build #145 — failure
Date: Mon, 19 May 2026 17:02:09 +0000
Content-Type: text/html; charset=utf-8
MIME-Version: 1.0

<html><body>
<div style="font-family: sans-serif">
  <h2>Build #145 — failure</h2>
  <table>
    <tr><td>Repository:</td><td>acme-corp/widget-api</td></tr>
    <tr><td>Branch:</td><td>feature/refactor-db</td></tr>
    <tr><td>Commit:</td><td>d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3</td></tr>
    <tr><td>Triggered by:</td><td>charlie-ops</td></tr>
    <tr><td>Duration:</td><td>0m 47s</td></tr>
    <tr><td>Failure stage:</td><td>compile</td></tr>
  </table>
  <h3>Build error</h3>
  <pre>error[E0432]: unresolved import `crate::auth::middleware`
  --> src/api/routes.rs:12:5</pre>
</div>
</body></html>
```

- [ ] **Step 5: Create `fixtures/github_actions/cancelled-superseded.eml`**

```
From: noreply@github.com
To: jamil@example.com
Subject: [acme-corp/widget-api] Build #146 — cancelled
Date: Mon, 19 May 2026 17:15:33 +0000
Content-Type: text/html; charset=utf-8
MIME-Version: 1.0

<html><body>
<div style="font-family: sans-serif">
  <h2>Build #146 — cancelled</h2>
  <table>
    <tr><td>Repository:</td><td>acme-corp/widget-api</td></tr>
    <tr><td>Branch:</td><td>feature/refactor-db</td></tr>
    <tr><td>Triggered by:</td><td>charlie-ops</td></tr>
    <tr><td>Reason:</td><td>Superseded by build #147</td></tr>
  </table>
</div>
</body></html>
```

- [ ] **Step 6: Create `fixtures/github_actions/matrix-build-mixed.eml`** (rare variant — exercises dynamic JSONB)

```
From: noreply@github.com
To: jamil@example.com
Subject: [acme-corp/widget-api] Build #147 — failure
Date: Mon, 19 May 2026 17:58:12 +0000
Content-Type: text/html; charset=utf-8
MIME-Version: 1.0

<html><body>
<div style="font-family: sans-serif">
  <h2>Build #147 — failure (matrix build, 1 of 4 jobs failed)</h2>
  <table>
    <tr><td>Repository:</td><td>acme-corp/widget-api</td></tr>
    <tr><td>Branch:</td><td>main</td></tr>
    <tr><td>Commit:</td><td>e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4</td></tr>
    <tr><td>Triggered by:</td><td>alice-dev</td></tr>
    <tr><td>Duration:</td><td>6m 04s</td></tr>
    <tr><td>Matrix jobs:</td><td>4</td></tr>
    <tr><td>Matrix passed:</td><td>3</td></tr>
    <tr><td>Matrix failed:</td><td>1</td></tr>
  </table>
  <h3>Matrix job results</h3>
  <ul>
    <li>python-3.10: success</li>
    <li>python-3.11: success</li>
    <li>python-3.12: success</li>
    <li>python-3.13-beta: failure</li>
  </ul>
</div>
</body></html>
```

- [ ] **Step 7: Verify fixtures load via Python's email module**

```bash
python -c "from email import policy; from email.parser import BytesParser; from pathlib import Path; [print(p.name, BytesParser(policy=policy.default).parsebytes(p.read_bytes())['Subject']) for p in Path('fixtures/github_actions').glob('*.eml')]"
```

Expected: 6 lines, each printing the filename + extracted subject.

- [ ] **Step 8: Commit**

```bash
git add fixtures/github_actions/
git commit -m "feat: add 6 GitHub Actions fixture .eml files (success/failure/cancelled/matrix)"
```

---

### Task 6: CircleCI fixtures (6 .eml files)

**Files:**
- Create: `fixtures/circleci/success-main.eml`
- Create: `fixtures/circleci/success-feature-branch.eml`
- Create: `fixtures/circleci/failure-linter.eml`
- Create: `fixtures/circleci/failure-flaky-test.eml`
- Create: `fixtures/circleci/cancelled-manual.eml`
- Create: `fixtures/circleci/parallel-job-failure.eml`

CircleCI emails use a different visual style — colored status banner with status name as a header, then a list of key-value pairs.

- [ ] **Step 1: Create `fixtures/circleci/success-main.eml`**

```
From: noreply@circleci.com
To: jamil@example.com
Subject: Project widget-api: build #1024 [success]
Date: Tue, 20 May 2026 09:14:22 +0000
Content-Type: text/html; charset=utf-8
MIME-Version: 1.0

<html><body>
<div style="font-family: Helvetica, Arial">
  <div style="background: #00C853; color: white; padding: 12px">SUCCESS</div>
  <h2>Project: widget-api / build #1024</h2>
  <p>Branch: <b>main</b></p>
  <p>Commit: <code>a3f8c92</code> — alice-dev</p>
  <p>Duration: 2 minutes 14 seconds</p>
  <p>Workflow: <b>deploy</b></p>
</div>
</body></html>
```

- [ ] **Step 2: Create `fixtures/circleci/success-feature-branch.eml`**

```
From: noreply@circleci.com
To: jamil@example.com
Subject: Project widget-api: build #1025 [success]
Date: Tue, 20 May 2026 10:02:51 +0000
Content-Type: text/html; charset=utf-8
MIME-Version: 1.0

<html><body>
<div style="font-family: Helvetica, Arial">
  <div style="background: #00C853; color: white; padding: 12px">SUCCESS</div>
  <h2>Project: widget-api / build #1025</h2>
  <p>Branch: <b>feature/payments-v2</b></p>
  <p>Commit: <code>b7c9d2e</code> — bob-eng</p>
  <p>Duration: 1 minute 47 seconds</p>
  <p>Workflow: <b>pr-check</b></p>
  <p>Pull request: #94</p>
</div>
</body></html>
```

- [ ] **Step 3: Create `fixtures/circleci/failure-linter.eml`**

```
From: noreply@circleci.com
To: jamil@example.com
Subject: Project widget-api: build #1026 [failed]
Date: Tue, 20 May 2026 11:33:08 +0000
Content-Type: text/html; charset=utf-8
MIME-Version: 1.0

<html><body>
<div style="font-family: Helvetica, Arial">
  <div style="background: #D50000; color: white; padding: 12px">FAILED</div>
  <h2>Project: widget-api / build #1026</h2>
  <p>Branch: <b>feature/payments-v2</b></p>
  <p>Commit: <code>c1d2e3f</code> — bob-eng</p>
  <p>Duration: 0 minutes 38 seconds</p>
  <p>Failed step: <b>lint</b></p>
  <pre>ruff check failed: E501 line too long (147 > 100) at api/handlers.py:42</pre>
</div>
</body></html>
```

- [ ] **Step 4: Create `fixtures/circleci/failure-flaky-test.eml`**

```
From: noreply@circleci.com
To: jamil@example.com
Subject: Project widget-api: build #1027 [failed]
Date: Tue, 20 May 2026 12:08:44 +0000
Content-Type: text/html; charset=utf-8
MIME-Version: 1.0

<html><body>
<div style="font-family: Helvetica, Arial">
  <div style="background: #D50000; color: white; padding: 12px">FAILED</div>
  <h2>Project: widget-api / build #1027</h2>
  <p>Branch: <b>main</b></p>
  <p>Commit: <code>d4e5f6a</code> — alice-dev</p>
  <p>Duration: 3 minutes 22 seconds</p>
  <p>Failed step: <b>test</b></p>
  <p>Failed tests: 1</p>
  <ul>
    <li>tests/integration/test_payments.py::test_concurrent_charge</li>
  </ul>
</div>
</body></html>
```

- [ ] **Step 5: Create `fixtures/circleci/cancelled-manual.eml`**

```
From: noreply@circleci.com
To: jamil@example.com
Subject: Project widget-api: build #1028 [cancelled]
Date: Tue, 20 May 2026 12:31:19 +0000
Content-Type: text/html; charset=utf-8
MIME-Version: 1.0

<html><body>
<div style="font-family: Helvetica, Arial">
  <div style="background: #757575; color: white; padding: 12px">CANCELLED</div>
  <h2>Project: widget-api / build #1028</h2>
  <p>Branch: <b>main</b></p>
  <p>Cancelled by: alice-dev</p>
  <p>Reason: manual</p>
</div>
</body></html>
```

- [ ] **Step 6: Create `fixtures/circleci/parallel-job-failure.eml`** (rare variant)

```
From: noreply@circleci.com
To: jamil@example.com
Subject: Project widget-api: build #1029 [failed]
Date: Tue, 20 May 2026 13:45:01 +0000
Content-Type: text/html; charset=utf-8
MIME-Version: 1.0

<html><body>
<div style="font-family: Helvetica, Arial">
  <div style="background: #D50000; color: white; padding: 12px">FAILED</div>
  <h2>Project: widget-api / build #1029</h2>
  <p>Branch: <b>main</b></p>
  <p>Commit: <code>e5f6a7b</code> — charlie-ops</p>
  <p>Duration: 4 minutes 09 seconds</p>
  <p>Parallel jobs: 8</p>
  <p>Parallel passed: 7</p>
  <p>Parallel failed: 1 (job index 3)</p>
  <p>Failed step (in failed job): <b>integration-tests</b></p>
</div>
</body></html>
```

- [ ] **Step 7: Verify fixtures load**

```bash
python -c "from email import policy; from email.parser import BytesParser; from pathlib import Path; [print(p.name, BytesParser(policy=policy.default).parsebytes(p.read_bytes())['Subject']) for p in Path('fixtures/circleci').glob('*.eml')]"
```

Expected: 6 lines.

- [ ] **Step 8: Commit**

```bash
git add fixtures/circleci/
git commit -m "feat: add 6 CircleCI fixture .eml files"
```

---

### Task 7: Jenkins fixtures (6 .eml files)

**Files:**
- Create: `fixtures/jenkins/success-nightly.eml`
- Create: `fixtures/jenkins/success-release.eml`
- Create: `fixtures/jenkins/failure-compile.eml`
- Create: `fixtures/jenkins/failure-deploy.eml`
- Create: `fixtures/jenkins/aborted-timeout.eml`
- Create: `fixtures/jenkins/multi-stage-partial.eml`

Jenkins emails are plainer — `<pre>` blocks with labeled lines.

- [ ] **Step 1: Create `fixtures/jenkins/success-nightly.eml`**

```
From: jenkins@build.example.com
To: jamil@example.com
Subject: Build #2142 — widget-api/main — SUCCESS
Date: Wed, 21 May 2026 03:00:14 +0000
Content-Type: text/html; charset=utf-8
MIME-Version: 1.0

<html><body>
<pre>
Project: widget-api
Build: #2142
Branch: main
Status: SUCCESS
Commit: a3f8c92d
Triggered: Timer (nightly)
Duration: 7 min 33 sec
Workspace: /var/jenkins/workspace/widget-api-nightly
</pre>
</body></html>
```

- [ ] **Step 2: Create `fixtures/jenkins/success-release.eml`**

```
From: jenkins@build.example.com
To: jamil@example.com
Subject: Build #2143 — widget-api/release-v2.4 — SUCCESS
Date: Wed, 21 May 2026 08:14:22 +0000
Content-Type: text/html; charset=utf-8
MIME-Version: 1.0

<html><body>
<pre>
Project: widget-api
Build: #2143
Branch: release-v2.4
Status: SUCCESS
Commit: b7c9d2e3
Triggered: alice-dev (manual)
Duration: 12 min 04 sec
Artifacts: widget-api-2.4.0.tar.gz, widget-api-2.4.0.deb
</pre>
</body></html>
```

- [ ] **Step 3: Create `fixtures/jenkins/failure-compile.eml`**

```
From: jenkins@build.example.com
To: jamil@example.com
Subject: Build #2144 — widget-api/main — FAILURE
Date: Wed, 21 May 2026 10:42:55 +0000
Content-Type: text/html; charset=utf-8
MIME-Version: 1.0

<html><body>
<pre>
Project: widget-api
Build: #2144
Branch: main
Status: FAILURE
Commit: c1d2e3f4
Triggered: SCM polling
Duration: 1 min 12 sec
Failed stage: build
Error: compilation failed (see console output)
</pre>
</body></html>
```

- [ ] **Step 4: Create `fixtures/jenkins/failure-deploy.eml`**

```
From: jenkins@build.example.com
To: jamil@example.com
Subject: Build #2145 — widget-api/main — FAILURE
Date: Wed, 21 May 2026 11:08:17 +0000
Content-Type: text/html; charset=utf-8
MIME-Version: 1.0

<html><body>
<pre>
Project: widget-api
Build: #2145
Branch: main
Status: FAILURE
Commit: d4e5f6a7
Triggered: alice-dev (manual)
Duration: 4 min 51 sec
Failed stage: deploy
Error: SSH connection to deploy host timed out
</pre>
</body></html>
```

- [ ] **Step 5: Create `fixtures/jenkins/aborted-timeout.eml`**

```
From: jenkins@build.example.com
To: jamil@example.com
Subject: Build #2146 — widget-api/feature-x — ABORTED
Date: Wed, 21 May 2026 14:30:00 +0000
Content-Type: text/html; charset=utf-8
MIME-Version: 1.0

<html><body>
<pre>
Project: widget-api
Build: #2146
Branch: feature-x
Status: ABORTED
Commit: e5f6a7b8
Triggered: charlie-ops (manual)
Duration: 30 min 00 sec
Aborted by: timeout (exceeded 30-minute limit)
</pre>
</body></html>
```

- [ ] **Step 6: Create `fixtures/jenkins/multi-stage-partial.eml`** (rare variant)

```
From: jenkins@build.example.com
To: jamil@example.com
Subject: Build #2147 — widget-api/main — UNSTABLE
Date: Wed, 21 May 2026 16:22:09 +0000
Content-Type: text/html; charset=utf-8
MIME-Version: 1.0

<html><body>
<pre>
Project: widget-api
Build: #2147
Branch: main
Status: UNSTABLE
Commit: f6a7b8c9
Triggered: alice-dev (manual)
Duration: 18 min 44 sec
Stages: 5
Stages passed: 4
Stages unstable: 1
Unstable stage: integration-tests (2 of 47 tests failed but threshold not exceeded)
</pre>
</body></html>
```

- [ ] **Step 7: Verify fixtures load**

```bash
python -c "from email import policy; from email.parser import BytesParser; from pathlib import Path; [print(p.name, BytesParser(policy=policy.default).parsebytes(p.read_bytes())['Subject']) for p in Path('fixtures/jenkins').glob('*.eml')]"
```

- [ ] **Step 8: Commit**

```bash
git add fixtures/jenkins/
git commit -m "feat: add 6 Jenkins fixture .eml files"
```

---

# Phase 5 — Parser Core

### Task 8: `parse_email` + vendor extractors (TDD)

**Files:**
- Modify: `ci_email_scraper/parser.py` (extend with vendor extractors + parse_email)
- Create: `tests/test_parser.py`

- [ ] **Step 1: Write failing tests at `tests/test_parser.py`**

```python
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
        try:
            received_at = parsedate_to_datetime(date_header)
        except (TypeError, ValueError):
            pass
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
```

- [ ] **Step 2: Run, confirm fail**

```bash
pytest tests/test_parser.py -v
```
Expected: FAIL — `ImportError: cannot import name 'parse_email' from 'ci_email_scraper.parser'`.

- [ ] **Step 3: Extend `ci_email_scraper/parser.py`**

Replace the file entirely with the version below (preserves `_clean_html` from Task 4, adds the parser):

```python
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
```

- [ ] **Step 4: Run tests, confirm pass**

```bash
pytest tests/test_parser.py -v
```
Expected: PASS, all tests.

- [ ] **Step 5: Run all tests + coverage**

```bash
pytest --cov
```
Expected: ≥ 80% coverage on `parser.py` and `patterns.py`.

- [ ] **Step 6: Commit**

```bash
git add ci_email_scraper/parser.py tests/test_parser.py
git commit -m "feat: parse_email + per-vendor extractors with stable message ids"
```

---

# Phase 6 — Fixture Loader

### Task 9: `fixtures.py` — filesystem walk + .eml decode

**Files:**
- Create: `ci_email_scraper/fixtures.py`

- [ ] **Step 1: Implement `ci_email_scraper/fixtures.py`**

```python
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
```

- [ ] **Step 2: Smoke-test it**

```bash
python -c "from ci_email_scraper.fixtures import load_fixture_dir; from pathlib import Path; [print(r.subject) for r in load_fixture_dir(Path('fixtures'))]"
```

Expected: 18 subject lines printed.

- [ ] **Step 3: Commit**

```bash
git add ci_email_scraper/fixtures.py
git commit -m "feat: fixture loader for .eml files"
```

---

# Phase 7 — Database Layer

### Task 10: `db.py` + `conftest.py` + upsert tests

**Files:**
- Create: `ci_email_scraper/db.py`
- Create: `tests/conftest.py`
- Create: `tests/test_upsert.py`

- [ ] **Step 1: Create `tests/conftest.py`** (spins up Postgres via testcontainers for integration tests)

```python
import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from testcontainers.postgres import PostgresContainer

import asyncpg


@pytest.fixture(scope="session")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    """Boot a Postgres container for the test session.

    Skipped if SKIP_INTEGRATION_TESTS=1 (use for fast local iteration).
    """
    if os.environ.get("SKIP_INTEGRATION_TESTS") == "1":
        pytest.skip("integration tests skipped")
    with PostgresContainer("postgres:16") as pg:
        url = pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql://")
        yield url


@pytest_asyncio.fixture(scope="function")
async def db_pool(postgres_url: str) -> AsyncIterator[asyncpg.Pool]:
    """Fresh connection pool + schema for every test."""
    pool = await asyncpg.create_pool(postgres_url, min_size=1, max_size=2)
    assert pool is not None
    schema_sql = Path("ci_email_scraper/schema.sql").read_text()
    async with pool.acquire() as conn:
        await conn.execute("drop table if exists ci_builds cascade")
        await conn.execute(schema_sql)
    try:
        yield pool
    finally:
        await pool.close()
```

- [ ] **Step 2: Write failing tests at `tests/test_upsert.py`**

```python
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ci_email_scraper.db import upsert_parsed
from ci_email_scraper.fixtures import load_fixture_dir
from ci_email_scraper.parser import parse_email
from ci_email_scraper.types import ParsedEmail


def _make_email(message_id: str = "abc123") -> ParsedEmail:
    return ParsedEmail(
        vendor="github_actions",
        message_id=message_id,
        build_id="42",
        status="success",
        received_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
        fields={"repo": "acme/widget", "branch": "main"},
    )


class TestUpsert:
    @pytest.mark.asyncio
    async def test_inserts_new_row(self, db_pool) -> None:
        n_inserted = await upsert_parsed(db_pool, [_make_email()])
        assert n_inserted == 1
        async with db_pool.acquire() as conn:
            count = await conn.fetchval("select count(*) from ci_builds")
            assert count == 1

    @pytest.mark.asyncio
    async def test_running_twice_is_idempotent(self, db_pool) -> None:
        email = _make_email()
        first = await upsert_parsed(db_pool, [email])
        second = await upsert_parsed(db_pool, [email])
        assert first == 1
        assert second == 0  # ON CONFLICT DO NOTHING — no new row

        async with db_pool.acquire() as conn:
            count = await conn.fetchval("select count(*) from ci_builds")
            assert count == 1

    @pytest.mark.asyncio
    async def test_different_message_ids_produce_separate_rows(self, db_pool) -> None:
        await upsert_parsed(db_pool, [_make_email("aaa")])
        await upsert_parsed(db_pool, [_make_email("bbb")])
        async with db_pool.acquire() as conn:
            count = await conn.fetchval("select count(*) from ci_builds")
            assert count == 2

    @pytest.mark.asyncio
    async def test_fields_round_trip_as_jsonb(self, db_pool) -> None:
        email = _make_email()
        await upsert_parsed(db_pool, [email])
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("select fields from ci_builds where message_id=$1", "abc123")
        import json
        assert row is not None
        assert json.loads(row["fields"]) == {"repo": "acme/widget", "branch": "main"}


class TestEndToEndIngestion:
    @pytest.mark.asyncio
    async def test_all_18_fixtures_ingest(self, db_pool) -> None:
        emails = []
        for raw in load_fixture_dir(Path("fixtures")):
            emails.append(parse_email(raw.subject, raw.body_html, raw.received_at, raw.from_addr))

        n = await upsert_parsed(db_pool, emails)
        assert n == 18

        async with db_pool.acquire() as conn:
            by_vendor = await conn.fetch(
                "select vendor, count(*) as c from ci_builds group by vendor order by vendor"
            )
        result = {row["vendor"]: row["c"] for row in by_vendor}
        assert result["github_actions"] == 6
        assert result["circleci"] == 6
        assert result["jenkins"] == 6
```

- [ ] **Step 3: Run, confirm fail**

```bash
pytest tests/test_upsert.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'ci_email_scraper.db'`.

- [ ] **Step 4: Implement `ci_email_scraper/db.py`**

```python
"""Database layer — asyncpg pool + JSONB upserts.

Idempotent ON CONFLICT DO NOTHING by message_id. Re-running ingestion is free.
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from pathlib import Path

import asyncpg

from ci_email_scraper.types import ParsedEmail

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable not set")
    return url


async def create_pool() -> asyncpg.Pool:
    """Create an asyncpg pool from DATABASE_URL."""
    pool = await asyncpg.create_pool(_database_url(), min_size=1, max_size=10)
    assert pool is not None
    return pool


async def init_schema(pool: asyncpg.Pool) -> None:
    """Apply schema.sql against the pool (idempotent — uses IF NOT EXISTS)."""
    sql = _SCHEMA_PATH.read_text()
    async with pool.acquire() as conn:
        await conn.execute(sql)


async def upsert_parsed(pool: asyncpg.Pool, emails: Sequence[ParsedEmail]) -> int:
    """Insert each ParsedEmail. Returns the count of NEW rows (conflicts skipped).

    Uses ON CONFLICT (message_id) DO NOTHING — running twice is a no-op.
    """
    if not emails:
        return 0

    sql = """
        insert into ci_builds (message_id, vendor, build_id, status, fields, received_at)
        values ($1, $2, $3, $4, $5::jsonb, $6)
        on conflict (message_id) do nothing
    """
    n_new = 0
    async with pool.acquire() as conn:
        for email in emails:
            # Skip unknown-vendor emails (no build_id, no useful insert)
            if email["vendor"] == "unknown":
                continue
            result = await conn.execute(
                sql,
                email["message_id"],
                email["vendor"],
                email["build_id"],
                email["status"],
                json.dumps(email["fields"]),
                email["received_at"],
            )
            # asyncpg returns "INSERT 0 1" or "INSERT 0 0"
            if result.endswith(" 1"):
                n_new += 1
    return n_new


async def query_builds(
    pool: asyncpg.Pool,
    vendor: str | None = None,
    status: str | None = None,
    repo: str | None = None,
    branch: str | None = None,
    limit: int = 50,
) -> list[asyncpg.Record]:
    """Run a parameterized query for the CLI."""
    clauses: list[str] = []
    params: list[object] = []

    def add(clause: str, value: object) -> None:
        params.append(value)
        clauses.append(clause.format(idx=len(params)))

    if vendor:
        add("vendor = ${idx}", vendor)
    if status:
        add("status = ${idx}", status)
    if repo:
        add("fields->>'repo' = ${idx}", repo)
    if branch:
        add("fields->>'branch' = ${idx}", branch)

    where = f"where {' and '.join(clauses)}" if clauses else ""
    params.append(limit)
    sql = f"""
        select message_id, vendor, build_id, status, fields, received_at
        from ci_builds
        {where}
        order by received_at desc
        limit ${len(params)}
    """

    async with pool.acquire() as conn:
        return await conn.fetch(sql, *params)
```

- [ ] **Step 5: Run tests, confirm pass**

```bash
pytest tests/test_upsert.py -v
```
Expected: PASS (5 tests). First run is slow (~30s) because testcontainers boots a Postgres container.

- [ ] **Step 6: Run all tests + coverage**

```bash
pytest --cov
```
Expected: all tests pass, coverage ≥ 80% on `parser.py`, `patterns.py`, `db.py`.

- [ ] **Step 7: Commit**

```bash
git add ci_email_scraper/db.py tests/conftest.py tests/test_upsert.py
git commit -m "feat: asyncpg DB layer with idempotent upsert + query helpers"
```

---

# Phase 8 — CLI

### Task 11: `cli.py` + `__main__.py` + CLI tests

**Files:**
- Create: `ci_email_scraper/cli.py`
- Create: `ci_email_scraper/__main__.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests at `tests/test_cli.py`**

```python
from unittest.mock import AsyncMock, patch

import pytest

from ci_email_scraper.cli import build_parser, main


class TestCLIParser:
    def test_run_subcommand_default_fixtures_path(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["run"])
        assert args.command == "run"
        assert args.fixtures == "fixtures"

    def test_run_with_custom_fixtures(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["run", "--fixtures", "/tmp/emails"])
        assert args.fixtures == "/tmp/emails"

    def test_query_with_filters(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["query", "--status", "failure", "--vendor", "circleci"])
        assert args.command == "query"
        assert args.status == "failure"
        assert args.vendor == "circleci"

    def test_init_db_subcommand(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["init-db"])
        assert args.command == "init-db"


class TestCLISmoke:
    @pytest.mark.asyncio
    async def test_run_command_calls_upsert(self) -> None:
        with patch("ci_email_scraper.cli.create_pool", new_callable=AsyncMock) as create_pool_mock, \
             patch("ci_email_scraper.cli.upsert_parsed", new_callable=AsyncMock) as upsert_mock, \
             patch("ci_email_scraper.cli.load_fixture_dir") as load_mock:

            load_mock.return_value = []
            upsert_mock.return_value = 0
            create_pool_mock.return_value.close = AsyncMock()

            exit_code = await main(["run", "--fixtures", "fixtures"])
            assert exit_code == 0
            upsert_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_command_calls_query_builds(self) -> None:
        with patch("ci_email_scraper.cli.create_pool", new_callable=AsyncMock) as create_pool_mock, \
             patch("ci_email_scraper.cli.query_builds", new_callable=AsyncMock) as query_mock:

            query_mock.return_value = []
            create_pool_mock.return_value.close = AsyncMock()

            exit_code = await main(["query", "--vendor", "github_actions"])
            assert exit_code == 0
            query_mock.assert_called_once()
```

- [ ] **Step 2: Run, confirm fail**

```bash
pytest tests/test_cli.py -v
```
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `ci_email_scraper/cli.py`**

```python
"""Command-line interface — argparse with run / query / init-db subcommands."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from ci_email_scraper.db import create_pool, init_schema, query_builds, upsert_parsed
from ci_email_scraper.fixtures import load_fixture_dir
from ci_email_scraper.parser import parse_email


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ci-email-scraper",
        description="Parse CI/CD build notification emails into Postgres JSONB.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Ingest .eml fixtures into Postgres")
    run_parser.add_argument(
        "--fixtures", default="fixtures", help="Path to fixtures directory (default: ./fixtures)"
    )

    query_parser = subparsers.add_parser("query", help="Query stored builds")
    query_parser.add_argument("--vendor", help="Filter by vendor")
    query_parser.add_argument("--status", help="Filter by status")
    query_parser.add_argument("--repo", help="Filter by fields->>'repo'")
    query_parser.add_argument("--branch", help="Filter by fields->>'branch'")
    query_parser.add_argument("--limit", type=int, default=50, help="Max rows (default: 50)")

    subparsers.add_parser("init-db", help="Apply schema.sql to the configured DATABASE_URL")

    return parser


async def _run(fixtures_path: str) -> int:
    emails = []
    for raw in load_fixture_dir(Path(fixtures_path)):
        emails.append(parse_email(raw.subject, raw.body_html, raw.received_at, raw.from_addr))

    pool = await create_pool()
    try:
        n_new = await upsert_parsed(pool, emails)
        n_total = len(emails)
        n_dupes = n_total - n_new
        print(f"Ingested {n_total} emails ({n_new} new, {n_dupes} duplicates)")
        return 0
    finally:
        await pool.close()


async def _query(args: argparse.Namespace) -> int:
    pool = await create_pool()
    try:
        rows = await query_builds(
            pool,
            vendor=args.vendor,
            status=args.status,
            repo=args.repo,
            branch=args.branch,
            limit=args.limit,
        )
        if not rows:
            print("No matching builds.")
            return 0
        # Simple table output
        print(f"{'vendor':<18} {'build':<8} {'status':<10} {'received_at':<25}")
        print("-" * 65)
        for row in rows:
            received = row["received_at"].isoformat() if row["received_at"] else ""
            print(
                f"{row['vendor']:<18} {row['build_id']:<8} {row['status']:<10} {received:<25}"
            )
        return 0
    finally:
        await pool.close()


async def _init_db() -> int:
    pool = await create_pool()
    try:
        await init_schema(pool)
        print("Schema applied.")
        return 0
    finally:
        await pool.close()


async def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        return await _run(args.fixtures)
    if args.command == "query":
        return await _query(args)
    if args.command == "init-db":
        return await _init_db()
    parser.print_help()
    return 1


def cli_entry() -> None:
    sys.exit(asyncio.run(main()))
```

- [ ] **Step 4: Implement `ci_email_scraper/__main__.py`**

```python
"""Module entry: python -m ci_email_scraper"""

from ci_email_scraper.cli import cli_entry

if __name__ == "__main__":
    cli_entry()
```

- [ ] **Step 5: Update the `pyproject.toml` entry script target**

The current `[project.scripts]` block has:
```toml
ci-email-scraper = "ci_email_scraper.cli:main"
```
That's wrong (main is async). Replace with:
```toml
ci-email-scraper = "ci_email_scraper.cli:cli_entry"
```

After editing, reinstall:
```bash
pip install -e .[dev]
```

- [ ] **Step 6: Run tests, confirm pass**

```bash
pytest tests/test_cli.py -v
```
Expected: PASS (6 tests).

- [ ] **Step 7: End-to-end smoke test**

```bash
docker compose up -d
# wait for healthy
python -m ci_email_scraper init-db
python -m ci_email_scraper run
python -m ci_email_scraper query --status success --limit 5
docker compose down
```

Expected:
- init-db → `Schema applied.`
- run → `Ingested 18 emails (18 new, 0 duplicates)`
- query → table of success builds

- [ ] **Step 8: Commit**

```bash
git add ci_email_scraper/cli.py ci_email_scraper/__main__.py pyproject.toml tests/test_cli.py
git commit -m "feat: CLI with run / query / init-db subcommands"
```

---

# Phase 9 — GitHub Actions CI

### Task 12: GHA workflows for test + lint

**Files:**
- Create: `.github/workflows/test.yml`
- Create: `.github/workflows/lint.yml`

- [ ] **Step 1: Create `.github/workflows/test.yml`**

```yaml
name: Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: ci_emails
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e .[dev]

      - name: Run tests with coverage
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/ci_emails
          SKIP_INTEGRATION_TESTS: "0"
        run: pytest --cov --cov-report=xml --cov-report=term

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml
          fail_ci_if_error: false
```

- [ ] **Step 2: Create `.github/workflows/lint.yml`**

```yaml
name: Lint

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e .[dev]

      - name: Ruff check
        run: ruff check ci_email_scraper tests

      - name: Ruff format check
        run: ruff format --check ci_email_scraper tests

      - name: Mypy
        run: mypy ci_email_scraper
```

- [ ] **Step 3: Run lint locally first to catch issues before push**

```bash
ruff check ci_email_scraper tests
ruff format --check ci_email_scraper tests
mypy ci_email_scraper
```

Fix any reported issues before committing. If `mypy` complains about missing type stubs, install them or add to ignore_missing_imports in pyproject.toml.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/test.yml .github/workflows/lint.yml
git commit -m "feat: GitHub Actions CI for tests + lint"
```

---

# Phase 10 — README + Final Verification

### Task 13: README.md with story + Mermaid diagram

**Files:**
- Modify: `README.md` (overwrites the existing placeholder)

- [ ] **Step 1: Overwrite `README.md`**

```markdown
# ci-email-scraper

![Tests](https://github.com/Jamil1016/gmail-scraper/actions/workflows/test.yml/badge.svg)
![Lint](https://github.com/Jamil1016/gmail-scraper/actions/workflows/lint.yml/badge.svg)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Open-source reference implementation of the "HTML email → JSONB" pattern, using synthetic CI/CD build notifications (GitHub Actions, CircleCI, Jenkins) as the demo domain.

## The Pattern

CI/CD platforms email a build summary on every job. These emails are searchable in your inbox but useless once you want trends, cross-repo views, or programmatic analysis. This repo demonstrates the parser pattern that turns those emails into queryable structured data — without committing to a fixed schema that breaks every time the email format changes.

The same pattern, against real Gmail at production scale, runs in a private repo at my employer. This is a clean-room implementation against synthetic CI/CD emails so the architecture is verifiable.

## Architecture

```mermaid
graph LR
  F[fixtures/*.eml] --> P[parser.parse_email]
  P --> H[patterns.match_vendor]
  H --> E[Vendor extractor<br/>GHA / CircleCI / Jenkins]
  E --> D[db.upsert_parsed]
  D --> PG[(Postgres<br/>ci_builds.fields JSONB)]
  PG --> Q[cli.query]
```

Three core moves:
1. **Ordered header patterns** identify the CI vendor from subject + From-header. Longer/more-specific patterns are checked first to avoid prefix collisions.
2. **Hidden-span removal + word-rejoin** cleans up tracking pixel spans that `BeautifulSoup.get_text()` would otherwise split words across.
3. **Dynamic JSONB column** absorbs vendor-specific fields without schema migration.

## Quick Start

```bash
git clone https://github.com/Jamil1016/gmail-scraper
cd gmail-scraper
docker compose up -d
pip install -e .
cp .env.example .env  # default DATABASE_URL works with docker-compose
python -m ci_email_scraper init-db
python -m ci_email_scraper run
python -m ci_email_scraper query --status failure
```

## How It Works

See `ci_email_scraper/parser.py` for the parser core, `patterns.py` for vendor detection, `db.py` for the asyncpg-based upsert layer.

## Tests

```bash
pytest                              # all tests
SKIP_INTEGRATION_TESTS=1 pytest     # unit only (no Postgres container needed)
pytest --cov                        # with coverage
```

| Test file | Covers |
|---|---|
| `test_patterns.py` | Vendor detection + prefix disambiguation |
| `test_dirty_html.py` | Hidden-span removal + word rejoin |
| `test_parser.py` | Full per-vendor parse against fixtures |
| `test_upsert.py` | Idempotency + JSONB round-trip (testcontainers) |
| `test_cli.py` | CLI argument parsing + command dispatch |

## Background

I built this pattern at scale at $WORK (private repo). The case study with production metrics is at:
**https://portfolio-gules-gamma-14.vercel.app/projects/gmail-scraper**

## License

MIT
```

- [ ] **Step 2: Verify build hasn't broken**

```bash
pytest
ruff check ci_email_scraper tests
ruff format --check ci_email_scraper tests
mypy ci_email_scraper
```

Expected: all green.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: replace placeholder README with full project documentation"
```

---

### Task 14: End-to-end verification + push + verify CI

**Files:** (none — verification only)

- [ ] **Step 1: Full local smoke**

```bash
docker compose down -v  # clean slate
docker compose up -d
sleep 5
python -m ci_email_scraper init-db
python -m ci_email_scraper run
python -m ci_email_scraper query --status failure --limit 10
python -m ci_email_scraper query --vendor circleci --limit 10
python -m ci_email_scraper run  # second time — should report duplicates
docker compose down
```

Expected:
- First run: `Ingested 18 emails (18 new, 0 duplicates)`
- Query failure: prints rows with status=failure
- Second run: `Ingested 18 emails (0 new, 18 duplicates)`

- [ ] **Step 2: Push to `main`**

The current branch is `main`. `gh` defaults to the work account; switch to personal first:

```bash
gh auth switch -u Jamil1016
git push origin main
gh auth switch -u jamilmendez-ontel
```

- [ ] **Step 3: Verify GHA workflows pass**

Open `https://github.com/Jamil1016/gmail-scraper/actions` in a browser. The `Tests` and `Lint` workflows should run on the push. Wait for both to go green (~2–3 min). If either fails:
- Read the workflow logs
- Fix the issue locally
- Push the fix

- [ ] **Step 4: Update the portfolio case study to flip `publicRepoStatus`**

Now that the repo has working code, update the portfolio's `lib/projects.ts` to flip the `gmail-scraper` entry from `"coming"` to `"live"`. This is a separate small commit on the portfolio repo.

```bash
cd "C:\Users\admin\Desktop\Projects\personal\portfolio"
# Edit lib/projects.ts: change publicRepoStatus: "coming" to "live" for gmail-scraper
# Also delete publicEtaWeek for that entry
```

Then commit + push to main:

```bash
git add lib/projects.ts
git commit -m "feat: flip gmail-scraper status from 'coming' to 'live'"
gh auth switch -u Jamil1016
git push origin main
gh auth switch -u jamilmendez-ontel
```

Vercel auto-deploys; case study page on the portfolio loses the "Open-source reference implementation coming W3" text and the bento tile loses the "OSS · W3" badge.

- [ ] **Step 5: Final acceptance checklist (manual)**

- [ ] `https://github.com/Jamil1016/gmail-scraper` README badges show green Tests + Lint
- [ ] `https://github.com/Jamil1016/gmail-scraper` README renders with Mermaid diagram
- [ ] Clone repo to a fresh directory and run the Quick Start commands end-to-end — works first time
- [ ] Portfolio `/projects/gmail-scraper` shows "live" status and the bento tile no longer has "OSS · W3"
- [ ] Sanitization sweep: `grep -ri "ontel\|nanoninth\|AT&T\|T-Mobile\|Verizon\|jamil.mendez@ontel.co\|FA[0-9]\|NNI" ci_email_scraper/ tests/ fixtures/ README.md` returns no matches

If all check, commit an empty "milestone" commit:

```bash
cd "C:\Users\admin\Desktop\Projects\personal\gmail-scraper"
git commit --allow-empty -m "milestone: v0.1.0 shipped — first clean-room repo of six"
gh auth switch -u Jamil1016
git push origin main
gh auth switch -u jamilmendez-ontel
```

---

## Self-Review

### Spec coverage

| Spec section | Implemented by |
|---|---|
| §1 Summary — runnable, sanitized, dogfooded with CI | All tasks combined |
| §2 Goals: runnable end-to-end | Tasks 1, 11, 14 |
| §2 Goals: ordered header patterns + dynamic JSONB + idempotent upserts | Tasks 3, 8, 10 |
| §2 Goals: ≥15 fixtures across 3 vendors | Tasks 5, 6, 7 (18 total) |
| §2 Goals: pytest ≥80% coverage | Tasks 3, 4, 8, 10, 11 |
| §2 Goals: GHA on the public repo | Task 12 |
| §2 Goals: README + portfolio backlink | Task 13 |
| §2 Goals: no employer/customer terms | Sanitization check in Task 14 |
| §3 Domain — 3 CI vendors | Tasks 5, 6, 7 |
| §4 Architecture (fixtures → parser → DB → CLI) | Tasks 1, 8, 9, 10, 11 |
| §5 Repo structure | All tasks combined; final state matches the spec |
| §6 Parser design — ParsedEmail, _clean_html, vendor extractors, _stable_id | Tasks 2, 4, 8 |
| §7 18 fixtures, 6 per vendor | Tasks 5, 6, 7 |
| §8 Postgres schema + indexes | Task 1 (schema.sql) |
| §9 CLI surface (run / query / init-db) | Task 11 |
| §10 Tests (5 files) | Tasks 3, 4, 8, 10, 11 |
| §11 GHA workflows (test + lint) | Task 12 |
| §12 README template | Task 13 |
| §13 Success criteria 1–8 | Task 14 |

### Placeholder scan

No "TBD" / "TODO" / "implement later" markers in the plan. Every code block contains complete, runnable code. Every command has explicit expected output. The "rare variant" fixture descriptions in Tasks 5–7 are conceptual labels but each fixture has fully-spelled-out content.

### Type consistency

- `ParsedEmail` TypedDict defined in Task 2, consumed in Tasks 8, 10, 11
- `RawEmail` dataclass defined in Task 2, consumed in Tasks 9, 11
- `ParseError` defined in Task 2, raised in Task 8 vendor extractors, tested in Task 8
- `match_vendor(subject, from_addr, body_html)` signature defined in Task 3, called from `parse_email` in Task 8
- `create_pool`, `init_schema`, `upsert_parsed`, `query_builds` defined in Task 10, called from CLI in Task 11
- `load_fixture_dir(root)` defined in Task 9, called from CLI in Task 11
- CLI's `cli_entry` wired up in `pyproject.toml` after Task 11 (Task 11 Step 5 fixes the original wrong target `cli:main`)

One subtle inconsistency to flag: Task 1 Step 3's `pyproject.toml` puts `ci_email_scraper.cli:main` as the script target, but `main` is an async function — calling it from `[project.scripts]` would error. Task 11 Step 5 fixes this to `cli_entry`. An engineer reading the plan in order won't hit the error; one skipping around might. Both versions of the line are explicit so the fix is unambiguous.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-22-gmail-scraper-clean-room.md`.

Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — I execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
