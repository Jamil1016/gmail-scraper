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
