"""Tests for version command."""

from click.testing import CliRunner

from cli import main
from discord_chat.commands.version import get_version


def test_version_command():
    """Test that version command runs successfully."""
    runner = CliRunner()
    result = runner.invoke(main, ["version"])
    assert result.exit_code == 0
    assert "version" in result.output.lower()


def test_get_version():
    """Test that get_version returns a valid version string."""
    version = get_version()
    assert version is not None
    assert version != "unknown"
