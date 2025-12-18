# Adding New Commands

This guide explains how to add new CLI commands to the discord-chat project.

## Project Structure

Commands live in `discord_chat/commands/` with one file per command or command group:

```
discord_chat/
└── commands/
    ├── __init__.py
    ├── version.py      # Top-level command
    └── config.py       # Command group example
```

## Adding a Top-Level Command

Top-level commands are invoked directly: `discord-chat mycommand`

### Step 1: Create the Command File

Create a new file in `discord_chat/commands/`. For example, `discord_chat/commands/hello.py`:

```python
"""Hello command - greets the user."""

import click


@click.command()
@click.option("--name", "-n", default="World", help="Name to greet")
def hello(name: str) -> None:
    """Greet someone by name."""
    click.echo(f"Hello, {name}!")
```

### Step 2: Register the Command

Import and register the command in `cli.py`:

```python
#!/usr/bin/env python3
"""Main CLI entry point for discord-chat."""

import click

from discord_chat.commands.version import version
from discord_chat.commands.hello import hello  # Add import


@click.group()
@click.pass_context
def main(ctx: click.Context) -> None:
    """discord-chat - A CLI application."""
    ctx.ensure_object(dict)


# Register commands
main.add_command(version)
main.add_command(hello)  # Add registration


if __name__ == "__main__":
    main()
```

### Step 3: Test the Command

```bash
# Test it works
uv run python cli.py hello
uv run python cli.py hello --name "Developer"

# Run linter and tests
make check
```

### Step 4: Add Tests

Create `tests/test_hello.py`:

```python
"""Tests for hello command."""

from click.testing import CliRunner

from cli import main


def test_hello_default():
    """Test hello with default name."""
    runner = CliRunner()
    result = runner.invoke(main, ["hello"])
    assert result.exit_code == 0
    assert "Hello, World!" in result.output


def test_hello_with_name():
    """Test hello with custom name."""
    runner = CliRunner()
    result = runner.invoke(main, ["hello", "--name", "Developer"])
    assert result.exit_code == 0
    assert "Hello, Developer!" in result.output
```

---

## Adding a Command Group

Command groups organize related subcommands: `discord-chat config get`, `discord-chat config set`

### Step 1: Create the Command Group File

Create `discord_chat/commands/config.py`:

```python
"""Config command group - manage application configuration."""

import click


@click.group()
def config() -> None:
    """Manage application configuration."""
    pass


@config.command()
@click.argument("key")
def get(key: str) -> None:
    """Get a configuration value.

    KEY is the configuration key to retrieve.
    """
    # In a real app, this would read from a config file
    click.echo(f"Getting config: {key}")


@config.command()
@click.argument("key")
@click.argument("value")
def set(key: str, value: str) -> None:
    """Set a configuration value.

    KEY is the configuration key to set.
    VALUE is the value to assign.
    """
    # In a real app, this would write to a config file
    click.echo(f"Setting {key} = {value}")


@config.command()
def list() -> None:
    """List all configuration values."""
    click.echo("Listing all config values...")
```

### Step 2: Register the Command Group

In `cli.py`, add the group the same way as a regular command:

```python
from discord_chat.commands.config import config

# Register commands
main.add_command(version)
main.add_command(config)  # Groups are registered the same way
```

### Step 3: Test the Command Group

```bash
# View group help
uv run python cli.py config --help

# Test subcommands
uv run python cli.py config get api_key
uv run python cli.py config set api_key "abc123"
uv run python cli.py config list
```

### Step 4: Add Tests

Create `tests/test_config.py`:

```python
"""Tests for config command group."""

from click.testing import CliRunner

from cli import main


def test_config_get():
    """Test config get subcommand."""
    runner = CliRunner()
    result = runner.invoke(main, ["config", "get", "api_key"])
    assert result.exit_code == 0
    assert "api_key" in result.output


def test_config_set():
    """Test config set subcommand."""
    runner = CliRunner()
    result = runner.invoke(main, ["config", "set", "api_key", "test123"])
    assert result.exit_code == 0
    assert "api_key" in result.output
    assert "test123" in result.output


def test_config_list():
    """Test config list subcommand."""
    runner = CliRunner()
    result = runner.invoke(main, ["config", "list"])
    assert result.exit_code == 0
```

---

## Common Click Decorators

### Options vs Arguments

```python
# Options are optional, have flags, and can have defaults
@click.option("--count", "-c", default=1, help="Number of times")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")

# Arguments are positional and typically required
@click.argument("filename")
@click.argument("names", nargs=-1)  # Variable number of args
```

### Option Types

```python
@click.option("--count", type=int, default=1)
@click.option("--rate", type=float, default=1.0)
@click.option("--format", type=click.Choice(["json", "yaml", "text"]))
@click.option("--config", type=click.Path(exists=True))
@click.option("--output", type=click.File("w"))
```

### Passing Context Between Commands

```python
@click.group()
@click.option("--debug/--no-debug", default=False)
@click.pass_context
def main(ctx: click.Context, debug: bool) -> None:
    """CLI with shared context."""
    ctx.ensure_object(dict)
    ctx.obj["DEBUG"] = debug


@main.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show status (respects --debug flag)."""
    if ctx.obj["DEBUG"]:
        click.echo("Debug mode is ON")
    click.echo("Status: OK")
```

Usage: `discord-chat --debug status`

### Command Aliases

```python
@click.command(name="ls")  # Command will be 'ls' not 'list_items'
def list_items() -> None:
    """List all items."""
    pass
```

---

## Best Practices

1. **One file per command/group**: Keeps code organized and testable
2. **Docstrings become help text**: The function docstring is shown in `--help`
3. **Use type hints**: Makes code clearer and enables IDE support
4. **Test with CliRunner**: Click's test runner captures output and exit codes
5. **Handle errors gracefully**: Use `click.echo()` for output, `sys.exit(1)` for errors

```python
@click.command()
def risky() -> None:
    """A command that might fail."""
    try:
        do_something()
    except SomeError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
```

---

## Quick Reference

| Action | Code |
|--------|------|
| Create command | `@click.command()` |
| Create group | `@click.group()` |
| Add subcommand | `@group.command()` |
| Optional flag | `@click.option("--verbose", is_flag=True)` |
| Required option | `@click.option("--name", required=True)` |
| Positional arg | `@click.argument("name")` |
| Multiple args | `@click.argument("files", nargs=-1)` |
| Pass context | `@click.pass_context` |
| Output text | `click.echo("message")` |
| Output to stderr | `click.echo("error", err=True)` |
| Prompt for input | `click.prompt("Enter value")` |
| Confirm action | `click.confirm("Continue?")` |
