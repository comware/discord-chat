"""Tests for the Discord client service."""

import tempfile
from unittest.mock import patch

import pytest

from discord_chat.services.discord_client import (
    ChannelMessages,
    DiscordClientError,
    DiscordMessageFetcher,
    ServerDigestData,
    ServerNotFoundError,
    _get_env_int,
)


class TestGetEnvInt:
    """Tests for _get_env_int helper function."""

    def test_returns_default_when_not_set(self):
        """Test returns default when env var is not set."""
        with patch.dict("os.environ", {}, clear=True):
            result = _get_env_int("MISSING_VAR", 10, 1, 100)
            assert result == 10

    def test_returns_env_value_when_set(self):
        """Test returns env value when set."""
        with patch.dict("os.environ", {"TEST_VAR": "50"}):
            result = _get_env_int("TEST_VAR", 10, 1, 100)
            assert result == 50

    def test_returns_default_when_below_min(self):
        """Test returns default when value is below minimum."""
        with patch.dict("os.environ", {"TEST_VAR": "0"}):
            result = _get_env_int("TEST_VAR", 10, 1, 100)
            assert result == 10

    def test_returns_default_when_above_max(self):
        """Test returns default when value is above maximum."""
        with patch.dict("os.environ", {"TEST_VAR": "200"}):
            result = _get_env_int("TEST_VAR", 10, 1, 100)
            assert result == 10

    def test_returns_default_on_invalid_value(self):
        """Test returns default when value is not an integer."""
        with patch.dict("os.environ", {"TEST_VAR": "not-a-number"}):
            result = _get_env_int("TEST_VAR", 10, 1, 100)
            assert result == 10

    def test_accepts_boundary_values(self):
        """Test accepts values at boundaries."""
        with patch.dict("os.environ", {"TEST_VAR": "1"}):
            result = _get_env_int("TEST_VAR", 10, 1, 100)
            assert result == 1

        with patch.dict("os.environ", {"TEST_VAR": "100"}):
            result = _get_env_int("TEST_VAR", 10, 1, 100)
            assert result == 100


class TestDiscordMessageFetcher:
    """Tests for DiscordMessageFetcher class."""

    def test_init_requires_token(self):
        """Test initialization fails without token."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(DiscordClientError) as exc_info:
                DiscordMessageFetcher()
            assert "DISCORD_BOT_TOKEN" in str(exc_info.value)

    def test_init_rejects_short_token(self):
        """Test initialization rejects short tokens."""
        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "short"}):
            with pytest.raises(DiscordClientError) as exc_info:
                DiscordMessageFetcher()
            assert "too short" in str(exc_info.value).lower()

    @patch("discord_chat.services.discord_client.discord.Client")
    def test_init_accepts_valid_token(self, mock_client):
        """Test initialization accepts valid token."""
        valid_token = "x" * 60  # Token length >= 50
        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": valid_token}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    fetcher = DiscordMessageFetcher()
                    assert fetcher._token == valid_token

    @patch("discord_chat.services.discord_client.discord.Client")
    def test_max_messages_from_env(self, mock_client):
        """Test max_messages_per_channel reads from environment."""
        valid_token = "x" * 60
        with patch.dict(
            "os.environ",
            {"DISCORD_BOT_TOKEN": valid_token, "DISCORD_CHAT_MAX_MESSAGES": "500"},
        ):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    fetcher = DiscordMessageFetcher()
                    assert fetcher.max_messages_per_channel == 500

    @patch("discord_chat.services.discord_client.discord.Client")
    def test_max_concurrent_from_env(self, mock_client):
        """Test max_concurrent_channels reads from environment."""
        valid_token = "x" * 60
        with patch.dict(
            "os.environ",
            {"DISCORD_BOT_TOKEN": valid_token, "DISCORD_CHAT_MAX_CONCURRENT": "10"},
        ):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    fetcher = DiscordMessageFetcher()
                    assert fetcher.max_concurrent_channels == 10

    @patch("discord_chat.services.discord_client.discord.Client")
    def test_timeout_from_env(self, mock_client):
        """Test operation_timeout reads from environment."""
        valid_token = "x" * 60
        with patch.dict(
            "os.environ",
            {"DISCORD_BOT_TOKEN": valid_token, "DISCORD_CHAT_TIMEOUT": "120"},
        ):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    fetcher = DiscordMessageFetcher()
                    assert fetcher.operation_timeout == 120.0


class TestDataClasses:
    """Tests for data classes."""

    def test_channel_messages(self):
        """Test ChannelMessages dataclass."""
        channel = ChannelMessages(
            channel_name="general",
            channel_id=123,
            messages=[{"id": 1}, {"id": 2}],
        )

        assert channel.channel_name == "general"
        assert channel.channel_id == 123
        assert len(channel.messages) == 2

    def test_server_digest_data(self):
        """Test ServerDigestData dataclass."""
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        data = ServerDigestData(
            server_name="Test Server",
            server_id=123,
            channels=[],
            start_time=now,
            end_time=now,
            total_messages=0,
        )

        assert data.server_name == "Test Server"
        assert data.server_id == 123
        assert data.total_messages == 0


class TestServerNotFoundError:
    """Tests for ServerNotFoundError exception."""

    def test_is_discord_client_error(self):
        """Test ServerNotFoundError is a DiscordClientError."""
        error = ServerNotFoundError("Server not found")
        assert isinstance(error, DiscordClientError)

    def test_message_preserved(self):
        """Test error message is preserved."""
        error = ServerNotFoundError("Test message")
        assert str(error) == "Test message"


class TestDiscordClientError:
    """Tests for DiscordClientError exception."""

    def test_is_exception(self):
        """Test DiscordClientError is an Exception."""
        error = DiscordClientError("Error")
        assert isinstance(error, Exception)

    def test_message_preserved(self):
        """Test error message is preserved."""
        error = DiscordClientError("Test message")
        assert str(error) == "Test message"
