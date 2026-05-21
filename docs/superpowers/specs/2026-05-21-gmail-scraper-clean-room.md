# Clean-Room gmail-scraper — Design Spec

**Date:** 2026-05-21
**Owner:** Jamil Mendez (`Jamil1016` on GitHub)
**Status:** Approved for implementation planning
**Context:** First of six clean-room reference implementations (Sub-project B of the portfolio expansion). The production version operates privately at scale against real Gmail; this repo is the open-source pattern-demo on synthetic data.

**Cross-references:**
- Portfolio case study: https://portfolio-gules-gamma-14.vercel.app/projects/gmail-scraper
- Pattern source: production work on private repo (`jamilmendez-ontel/gmail-scraper`)

---

## 1. Summary

A working open-source Python implementation of the "HTML email → JSONB" pattern using **synthetic CI/CD build notifications** as the demo domain. Parses fixture `.eml` files from three CI vendors (GitHub Actions, CircleCI, Jenkins), normalizes their fields into a dynamic JSONB schema, upserts into Postgres, and exposes a CLI for querying. Same architectural pattern as the production system; entirely new domain and codebase. Demonstrates senior-IC-level engineering on a runnable, dogfooded repo with green CI.

---

## 2. Goals & Non-Goals

### Goals
- Runnable end-to-end on a fresh machine: `git clone && docker compose up && python -m ci_email_scraper run`
- Demonstrates the **ordered header pattern matching** + **dynamic JSONB schema** + **idempotent upserts** patterns from production
- ≥ 15 synthetic `.eml` fixtures across 3 CI vendors
- pytest suite with ≥ 80% coverage on `parser.py` + `patterns.py`
- GitHub Actions CI on the public repo running tests on every push (green badge in README)
- README that frames the pattern + links back to portfolio case study
- Zero references to production employer / customers / proprietary terms

### Non-Goals (v1)
- Real Gmail API integration — fixture-driven only
- Web dashboard / UI (deferred, possibly never)
- Email notification / alert system on parsed results
- Excel / CSV export
- Vector search or semantic indexing over parsed fields
- Multi-account / multi-tenant support
- Cloud deployment instructions (the repo is a pattern reference, not a SaaS)
- Real-time stream processing (Gmail push notifications, etc.)

---

## 3. Domain — CI/CD Build Notifications

The repo simulates emails sent by CI/CD platforms summarizing build results. Three vendors are simulated to demonstrate that the same parser absorbs format variation:

| Vendor | Distinctive characteristics |
|---|---|
| **GitHub Actions** | Subject contains `[<repo>]`, body uses `<table>` for build summary, status conveyed by emoji + text |
| **CircleCI** | Subject pattern `Project X: build #N`, body has a colored status banner, fields in flat key-value pairs |
| **Jenkins** | Subject is `Build #N` with project name, body is plain-text-ish with `<pre>` blocks, fields formatted as labels with colons |

This diversity proves the value of the pattern: a single parser with vendor-aware header patterns and a dynamic JSONB schema absorbs all three without per-vendor extraction code.

---

## 4. Architecture

```
fixtures/*.eml  →  fixtures.load()  →  parser.parse()  →  db.upsert()  →  Postgres (ci_builds.fields JSONB)
                                              ↑                                       ↓
                                    patterns.match_vendor()             cli.query() → SQL → results
```

- **Synchronous parsing** — no async needed for the parser itself; `.eml` files load fast
- **Async DB layer** — `asyncpg` pool, matches production pattern, supports future scaling
- **CLI wrapper** — `__main__.py` calls into `cli.py` with `argparse` subcommands; CLI handles the sync/async bridge

Single Python package. No microservices. No frameworks beyond the standard library plus three core deps: `beautifulsoup4`, `asyncpg`, `python-dotenv`.

---

## 5. Repository Layout

