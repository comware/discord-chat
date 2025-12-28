"""Tests for CLI flags and main command."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from cli import main
from discord_chat.services.discord_client import ChannelMessages, ServerDigestData
from discord_chat.services.llm.base import LLMProvider


def create_sample_data() -> ServerDigestData:
    """Create sample server data for testing."""
    end_time = datetime.now(UTC)
    start_time = end_time - timedelta(hours=6)

    return ServerDigestData(
        server_name="Test Server",
        server_id=123456789,
        channels=[
            ChannelMessages(
                channel_name="general",
                channel_id=111,
                messages=[
                    {
                        "id": 1,
                        "author": "Alice",
                        "author_id": 1001,
                        "content": "Hello!",
                        "timestamp": "2024-01-01T12:00:00",
                        "attachments": [],
                        "reactions": [],
                    },
                ],
            ),
        ],
        start_time=start_time,
        end_time=end_time,
        total_messages=1,
    )


class TestMainCLI:
    """Tests for main CLI command."""

    def test_version_flag(self):
        """Test --version flag displays version."""
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])

        assert result.exit_code == 0
        assert "discord-chat" in result.output
        assert "version" in result.output.lower()

    def test_help_flag(self):
        """Test --help flag displays help."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "discord-chat" in result.output
        assert "--version" in result.output
        assert "--debug" in result.output
        assert "digest" in result.output
        assert "activity" in result.output

    def test_debug_flag_exists(self):
        """Test --debug flag is recognized."""
        runner = CliRunner()
        result = runner.invoke(main, ["--debug", "--help"])

        assert result.exit_code == 0


class TestDigestDryRun:
    """Tests for digest --dry-run flag."""

    @patch("discord_chat.commands.digest.fetch_server_messages")
    @patch("discord_chat.commands.digest.get_provider")
    @patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "test-token"})
    def test_dry_run_no_llm_call(self, mock_get_provider, mock_fetch):
        """Test --dry-run does not call LLM."""
        mock_fetch.return_value = create_sample_data()
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.name = "TestLLM"
        mock_get_provider.return_value = mock_provider

        runner = CliRunner()
        result = runner.invoke(main, ["digest", "test-server", "--dry-run"])

        assert result.exit_code == 0
        assert "[DRY RUN]" in result.output
        assert "Preview" in result.output
        # LLM should not be called
        mock_provider.generate_digest.assert_not_called()

    @patch("discord_chat.commands.digest.fetch_server_messages")
    @patch("discord_chat.commands.digest.get_provider")
    @patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "test-token"})
    def test_dry_run_shows_preview_info(self, mock_get_provider, mock_fetch):
        """Test --dry-run shows useful preview information."""
        mock_fetch.return_value = create_sample_data()
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.name = "TestLLM"
        mock_get_provider.return_value = mock_provider

        runner = CliRunner()
        result = runner.invoke(main, ["digest", "test-server", "--dry-run"])

        assert result.exit_code == 0
        assert "Server:" in result.output
        assert "Channels:" in result.output
        assert "Messages:" in result.output
        assert "LLM provider:" in result.output
        assert "Estimated prompt size:" in result.output
        # Without --file flag, it should indicate screen output
        assert "Would display digest to screen" in result.output
        assert "No API calls made" in result.output

    @patch("discord_chat.commands.digest.fetch_server_messages")
    @patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "test-token"})
    def test_dry_run_no_messages(self, mock_fetch):
        """Test --dry-run with no messages still exits cleanly."""
        mock_fetch.return_value = ServerDigestData(
            server_name="Empty Server",
            server_id=1,
            channels=[],
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
            total_messages=0,
        )

        runner = CliRunner()
        result = runner.invoke(main, ["digest", "test-server", "--dry-run"])

        assert result.exit_code == 0
        assert "No messages found" in result.output


