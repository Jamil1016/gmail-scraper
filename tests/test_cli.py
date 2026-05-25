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
        with (
            patch("ci_email_scraper.cli.create_pool", new_callable=AsyncMock) as create_pool_mock,
            patch("ci_email_scraper.cli.upsert_parsed", new_callable=AsyncMock) as upsert_mock,
            patch("ci_email_scraper.cli.load_fixture_dir") as load_mock,
        ):
            load_mock.return_value = []
            upsert_mock.return_value = 0
            create_pool_mock.return_value.close = AsyncMock()

            exit_code = await main(["run", "--fixtures", "fixtures"])
            assert exit_code == 0
            upsert_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_command_calls_query_builds(self) -> None:
        with (
            patch("ci_email_scraper.cli.create_pool", new_callable=AsyncMock) as create_pool_mock,
            patch("ci_email_scraper.cli.query_builds", new_callable=AsyncMock) as query_mock,
        ):
            query_mock.return_value = []
            create_pool_mock.return_value.close = AsyncMock()

            exit_code = await main(["query", "--vendor", "github_actions"])
            assert exit_code == 0
            query_mock.assert_called_once()