```
gmail-scraper/                                  # repo root (Jamil1016/gmail-scraper)
├── ci_email_scraper/
│   ├── __init__.py                             # version, exports
│   ├── __main__.py                             # python -m ci_email_scraper entry
│   ├── cli.py                                  # argparse subcommands: run, query
│   ├── parser.py                               # parse_email(html: str) -> ParsedEmail
│   ├── patterns.py                             # ordered header patterns per vendor
│   ├── fixtures.py                             # load_fixture_dir(path) -> Iterator[RawEmail]
│   ├── db.py                                   # asyncpg pool + upsert
│   ├── schema.sql                              # CREATE TABLE migration
│   └── types.py                                # ParsedEmail TypedDict, RawEmail dataclass
├── fixtures/
│   ├── github_actions/
│   │   ├── success-main-deploy.eml
│   │   ├── success-pr-merged.eml
│   │   ├── failure-broken-tests.eml
│   │   ├── failure-build-error.eml
│   │   ├── cancelled-superseded.eml
│   │   └── matrix-build-mixed.eml              # rare variant
│   ├── circleci/
│   │   ├── success-main.eml
│   │   ├── success-feature-branch.eml
│   │   ├── failure-linter.eml
│   │   ├── failure-flaky-test.eml
│   │   ├── cancelled-manual.eml
│   │   └── parallel-job-failure.eml            # rare variant
│   └── jenkins/
│       ├── success-nightly.eml
│       ├── success-release.eml
│       ├── failure-compile.eml
│       ├── failure-deploy.eml
│       ├── aborted-timeout.eml
│       └── multi-stage-partial.eml             # rare variant
├── tests/
│   ├── __init__.py
│   ├── conftest.py                             # fixtures: postgres testcontainer, sample emails
│   ├── test_patterns.py                        # vendor detection, no cross-vendor false positives
│   ├── test_parser.py                          # per-vendor full-parse assertions
│   ├── test_dirty_html.py                      # hidden spans, word-split rejoin, dirty dates
│   ├── test_upsert.py                          # idempotency: re-run produces same row count
│   └── test_cli.py                             # smoke test of run + query commands
├── .github/
│   └── workflows/
│       ├── test.yml                            # CI: pytest + coverage on push/PR
│       └── lint.yml                            # ruff + mypy
├── .env.example                                # DATABASE_URL template
├── .gitignore
├── docker-compose.yml                          # Postgres 16 service
├── pyproject.toml                              # PEP 621, ruff config, mypy config
├── README.md                                   # story + Mermaid diagram + quick-start
└── LICENSE                                     # MIT
```

Each file has one clear responsibility:
- `parser.py` is pure HTML → dict logic, no IO, fully testable in isolation
- `patterns.py` is the ordered pattern list — single source of truth for vendor detection
- `fixtures.py` walks the filesystem; no parsing
- `db.py` owns the asyncpg pool and the upsert SQL
- `cli.py` glues them together
- `types.py` centralizes the data contracts

---

## 6. Parser Design

### 6.1 Input

`parse_email(html: str, subject: str, received_at: datetime) -> ParsedEmail`

The function takes the raw email HTML, subject line, and received timestamp. Returns a `ParsedEmail` TypedDict.

### 6.2 Output shape — `ParsedEmail`

```python
class ParsedEmail(TypedDict):
    vendor: str              # "github_actions" | "circleci" | "jenkins" | "unknown"
    message_id: str          # stable hash for dedup
    build_id: str            # required if vendor != "unknown"
    status: str              # "success" | "failure" | "cancelled" | "unknown"
    received_at: datetime
    fields: dict[str, Any]   # everything else dynamic
```

Required top-level keys: `vendor`, `message_id`, `received_at`. `build_id` and `status` are required when `vendor != "unknown"` (asserted in tests).

### 6.3 Pipeline

Vendor detection (`patterns.match_vendor`) inspects the subject line first (more discriminating in practice — `[owner/repo]` for GHA, `Project X: build #N` for CircleCI, `Build #N — project` for Jenkins), then falls back to From-header domain (`noreply@github.com`, `noreply@circleci.com`, `jenkins@*`) if the subject is ambiguous. Patterns are checked in defined order (longer/more-specific first) to avoid prefix collisions.

