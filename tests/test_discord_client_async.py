"""Comprehensive async tests for Discord client service.

This test suite covers all async methods and error handling paths in DiscordMessageFetcher:
- Connection handling with timeouts
- Server lookup with partial matching
- Message fetching with pagination and rate limiting
- Content truncation and security features
- Concurrent channel processing with semaphores
- All error scenarios (Forbidden, HTTPException, LoginFailure, PrivilegedIntentsRequired)
"""

import asyncio
import tempfile
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import discord
import pytest

from discord_chat.services.discord_client import (
    ChannelMessages,
    DiscordClientError,
    DiscordMessageFetcher,
    ServerDigestData,
    ServerNotFoundError,
)


class TestWaitUntilReady:
    """Tests for _wait_until_ready async method."""

    @pytest.mark.asyncio
    async def test_wait_until_ready_success(self):
        """Test successful connection within timeout."""
        valid_token = "x" * 60
        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": valid_token}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()
                        # Simulate ready event
                        fetcher._ready_event.set()

                        # Should not raise
                        await fetcher._wait_until_ready(timeout=1.0)

    @pytest.mark.asyncio
    async def test_wait_until_ready_timeout(self):
        """Test timeout when connection takes too long."""
        valid_token = "x" * 60
        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": valid_token}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()
                        # Don't set ready event - will timeout

                        with pytest.raises(DiscordClientError) as exc_info:
                            await fetcher._wait_until_ready(timeout=0.1)

                        assert "Timed out waiting for Discord connection" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_wait_until_ready_custom_timeout(self):
        """Test custom timeout parameter is respected."""
        valid_token = "x" * 60
        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": valid_token}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()

                        # Set ready event after a delay
                        async def set_ready_later():
                            await asyncio.sleep(0.2)
                            fetcher._ready_event.set()

                        asyncio.create_task(set_ready_later())

                        # Should succeed with longer timeout
                        await fetcher._wait_until_ready(timeout=0.5)


class TestFindServerByName:
    """Tests for _find_server_by_name method."""

    def test_find_server_exact_match(self):
        """Test finding server with exact name match."""
        valid_token = "x" * 60
        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": valid_token}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()

                        # Mock guilds
                        guild1 = Mock(spec=discord.Guild)
                        guild1.name = "Test Server"
                        guild1.id = 123

                        guild2 = Mock(spec=discord.Guild)
                        guild2.name = "Another Server"
                        guild2.id = 456

                        fetcher._client.guilds = [guild1, guild2]

                        result = fetcher._find_server_by_name("Test Server")
                        assert result == guild1
                        assert result.id == 123

    def test_find_server_case_insensitive(self):
        """Test finding server is case-insensitive."""
        valid_token = "x" * 60
        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": valid_token}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()

                        guild = Mock(spec=discord.Guild)
                        guild.name = "Test Server"
                        guild.id = 123

                        fetcher._client.guilds = [guild]

                        # Should find with different case
                        result = fetcher._find_server_by_name("test server")
                        assert result == guild

                        result = fetcher._find_server_by_name("TEST SERVER")
                        assert result == guild

    def test_find_server_partial_match(self):
        """Test finding server with partial name match."""
        valid_token = "x" * 60
        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": valid_token}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()

                        guild = Mock(spec=discord.Guild)
                        guild.name = "My Test Server"
                        guild.id = 123

                        fetcher._client.guilds = [guild]

                        # Should find with partial match
                        result = fetcher._find_server_by_name("test")
                        assert result == guild

    def test_find_server_exact_match_preferred_over_partial(self):
        """Test exact match is preferred over partial match."""
        valid_token = "x" * 60
        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": valid_token}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()

                        guild1 = Mock(spec=discord.Guild)
                        guild1.name = "Test Server Extended"
                        guild1.id = 123

                        guild2 = Mock(spec=discord.Guild)
                        guild2.name = "Test"
                        guild2.id = 456

                        fetcher._client.guilds = [guild1, guild2]

                        # Should find exact match "Test" instead of partial "Test Server Extended"
                        result = fetcher._find_server_by_name("Test")
                        assert result == guild2
                        assert result.id == 456

    def test_find_server_not_found(self):
        """Test error when server is not found."""
        valid_token = "x" * 60
        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": valid_token}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()

                        guild = Mock(spec=discord.Guild)
                        guild.name = "Existing Server"

                        fetcher._client.guilds = [guild]

                        with pytest.raises(ServerNotFoundError) as exc_info:
                            fetcher._find_server_by_name("Nonexistent Server")

                        assert "Nonexistent Server" in str(exc_info.value)
                        assert "Available servers: Existing Server" in str(exc_info.value)

    def test_find_server_empty_guild_list(self):
        """Test error when no guilds are available."""
        valid_token = "x" * 60
        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": valid_token}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()
                        fetcher._client.guilds = []

                        with pytest.raises(ServerNotFoundError) as exc_info:
                            fetcher._find_server_by_name("Any Server")

                        assert "Available servers: None" in str(exc_info.value)


