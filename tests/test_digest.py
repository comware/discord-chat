"""Tests for the digest command."""

from datetime import UTC, datetime, timedelta
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from rich.console import Console

from cli import main
from discord_chat.services.discord_client import ChannelMessages, ServerDigestData
from discord_chat.services.llm import LLMError, get_provider
from discord_chat.services.llm.base import LLMProvider
from discord_chat.utils.digest_formatter import (
    InvalidServerNameError,
    format_messages_for_llm,
    format_time_range,
    get_default_output_filename,
    validate_server_name,
)


# Sample test data
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
                        "content": "Hello everyone!",
                        "timestamp": "2024-01-01T12:00:00",
                        "attachments": [],
                        "reactions": [],
                    },
                    {
                        "id": 2,
                        "author": "Bob",
                        "author_id": 1002,
                        "content": "Hi Alice!",
                        "timestamp": "2024-01-01T12:05:00",
                        "attachments": [],
                        "reactions": [{"emoji": "👋", "count": 2}],
                    },
                ],
            ),
            ChannelMessages(
                channel_name="dev",
                channel_id=222,
                messages=[
                    {
                        "id": 3,
                        "author": "Charlie",
                        "author_id": 1003,
                        "content": "Fixed the bug in PR #42",
                        "timestamp": "2024-01-01T13:00:00",
                        "attachments": ["screenshot.png"],
                        "reactions": [],
                    },
                ],
            ),
        ],
        start_time=start_time,
        end_time=end_time,
        total_messages=3,
    )


class TestDigestFormatter:
    """Tests for digest formatter utilities."""

    def test_format_messages_for_llm(self):
        """Test formatting messages for LLM consumption."""
        data = create_sample_data()
        result = format_messages_for_llm(data)

        assert "## #general" in result
        assert "## #dev" in result
        assert "**Alice**" in result
        assert "Hello everyone!" in result
        assert "**Charlie**" in result
        assert "Fixed the bug in PR #42" in result
        assert "_Attachments: screenshot.png_" in result

    def test_format_messages_empty(self):
        """Test formatting when no messages exist."""
        data = ServerDigestData(
            server_name="Empty Server",
            server_id=1,
            channels=[],
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
            total_messages=0,
        )
        result = format_messages_for_llm(data)
        assert "No messages found" in result

    def test_format_time_range(self):
        """Test time range formatting."""
        start = datetime(2024, 1, 1, 10, 0, tzinfo=UTC)
        end = datetime(2024, 1, 1, 16, 0, tzinfo=UTC)

        result = format_time_range(start, end)

        assert "2024-01-01 10:00 UTC" in result
        assert "2024-01-01 16:00 UTC" in result

    def test_get_default_output_filename(self):
        """Test default filename generation."""
        filename = get_default_output_filename("My Test Server")

        assert filename.startswith("digest-my-test-server-")
        assert filename.endswith(".md")

    def test_get_default_output_filename_special_chars(self):
        """Test filename generation with special characters."""
        filename = get_default_output_filename("Server@#$%Name!")

        assert "digest-" in filename
        assert ".md" in filename
        # Should not contain special chars
        assert "@" not in filename
        assert "#" not in filename