```python
def parse_email(html, subject, received_at):
    # 1. Detect vendor from ordered header patterns (longer/more-specific first)
    vendor = patterns.match_vendor(subject, html)
    if vendor == "unknown":
        return _unknown_email(html, subject, received_at)

    # 2. Clean HTML: remove tracking spans, rejoin split words
    cleaned_text = _clean_html(html)

    # 3. Vendor-specific field extraction (each vendor has its own extractor)
    extractor = EXTRACTORS[vendor]
    fields = extractor.extract(cleaned_text, html, subject)

    # 4. Compute stable message_id
    message_id = _stable_id(subject, fields.get("build_id", ""), received_at)

    # 5. Assemble ParsedEmail
    return ParsedEmail(
        vendor=vendor,
        message_id=message_id,
        build_id=fields.pop("build_id"),
        status=fields.pop("status"),
        received_at=received_at,
        fields=fields,  # everything else flows into JSONB
    )
```

### 6.4 `_clean_html`

```python
def _clean_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    # Strip zero-width / 1pt tracking spans
    for span in soup.find_all("span", style=re.compile(r"font-size:\s*[01]p?[tx]?")):
        span.decompose()
    # Strip <script> and <style>
    for tag in soup.find_all(["script", "style"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    # Rejoin single uppercase letters that BS split apart
    text = re.sub(r"\b([A-Z])\s([a-z])", r"\1\2", text)
    return text
```

Same algorithm as production. Lifted intact.

### 6.5 Vendor extractors

Each vendor gets its own extractor class in `parser.py` (kept in one file for v1 — split per file if `parser.py` grows past ~300 lines):

```python
class GitHubActionsExtractor:
    @staticmethod
    def extract(text: str, html: str, subject: str) -> dict[str, Any]:
        # Subject: "[owner/repo] Build #123 — success"
        m = re.search(r"\[([\w-]+/[\w.-]+)\]\s+Build\s+#(\d+)\s+—\s+(\w+)", subject)
        if not m:
            raise ParseError("github_actions subject pattern not matched")
        return {
            "repo": m.group(1),
            "build_id": m.group(2),
            "status": m.group(3).lower(),
            "branch": _extract_after_label(text, "Branch:"),
            "commit_sha": _extract_after_label(text, "Commit:")[:7],
            "duration_seconds": _parse_duration(_extract_after_label(text, "Duration:")),
            "actor": _extract_after_label(text, "Triggered by:"),
            # vendor-specific dynamic fields go into fields dict
        }
```

CircleCI and Jenkins follow the same shape. Each extractor is self-contained and unit-tested.

### 6.6 `_stable_id`

```python
def _stable_id(subject: str, build_id: str, received_at: datetime) -> str:
    raw = f"{subject}|{build_id}|{received_at.isoformat()}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]
```

16-char MD5 hex. Stable across re-runs of the same fixture; collision-resistant enough for a portfolio-scale demo.

---

## 7. Fixture Taxonomy

18 fixtures total (6 per vendor). Each `.eml` file:
- Realistic HTML body (not stripped-down — includes the tracking spans, tables, styling that real emails have)
- Realistic subject line
- `Date:` header set to a sensible recent timestamp (last 30 days)
- `From:` header from the right vendor domain (`noreply@github.com`, `noreply@circleci.com`, `jenkins@example.com`)

Per vendor, the 6 fixtures cover:
1. **Success on main branch** — full happy path field set
2. **Success on PR / feature branch** — slightly different field set (PR-specific keys)
3. **Failure — failed tests** — populates `failed_tests` array
4. **Failure — build/compile error** — different failure shape (no test array, just stderr snippet)
5. **Cancelled / aborted** — minimal field set
6. **Rare variant** — matrix build (GHA), parallel job (CircleCI), multi-stage pipeline (Jenkins) — exercises dynamic JSONB by introducing keys not present elsewhere

Fixtures are committed verbatim to the repo. Anyone running tests gets reproducible parses.

---

## 8. Data Model — Postgres