class TestDigestQuiet:
    """Tests for digest --quiet flag."""

    @patch("discord_chat.commands.digest.fetch_server_messages")
    @patch("discord_chat.commands.digest.get_provider")
    @patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "test-token"})
    def test_quiet_suppresses_console_output(self, mock_get_provider, mock_fetch):
        """Test --quiet suppresses console output."""
        mock_fetch.return_value = create_sample_data()
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.name = "TestLLM"
        mock_provider.generate_digest.return_value = "# Test Digest"
        mock_get_provider.return_value = mock_provider

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["digest", "test-server", "--quiet", "--file", "."])

        assert result.exit_code == 0
        # Should not have verbose output
        assert "Fetching messages" not in result.output
        assert "Found" not in result.output
        # Digest content should not be printed
        assert "Test Digest" not in result.output

    @patch("discord_chat.commands.digest.fetch_server_messages")
    @patch("discord_chat.commands.digest.get_provider")
    @patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "test-token"})
    def test_quiet_still_writes_file(self, mock_get_provider, mock_fetch):
        """Test --quiet still writes output file."""
        mock_fetch.return_value = create_sample_data()
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.name = "TestLLM"
        mock_provider.generate_digest.return_value = "# Test Digest"
        mock_get_provider.return_value = mock_provider

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["digest", "test-server", "--quiet", "--file", "."])

            assert result.exit_code == 0
            # Check that a file was created
            import os

            files = os.listdir(".")
            digest_files = [f for f in files if f.startswith("digest-") and f.endswith(".md")]
            assert len(digest_files) == 1

    @patch("discord_chat.commands.digest.fetch_server_messages")
    @patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "test-token"})
    def test_quiet_no_messages_silent(self, mock_fetch):
        """Test --quiet is silent even with no messages."""
        mock_fetch.return_value = ServerDigestData(
            server_name="Empty Server",
            server_id=1,
            channels=[],
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
            total_messages=0,
        )

        runner = CliRunner()
        result = runner.invoke(main, ["digest", "test-server", "--quiet"])

        assert result.exit_code == 0
        # Output should be empty or minimal
        assert len(result.output.strip()) == 0 or "No messages" not in result.output


class TestDigestQuietShortFlag:
    """Tests for digest -q short flag."""

    @patch("discord_chat.commands.digest.fetch_server_messages")
    @patch("discord_chat.commands.digest.get_provider")
    @patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "test-token"})
    def test_short_quiet_flag(self, mock_get_provider, mock_fetch):
        """Test -q works same as --quiet."""
        mock_fetch.return_value = create_sample_data()
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.name = "TestLLM"
        mock_provider.generate_digest.return_value = "# Test Digest"
        mock_get_provider.return_value = mock_provider

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["digest", "test-server", "-q", "--file", "."])

        assert result.exit_code == 0
        assert "Fetching messages" not in result.output


class TestDigestCombinedFlags:
    """Tests for combining digest flags."""

    @patch("discord_chat.commands.digest.fetch_server_messages")
    @patch("discord_chat.commands.digest.get_provider")
    @patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "test-token"})
    def test_dry_run_with_quiet(self, mock_get_provider, mock_fetch):
        """Test --dry-run with --quiet shows nothing."""
        mock_fetch.return_value = create_sample_data()
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.name = "TestLLM"
        mock_get_provider.return_value = mock_provider

        runner = CliRunner()
        result = runner.invoke(main, ["digest", "test-server", "--dry-run", "--quiet"])

        assert result.exit_code == 0
        # Quiet should suppress dry-run output too
        assert "[DRY RUN]" not in result.output


class TestProgressStatus:
    """Tests for progress status indicators."""

    @patch("discord_chat.commands.digest.fetch_server_messages")
    @patch("discord_chat.commands.digest.get_provider")
    @patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "test-token"})
    def test_progress_shows_timing(self, mock_get_provider, mock_fetch):
        """Test that progress indicators show timing."""
        mock_fetch.return_value = create_sample_data()
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.name = "TestLLM"
        mock_provider.generate_digest.return_value = "# Test Digest"
        mock_get_provider.return_value = mock_provider

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["digest", "test-server", "--file", "."])

        assert result.exit_code == 0
        # Should show timing like "done (0.1s)"
        assert "done" in result.output
        assert "s)" in result.output  # seconds indicator
