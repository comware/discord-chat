#!/usr/bin/env python3
"""Main CLI entry point for discord-chat."""

import logging
import sys

import click
from dotenv import load_dotenv

from discord_chat.commands.activity import activity
from discord_chat.commands.digest import digest
from discord_chat.commands.version import get_version, version

# Load environment variables from .env file if present
load_dotenv()


def setup_logging(debug: bool) -> None:
    """Configure logging based on debug flag."""
    level = logging.DEBUG if debug else logging.WARNING
    format_str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s" if debug else "%(message)s"
    logging.basicConfig(
        level=level,
        format=format_str,
        stream=sys.stderr,
    )
    # Suppress noisy discord.py warnings (e.g., "PyNaCl is not installed")
    if not debug:
        logging.getLogger("discord").setLevel(logging.ERROR)
    if debug:
        logging.debug("Debug logging enabled")


@click.group()
@click.version_option(version=get_version(), prog_name="discord-chat")
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    envvar="DISCORD_CHAT_DEBUG",
    help="Enable debug logging output",
)
@click.pass_context
def main(ctx: click.Context, debug: bool) -> None:
    """discord-chat - A CLI tool for Discord server activity digests."""
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug
    setup_logging(debug)


# Register commands
main.add_command(activity)
main.add_command(digest)
main.add_command(version)


if __name__ == "__main__":
    main()
