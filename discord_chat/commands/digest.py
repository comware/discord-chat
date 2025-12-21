"""Digest command for generating Discord server activity summaries."""

import os
import stat
import time
from collections.abc import Generator
from contextlib import contextmanager
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
from discord_chat.utils.security_logger import get_security_logger

# Constants for validation
MIN_HOURS = 1
MAX_HOURS = 168  # 1 week maximum


@contextmanager
def progress_status(message: str, quiet: bool = False) -> Generator[None, None, None]:
    """Context manager that shows operation status with timing.

    Args:
        message: Status message to display (e.g., "Fetching messages").
        quiet: If True, suppress output.

    Yields:
        Control back to the caller.

    Example:
        with progress_status("Fetching messages"):
            fetch_messages()
        # Output: Fetching messages... done (2.3s)
    """
    if quiet:
        yield
        return

    click.echo(f"{message}... ", nl=False)
    start = time.time()
    try:
        yield
        elapsed = time.time() - start
        click.echo(f"done ({elapsed:.1f}s)")
    except Exception:
        elapsed = time.time() - start
        click.echo(f"failed ({elapsed:.1f}s)")
        raise


def write_file_secure(path: Path, content: str) -> None:
    """Write file with secure permissions (owner read/write only).

    Args:
        path: Path to write to.
        content: Content to write.

    Raises:
        OSError: If file write fails or path is invalid.
        ValueError: If attempting to overwrite a symlink (security check).
    """
    # HIGH-006 fix: Check if path exists and is a symlink before writing
    # This prevents TOCTOU symlink attacks
    if path.exists() or path.is_symlink():
        # Check if it's a symlink (even if broken)
        if path.is_symlink():
            raise ValueError(
                f"Refusing to write to symlink: {path}. "
                "This could be a security issue. Delete the symlink first."
            )

    # Use os.open with O_EXCL to fail if file exists (prevents races)
    # We use O_CREAT | O_EXCL to atomically create the file
    try:
        fd = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,  # O_EXCL fails if file exists
            stat.S_IRUSR | stat.S_IWUSR,  # 0600 permissions
        )
    except FileExistsError:
        # File already exists, overwrite it but check it's not a symlink first
        if path.is_symlink():
            raise ValueError(f"Refusing to overwrite symlink: {path}")
        # Safe to overwrite - use O_TRUNC
        fd = os.open(path, os.O_WRONLY | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)

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
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview what would be done without calling the LLM API",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    default=False,
    help="Suppress console output (only write to file)",
)
def digest(
    server_name: str, hours: int, llm: str | None, output: str, dry_run: bool, quiet: bool
) -> None:
    """Generate a digest of Discord server activity.

    Fetches messages from all channels in SERVER_NAME over the specified
    time period and uses an LLM to create a summarized digest.

    Example:
        discord-chat digest "tne.ai" --hours 3 --llm claude

    Requires DISCORD_BOT_TOKEN environment variable to be set.
    For LLM, set ANTHROPIC_API_KEY (Claude) or OPENAI_API_KEY (OpenAI).
    """
    security_logger = get_security_logger()

    # Validate server name to prevent path traversal
    try:
        validated_server_name = validate_server_name(server_name)
    except InvalidServerNameError as e:
        security_logger.log_input_validation_failure("server_name", server_name, str(e))
        raise click.ClickException(str(e))

    # Validate hours range
    if hours < MIN_HOURS or hours > MAX_HOURS:
        security_logger.log_input_validation_failure(
            "hours", str(hours), f"Must be between {MIN_HOURS} and {MAX_HOURS}"
        )
        raise click.ClickException(
            f"Hours must be between {MIN_HOURS} and {MAX_HOURS}. Got: {hours}"
        )

    # Validate environment
    if not os.environ.get("DISCORD_BOT_TOKEN"):
        raise click.ClickException(
            "DISCORD_BOT_TOKEN environment variable is required. "
            "Create a Discord bot and set its token."
        )

    # Helper for conditional output
    def echo(msg: str) -> None:
        if not quiet:
            click.echo(msg)

    if dry_run:
        echo("[DRY RUN] Would fetch messages from Discord and generate digest")

    # Fetch messages from Discord
    try:
        with progress_status(
            f"Fetching messages from '{validated_server_name}' (last {hours}h)", quiet
        ):
            data = fetch_server_messages(validated_server_name, hours)
    except ServerNotFoundError as e:
        raise click.ClickException(str(e))
    except DiscordClientError as e:
        raise click.ClickException(f"Discord error: {e}")

    if data.total_messages == 0:
        echo(f"No messages found in '{data.server_name}' in the last {hours} hours.")
        return

    echo(f"Found {data.total_messages} messages across {len(data.channels)} channels.")

    # Get LLM provider
    try:
        provider = get_provider(llm)
    except LLMError as e:
        raise click.ClickException(str(e))

    # Format messages for LLM
    messages_text = format_messages_for_llm(data)
    time_range = format_time_range(data.start_time, data.end_time)

    # In dry-run mode, show preview and exit
    if dry_run:
        echo("\n[DRY RUN] Preview:")
        echo(f"  Server: {data.server_name}")
        echo(f"  Channels: {len(data.channels)}")
        echo(f"  Messages: {data.total_messages}")
        echo(f"  Time range: {time_range}")
        echo(f"  LLM provider: {provider.name}")
        echo(f"  Estimated prompt size: ~{len(messages_text):,} characters")
        output_file = Path(output) / get_default_output_filename(data.server_name)
        echo(f"\n[DRY RUN] Would write digest to: {output_file}")
        echo("[DRY RUN] No API calls made. Remove --dry-run to generate digest.")
        return

    # Generate digest with LLM
    try:
        with progress_status(f"Generating digest with {provider.name}", quiet):
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

    # Print to console (unless quiet mode)
    if not quiet:
        click.echo("\n" + "=" * 60)
        click.echo(full_digest)
        click.echo("=" * 60 + "\n")

    # Save to file
    output_dir = Path(output)
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = get_default_output_filename(data.server_name)
    output_path = output_dir / filename

    write_file_secure(output_path, full_digest)
    security_logger.log_file_operation("write", str(output_path), "0600")
    echo(f"Digest saved to: {output_path}")
