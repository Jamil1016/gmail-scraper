"""Command-line interface — argparse with run / query / init-db subcommands."""

from __future__ import annotations

import argparse
import asyncio
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
