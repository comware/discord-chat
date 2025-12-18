"""Tests for the digest command."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from cli import main
from discord_chat.services.discord_client import ChannelMessages, ServerDigestData
from discord_chat.services.llm import LLMError, get_provider
from discord_chat.services.llm.base import LLMProvider
from discord_chat.utils.digest_formatter import (
    format_messages_for_llm,
    format_time_range,
    get_default_output_filename,
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
            result = runner.invoke(main, ["digest", "test-server", "--output", "."])

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
        assert "--output" in result.output
