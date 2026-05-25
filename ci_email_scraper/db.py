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
        rows: list[asyncpg.Record] = await conn.fetch(sql, *params)
        return rows