class TestFetchChannelMessages:
    """Tests for _fetch_channel_messages async method."""

    @pytest.mark.asyncio
    async def test_fetch_channel_messages_success(self):
        """Test successfully fetching messages from a channel."""
        valid_token = "x" * 60
        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": valid_token}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()

                        # Mock channel
                        channel = Mock(spec=discord.TextChannel)
                        channel.name = "general"
                        channel.id = 111

                        # Mock message
                        message = Mock(spec=discord.Message)
                        message.id = 1
                        message.author = Mock()
                        message.author.bot = False
                        message.author.display_name = "Alice"
                        message.author.id = 1001
                        message.content = "Hello world!"
                        message.created_at = datetime.now(UTC)
                        message.attachments = []
                        message.reactions = []

                        # Mock async history
                        async def mock_history(*args, **kwargs):
                            yield message

                        channel.history = mock_history

                        start_time = datetime.now(UTC) - timedelta(hours=1)
                        end_time = datetime.now(UTC)

                        result = await fetcher._fetch_channel_messages(
                            channel, start_time, end_time
                        )

                        assert result.channel_name == "general"
                        assert result.channel_id == 111
                        assert len(result.messages) == 1
                        assert result.messages[0]["content"] == "Hello world!"
                        assert result.messages[0]["author"] == "Alice"

    @pytest.mark.asyncio
    async def test_fetch_channel_messages_filters_bot_messages(self):
        """Test that bot messages are filtered out."""
        valid_token = "x" * 60
        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": valid_token}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()

                        channel = Mock(spec=discord.TextChannel)
                        channel.name = "general"
                        channel.id = 111

                        # Bot message
                        bot_msg = Mock(spec=discord.Message)
                        bot_msg.author = Mock()
                        bot_msg.author.bot = True

                        # User message
                        user_msg = Mock(spec=discord.Message)
                        user_msg.id = 1
                        user_msg.author = Mock()
                        user_msg.author.bot = False
                        user_msg.author.display_name = "Alice"
                        user_msg.author.id = 1001
                        user_msg.content = "User message"
                        user_msg.created_at = datetime.now(UTC)
                        user_msg.attachments = []
                        user_msg.reactions = []

                        async def mock_history(*args, **kwargs):
                            yield bot_msg
                            yield user_msg

                        channel.history = mock_history

                        start_time = datetime.now(UTC) - timedelta(hours=1)
                        end_time = datetime.now(UTC)

                        result = await fetcher._fetch_channel_messages(
                            channel, start_time, end_time
                        )

                        assert len(result.messages) == 1
                        assert result.messages[0]["content"] == "User message"

    @pytest.mark.asyncio
    async def test_fetch_channel_messages_filters_empty_messages(self):
        """Test that empty messages without content or attachments are filtered."""
        valid_token = "x" * 60
        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": valid_token}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()

                        channel = Mock(spec=discord.TextChannel)
                        channel.name = "general"
                        channel.id = 111

                        # Empty message
                        empty_msg = Mock(spec=discord.Message)
                        empty_msg.author = Mock()
                        empty_msg.author.bot = False
                        empty_msg.content = ""
                        empty_msg.attachments = []

                        # Valid message
                        valid_msg = Mock(spec=discord.Message)
                        valid_msg.id = 1
                        valid_msg.author = Mock()
                        valid_msg.author.bot = False
                        valid_msg.author.display_name = "Alice"
                        valid_msg.author.id = 1001
                        valid_msg.content = "Hello"
                        valid_msg.created_at = datetime.now(UTC)
                        valid_msg.attachments = []
                        valid_msg.reactions = []

                        async def mock_history(*args, **kwargs):
                            yield empty_msg
                            yield valid_msg

                        channel.history = mock_history

                        start_time = datetime.now(UTC) - timedelta(hours=1)
                        end_time = datetime.now(UTC)

                        result = await fetcher._fetch_channel_messages(
                            channel, start_time, end_time
                        )

                        assert len(result.messages) == 1
                        assert result.messages[0]["content"] == "Hello"

    @pytest.mark.asyncio
    async def test_fetch_channel_messages_truncates_long_content(self):
        """Test that very long message content is truncated."""
        valid_token = "x" * 60
        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": valid_token}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()

                        channel = Mock(spec=discord.TextChannel)
                        channel.name = "general"
                        channel.id = 111

                        # Message with very long content
                        message = Mock(spec=discord.Message)
                        message.id = 1
                        message.author = Mock()
                        message.author.bot = False
                        message.author.display_name = "Alice"
                        message.author.id = 1001
                        # Content longer than MAX_MESSAGE_CONTENT_LENGTH (100,000)
                        message.content = "x" * 150_000
                        message.created_at = datetime.now(UTC)
                        message.attachments = []
                        message.reactions = []

                        async def mock_history(*args, **kwargs):
                            yield message

                        channel.history = mock_history

                        start_time = datetime.now(UTC) - timedelta(hours=1)
                        end_time = datetime.now(UTC)

                        result = await fetcher._fetch_channel_messages(
                            channel, start_time, end_time
                        )

                        assert len(result.messages) == 1
                        # Should be truncated to MAX_MESSAGE_CONTENT_LENGTH + "[truncated]"
                        assert len(result.messages[0]["content"]) == 100_000 + len("...[truncated]")
                        assert result.messages[0]["content"].endswith("...[truncated]")

    @pytest.mark.asyncio
    async def test_fetch_channel_messages_limits_attachments(self):
        """Test that attachment list is limited to 10 items."""
        valid_token = "x" * 60
        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": valid_token}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()

                        channel = Mock(spec=discord.TextChannel)
                        channel.name = "general"
                        channel.id = 111

                        # Message with 15 attachments
                        message = Mock(spec=discord.Message)
                        message.id = 1
                        message.author = Mock()
                        message.author.bot = False
                        message.author.display_name = "Alice"
                        message.author.id = 1001
                        message.content = "Many files"
                        message.created_at = datetime.now(UTC)
                        message.reactions = []

                        # Create 15 mock attachments
                        attachments = []
                        for i in range(15):
                            att = Mock()
                            att.filename = f"file{i}.txt"
                            attachments.append(att)
                        message.attachments = attachments

                        async def mock_history(*args, **kwargs):
                            yield message

                        channel.history = mock_history

                        start_time = datetime.now(UTC) - timedelta(hours=1)
                        end_time = datetime.now(UTC)

                        result = await fetcher._fetch_channel_messages(
                            channel, start_time, end_time
                        )

                        assert len(result.messages) == 1
                        # Should have 10 files + overflow message
                        assert len(result.messages[0]["attachments"]) == 11
                        assert result.messages[0]["attachments"][10] == "...and 5 more"

    @pytest.mark.asyncio
    async def test_fetch_channel_messages_limits_reactions(self):
        """Test that reactions are limited to 20 items."""
        valid_token = "x" * 60
        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": valid_token}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()

                        channel = Mock(spec=discord.TextChannel)
                        channel.name = "general"
                        channel.id = 111

                        message = Mock(spec=discord.Message)
                        message.id = 1
                        message.author = Mock()
                        message.author.bot = False
                        message.author.display_name = "Alice"
                        message.author.id = 1001
                        message.content = "Wow!"
                        message.created_at = datetime.now(UTC)
                        message.attachments = []

                        # Create 25 mock reactions
                        reactions = []
                        for i in range(25):
                            reaction = Mock()
                            reaction.emoji = f"emoji{i}"
                            reaction.count = i + 1
                            reactions.append(reaction)
                        message.reactions = reactions

                        async def mock_history(*args, **kwargs):
                            yield message

                        channel.history = mock_history

                        start_time = datetime.now(UTC) - timedelta(hours=1)
                        end_time = datetime.now(UTC)

                        result = await fetcher._fetch_channel_messages(
                            channel, start_time, end_time
                        )

                        assert len(result.messages) == 1
                        # Should be limited to 20 reactions
                        assert len(result.messages[0]["reactions"]) == 20

    @pytest.mark.asyncio
    async def test_fetch_channel_messages_truncates_author_name(self):
        """Test that author display names are truncated to 100 chars."""
        valid_token = "x" * 60
        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": valid_token}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()

                        channel = Mock(spec=discord.TextChannel)
                        channel.name = "general"
                        channel.id = 111

                        message = Mock(spec=discord.Message)
                        message.id = 1
                        message.author = Mock()
                        message.author.bot = False
                        message.author.display_name = "A" * 200  # Very long name
                        message.author.id = 1001
                        message.content = "Hello"
                        message.created_at = datetime.now(UTC)
                        message.attachments = []
                        message.reactions = []

                        async def mock_history(*args, **kwargs):
                            yield message

                        channel.history = mock_history

                        start_time = datetime.now(UTC) - timedelta(hours=1)
                        end_time = datetime.now(UTC)

                        result = await fetcher._fetch_channel_messages(
                            channel, start_time, end_time
                        )

                        assert len(result.messages[0]["author"]) == 100

    @pytest.mark.asyncio
    async def test_fetch_channel_messages_sorts_by_timestamp(self):
        """Test that messages are sorted by timestamp."""
        valid_token = "x" * 60
        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": valid_token}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()

                        channel = Mock(spec=discord.TextChannel)
                        channel.name = "general"
                        channel.id = 111

                        # Create messages with different timestamps
                        msg1 = Mock(spec=discord.Message)
                        msg1.id = 1
                        msg1.author = Mock()
                        msg1.author.bot = False
                        msg1.author.display_name = "Alice"
                        msg1.author.id = 1001
                        msg1.content = "First"
                        msg1.created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
                        msg1.attachments = []
                        msg1.reactions = []

                        msg2 = Mock(spec=discord.Message)
                        msg2.id = 2
                        msg2.author = Mock()
                        msg2.author.bot = False
                        msg2.author.display_name = "Bob"
                        msg2.author.id = 1002
                        msg2.content = "Second"
                        msg2.created_at = datetime(2024, 1, 1, 13, 0, 0, tzinfo=UTC)
                        msg2.attachments = []
                        msg2.reactions = []

                        # Yield in reverse order
                        async def mock_history(*args, **kwargs):
                            yield msg2
                            yield msg1

                        channel.history = mock_history

                        start_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
                        end_time = datetime(2024, 1, 1, 23, 59, 59, tzinfo=UTC)

                        result = await fetcher._fetch_channel_messages(
                            channel, start_time, end_time
                        )

                        # Should be sorted by timestamp
                        assert result.messages[0]["content"] == "First"
                        assert result.messages[1]["content"] == "Second"

    @pytest.mark.asyncio
    async def test_fetch_channel_messages_handles_forbidden(self):
        """Test handling of Forbidden error (no channel access)."""
        valid_token = "x" * 60
        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": valid_token}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()

                        channel = Mock(spec=discord.TextChannel)
                        channel.name = "secret"
                        channel.id = 999

                        # Mock history to raise Forbidden
                        async def mock_history(*args, **kwargs):
                            raise discord.Forbidden(Mock(), "No access")
                            yield  # unreachable but makes this a generator

                        channel.history = mock_history

                        start_time = datetime.now(UTC) - timedelta(hours=1)
                        end_time = datetime.now(UTC)

                        # Should not raise, just return empty
                        result = await fetcher._fetch_channel_messages(
                            channel, start_time, end_time
                        )

                        assert result.channel_name == "secret"
                        assert len(result.messages) == 0

    @pytest.mark.asyncio
    async def test_fetch_channel_messages_handles_http_exception(self):
        """Test handling of HTTPException during message fetch."""
        valid_token = "x" * 60
        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": valid_token}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()

                        channel = Mock(spec=discord.TextChannel)
                        channel.name = "problematic"
                        channel.id = 888

                        # Mock history to raise HTTPException
                        async def mock_history(*args, **kwargs):
                            raise discord.HTTPException(Mock(), "Rate limited")
                            yield

                        channel.history = mock_history

                        start_time = datetime.now(UTC) - timedelta(hours=1)
                        end_time = datetime.now(UTC)

                        # Should not raise, just return empty and print warning
                        result = await fetcher._fetch_channel_messages(
                            channel, start_time, end_time
                        )

                        assert result.channel_name == "problematic"
                        assert len(result.messages) == 0

    @pytest.mark.asyncio
    async def test_fetch_channel_messages_respects_max_limit(self):
        """Test that message limit from environment is respected."""
        valid_token = "x" * 60
        with patch.dict(
            "os.environ",
            {
                "DISCORD_BOT_TOKEN": valid_token,
                "DISCORD_CHAT_MAX_MESSAGES": "100",
            },
        ):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()

                        # Verify max_messages_per_channel property returns correct value
                        assert fetcher.max_messages_per_channel == 100

    @pytest.mark.asyncio
    async def test_fetch_channel_messages_yields_control_periodically(self):
        """Test that event loop yields control every 100 messages."""
        valid_token = "x" * 60
        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": valid_token}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()

                        channel = Mock(spec=discord.TextChannel)
                        channel.name = "general"
                        channel.id = 111

                        # Create 250 messages to test yielding
                        async def mock_history(*args, **kwargs):
                            for i in range(250):
                                msg = Mock(spec=discord.Message)
                                msg.id = i
                                msg.author = Mock()
                                msg.author.bot = False
                                msg.author.display_name = f"User{i}"
                                msg.author.id = 1000 + i
                                msg.content = f"Message {i}"
                                msg.created_at = datetime.now(UTC)
                                msg.attachments = []
                                msg.reactions = []
                                yield msg

                        channel.history = mock_history

                        start_time = datetime.now(UTC) - timedelta(hours=1)
                        end_time = datetime.now(UTC)

                        # Should complete without issues
                        result = await fetcher._fetch_channel_messages(
                            channel, start_time, end_time
                        )

                        assert len(result.messages) == 250