class TestServerNameValidation:
    """Tests for server name validation (security)."""

    def test_validate_server_name_valid(self):
        """Test validation passes for normal server names."""
        assert validate_server_name("My Server") == "My Server"
        assert validate_server_name("  Trimmed  ") == "Trimmed"
        assert validate_server_name("Server123") == "Server123"

    def test_validate_server_name_empty(self):
        """Test validation fails for empty names."""
        with pytest.raises(InvalidServerNameError) as exc_info:
            validate_server_name("")
        assert "empty" in str(exc_info.value).lower()

        with pytest.raises(InvalidServerNameError):
            validate_server_name("   ")

    def test_validate_server_name_path_traversal(self):
        """Test validation blocks path traversal attempts."""
        with pytest.raises(InvalidServerNameError) as exc_info:
            validate_server_name("../../../etc/passwd")
        assert "path traversal" in str(exc_info.value).lower()

        with pytest.raises(InvalidServerNameError):
            validate_server_name("server/../secret")

        with pytest.raises(InvalidServerNameError):
            validate_server_name("/etc/passwd")

        with pytest.raises(InvalidServerNameError):
            validate_server_name("\\windows\\system32")

    def test_validate_server_name_control_chars(self):
        """Test validation blocks control characters."""
        with pytest.raises(InvalidServerNameError) as exc_info:
            validate_server_name("server\x00name")
        assert "control" in str(exc_info.value).lower()

        with pytest.raises(InvalidServerNameError):
            validate_server_name("server\nname")

    def test_validate_server_name_too_long(self):
        """Test validation fails for excessively long names."""
        long_name = "a" * 101
        with pytest.raises(InvalidServerNameError) as exc_info:
            validate_server_name(long_name)
        assert "too long" in str(exc_info.value).lower()

    def test_get_default_output_filename_path_traversal(self):
        """Test filename generation blocks path traversal."""
        with pytest.raises(InvalidServerNameError):
            get_default_output_filename("../../../etc/passwd")


class TestHoursValidation:
    """Tests for hours range validation."""

    @patch("discord_chat.commands.digest.fetch_server_messages")
    @patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "test-token"})
    def test_digest_hours_too_low(self, mock_fetch):
        """Test digest command rejects hours < 1."""
        runner = CliRunner()
        result = runner.invoke(main, ["digest", "test-server", "--hours", "0"])

        assert result.exit_code != 0
        assert "Hours must be between" in result.output

    @patch("discord_chat.commands.digest.fetch_server_messages")
    @patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "test-token"})
    def test_digest_hours_too_high(self, mock_fetch):
        """Test digest command rejects hours > 168."""
        runner = CliRunner()
        result = runner.invoke(main, ["digest", "test-server", "--hours", "200"])

        assert result.exit_code != 0
        assert "Hours must be between" in result.output

    @patch("discord_chat.commands.digest.fetch_server_messages")
    @patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "test-token"})
    def test_digest_hours_negative(self, mock_fetch):
        """Test digest command rejects negative hours."""
        runner = CliRunner()
        result = runner.invoke(main, ["digest", "test-server", "--hours", "-5"])

        assert result.exit_code != 0
        assert "Hours must be between" in result.output


class TestLLMProvider:
    """Tests for LLM provider functionality."""

    def test_get_provider_invalid(self):
        """Test that invalid provider name raises error."""
        with pytest.raises(LLMError) as exc_info:
            get_provider("invalid_provider")

        assert "Unknown provider" in str(exc_info.value)

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}, clear=False)
    def test_get_provider_claude_not_available(self):
        """Test Claude provider unavailable without API key."""
        # Clear the API key
        import os

        original = os.environ.pop("ANTHROPIC_API_KEY", None)
        os.environ.pop("OPENAI_API_KEY", None)

        try:
            with pytest.raises(LLMError) as exc_info:
                get_provider("claude")
            assert "not available" in str(exc_info.value)
        finally:
            if original:
                os.environ["ANTHROPIC_API_KEY"] = original

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    def test_get_provider_claude_available(self):
        """Test Claude provider available with API key."""
        provider = get_provider("claude")
        assert provider.name == "Claude"


