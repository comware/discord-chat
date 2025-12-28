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
    ServerDigestData,
    ServerNotFoundError,
    fetch_server_messages,
)
from discord_chat.services.llm import LLMError, get_provider
from discord_chat.utils.console_output import Console, create_console, render_digest_to_console
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
def progress_status(
    message: str,
    quiet: bool = False,
    console: "Console | None" = None,
) -> Generator[None, None, None]:
    """Context manager that shows operation status with timing.

    Args:
        message: Status message to display (e.g., "Fetching messages").
        quiet: If True, suppress output.
        console: Optional Rich Console instance for output.

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

    if console is None:
        console = create_console()

    console.print(f"[dim]{message}...[/dim] ", end="")
    start = time.time()
    try:
        yield
        elapsed = time.time() - start
        console.print(f"[green]done[/green] [dim]({elapsed:.1f}s)[/dim]")
    except Exception:
        elapsed = time.time() - start
        console.print(f"[red]failed[/red] [dim]({elapsed:.1f}s)[/dim]")
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
    "--file",
    "-f",
    "output_file",
    type=click.Path(),
    default=None,
    help="Save digest to file. Specify a directory (auto-generates filename) or full path.",
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
    help="Suppress all console output (use with --file for silent file save)",
)
@click.option(
    "--no-color",
    is_flag=True,
    default=False,
    envvar="NO_COLOR",
    help="Disable colored/styled output (respects NO_COLOR env var)",
)
@click.option(
    "--channel",
    "-c",
    default=None,
    type=str,
    help="Generate digest for a specific channel only (case-insensitive)",
)
def digest(
    server_name: str,
    hours: int,
    llm: str | None,
    output_file: str | None,
    dry_run: bool,
    quiet: bool,
    no_color: bool,
    channel: str | None,
) -> None:
    """Generate a digest of Discord server activity.

    Fetches messages from all channels (or a specific channel) in SERVER_NAME
    over the specified time period and uses an LLM to create a summarized digest.

    By default, the digest is displayed in the terminal with markdown
    formatting. Use --file to also save to disk.

    Examples:
        discord-chat digest "tne.ai" --hours 3
        discord-chat digest "tne.ai" --channel general --hours 6
        discord-chat digest "tne.ai" -c announcements --file .
        discord-chat digest "tne.ai" --quiet --file .

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

    # Create console for Rich output
    console = create_console(no_color=no_color)

    # Helper for conditional output
    def echo(msg: str, style: str | None = None) -> None:
        if not quiet:
            if style:
                console.print(f"[{style}]{msg}[/{style}]")
            else:
                console.print(msg)

    if dry_run:
        echo("[DRY RUN] Would fetch messages from Discord and generate digest", "yellow")

    # Fetch messages from Discord
    channel_info = f" (#{channel})" if channel else ""
    try:
        with progress_status(
            f"Fetching messages from '{validated_server_name}'{channel_info} (last {hours}h)",
            quiet=quiet,
            console=console,
        ):
            data = fetch_server_messages(validated_server_name, hours)
    except ServerNotFoundError as e:
        raise click.ClickException(str(e))
    except DiscordClientError as e:
        raise click.ClickException(f"Discord error: {e}")

    # Filter to specific channel if requested
    if channel:
        channel_lower = channel.lower().lstrip("#")  # Allow "#general" or "general"
        matching_channels = [ch for ch in data.channels if ch.channel_name.lower() == channel_lower]

        if not matching_channels:
            available = sorted([ch.channel_name for ch in data.channels])
            available_list = ", ".join(f"#{ch}" for ch in available) if available else "none"
            raise click.ClickException(
                f"Channel '#{channel}' not found in '{data.server_name}'. "
                f"Available channels: {available_list}"
            )

        # Create new ServerDigestData with filtered channel
        data = ServerDigestData(
            server_name=data.server_name,
            server_id=data.server_id,
            channels=matching_channels,
            start_time=data.start_time,
            end_time=data.end_time,
            total_messages=sum(len(ch.messages) for ch in matching_channels),
        )

    if data.total_messages == 0:
        if channel:
            echo(f"No messages found in #{channel} in the last {hours} hours.")
        else:
            echo(f"No messages found in '{data.server_name}' in the last {hours} hours.")
        return

    if channel:
        echo(f"Found {data.total_messages} messages in #{channel}.")
    else:
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
        echo("\n[DRY RUN] Preview:", "yellow")
        echo(f"  [bold]Server:[/bold] {data.server_name}")
        if channel:
            echo(f"  [bold]Channel filter:[/bold] #{channel}")
        echo(f"  [bold]Channels:[/bold] {len(data.channels)}")
        echo(f"  [bold]Messages:[/bold] {data.total_messages}")
        echo(f"  [bold]Time range:[/bold] {time_range}")
        echo(f"  [bold]LLM provider:[/bold] {provider.name}")
        echo(f"  [bold]Estimated prompt size:[/bold] ~{len(messages_text):,} characters")
        if output_file:
            preview_path = Path(output_file)
            if preview_path.is_dir() or (not preview_path.suffix and not preview_path.exists()):
                preview_path = preview_path / get_default_output_filename(data.server_name)
            echo(f"\n[DRY RUN] Would write digest to: {preview_path}", "yellow")
        else:
            echo("\n[DRY RUN] Would display digest to screen (no file output)", "yellow")
        echo("[DRY RUN] No API calls made. Remove --dry-run to generate digest.", "yellow")
        return

    # Generate digest with LLM
    try:
        with progress_status(
            f"Generating digest with {provider.name}",
            quiet=quiet,
            console=console,
        ):
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
    full_digest = create_full_digest(data, llm_digest, provider.name, channel)

    # Render to screen with Rich markdown (unless quiet mode)
    render_digest_to_console(full_digest, console=console, quiet=quiet)

    # Save to file only if --file flag is provided
    if output_file:
        output_path = Path(output_file)

        # Determine if output_file is a directory or a file path
        if output_path.is_dir() or (not output_path.suffix and not output_path.exists()):
            # It's a directory path - generate filename
            output_path.mkdir(parents=True, exist_ok=True)
            filename = get_default_output_filename(data.server_name)
            output_path = output_path / filename
        else:
            # It's a file path - ensure parent directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

        write_file_secure(output_path, full_digest)
        security_logger.log_file_operation("write", str(output_path), "0600")
        echo(f"Digest saved to: {output_path}", "green")