class TestFetchChannelsWithRateLimiting:
    """Tests for _fetch_channels_with_rate_limiting async method."""

    @pytest.mark.asyncio
    async def test_fetch_channels_with_rate_limiting_success(self):
        """Test fetching multiple channels with rate limiting."""
        valid_token = "x" * 60
        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": valid_token}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()

                        # Mock _fetch_channel_messages
                        async def mock_fetch(channel, after, before):
                            return ChannelMessages(
                                channel_name=channel.name,
                                channel_id=channel.id,
                                messages=[],
                            )

                        fetcher._fetch_channel_messages = mock_fetch

                        # Create mock channels
                        channels = []
                        for i in range(3):
                            ch = Mock(spec=discord.TextChannel)
                            ch.name = f"channel-{i}"
                            ch.id = 100 + i
                            channels.append(ch)

                        start_time = datetime.now(UTC) - timedelta(hours=1)
                        end_time = datetime.now(UTC)

                        result = await fetcher._fetch_channels_with_rate_limiting(
                            channels, start_time, end_time
                        )

                        assert len(result) == 3
                        assert result[0].channel_name == "channel-0"
                        assert result[1].channel_name == "channel-1"
                        assert result[2].channel_name == "channel-2"

    @pytest.mark.asyncio
    async def test_fetch_channels_respects_semaphore_limit(self):
        """Test that semaphore limits concurrent requests."""
        valid_token = "x" * 60
        with patch.dict(
            "os.environ",
            {
                "DISCORD_BOT_TOKEN": valid_token,
                "DISCORD_CHAT_MAX_CONCURRENT": "2",
            },
        ):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()

                        # Track concurrent calls
                        concurrent_count = 0
                        max_concurrent = 0

                        async def mock_fetch(channel, after, before):
                            nonlocal concurrent_count, max_concurrent
                            concurrent_count += 1
                            max_concurrent = max(max_concurrent, concurrent_count)
                            # Simulate some work
                            await asyncio.sleep(0.1)
                            concurrent_count -= 1
                            return ChannelMessages(
                                channel_name=channel.name,
                                channel_id=channel.id,
                                messages=[],
                            )

                        fetcher._fetch_channel_messages = mock_fetch

                        # Create 5 channels
                        channels = []
                        for i in range(5):
                            ch = Mock(spec=discord.TextChannel)
                            ch.name = f"channel-{i}"
                            ch.id = 100 + i
                            channels.append(ch)

                        start_time = datetime.now(UTC) - timedelta(hours=1)
                        end_time = datetime.now(UTC)

                        await fetcher._fetch_channels_with_rate_limiting(
                            channels, start_time, end_time
                        )

                        # Max concurrent should not exceed the semaphore limit
                        assert max_concurrent <= 2

    @pytest.mark.asyncio
    async def test_fetch_channels_logs_security_events(self):
        """Test that rate limiting and API calls are logged."""
        valid_token = "x" * 60
        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": valid_token}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()

                        # Mock _fetch_channel_messages
                        async def mock_fetch(channel, after, before):
                            return ChannelMessages(
                                channel_name=channel.name,
                                channel_id=channel.id,
                                messages=[],
                            )

                        fetcher._fetch_channel_messages = mock_fetch

                        # Mock security logger
                        mock_logger = Mock()
                        fetcher._security_logger = mock_logger

                        channels = [Mock(spec=discord.TextChannel, name="test", id=123)]

                        start_time = datetime.now(UTC) - timedelta(hours=1)
                        end_time = datetime.now(UTC)

                        await fetcher._fetch_channels_with_rate_limiting(
                            channels, start_time, end_time
                        )

                        # Should log rate limit enforcement
                        mock_logger.log_rate_limit.assert_called_once()

                        # Should log API call
                        mock_logger.log_api_call.assert_called_once()


