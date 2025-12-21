"""Activity command for checking Discord server message counts."""

import os

import click

from discord_chat.services.discord_client import (
    DiscordClientError,
    ServerNotFoundError,
    fetch_server_messages,
)


@click.command()
@click.argument("server_name")
@click.option(
    "--hours",
    "-h",
    default=24,
    type=int,
    help="Number of hours to look back (default: 24)",
)
def activity(server_name: str, hours: int) -> None:
    """Check message activity in a Discord server.

    Outputs each channel name and message count, nothing more.

    Example:
        discord-chat activity "tne.ai" --hours 12
    """
    if not os.environ.get("DISCORD_BOT_TOKEN"):
        raise click.ClickException("DISCORD_BOT_TOKEN environment variable is required.")

    try:
        data = fetch_server_messages(server_name, hours)
    except ServerNotFoundError as e:
        raise click.ClickException(str(e))
    except DiscordClientError as e:
        raise click.ClickException(f"Discord error: {e}")

    if data.total_messages == 0:
        click.echo("No messages found.")
        return

    # Sort by message count descending
    sorted_channels = sorted(data.channels, key=lambda c: -len(c.messages))

    # Calculate column widths
    max_name_len = max(len(c.channel_name) for c in sorted_channels)
    col_width = max(max_name_len + 1, 20)  # minimum 20 chars

    # Print table header
    click.echo(f"{'Channel':<{col_width}} {'Messages':>10}")
    click.echo(f"{'-' * col_width} {'-' * 10}")

    # Print rows
    for channel in sorted_channels:
        click.echo(f"#{channel.channel_name:<{col_width - 1}} {len(channel.messages):>10}")

    # Print total
    click.echo(f"{'-' * col_width} {'-' * 10}")
    click.echo(f"{'Total':<{col_width}} {data.total_messages:>10}")
