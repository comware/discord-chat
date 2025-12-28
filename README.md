# discord-chat

A CLI application built with Click.

## Installation

```bash
# Install dependencies
uv sync

# Install git hooks
make hooks
```

## Environment Variables

Required environment variables for the `digest` command:

| Variable | Description |
|----------|-------------|
| `DISCORD_BOT_TOKEN` | Your Discord bot token (required) |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude (optional) |
| `OPENAI_API_KEY` | OpenAI API key (optional) |

At least one LLM API key is required to generate digests.

## Usage

```bash
# Run the CLI
uv run python cli.py --help

# Show version
uv run python cli.py version
# or
make version

# Generate a digest of Discord server activity
uv run python cli.py digest "server-name" --hours 6

# Generate a digest for a specific channel only
uv run python cli.py digest "server-name" --channel general --hours 6
uv run python cli.py digest "server-name" -c announcements --hours 24

# Use specific LLM provider
uv run python cli.py digest "server-name" --llm claude
uv run python cli.py digest "server-name" --llm openai

# Save to file (auto-generates filename in directory, or specify full path)
uv run python cli.py digest "server-name" --file ./digests/
uv run python cli.py digest "server-name" --file ./my-digest.md

# Preview without calling LLM API
uv run python cli.py digest "server-name" --dry-run

# Silent mode (useful for cron jobs)
uv run python cli.py digest "server-name" --quiet --file ./digests/
```

### Digest Command

The `digest` command fetches messages from a Discord server (all channels or a specific channel) and generates an AI-powered summary.

**Arguments:**
- `SERVER_NAME` - Name of the Discord server (case-insensitive)

**Options:**
- `--hours, -h` - Hours to look back (default: 6, max: 168)
- `--channel, -c` - Generate digest for a specific channel only (case-insensitive)
- `--llm, -l` - LLM provider: `claude` or `openai` (auto-selects if not specified)
- `--file, -f` - Save digest to file (directory for auto-filename, or full path)
- `--dry-run` - Preview what would be done without calling the LLM API
- `--quiet, -q` - Suppress console output (use with `--file` for silent operation)
- `--no-color` - Disable colored output (also respects `NO_COLOR` env var)

### Makefile Shortcuts

For the `tne.ai` server, convenient Makefile targets are available:

```bash
# Generate digest for all channels (default: 24 hours)
make tne-digest

# Generate digest for last 6 hours
make tne-digest HOURS=6

# Generate digest for a specific channel
make tne-digest CHANNEL=general
make tne-digest CHANNEL=announcements HOURS=12

# Show message activity per channel
make tne-activity
make tne-activity HOURS=48
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
│   ├── version.py      # Version command
│   ├── digest.py       # Digest command
│   └── activity.py     # Activity command
├── services/           # Service modules
│   ├── discord_client.py  # Discord API integration
│   └── llm/            # LLM providers
│       ├── base.py     # Abstract LLM interface
│       ├── claude.py   # Claude provider
│       └── openai_provider.py  # OpenAI provider
└── utils/              # Utility modules
    ├── digest_formatter.py  # Digest formatting
    ├── console_output.py    # Rich console output
    └── security_logger.py   # Security event logging

tests/                  # Test files
hooks/                  # Git hooks
```

## Adding New Commands

1. Create a new file in `discord_chat/commands/`
2. Define your command using `@click.command()`
3. Import and register in `cli.py` using `main.add_command()`
