"""Digest command for generating Discord server activity summaries."""

import os
import stat
from pathlib import Path

import click

from discord_chat.services.discord_client import (
    DiscordClientError,
    ServerNotFoundError,
    fetch_server_messages,
)
from discord_chat.services.llm import LLMError, get_provider
from discord_chat.utils.digest_formatter import (
    InvalidServerNameError,
    create_full_digest,
    format_messages_for_llm,
    format_time_range,
    get_default_output_filename,
    validate_server_name,
)

# Constants for validation
MIN_HOURS = 1
MAX_HOURS = 168  # 1 week maximum


def write_file_secure(path: Path, content: str) -> None:
    """Write file with secure permissions (owner read/write only).

    Args:
        path: Path to write to.
        content: Content to write.
    """
    # Use os.open with explicit permissions to avoid race conditions
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
    try:
        os.write(fd, content.encode("utf-8"))
    finally:
        os.close(fd)


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
    # Validate server name to prevent path traversal
    try:
        validated_server_name = validate_server_name(server_name)
    except InvalidServerNameError as e:
        raise click.ClickException(str(e))

    # Validate hours range
    if hours < MIN_HOURS or hours > MAX_HOURS:
        raise click.ClickException(
            f"Hours must be between {MIN_HOURS} and {MAX_HOURS}. Got: {hours}"
        )

    # Validate environment
    if not os.environ.get("DISCORD_BOT_TOKEN"):
        raise click.ClickException(
            "DISCORD_BOT_TOKEN environment variable is required. "
            "Create a Discord bot and set its token."
        )

    click.echo(f"Fetching messages from '{validated_server_name}' (last {hours} hours)...")

    # Fetch messages from Discord
    try:
        data = fetch_server_messages(validated_server_name, hours)
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

    write_file_secure(output_path, full_digest)
    click.echo(f"Digest saved to: {output_path}")