```sql
-- ci_email_scraper/schema.sql
create table if not exists ci_builds (
  message_id    text primary key,
  vendor        text not null,
  build_id      text not null,
  status        text not null,
  fields        jsonb not null,
  received_at   timestamptz not null,
  created_at    timestamptz not null default now()
);

create index if not exists ci_builds_repo_idx on ci_builds ((fields->>'repo'));
create index if not exists ci_builds_vendor_received_idx on ci_builds (vendor, received_at desc);
create index if not exists ci_builds_status_idx on ci_builds (status);
```

**Upsert:** `INSERT ... ON CONFLICT (message_id) DO NOTHING`. Re-running ingestion is free.

**No migrations framework.** v1 uses raw SQL applied once. Future versions may add Alembic if the schema grows; YAGNI now.

---

## 9. CLI Surface

```
python -m ci_email_scraper run [--fixtures PATH]
python -m ci_email_scraper query [--vendor V] [--status S] [--repo R] [--branch B] [--limit N]
python -m ci_email_scraper init-db                    # apply schema.sql
python -m ci_email_scraper --help
```

### `run`
- Default `--fixtures` points to `./fixtures/`
- Walks the directory, calls `parse_email`, upserts each result
- Prints `Ingested N emails (M new, K duplicates)` on completion

### `query`
- Builds a parameterized SQL query from flags
- Prints results as a readable table (use `rich` or hand-rolled; prefer hand-rolled to keep deps minimal)
- Supports combining flags (`--status failure --vendor circleci`)

### `init-db`
- Applies `schema.sql` against the configured `DATABASE_URL`
- Idempotent (uses `IF NOT EXISTS`)

The CLI uses `argparse` only — no Click / Typer. Keeps deps tight.

---

## 10. Testing

### Test files & their responsibilities

| File | Responsibility | Coverage target |
|---|---|---|
| `test_patterns.py` | `match_vendor()` correctly identifies each fixture; no false positives across vendors | 100% of `patterns.py` |
| `test_parser.py` | Per-vendor full-parse assertions: required fields present, dynamic fields land in `fields` dict | ≥ 90% of `parser.py` |
| `test_dirty_html.py` | Hidden-span removal, word rejoin, dirty date variants (two-digit years, placeholders, embedded spaces) | covers `_clean_html` edge cases |
| `test_upsert.py` | Running ingestion twice produces same row count; corrupted fixture doesn't break the run; transaction rollback on error | covers `db.py` |
| `test_cli.py` | Smoke test: `run` + `query` with mocked DB layer; no real Postgres needed | covers `cli.py` happy path |

### Postgres for integration tests

`test_upsert.py` uses `testcontainers-postgres` to spin up a real Postgres in Docker for the test session. Slower than a mock but proves the upsert behavior on a real database. GHA workflow uses a `services: postgres` block to provide the DB without Docker-in-Docker.

### TDD discipline

For each implementation file, the corresponding test file is written first. Implementation lands only after tests fail for the right reason.

### Coverage

`pytest-cov` reports per-file. Target ≥ 80% on `parser.py` + `patterns.py` + `db.py`. CI fails if coverage drops below threshold.

---

## 11. CI on the Public Repo

### `.github/workflows/test.yml`

Triggers: `push` to any branch, `pull_request` to `main`.

Steps:
1. Checkout
2. Set up Python 3.12
3. Install dev deps via `pip install -e .[dev]`
4. Run pytest with coverage
5. (Optional) Upload coverage to Codecov

Postgres provided as a service container in the workflow (no testcontainers in CI — services block is faster and simpler).

### `.github/workflows/lint.yml`

Same triggers.
Steps: `ruff check` + `ruff format --check` + `mypy ci_email_scraper`.

### README badges

Two badges at the top of README.md:
- Test status (from `test.yml`)
- License (MIT)

Both auto-generated by GitHub Actions / Shields.io.

---

## 12. README Structure

Tight, scannable, hiring-friendly:

