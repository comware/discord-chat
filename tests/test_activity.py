"""Tests for the activity command."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from click.testing import CliRunner

from cli import main
from discord_chat.services.discord_client import (
    ChannelMessages,
    DiscordClientError,
    ServerDigestData,
    ServerNotFoundError,
)


def create_activity_data() -> ServerDigestData:
    """Create sample server data for activity testing."""
    end_time = datetime.now(UTC)
    start_time = end_time - timedelta(hours=24)

    return ServerDigestData(
        server_name="Test Server",
        server_id=123456789,
        channels=[
            ChannelMessages(
                channel_name="general",
                channel_id=111,
                messages=[{"id": i} for i in range(42)],
            ),
            ChannelMessages(
                channel_name="dev",
                channel_id=222,
                messages=[{"id": i} for i in range(15)],
            ),
            ChannelMessages(
                channel_name="announcements",
                channel_id=333,
                messages=[{"id": i} for i in range(3)],
            ),
        ],
        start_time=start_time,
        end_time=end_time,
        total_messages=60,
    )


class TestActivityCommand:
    """Tests for the activity CLI command."""

    def test_activity_no_token(self):
        """Test activity command fails without Discord token."""
        runner = CliRunner()

        with patch.dict("os.environ", {}, clear=True):
            result = runner.invoke(main, ["activity", "test-server"])

        assert result.exit_code != 0
        assert "DISCORD_BOT_TOKEN" in result.output

    @patch("discord_chat.commands.activity.fetch_server_messages")
    @patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "test-token"})
    def test_activity_no_messages(self, mock_fetch):
        """Test activity command with no messages found."""
        mock_fetch.return_value = ServerDigestData(
            server_name="Test Server",
            server_id=1,
            channels=[],
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
            total_messages=0,
        )

        runner = CliRunner()
        result = runner.invoke(main, ["activity", "test-server"])

        assert result.exit_code == 0
        assert "No messages found" in result.output

    @patch("discord_chat.commands.activity.fetch_server_messages")
    @patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "test-token"})
    def test_activity_success(self, mock_fetch):
        """Test successful activity display."""
        mock_fetch.return_value = create_activity_data()

        runner = CliRunner()
        result = runner.invoke(main, ["activity", "test-server"])

        assert result.exit_code == 0
        assert "Channel" in result.output
        assert "Messages" in result.output
        assert "#general" in result.output
        assert "#dev" in result.output
        assert "#announcements" in result.output
        assert "42" in result.output
        assert "15" in result.output
        assert "3" in result.output
        assert "Total" in result.output
        assert "60" in result.output

    @patch("discord_chat.commands.activity.fetch_server_messages")
    @patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "test-token"})
    def test_activity_sorted_by_message_count(self, mock_fetch):
        """Test that channels are sorted by message count descending."""
        mock_fetch.return_value = create_activity_data()

        runner = CliRunner()
        result = runner.invoke(main, ["activity", "test-server"])

        assert result.exit_code == 0
        # Find positions in output
        general_pos = result.output.find("#general")
        dev_pos = result.output.find("#dev")
        announce_pos = result.output.find("#announcements")

        # general (42) should come before dev (15) which should come before announcements (3)
        assert general_pos < dev_pos < announce_pos

    @patch("discord_chat.commands.activity.fetch_server_messages")
    @patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "test-token"})
    def test_activity_custom_hours(self, mock_fetch):
        """Test activity command with custom hours parameter."""
        mock_fetch.return_value = create_activity_data()

        runner = CliRunner()
        result = runner.invoke(main, ["activity", "test-server", "--hours", "12"])

        assert result.exit_code == 0
        mock_fetch.assert_called_once_with("test-server", 12)

    @patch("discord_chat.commands.activity.fetch_server_messages")
    @patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "test-token"})
    def test_activity_server_not_found(self, mock_fetch):
        """Test activity command when server is not found."""
        mock_fetch.side_effect = ServerNotFoundError("Server 'unknown' not found")

        runner = CliRunner()
        result = runner.invoke(main, ["activity", "unknown-server"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    @patch("discord_chat.commands.activity.fetch_server_messages")
    @patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "test-token"})
    def test_activity_discord_error(self, mock_fetch):
        """Test activity command handles Discord errors."""
        mock_fetch.side_effect = DiscordClientError("Connection failed")

        runner = CliRunner()
        result = runner.invoke(main, ["activity", "test-server"])

        assert result.exit_code != 0
        assert "Discord error" in result.output

    def test_activity_help(self):
        """Test activity command help."""
        runner = CliRunner()
        result = runner.invoke(main, ["activity", "--help"])

        assert result.exit_code == 0
        assert "Check message activity" in result.output
        assert "--hours" in result.output