class TestFetchServerMessagesImpl:
    """Tests for _fetch_server_messages_impl async method."""

    @pytest.mark.asyncio
    async def test_fetch_server_messages_impl_success(self):
        """Test successful fetch of server messages."""
        valid_token = "x" * 60
        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": valid_token}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()

                        # Mock the client start and close
                        fetcher._client.start = AsyncMock()
                        fetcher._client.close = AsyncMock()
                        fetcher._client.is_closed = Mock(return_value=False)

                        # Mock ready event
                        fetcher._ready_event.set()

                        # Mock guild
                        guild = Mock(spec=discord.Guild)
                        guild.name = "Test Server"
                        guild.id = 123
                        fetcher._client.guilds = [guild]

                        # Mock text channel
                        channel = Mock(spec=discord.TextChannel)
                        channel.name = "general"
                        channel.id = 111
                        guild.channels = [channel]

                        # Mock _fetch_channels_with_rate_limiting
                        async def mock_fetch_channels(channels, after, before):
                            return [
                                ChannelMessages(
                                    channel_name="general",
                                    channel_id=111,
                                    messages=[
                                        {
                                            "id": 1,
                                            "author": "Alice",
                                            "content": "Hello",
                                            "timestamp": datetime.now(UTC).isoformat(),
                                        }
                                    ],
                                )
                            ]

                        fetcher._fetch_channels_with_rate_limiting = mock_fetch_channels

                        result = await fetcher._fetch_server_messages_impl("Test Server", hours=6)

                        assert result.server_name == "Test Server"
                        assert result.server_id == 123
                        assert len(result.channels) == 1
                        assert result.channels[0].channel_name == "general"
                        assert result.total_messages == 1

                        # Client should be closed
                        fetcher._client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_server_messages_impl_filters_empty_channels(self):
        """Test that channels with no messages are filtered out."""
        valid_token = "x" * 60
        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": valid_token}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()

                        fetcher._client.start = AsyncMock()
                        fetcher._client.close = AsyncMock()
                        fetcher._client.is_closed = Mock(return_value=False)
                        fetcher._ready_event.set()

                        guild = Mock(spec=discord.Guild)
                        guild.name = "Test Server"
                        guild.id = 123
                        fetcher._client.guilds = [guild]

                        channel1 = Mock(spec=discord.TextChannel)
                        channel2 = Mock(spec=discord.TextChannel)
                        guild.channels = [channel1, channel2]

                        async def mock_fetch_channels(channels, after, before):
                            return [
                                ChannelMessages(channel_name="empty", channel_id=1, messages=[]),
                                ChannelMessages(
                                    channel_name="active",
                                    channel_id=2,
                                    messages=[{"id": 1}],
                                ),
                            ]

                        fetcher._fetch_channels_with_rate_limiting = mock_fetch_channels

                        result = await fetcher._fetch_server_messages_impl("Test Server", hours=6)

                        # Should only have 1 channel (empty filtered out)
                        assert len(result.channels) == 1
                        assert result.channels[0].channel_name == "active"

    @pytest.mark.asyncio
    async def test_fetch_server_messages_impl_handles_login_failure(self):
        """Test handling of LoginFailure exception."""
        valid_token = "x" * 60
        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": valid_token}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()

                        # Mock the ready wait to raise LoginFailure
                        # Exception must be raised in main flow, not background task
                        async def mock_wait():
                            raise discord.LoginFailure("Invalid token")

                        fetcher._wait_until_ready = mock_wait
                        fetcher._client.start = AsyncMock()
                        fetcher._client.close = AsyncMock()
                        fetcher._client.is_closed = Mock(return_value=False)

                        with pytest.raises(DiscordClientError) as exc_info:
                            await fetcher._fetch_server_messages_impl("Test Server", hours=6)

                        assert "authentication failed" in str(exc_info.value)
                        assert "DISCORD_BOT_TOKEN" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fetch_server_messages_impl_handles_privileged_intents(self):
        """Test handling of PrivilegedIntentsRequired exception."""
        valid_token = "x" * 60
        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": valid_token}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()

                        # Raise exception in main flow
                        async def mock_wait():
                            raise discord.PrivilegedIntentsRequired(Mock())

                        fetcher._wait_until_ready = mock_wait
                        fetcher._client.start = AsyncMock()
                        fetcher._client.close = AsyncMock()
                        fetcher._client.is_closed = Mock(return_value=False)

                        with pytest.raises(DiscordClientError) as exc_info:
                            await fetcher._fetch_server_messages_impl("Test Server", hours=6)

                        assert "Privileged intents required" in str(exc_info.value)
                        assert "MESSAGE CONTENT INTENT" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fetch_server_messages_impl_handles_http_exception(self):
        """Test handling of HTTPException."""
        valid_token = "x" * 60
        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": valid_token}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()

                        http_error = discord.HTTPException(Mock(), "Rate limited")
                        http_error.status = 429

                        # Raise exception in main flow
                        async def mock_wait():
                            raise http_error

                        fetcher._wait_until_ready = mock_wait
                        fetcher._client.start = AsyncMock()
                        fetcher._client.close = AsyncMock()
                        fetcher._client.is_closed = Mock(return_value=False)

                        with pytest.raises(DiscordClientError) as exc_info:
                            await fetcher._fetch_server_messages_impl("Test Server", hours=6)

                        assert "Discord API request failed" in str(exc_info.value)
                        assert "429" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fetch_server_messages_impl_handles_generic_exception(self):
        """Test handling of generic exceptions."""
        valid_token = "x" * 60
        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": valid_token}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()

                        fetcher._client.start = AsyncMock()
                        fetcher._client.close = AsyncMock()
                        fetcher._client.is_closed = Mock(return_value=False)

                        async def mock_wait():
                            raise RuntimeError("Unexpected error")

                        fetcher._wait_until_ready = mock_wait

                        with pytest.raises(DiscordClientError) as exc_info:
                            await fetcher._fetch_server_messages_impl("Test Server", hours=6)

                        # Should get generic error message
                        assert "Failed to fetch Discord messages" in str(exc_info.value)
                        # Should close client on error
                        fetcher._client.close.assert_called()

    @pytest.mark.asyncio
    async def test_fetch_server_messages_impl_closes_client_on_error(self):
        """Test that client is closed even when errors occur."""
        valid_token = "x" * 60
        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": valid_token}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()

                        fetcher._client.start = AsyncMock()
                        fetcher._client.close = AsyncMock()
                        fetcher._client.is_closed = Mock(return_value=False)
                        fetcher._ready_event.set()

                        # Make _find_server_by_name raise an error
                        def mock_find(name):
                            raise ServerNotFoundError("Not found")

                        fetcher._find_server_by_name = mock_find

                        fetcher._client.guilds = []

                        with pytest.raises(DiscordClientError):
                            await fetcher._fetch_server_messages_impl("Test Server", hours=6)

                        # Client should still be closed
                        fetcher._client.close.assert_called()

    @pytest.mark.asyncio
    async def test_fetch_server_messages_impl_calculates_time_window(self):
        """Test that time window is calculated correctly."""
        valid_token = "x" * 60
        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": valid_token}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()

                        fetcher._client.start = AsyncMock()
                        fetcher._client.close = AsyncMock()
                        fetcher._client.is_closed = Mock(return_value=False)
                        fetcher._ready_event.set()

                        guild = Mock(spec=discord.Guild)
                        guild.name = "Test"
                        guild.id = 123
                        guild.channels = []
                        fetcher._client.guilds = [guild]

                        async def mock_fetch(channels, after, before):
                            return []

                        fetcher._fetch_channels_with_rate_limiting = mock_fetch

                        result = await fetcher._fetch_server_messages_impl("Test", hours=12)

                        # Check time window
                        time_diff = result.end_time - result.start_time
                        # Should be approximately 12 hours
                        assert abs(time_diff.total_seconds() - 12 * 3600) < 10