class TestDigestCommand:
    """Tests for the digest CLI command."""

    def test_digest_no_token(self):
        """Test digest command fails without Discord token."""
        runner = CliRunner()

        with patch.dict("os.environ", {}, clear=True):
            result = runner.invoke(main, ["digest", "test-server"])

        assert result.exit_code != 0
        assert "DISCORD_BOT_TOKEN" in result.output

    @patch("discord_chat.commands.digest.fetch_server_messages")
    @patch("discord_chat.commands.digest.get_provider")
    @patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "test-token"})
    def test_digest_no_messages(self, mock_get_provider, mock_fetch):
        """Test digest command with no messages found."""
        mock_fetch.return_value = ServerDigestData(
            server_name="Test Server",
            server_id=1,
            channels=[],
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
            total_messages=0,
        )

        runner = CliRunner()
        result = runner.invoke(main, ["digest", "test-server"])

        assert result.exit_code == 0
        assert "No messages found" in result.output
        mock_get_provider.assert_not_called()

    @patch("discord_chat.commands.digest.fetch_server_messages")
    @patch("discord_chat.commands.digest.get_provider")
    @patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "test-token"})
    def test_digest_success(self, mock_get_provider, mock_fetch):
        """Test successful digest generation."""
        # Setup mocks
        mock_fetch.return_value = create_sample_data()

        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.name = "TestLLM"
        mock_provider.generate_digest.return_value = "# Test Digest\n\nThis is a test."
        mock_get_provider.return_value = mock_provider

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["digest", "test-server", "--file", "."])

        assert result.exit_code == 0
        assert "Found 3 messages" in result.output
        assert "Test Digest" in result.output
        assert "Digest saved to" in result.output

    def test_digest_help(self):
        """Test digest command help."""
        runner = CliRunner()
        result = runner.invoke(main, ["digest", "--help"])

        assert result.exit_code == 0
        assert "Generate a digest" in result.output
        assert "--hours" in result.output
        assert "--llm" in result.output
        assert "--file" in result.output
        assert "--no-color" in result.output


class TestDigestScreenOutput:
    """Tests for Rich screen output functionality."""

    @patch("discord_chat.commands.digest.fetch_server_messages")
    @patch("discord_chat.commands.digest.get_provider")
    @patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "t" * 60})
    def test_digest_screen_output_default_no_file(self, mock_get_provider, mock_fetch):
        """Test digest outputs to screen by default (no file created)."""
        mock_fetch.return_value = create_sample_data()
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.name = "TestLLM"
        mock_provider.generate_digest.return_value = "# Test Digest\n\nContent here."
        mock_get_provider.return_value = mock_provider

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["digest", "test-server"])

            # Should succeed
            assert result.exit_code == 0
            # Should contain digest content (via Rich rendering)
            assert "Test Digest" in result.output or "test" in result.output.lower()
            # Should NOT create a file (no --file flag)
            import os

            files = os.listdir(".")
            digest_files = [f for f in files if f.startswith("digest-")]
            assert len(digest_files) == 0

    @patch("discord_chat.commands.digest.fetch_server_messages")
    @patch("discord_chat.commands.digest.get_provider")
    @patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "t" * 60})
    def test_digest_file_output_with_flag(self, mock_get_provider, mock_fetch):
        """Test digest saves to file when --file flag is provided."""
        mock_fetch.return_value = create_sample_data()
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.name = "TestLLM"
        mock_provider.generate_digest.return_value = "# Test Digest\n\nContent here."
        mock_get_provider.return_value = mock_provider

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["digest", "test-server", "--file", "."])

            assert result.exit_code == 0
            assert "Digest saved to" in result.output
            # Should create a file
            import os

            files = os.listdir(".")
            digest_files = [f for f in files if f.startswith("digest-")]
            assert len(digest_files) == 1

    @patch("discord_chat.commands.digest.fetch_server_messages")
    @patch("discord_chat.commands.digest.get_provider")
    @patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "t" * 60})
    def test_digest_quiet_mode_with_file(self, mock_get_provider, mock_fetch):
        """Test quiet mode suppresses output but still saves file."""
        mock_fetch.return_value = create_sample_data()
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.name = "TestLLM"
        mock_provider.generate_digest.return_value = "# Test Digest"
        mock_get_provider.return_value = mock_provider

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["digest", "test-server", "--quiet", "--file", "."])

            assert result.exit_code == 0
            # Quiet mode should suppress digest output
            assert "Discord Digest" not in result.output
            # But file should still be created
            import os

            files = os.listdir(".")
            digest_files = [f for f in files if f.startswith("digest-")]
            assert len(digest_files) == 1

    @patch("discord_chat.commands.digest.fetch_server_messages")
    @patch("discord_chat.commands.digest.get_provider")
    @patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "t" * 60})
    def test_digest_file_with_custom_path(self, mock_get_provider, mock_fetch):
        """Test --file with a specific file path."""
        mock_fetch.return_value = create_sample_data()
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.name = "TestLLM"
        mock_provider.generate_digest.return_value = "# Test"
        mock_get_provider.return_value = mock_provider

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["digest", "test-server", "--file", "my-digest.md"])

            assert result.exit_code == 0
            import os

            assert os.path.exists("my-digest.md")

    @patch("discord_chat.commands.digest.fetch_server_messages")
    @patch("discord_chat.commands.digest.get_provider")
    @patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "t" * 60})
    def test_digest_no_color_flag(self, mock_get_provider, mock_fetch):
        """Test --no-color flag disables styling."""
        mock_fetch.return_value = create_sample_data()
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.name = "TestLLM"
        mock_provider.generate_digest.return_value = "# Test Digest"
        mock_get_provider.return_value = mock_provider

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["digest", "test-server", "--no-color"])

            assert result.exit_code == 0
            # Output should still contain content
            assert "Test" in result.output or "test" in result.output.lower()


