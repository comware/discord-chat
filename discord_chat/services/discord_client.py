"""Discord client service for fetching messages from servers."""

import asyncio
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import discord

from discord_chat.utils.security_logger import get_security_logger


@dataclass
class ChannelMessages:
    """Messages from a single channel."""

    channel_name: str
    channel_id: int
    messages: list[dict]


@dataclass
class ServerDigestData:
    """All messages from a server within a time window."""

    server_name: str
    server_id: int
    channels: list[ChannelMessages]
    start_time: datetime
    end_time: datetime
    total_messages: int


class DiscordClientError(Exception):
    """Base exception for Discord client errors."""

    pass


class ServerNotFoundError(DiscordClientError):
    """Raised when the specified server is not found."""

    pass


def _get_env_int(name: str, default: int, min_val: int, max_val: int) -> int:
    """Get an integer from environment with validation.

    Args:
        name: Environment variable name.
        default: Default value if not set.
        min_val: Minimum allowed value.
        max_val: Maximum allowed value.

    Returns:
        Validated integer value.
    """
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        int_val = int(value)
        if int_val < min_val or int_val > max_val:
            # Log warning but use default
            return default
        return int_val
    except ValueError:
        return default


class DiscordMessageFetcher:
    """Fetches messages from Discord servers.

    This class handles connecting to Discord, finding servers by name,
    and fetching messages from all text channels within a specified time window.

    Thread Safety: NOT thread-safe. Create a new instance for each concurrent operation.

    Configuration via environment variables:
        DISCORD_CHAT_TIMEOUT: Operation timeout in seconds (default: 60, range: 10-300)
        DISCORD_CHAT_MAX_MESSAGES: Max messages per channel (default: 1000, range: 100-10000)
        DISCORD_CHAT_MAX_CONCURRENT: Max concurrent channel fetches (default: 5, range: 1-20)
    """

    # Default security constants (can be overridden via environment)
    DEFAULT_TIMEOUT = 60.0  # Overall operation timeout in seconds
    DEFAULT_MAX_MESSAGES_PER_CHANNEL = 1000  # Prevent resource exhaustion
    DEFAULT_MAX_CONCURRENT_CHANNELS = 5  # Rate limiting: max concurrent channel fetches
    MAX_MESSAGE_CONTENT_LENGTH = 100_000  # Max 100KB per message (CRIT-005 fix)

    @property
    def max_messages_per_channel(self) -> int:
        """Get max messages per channel from environment or default."""
        return _get_env_int(
            "DISCORD_CHAT_MAX_MESSAGES",
            self.DEFAULT_MAX_MESSAGES_PER_CHANNEL,
            min_val=100,
            max_val=10000,
        )

    @property
    def max_concurrent_channels(self) -> int:
        """Get max concurrent channel fetches from environment or default."""
        return _get_env_int(
            "DISCORD_CHAT_MAX_CONCURRENT",
            self.DEFAULT_MAX_CONCURRENT_CHANNELS,
            min_val=1,
            max_val=20,
        )

    @property
    def operation_timeout(self) -> float:
        """Get operation timeout from environment or default."""
        return float(
            _get_env_int(
                "DISCORD_CHAT_TIMEOUT",
                int(self.DEFAULT_TIMEOUT),
                min_val=10,
                max_val=300,
            )
        )

    def __init__(self):
        """Initialize the Discord message fetcher.

        Token is read exclusively from DISCORD_BOT_TOKEN environment variable
        for security (prevents token exposure in process listings).
        """
        self._token = self._load_token()
        self._security_logger = get_security_logger()

        # Set up intents - we need message content and guild access
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True

        self._client = discord.Client(intents=intents)
        self._ready_event = asyncio.Event()

        @self._client.event
        async def on_ready():
            self._ready_event.set()
            self._security_logger.log_auth_attempt(True, "Discord")

    @staticmethod
    def _load_token() -> str:
        """Load and validate Discord bot token from environment.

        Returns:
            Validated Discord bot token.

        Raises:
            DiscordClientError: If token is missing or invalid format.
        """
        token = os.environ.get("DISCORD_BOT_TOKEN")
        if not token:
            raise DiscordClientError(
                "DISCORD_BOT_TOKEN environment variable is required. "
                "Set it in your .env file or environment."
            )
        token = token.strip()
        # Discord bot tokens are typically 70+ characters
        if len(token) < 50:
            raise DiscordClientError(
                "Invalid Discord bot token format. "
                "Token appears too short - please verify your DISCORD_BOT_TOKEN."
            )
        return token

    async def _wait_until_ready(self, timeout: float = 30.0):
        """Wait for the client to be ready."""
        try:
            await asyncio.wait_for(self._ready_event.wait(), timeout=timeout)
        except TimeoutError:
            raise DiscordClientError("Timed out waiting for Discord connection")

    def _find_server_by_name(self, server_name: str) -> discord.Guild:
        """Find a server (guild) by name.

        Args:
            server_name: The name of the server to find (case-insensitive).

        Returns:
            The Discord guild object.

        Raises:
            ServerNotFoundError: If no server with the given name is found.
        """
        server_name_lower = server_name.lower()
        for guild in self._client.guilds:
            if guild.name.lower() == server_name_lower:
                return guild

        # If exact match not found, try partial match
        for guild in self._client.guilds:
            if server_name_lower in guild.name.lower():
                return guild

        available_servers = [g.name for g in self._client.guilds]
        raise ServerNotFoundError(
            f"Server '{server_name}' not found. "
            f"Available servers: {', '.join(available_servers) or 'None'}"
        )

    async def _fetch_channel_messages(
        self,
        channel: discord.TextChannel,
        after: datetime,
        before: datetime,
    ) -> ChannelMessages:
        """Fetch messages from a single channel within a time window.

        Args:
            channel: The Discord text channel to fetch from.
            after: Fetch messages after this time.
            before: Fetch messages before this time.

        Returns:
            ChannelMessages object containing the channel info and messages.
        """
        messages = []
        try:
            # Use message limit to prevent resource exhaustion
            async for message in channel.history(
                after=after, before=before, limit=self.max_messages_per_channel
            ):
                # Skip bot messages and empty messages
                if message.author.bot:
                    continue
                if not message.content and not message.attachments:
                    continue

                # Truncate message content to prevent memory exhaustion (CRIT-005 fix)
                content = message.content
                if len(content) > self.MAX_MESSAGE_CONTENT_LENGTH:
                    content = content[: self.MAX_MESSAGE_CONTENT_LENGTH] + "...[truncated]"

                # Limit attachments to prevent memory issues
                attachments = [a.filename for a in message.attachments[:10]]  # Max 10 attachments
                if len(message.attachments) > 10:
                    attachments.append(f"...and {len(message.attachments) - 10} more")

                messages.append(
                    {
                        "id": message.id,
                        "author": message.author.display_name[:100],  # Limit author name
                        "author_id": message.author.id,
                        "content": content,
                        "timestamp": message.created_at.isoformat(),
                        "attachments": attachments,
                        "reactions": [
                            {"emoji": str(r.emoji)[:20], "count": r.count}  # Limit emoji length
                            for r in list(message.reactions)[:20]  # Max 20 reactions
                        ],
                    }
                )

                # HIGH-007 fix: Yield control periodically to prevent memory buildup
                # Allow garbage collection every 100 messages
                if len(messages) % 100 == 0:
                    await asyncio.sleep(0)  # Yield to event loop

        except discord.Forbidden:
            # Bot doesn't have permission to read this channel
            pass
        except discord.HTTPException as e:
            # Log but don't fail on individual channel errors
            print(f"Warning: Could not fetch messages from #{channel.name}: {e}")

        # Sort and return - this creates a new list, old messages can be GC'd
        result = ChannelMessages(
            channel_name=channel.name,
            channel_id=channel.id,
            messages=sorted(messages, key=lambda m: m["timestamp"]),
        )

        # Clear messages list to help garbage collection (HIGH-007 fix)
        messages.clear()

        return result

    async def _fetch_channels_with_rate_limiting(
        self,
        channels: list[discord.TextChannel],
        after: datetime,
        before: datetime,
    ) -> list[ChannelMessages]:
        """Fetch messages from multiple channels with rate limiting.

        Args:
            channels: List of Discord text channels to fetch from.
            after: Fetch messages after this time.
            before: Fetch messages before this time.

        Returns:
            List of ChannelMessages objects.
        """
        # Log rate limiting enforcement
        self._security_logger.log_rate_limit("Discord", self.max_concurrent_channels)

        # Create semaphore to limit concurrent API calls
        semaphore = asyncio.Semaphore(self.max_concurrent_channels)

        async def fetch_with_semaphore(channel: discord.TextChannel) -> ChannelMessages:
            """Wrapper to fetch channel messages with semaphore."""
            start_time = time.time()
            async with semaphore:
                result = await self._fetch_channel_messages(channel, after, before)
            duration_ms = (time.time() - start_time) * 1000
            self._security_logger.log_api_call(
                "Discord", f"fetch_messages:{channel.name}", duration_ms, True
            )
            return result

        # Fetch all channels with rate limiting
        tasks = [fetch_with_semaphore(ch) for ch in channels]
        return await asyncio.gather(*tasks)

    async def fetch_server_messages(
        self,
        server_name: str,
        hours: int = 6,
        timeout: float | None = None,
    ) -> ServerDigestData:
        """Fetch messages from all channels in a server.

        Args:
            server_name: Name of the Discord server (case-insensitive).
            hours: Number of hours to look back for messages.
            timeout: Overall operation timeout in seconds. Defaults to OPERATION_TIMEOUT.

        Returns:
            ServerDigestData containing all messages from the time window.

        Raises:
            DiscordClientError: On timeout or other Discord-related errors.
        """
        operation_timeout = timeout if timeout is not None else self.operation_timeout

        try:
            return await asyncio.wait_for(
                self._fetch_server_messages_impl(server_name, hours),
                timeout=operation_timeout,
            )
        except TimeoutError:
            # Ensure cleanup on timeout
            if not self._client.is_closed():
                await self._client.close()
            raise DiscordClientError(
                f"Operation timed out after {operation_timeout} seconds. "
                "The server may have too many channels or messages."
            )

    async def _fetch_server_messages_impl(
        self,
        server_name: str,
        hours: int,
    ) -> ServerDigestData:
        """Internal implementation of fetch_server_messages.

        This is separated to allow wrapping with timeout.
        """
        end_time = datetime.now(UTC)
        start_time = end_time - timedelta(hours=hours)

        try:
            # Start the client in a background task
            login_task = asyncio.create_task(self._client.start(self._token))

            try:
                # Wait for ready
                await self._wait_until_ready()

                # Find the server
                guild = self._find_server_by_name(server_name)

                # Get all text channels
                text_channels = [ch for ch in guild.channels if isinstance(ch, discord.TextChannel)]

                # Fetch messages from channels with rate limiting
                # Use semaphore to limit concurrent API calls
                channel_results = await self._fetch_channels_with_rate_limiting(
                    text_channels, start_time, end_time
                )

                # Filter out empty channels and calculate total
                channels_with_messages = [ch for ch in channel_results if ch.messages]
                total_messages = sum(len(ch.messages) for ch in channels_with_messages)

                return ServerDigestData(
                    server_name=guild.name,
                    server_id=guild.id,
                    channels=channels_with_messages,
                    start_time=start_time,
                    end_time=end_time,
                    total_messages=total_messages,
                )
            finally:
                # Always close the client
                await self._client.close()
                # Cancel the login task if still running
                login_task.cancel()
                try:
                    await login_task
                except asyncio.CancelledError:
                    pass

        except discord.PrivilegedIntentsRequired:
            raise DiscordClientError(
                "Privileged intents required. Please enable MESSAGE CONTENT INTENT "
                "in the Discord Developer Portal: "
                "https://discord.com/developers/applications/ → Bot → Privileged Gateway Intents"
            )
        except discord.LoginFailure:
            # Log auth failure
            self._security_logger.log_auth_attempt(False, "Discord", "Invalid token")
            # Sanitize login error to prevent credential exposure
            raise DiscordClientError(
                "Discord authentication failed. Please verify your DISCORD_BOT_TOKEN."
            )
        except discord.HTTPException as e:
            # Sanitize HTTP errors but include status code
            status = e.status if hasattr(e, "status") else "unknown"
            raise DiscordClientError(f"Discord API request failed (status: {status})")
        except Exception:
            # Ensure cleanup on any error
            if not self._client.is_closed():
                await self._client.close()
            # Generic error message to prevent internal info disclosure
            raise DiscordClientError(
                "Failed to fetch Discord messages. "
                "Please check your connection and bot permissions."
            )


def fetch_server_messages(server_name: str, hours: int = 6) -> ServerDigestData:
    """Synchronous wrapper for fetching server messages.

    This is the main entry point for CLI usage.

    Args:
        server_name: Name of the Discord server.
        hours: Number of hours to look back.

    Returns:
        ServerDigestData containing all messages.
    """
    fetcher = DiscordMessageFetcher()
    return asyncio.run(fetcher.fetch_server_messages(server_name, hours))
