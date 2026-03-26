# vecgate/tests/test_cli.py
from typer.testing import CliRunner
from vecgate.cli.main import app
import os

runner = CliRunner()
DB_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost/vecgate_test")


def test_init_help():
    """Verify init command is registered and shows help."""
    result = runner.invoke(app, ["init", "--help"])
    assert result.exit_code == 0
    assert "db-url" in result.output.lower()


def test_facet_help():
    """Verify facet subcommand is registered."""
    result = runner.invoke(app, ["facet", "--help"])
    assert result.exit_code == 0
    assert "create" in result.output.lower()


def test_status_help():
    """Verify status command is registered."""
    result = runner.invoke(app, ["status", "--help"])
    assert result.exit_code == 0


def test_app_help():
    """Verify root help shows all commands."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "facet" in result.output
    assert "role" in result.output
    assert "group" in result.output
    assert "init" in result.output
    assert "status" in result.output
    assert "serve" in result.output
