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

# Use specific LLM provider
uv run python cli.py digest "server-name" --llm claude
uv run python cli.py digest "server-name" --llm openai

# Save to specific output directory
uv run python cli.py digest "server-name" --output ./digests/
```

### Digest Command

The `digest` command fetches messages from all channels in a Discord server and generates an AI-powered summary.

**Arguments:**
- `SERVER_NAME` - Name of the Discord server (case-insensitive)

**Options:**
- `--hours, -h` - Hours to look back (default: 6)
- `--llm, -l` - LLM provider: `claude` or `openai` (auto-selects if not specified)
- `--output, -o` - Output directory for the digest file (default: current directory)

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
│   └── digest.py       # Digest command
├── services/           # Service modules
│   ├── discord_client.py  # Discord API integration
│   └── llm/            # LLM providers
│       ├── base.py     # Abstract LLM interface
│       ├── claude.py   # Claude provider
│       └── openai_provider.py  # OpenAI provider
└── utils/              # Utility modules
    └── digest_formatter.py  # Digest formatting

tests/                  # Test files
hooks/                  # Git hooks
```

## Adding New Commands

1. Create a new file in `discord_chat/commands/`
2. Define your command using `@click.command()`
3. Import and register in `cli.py` using `main.add_command()`
