"""Digest command for generating Discord server activity summaries."""

import os
from pathlib import Path

import click

from discord_chat.services.discord_client import (
    DiscordClientError,
    ServerNotFoundError,
    fetch_server_messages,
)
from discord_chat.services.llm import LLMError, get_provider
from discord_chat.utils.digest_formatter import (
    create_full_digest,
    format_messages_for_llm,
    format_time_range,
    get_default_output_filename,
)


@click.command()
@click.argument("server_name")
@click.option(
    "--hours",
    "-h",
    default=6,
    type=int,
    help="Number of hours to look back for messages (default: 6)",
)
@click.option(
    "--llm",
    "-l",
    type=click.Choice(["claude", "openai"], case_sensitive=False),
    default=None,
    help="LLM provider to use (auto-selects if not specified)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=".",
    help="Output directory for the digest file (default: current directory)",
)
def digest(server_name: str, hours: int, llm: str | None, output: str) -> None:
    """Generate a digest of Discord server activity.

    Fetches messages from all channels in SERVER_NAME over the specified
    time period and uses an LLM to create a summarized digest.

    Example:
        discord-chat digest "tne.ai" --hours 3 --llm claude

    Requires DISCORD_BOT_TOKEN environment variable to be set.
    For LLM, set ANTHROPIC_API_KEY (Claude) or OPENAI_API_KEY (OpenAI).
    """
    # Validate environment
    if not os.environ.get("DISCORD_BOT_TOKEN"):
        raise click.ClickException(
            "DISCORD_BOT_TOKEN environment variable is required. "
            "Create a Discord bot and set its token."
        )

    click.echo(f"Fetching messages from '{server_name}' (last {hours} hours)...")

    # Fetch messages from Discord
    try:
        data = fetch_server_messages(server_name, hours)
    except ServerNotFoundError as e:
        raise click.ClickException(str(e))
    except DiscordClientError as e:
        raise click.ClickException(f"Discord error: {e}")

    if data.total_messages == 0:
        click.echo(f"No messages found in '{data.server_name}' in the last {hours} hours.")
        return

    click.echo(f"Found {data.total_messages} messages across {len(data.channels)} channels.")

    # Get LLM provider
    try:
        provider = get_provider(llm)
        click.echo(f"Using {provider.name} to generate digest...")
    except LLMError as e:
        raise click.ClickException(str(e))

    # Format messages for LLM
    messages_text = format_messages_for_llm(data)
    time_range = format_time_range(data.start_time, data.end_time)

    # Generate digest with LLM
    try:
        llm_digest = provider.generate_digest(
            messages_text=messages_text,
            server_name=data.server_name,
            channel_count=len(data.channels),
            message_count=data.total_messages,
            time_range=time_range,
        )
    except LLMError as e:
        raise click.ClickException(f"LLM error: {e}")

    # Create full digest document
    full_digest = create_full_digest(data, llm_digest, provider.name)

    # Print to console
    click.echo("\n" + "=" * 60)
    click.echo(full_digest)
    click.echo("=" * 60 + "\n")

    # Save to file
    output_dir = Path(output)
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = get_default_output_filename(data.server_name)
    output_path = output_dir / filename

    output_path.write_text(full_digest, encoding="utf-8")
    click.echo(f"Digest saved to: {output_path}")
