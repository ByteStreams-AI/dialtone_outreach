from click.testing import CliRunner
import inspect

from cli import cli
from lead_tools import Lead, collect_leads


def test_lead_tools_package_exposes_basic_api() -> None:
    assert inspect.isclass(Lead)
    assert callable(collect_leads)


def test_cli_status_command() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["status"])

    assert result.exit_code == 0
    assert "lead discovery" in result.output.lower()
