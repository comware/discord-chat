# discord-chat

A CLI application built with Click.

## Installation

```bash
# Install dependencies
uv sync

# Install git hooks
make hooks
```

## Usage

```bash
# Run the CLI
uv run python cli.py --help

# Show version
uv run python cli.py version
# or
make version
```

## Development

```bash
# Run linter
make lint

# Run formatter
make format

# Run tests
make test

# Run all checks
make check
```

## Project Structure

```
discord_chat/           # Main package
├── commands/           # CLI commands (one file per command)
└── utils/              # Utility modules

tests/                  # Test files
hooks/                  # Git hooks
```

## Adding New Commands

1. Create a new file in `discord_chat/commands/`
2. Define your command using `@click.command()`
3. Import and register in `cli.py` using `main.add_command()`