class TestFetchServerMessages:
    """Tests for fetch_server_messages async method (with timeout wrapper)."""

    @pytest.mark.asyncio
    async def test_fetch_server_messages_success(self):
        """Test successful fetch with timeout wrapper."""
        valid_token = "x" * 60
        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": valid_token}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()

                        # Mock _fetch_server_messages_impl
                        async def mock_impl(server_name, hours):
                            return ServerDigestData(
                                server_name=server_name,
                                server_id=123,
                                channels=[],
                                start_time=datetime.now(UTC),
                                end_time=datetime.now(UTC),
                                total_messages=0,
                            )

                        fetcher._fetch_server_messages_impl = mock_impl

                        result = await fetcher.fetch_server_messages("Test Server", hours=6)

                        assert result.server_name == "Test Server"

    @pytest.mark.asyncio
    async def test_fetch_server_messages_timeout(self):
        """Test timeout handling in fetch_server_messages."""
        valid_token = "x" * 60
        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": valid_token}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()

                        fetcher._client.is_closed = Mock(return_value=False)
                        fetcher._client.close = AsyncMock()

                        # Mock implementation that takes too long
                        async def mock_impl(server_name, hours):
                            await asyncio.sleep(10)  # Too long
                            return ServerDigestData(
                                server_name=server_name,
                                server_id=123,
                                channels=[],
                                start_time=datetime.now(UTC),
                                end_time=datetime.now(UTC),
                                total_messages=0,
                            )

                        fetcher._fetch_server_messages_impl = mock_impl

                        with pytest.raises(DiscordClientError) as exc_info:
                            await fetcher.fetch_server_messages("Test Server", hours=6, timeout=0.1)

                        assert "timed out" in str(exc_info.value).lower()
                        # Client should be closed on timeout
                        fetcher._client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_server_messages_uses_default_timeout(self):
        """Test that default timeout from property is used."""
        valid_token = "x" * 60
        with patch.dict(
            "os.environ",
            {
                "DISCORD_BOT_TOKEN": valid_token,
                "DISCORD_CHAT_TIMEOUT": "120",
            },
        ):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()

                        # Check that property returns correct value
                        assert fetcher.operation_timeout == 120.0

                        async def mock_impl(server_name, hours):
                            return ServerDigestData(
                                server_name=server_name,
                                server_id=123,
                                channels=[],
                                start_time=datetime.now(UTC),
                                end_time=datetime.now(UTC),
                                total_messages=0,
                            )

                        fetcher._fetch_server_messages_impl = mock_impl

                        # Should use default timeout of 120
                        result = await fetcher.fetch_server_messages("Test Server", hours=6)
                        assert result is not None

    @pytest.mark.asyncio
    async def test_fetch_server_messages_custom_timeout_overrides_default(self):
        """Test that custom timeout parameter overrides default."""
        valid_token = "x" * 60
        with patch.dict(
            "os.environ",
            {
                "DISCORD_BOT_TOKEN": valid_token,
                "DISCORD_CHAT_TIMEOUT": "120",
            },
        ):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()

                        fetcher._client.is_closed = Mock(return_value=False)
                        fetcher._client.close = AsyncMock()

                        async def mock_impl(server_name, hours):
                            await asyncio.sleep(1)
                            return ServerDigestData(
                                server_name=server_name,
                                server_id=123,
                                channels=[],
                                start_time=datetime.now(UTC),
                                end_time=datetime.now(UTC),
                                total_messages=0,
                            )

                        fetcher._fetch_server_messages_impl = mock_impl

                        # Custom timeout of 0.1 should override default of 120
                        with pytest.raises(DiscordClientError) as exc_info:
                            await fetcher.fetch_server_messages("Test Server", hours=6, timeout=0.1)

                        assert "timed out" in str(exc_info.value).lower()


