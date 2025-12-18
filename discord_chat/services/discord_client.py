"""Discord client service for fetching messages from servers."""

import asyncio
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import discord


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


class DiscordMessageFetcher:
    """Fetches messages from Discord servers.

    This class handles connecting to Discord, finding servers by name,
    and fetching messages from all text channels within a specified time window.
    """

    def __init__(self, token: str | None = None):
        """Initialize the Discord message fetcher.

        Args:
            token: Discord bot token. If not provided, reads from DISCORD_BOT_TOKEN env var.
        """
        self.token = token or os.environ.get("DISCORD_BOT_TOKEN")
        if not self.token:
            raise DiscordClientError(
                "Discord bot token not provided. "
                "Set DISCORD_BOT_TOKEN environment variable or pass token parameter."
            )

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
            async for message in channel.history(after=after, before=before, limit=None):
                # Skip bot messages and empty messages
                if message.author.bot:
                    continue
                if not message.content and not message.attachments:
                    continue

                messages.append(
                    {
                        "id": message.id,
                        "author": message.author.display_name,
                        "author_id": message.author.id,
                        "content": message.content,
                        "timestamp": message.created_at.isoformat(),
                        "attachments": [a.filename for a in message.attachments],
                        "reactions": [
                            {"emoji": str(r.emoji), "count": r.count} for r in message.reactions
                        ],
                    }
                )
        except discord.Forbidden:
            # Bot doesn't have permission to read this channel
            pass
        except discord.HTTPException as e:
            # Log but don't fail on individual channel errors
            print(f"Warning: Could not fetch messages from #{channel.name}: {e}")

        return ChannelMessages(
            channel_name=channel.name,
            channel_id=channel.id,
            messages=sorted(messages, key=lambda m: m["timestamp"]),
        )

    async def fetch_server_messages(
        self,
        server_name: str,
        hours: int = 6,
    ) -> ServerDigestData:
        """Fetch messages from all channels in a server.

        Args:
            server_name: Name of the Discord server (case-insensitive).
            hours: Number of hours to look back for messages.

        Returns:
            ServerDigestData containing all messages from the time window.
        """
        end_time = datetime.now(UTC)
        start_time = end_time - timedelta(hours=hours)

        try:
            # Start the client in a background task
            login_task = asyncio.create_task(self._client.start(self.token))

            try:
                # Wait for ready
                await self._wait_until_ready()

                # Find the server
                guild = self._find_server_by_name(server_name)

                # Get all text channels
                text_channels = [ch for ch in guild.channels if isinstance(ch, discord.TextChannel)]

                # Fetch messages from all channels concurrently
                channel_tasks = [
                    self._fetch_channel_messages(ch, start_time, end_time) for ch in text_channels
                ]
                channel_results = await asyncio.gather(*channel_tasks)

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
        except discord.LoginFailure as e:
            raise DiscordClientError(f"Discord login failed: {e}")
        except Exception:
            # Ensure cleanup on any error
            if not self._client.is_closed():
                await self._client.close()
            raise


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