```markdown
# ci-email-scraper

![Tests](badge) ![License: MIT](badge)

> Open-source reference implementation of the "HTML email → JSONB" pattern,
> using synthetic CI/CD build notifications as the demo domain.

[Optional: 30-second terminal recording / asciinema GIF showing `python -m ci_email_scraper run`]

## The pattern

CI/CD platforms email a build summary on every job. These emails are searchable
in your inbox but useless once you want trends, cross-repo views, or programmatic
analysis. This repo demonstrates the parser pattern that turns those emails into
queryable structured data — without committing to a fixed schema that breaks
every time the email format changes.

The same pattern, against real Gmail at production scale, is in a private repo
at my employer. This is a clean-room implementation against synthetic CI/CD
emails so the architecture is verifiable.

## Architecture

[Mermaid diagram — same shape as the portfolio case study]

## Quick start

git clone https://github.com/Jamil1016/gmail-scraper
cd gmail-scraper
docker compose up -d
pip install -e .
python -m ci_email_scraper init-db
python -m ci_email_scraper run
python -m ci_email_scraper query --status failure

## How it works

Three core moves:
1. Ordered header patterns identify the vendor (longer-prefix patterns first
   to avoid `CLOSE OUT PACKAGE` matching `LANDLORD CLOSE OUT PACKAGE`)
2. Hidden span removal + word-rejoin cleans up tracking pixel spans that
   `get_text()` would otherwise split words across
3. Dynamic JSONB column absorbs vendor-specific fields without schema migration

See `ci_email_scraper/parser.py` for the implementation.

## Tests

pytest

[brief table of what each test file covers]

## Background

I built this pattern at scale at $WORK (private repo). The case study with
real production metrics is at:
https://<portfolio>/projects/gmail-scraper

## License

MIT
```

Total length target: under 150 lines including code blocks. Scannable in 30 seconds, runnable in 2 minutes.

---

## 13. Success Criteria

1. `git clone && docker compose up -d && pip install -e . && python -m ci_email_scraper init-db && python -m ci_email_scraper run` works on a fresh machine
2. All five test files green via `pytest`
3. Coverage on `parser.py`, `patterns.py`, `db.py` each ≥ 80%
4. `.github/workflows/test.yml` shows green on the README badge
5. README ≤ 200 lines (including Mermaid + code blocks)
6. 18 fixtures committed (6 per vendor × 3 vendors)
7. No mention of employer / customer / proprietary terms anywhere in the repo
8. The portfolio case study at `/projects/gmail-scraper` has a working `Read repo →` link to this repo

---

## 14. Out of Scope (Future Work)

| Feature | Why deferred |
|---|---|
| Real Gmail API integration | Production system has it; clean-room version is pattern-focused, not infra-focused |
| Web dashboard | Belongs in Sub-project C (live demos), not the OSS pattern repo |
| Alembic migrations | YAGNI for a single-table demo |
| Vector / semantic search | Not part of the gmail-scraper pattern |
| Multi-tenant / multi-account | Demo scope, not product scope |
| Async parser | Parser is fast enough sync; async DB layer is what matters |
| Mocked Gmail server for integration tests | Fixtures cover the same ground |
| Excel / CSV export | Generic tooling; out of pattern scope |

---

## 15. Open Questions (resolve during implementation)

- **Coverage badge:** Codecov vs. shields.io static — defer to implementation
- **License file template:** standard MIT — copy-paste from `choosealicense.com`
- **Terminal recording:** `vhs` (Charm) vs. `asciinema` vs. skip the GIF entirely — pick during README polish
- **Python version floor:** 3.12 (modern) or 3.10 (broader compatibility) — recommend 3.12 since this is a demo repo, no need to support legacy

These don't block the implementation plan.

---

## 16. Why This Spec Exists

This is the first of six clean-room implementations. The spec serves as both the design contract for this repo AND the template for the remaining five (pipeline-guardian W8, DARA W10, date-validator W11, report-automation W5, local-pipeline W12). Each subsequent spec will mirror this structure: synthetic domain → architecture preserved from production → repo scaffolding → testing → CI → README story → link back to portfolio case study.