class TestConsoleOutputModule:
    """Tests for the console_output utility module."""

    def test_render_digest_quiet_mode(self):
        """Test that quiet mode produces no output."""
        from discord_chat.utils.console_output import render_digest_to_console

        output = StringIO()
        console = Console(file=output, force_terminal=True)

        render_digest_to_console("# Test", console=console, quiet=True)

        assert output.getvalue() == ""

    def test_render_digest_produces_output(self):
        """Test that normal mode produces output."""
        from discord_chat.utils.console_output import render_digest_to_console

        output = StringIO()
        console = Console(file=output, force_terminal=True)

        render_digest_to_console("# Test Heading", console=console, quiet=False)

        result = output.getvalue()
        assert len(result) > 0
        # Rich will render the heading (may include formatting codes)
        assert "Test" in result or "test" in result.lower()

    def test_create_console_no_color(self):
        """Test that no_color disables styling."""
        from discord_chat.utils.console_output import create_console

        console = create_console(no_color=True)
        assert console.no_color is True

    def test_create_console_default(self):
        """Test default console creation."""
        from discord_chat.utils.console_output import create_console

        console = create_console()
        assert console is not None


class TestDigestChannelFilter:
    """Tests for --channel filtering option."""

    @patch("discord_chat.commands.digest.fetch_server_messages")
    @patch("discord_chat.commands.digest.get_provider")
    @patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "test-token"})
    def test_channel_filter_single_channel(self, mock_get_provider, mock_fetch):
        """Test digest with --channel filters to single channel."""
        mock_fetch.return_value = create_sample_data()

        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.name = "TestLLM"
        mock_provider.generate_digest.return_value = "# Filtered Digest"
        mock_get_provider.return_value = mock_provider

        runner = CliRunner()
        result = runner.invoke(main, ["digest", "test-server", "--channel", "general"])

        assert result.exit_code == 0
        # Should show messages only from general (2 messages)
        assert "Found 2 messages in #general" in result.output

    @patch("discord_chat.commands.digest.fetch_server_messages")
    @patch("discord_chat.commands.digest.get_provider")
    @patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "test-token"})
    def test_channel_filter_case_insensitive(self, mock_get_provider, mock_fetch):
        """Test --channel is case-insensitive."""
        mock_fetch.return_value = create_sample_data()

        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.name = "TestLLM"
        mock_provider.generate_digest.return_value = "# Filtered Digest"
        mock_get_provider.return_value = mock_provider

        runner = CliRunner()
        # Use uppercase "GENERAL" to match "general"
        result = runner.invoke(main, ["digest", "test-server", "--channel", "GENERAL"])

        assert result.exit_code == 0
        assert "Found 2 messages in #GENERAL" in result.output

    @patch("discord_chat.commands.digest.fetch_server_messages")
    @patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "test-token"})
    def test_channel_filter_not_found(self, mock_fetch):
        """Test error when specified channel doesn't exist."""
        mock_fetch.return_value = create_sample_data()

        runner = CliRunner()
        result = runner.invoke(main, ["digest", "test-server", "--channel", "nonexistent"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower()
        # Should list available channels
        assert "#dev" in result.output
        assert "#general" in result.output

    @patch("discord_chat.commands.digest.fetch_server_messages")
    @patch("discord_chat.commands.digest.get_provider")
    @patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "test-token"})
    def test_channel_filter_with_dry_run(self, mock_get_provider, mock_fetch):
        """Test --dry-run shows channel filter."""
        mock_fetch.return_value = create_sample_data()

        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.name = "TestLLM"
        mock_get_provider.return_value = mock_provider

        runner = CliRunner()
        result = runner.invoke(main, ["digest", "test-server", "--channel", "dev", "--dry-run"])

        assert result.exit_code == 0
        assert "Channel filter" in result.output
        assert "#dev" in result.output

    @patch("discord_chat.commands.digest.fetch_server_messages")
    @patch("discord_chat.commands.digest.get_provider")
    @patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "test-token"})
    def test_channel_filter_updates_message_count(self, mock_get_provider, mock_fetch):
        """Test total_messages reflects filtered channel only."""
        mock_fetch.return_value = create_sample_data()

        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.name = "TestLLM"
        mock_provider.generate_digest.return_value = "# Test"
        mock_get_provider.return_value = mock_provider

        runner = CliRunner()
        # Filter to "dev" channel which has 1 message
        result = runner.invoke(main, ["digest", "test-server", "--channel", "dev"])

        assert result.exit_code == 0
        assert "Found 1 messages in #dev" in result.output

    @patch("discord_chat.commands.digest.fetch_server_messages")
    @patch("discord_chat.commands.digest.get_provider")
    @patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "test-token"})
    def test_channel_filter_short_flag(self, mock_get_provider, mock_fetch):
        """Test -c short flag works."""
        mock_fetch.return_value = create_sample_data()

        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.name = "TestLLM"
        mock_provider.generate_digest.return_value = "# Test"
        mock_get_provider.return_value = mock_provider

        runner = CliRunner()
        result = runner.invoke(main, ["digest", "test-server", "-c", "general"])

        assert result.exit_code == 0
        assert "Found 2 messages in #general" in result.output

    @patch("discord_chat.commands.digest.fetch_server_messages")
    @patch("discord_chat.commands.digest.get_provider")
    @patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "test-token"})
    def test_channel_filter_with_hash_prefix(self, mock_get_provider, mock_fetch):
        """Test channel filter accepts #channel format."""
        mock_fetch.return_value = create_sample_data()

        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.name = "TestLLM"
        mock_provider.generate_digest.return_value = "# Test"
        mock_get_provider.return_value = mock_provider

        runner = CliRunner()
        # User passes "#general" instead of "general"
        result = runner.invoke(main, ["digest", "test-server", "--channel", "#general"])

        assert result.exit_code == 0
        assert "messages in ##general" in result.output or "Found 2 messages" in result.output

    @patch("discord_chat.commands.digest.fetch_server_messages")
    @patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "test-token"})
    def test_channel_filter_empty_channel(self, mock_fetch):
        """Test filtering to channel with no messages shows empty digest message."""
        # Create data with an empty channel
        data = create_sample_data()
        data.channels.append(
            ChannelMessages(channel_name="empty-channel", channel_id=333, messages=[])
        )
        mock_fetch.return_value = data

        runner = CliRunner()
        result = runner.invoke(main, ["digest", "test-server", "--channel", "empty-channel"])

        assert result.exit_code == 0
        assert "No messages found in #empty-channel" in result.output

    def test_channel_filter_in_help(self):
        """Test --channel appears in help."""
        runner = CliRunner()
        result = runner.invoke(main, ["digest", "--help"])

        assert result.exit_code == 0
        assert "--channel" in result.output
        assert "-c" in result.output
        assert "specific channel" in result.output.lower()