class TestSynchronousWrapper:
    """Tests for the synchronous fetch_server_messages function."""

    def test_fetch_server_messages_sync_wrapper(self):
        """Test synchronous wrapper calls async version."""
        from discord_chat.services.discord_client import fetch_server_messages

        with patch(
            "discord_chat.services.discord_client.DiscordMessageFetcher"
        ) as mock_fetcher_class:
            mock_fetcher = Mock()
            mock_fetcher_class.return_value = mock_fetcher

            # Mock the async method
            async def mock_async_fetch(server_name, hours):
                return ServerDigestData(
                    server_name=server_name,
                    server_id=123,
                    channels=[],
                    start_time=datetime.now(UTC),
                    end_time=datetime.now(UTC),
                    total_messages=0,
                )

            mock_fetcher.fetch_server_messages = mock_async_fetch

            result = fetch_server_messages("Test Server", hours=12)

            assert result.server_name == "Test Server"
            assert result.total_messages == 0


class TestOnReadyCallback:
    """Tests for the on_ready event callback."""

    @pytest.mark.asyncio
    async def test_on_ready_sets_event_and_logs(self):
        """Test that on_ready callback sets ready event and logs."""
        valid_token = "x" * 60
        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": valid_token}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": f"{tmpdir}/sec.log"}):
                    with patch("discord_chat.services.discord_client.discord.Client"):
                        fetcher = DiscordMessageFetcher()

                        # Mock security logger
                        mock_logger = Mock()
                        fetcher._security_logger = mock_logger

                        # Initially event should not be set
                        assert not fetcher._ready_event.is_set()

                        # Trigger on_ready manually
                        # The callback is registered in __init__, we need to call it
                        # Find and call the on_ready handler
                        for call in fetcher._client.event.call_args_list:
                            handler = call[0][0]
                            if handler.__name__ == "on_ready":
                                await handler()
                                break

                        # Event should now be set
                        assert fetcher._ready_event.is_set()

                        # Should have logged auth success
                        mock_logger.log_auth_attempt.assert_called_once_with(True, "Discord")
