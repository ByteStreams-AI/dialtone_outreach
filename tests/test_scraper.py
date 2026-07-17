from click.testing import CliRunner
from cli import cli
from scraper.fetch import fetch_page
from scraper.parser import parse_listing_page
from scraper.models import LeadItem


def test_imports() -> None:
    assert fetch_page
    assert parse_listing_page
    assert LeadItem


def test_cli_status_command() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["status"])

    assert result.exit_code == 0
    assert "lead discovery" in result.output.lower()
