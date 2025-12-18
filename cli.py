#!/usr/bin/env python3
"""Main CLI entry point for discord-chat."""

import click

from discord_chat.commands.version import version


@click.group()
@click.pass_context
def main(ctx: click.Context) -> None:
    """discord-chat - A CLI application."""
    ctx.ensure_object(dict)


# Register commands
main.add_command(version)


if __name__ == "__main__":
    main()
