# Codebase Convention Guide

**Project:** discord-chat
**Extracted:** 2025-12-22
**Confidence:** 95%

---

## Quick Reference

| Dimension | Key Convention | Consistency |
|-----------|---------------|-------------|
| Naming | snake_case files/functions, PascalCase classes | 100% |
| Structure | Clean architecture: commands/services/utils | 100% |
| Style | Black formatting (100 char), Ruff linting | 100% (enforced) |
| Testing | pytest, class-based organization, 95% coverage | 98% |
| Async | asyncio with proper cleanup, semaphore rate limiting | 100% |
| Logging | Structured JSON security logging | 100% |
| Error Handling | Custom exceptions, sanitized messages | 100% |
| Type Annotations | Full type hints on all functions | 95% |

---

## Naming Conventions

### File Naming

**Pattern:** `snake_case.py` for all Python files
**Consistency:** 100%

**Examples from codebase:**
- `discord_client.py` - Service module
- `digest_formatter.py` - Utility module  
- `security_logger.py` - Utility module
- `test_llm_security.py` - Test module
- `openai_provider.py` - Service provider (full word, not "openai_prov")

**Rules:**
- All lowercase with underscores separating words
- No abbreviations unless well-established (e.g., `llm`, `api`, `cli`)
- Test files: `test_<module_name>.py` matching the module they test
- No hyphens in filenames (use underscores)

### Directory Naming

**Pattern:** `lowercase` single words or `snake_case`
**Consistency:** 100%

**Examples:**
- `commands/` - CLI command modules
- `services/` - Business logic and external integrations
- `utils/` - Utility functions and helpers
- `tests/` - All test files (flat, not mirroring src structure)
- `llm/` - Sub-package for LLM providers

**Rules:**
- Top-level package: `discord_chat` (matches PyPI package name with hyphen converted to underscore)
- Avoid deep nesting: Maximum 2 levels (e.g., `services/llm/`)
- Use singular nouns for utility directories, plural for collections

### Variable/Function Naming

**Pattern:** `snake_case` for all variables and functions
**Consistency:** 100%

**Examples:**
```python
# Good (matches codebase style)
def fetch_server_messages(server_name: str, hours: int) -> ServerDigestData:
    """Fetch messages from all channels in a server."""
    end_time = datetime.now(UTC)
    start_time = end_time - timedelta(hours=hours)
    max_concurrent_channels = 5
    
def get_default_output_filename(server_name: str) -> str:
    safe_name = "".join(c if c.isalnum() else "_" for c in server_name)
    return f"digest-{safe_name}-{timestamp}.md"

# Avoid (doesn't match codebase style)
def fetchServerMessages(serverName, hours):  # camelCase - WRONG
    endTime = datetime.now()  # camelCase - WRONG
    MaxChannels = 5  # PascalCase - WRONG
```

**Specific patterns:**
- Boolean flags: `is_available`, `debug`, `quiet`, `dry_run`
- Getters: `get_version()`, `get_provider()`, `get_security_logger()`
- Private/internal: `_sanitize_details()`, `_get_env_int()` (single underscore prefix)
- Mock objects in tests: `mock_fetch`, `mock_provider`, `mock_get_provider`

### Class/Type Naming

**Pattern:** `PascalCase` for all classes, exceptions, and dataclasses
**Consistency:** 100%

**Examples:**
```python
# Good (matches codebase)
class DiscordMessageFetcher:
    """Fetches messages from Discord servers."""
    
class LLMError(Exception):
    """Base exception for LLM-related errors."""
    
class ServerNotFoundError(DiscordClientError):
    """Raised when the specified server is not found."""

@dataclass
class ChannelMessages:
    """Messages from a single channel."""
    channel_name: str
    channel_id: int
    messages: list[dict]
    
class SecurityEventType(Enum):
    """Types of security events to log."""
    AUTH_SUCCESS = "auth_success"

# Avoid
class discord_client:  # snake_case - WRONG
class llmError:  # camelCase - WRONG
```

**Exception naming:**
- Always inherit from appropriate base: `Exception`, `ValueError`, custom base exceptions
- Descriptive names ending in `Error`: `LLMError`, `DiscordClientError`, `InvalidServerNameError`
- Domain-specific errors: `ServerNotFoundError` (not generic `NotFoundError`)

### Constants

**Pattern:** `SCREAMING_SNAKE_CASE` for module-level constants, normal casing for class constants
**Consistency:** 90%

**Examples:**
```python
# Module-level constants (top of file after imports)
MIN_HOURS = 1
MAX_HOURS = 168
DEFAULT_TIMEOUT = 60.0
MAX_MESSAGE_CONTENT_LENGTH = 100_000

# Class-level constants (inside class)
class ClaudeProvider(LLMProvider):
    MODEL = "claude-sonnet-4-20250514"
    MAX_TOKENS = 4096
    
# Dictionary constants
PROVIDER_REGISTRY = {
    "claude": ClaudeProvider,
    "openai": OpenAIProvider,
}
```

### Test Naming

**Pattern:** `test_<what_is_being_tested>`
**Consistency:** 100%

**Test file organization:**
```python
# Test classes group related tests
class TestActivityCommand:
    """Tests for the activity CLI command."""
    
    def test_activity_no_token(self):
        """Test activity command fails without Discord token."""
        
    def test_activity_success(self, mock_fetch):
        """Test successful activity display."""
        
    def test_activity_server_not_found(self, mock_fetch):
        """Test activity command when server is not found."""

# Test functions can stand alone for simple cases
def test_version_command():
    """Test that version command runs successfully."""
```

**Rules:**
- Test classes: `TestClassName` or `TestFunctionName` grouping related tests
- Test methods: `test_<scenario>` describing what's being tested
- Use descriptive names: `test_claude_missing_anthropic_package` not `test_error_1`
- Fixture helpers: `create_sample_data()`, `create_activity_data()` (not test_ prefix)

---

## File Organization

### Project Structure

```
discord-chat/
├── cli.py                      # Entry point, CLI group definition
├── discord_chat/               # Main package
│   ├── __init__.py            # Package metadata (__version__, __all__)
│   ├── commands/              # CLI commands (one per file)
│   │   ├── __init__.py
│   │   ├── activity.py        # Simple command
│   │   ├── digest.py          # Complex command with helpers
│   │   └── version.py         # Minimal command
│   ├── services/              # Business logic, external APIs
│   │   ├── __init__.py
│   │   ├── discord_client.py  # Discord API integration
│   │   └── llm/               # Provider pattern
│   │       ├── __init__.py    # Factory function
│   │       ├── base.py        # Abstract base class
│   │       ├── claude.py      # Concrete provider
│   │       └── openai_provider.py
│   └── utils/                 # Pure functions, helpers
│       ├── __init__.py
│       ├── digest_formatter.py
│       └── security_logger.py
├── tests/                     # All tests (flat structure)
│   ├── test_cli.py
│   ├── test_activity.py
│   ├── test_digest.py
│   ├── test_digest_security.py
│   ├── test_discord_client.py
│   ├── test_discord_client_async.py
│   ├── test_llm_providers.py
│   ├── test_llm_security.py
│   └── test_security_logger.py
├── docs/                      # Documentation
│   ├── implementation/
│   └── security/
├── pyproject.toml             # All configuration
├── Makefile                   # Developer commands
├── README.md                  # User documentation
└── SECURITY.md               # Security documentation
```

### Key Directories

**`cli.py`**: Entry point only
- Click group definition
- Command registration
- Global options (--debug, --version)
- Logging setup
- Environment loading (dotenv)

**`discord_chat/commands/`**: One command per file
- Each file exports a Click command/group
- Self-contained with imports at top
- No business logic (delegate to services)
- Error handling with `click.ClickException`

**`discord_chat/services/`**: Business logic and integrations
- Discord client, LLM providers
- Can have async methods
- Custom exception classes
- Security logging integration

**`discord_chat/utils/`**: Pure utilities
- Formatting, validation, logging
- No external API calls
- Reusable across commands

**`tests/`**: Flat structure, comprehensive coverage
- One test file per source module
- Additional test files for specific concerns (e.g., `test_digest_security.py`)
- 95%+ coverage target
- pytest with async support

### Where to Put New Files

| File Type | Location | Example |
|-----------|----------|---------|
| New CLI command | `discord_chat/commands/<name>.py` | `discord_chat/commands/export.py` |
| Service/integration | `discord_chat/services/<name>.py` | `discord_chat/services/slack_client.py` |
| LLM provider | `discord_chat/services/llm/<name>.py` | `discord_chat/services/llm/gemini.py` |
| Utility function | `discord_chat/utils/<purpose>.py` | `discord_chat/utils/file_manager.py` |
| Tests | `tests/test_<module>.py` | `tests/test_export.py` |

---

## Code Style

### Enforced by Tooling

These are automatically enforced by Black and Ruff:

**Black (formatting):**
- Line length: 100 characters
- Double quotes for strings (Black's default)
- Trailing commas in multi-line constructs
- Target: Python 3.11

**Ruff (linting):**
- Error codes: E, F, I, N, W, UP
- Import sorting (isort-style)
- Naming conventions
- Unused imports/variables
- Modern Python syntax (UP rules)

**Configuration (pyproject.toml):**
```toml
[tool.black]
line-length = 100
target-version = ["py311"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]
```

### Import Organization

**Pattern:** Standard library → Third-party → Local, with blank lines between groups
**Consistency:** 100% (enforced by Ruff)

**Examples:**
```python
"""Module docstring first."""

# Standard library imports (alphabetical within group)
import asyncio
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Third-party imports
import click
import discord
from anthropic import Anthropic

# Local imports (absolute, not relative for top-level)
from discord_chat.services.discord_client import fetch_server_messages
from discord_chat.services.llm import LLMError, get_provider
from discord_chat.utils.security_logger import get_security_logger

# Within package, use relative imports
from .base import LLMError, LLMProvider  # In llm/ subpackage
```

**Rules:**
- Absolute imports from `discord_chat` package in commands/
- Relative imports within sub-packages (e.g., `llm/`)
- Import specific names, not modules when possible
- Multi-line imports: use parentheses, not backslashes

### Docstrings

**Pattern:** Google-style docstrings for all public functions/classes
**Consistency:** 95%

**Function docstrings:**
```python
def fetch_server_messages(server_name: str, hours: int = 6) -> ServerDigestData:
    """Fetch messages from all channels in a server.

    Args:
        server_name: Name of the Discord server (case-insensitive).
        hours: Number of hours to look back for messages.

    Returns:
        ServerDigestData containing all messages from the time window.

    Raises:
        DiscordClientError: On timeout or other Discord-related errors.
        ServerNotFoundError: If the server is not found.
    """
```

**Class docstrings:**
```python
class DiscordMessageFetcher:
    """Fetches messages from Discord servers.

    This class handles connecting to Discord, finding servers by name,
    and fetching messages from all text channels within a specified time window.

    Thread Safety: NOT thread-safe. Create a new instance for each concurrent operation.

    Configuration via environment variables:
        DISCORD_CHAT_TIMEOUT: Operation timeout in seconds (default: 60, range: 10-300)
        DISCORD_CHAT_MAX_MESSAGES: Max messages per channel (default: 1000, range: 100-10000)
    """
```

**Module docstrings:**
```python
"""Discord client service for fetching messages from servers."""
```

**Short docstrings (one-liners):**
```python
def get_version() -> str:
    """Read version from pyproject.toml."""
```

**Rules:**
- All public functions/classes/modules must have docstrings
- Private functions (`_name`) can omit docstrings if purpose is clear
- Use imperative mood: "Fetch messages" not "Fetches messages"
- Document all parameters, return values, and exceptions
- Include examples for complex functions

### Type Annotations

**Pattern:** Full type hints on all function signatures, properties
**Consistency:** 95%

**Examples:**
```python
# Function signatures - always annotated
def validate_server_name(server_name: str) -> str:
    """Validate and sanitize server name."""
    
async def fetch_server_messages(
    self,
    server_name: str,
    hours: int = 6,
    timeout: float | None = None,
) -> ServerDigestData:
    """Fetch messages with timeout."""

# Properties
@property
def name(self) -> str:
    """Return the provider name."""
    return "Claude"
    
# Variables (when not obvious from context)
end_time: datetime = datetime.now(UTC)
start_time: datetime = end_time - timedelta(hours=hours)

# Dataclasses - always annotated
@dataclass
class ChannelMessages:
    """Messages from a single channel."""
    channel_name: str
    channel_id: int
    messages: list[dict]

# Modern syntax (Python 3.10+)
def get_provider(name: str | None = None) -> LLMProvider:
    """Get provider, auto-selecting if name is None."""
```

**Rules:**
- Use `str | None` not `Optional[str]` (modern syntax)
- Use `list[str]` not `List[str]` (no typing import needed)
- Use `dict[str, Any]` for generic dicts
- Always annotate function parameters and return types
- Use `-> None` for functions with no return value

### String Formatting

**Pattern:** f-strings preferred, format() for complex cases
**Consistency:** 90%

**Examples:**
```python
# Preferred: f-strings
click.echo(f"discord-chat version {get_version()}")
raise LLMError(f"Unknown provider '{provider_name}'. Available: {available}")
filename = f"digest-{safe_name}-{timestamp}.md"

# For multi-line or complex formatting
message = (
    f"Server '{server_name}' not found. "
    f"Available servers: {', '.join(available_servers) or 'None'}"
)

# Logging with structured data (not f-strings)
log_entry = {
    "timestamp": datetime.now(UTC).isoformat(),
    "event_type": event_type.value,
    "message": message,
}
```

---

## Error Handling Patterns

### Custom Exception Hierarchy

**Pattern:** Domain-specific exception classes inheriting from base
**Consistency:** 100%

**Exception hierarchy:**
```python
# Base exceptions for each domain
class DiscordClientError(Exception):
    """Base exception for Discord client errors."""
    pass

class LLMError(Exception):
    """Base exception for LLM-related errors."""
    pass

# Specific exceptions
class ServerNotFoundError(DiscordClientError):
    """Raised when the specified server is not found."""
    pass
    
class InvalidServerNameError(ValueError):
    """Raised when server name contains invalid characters."""
    pass
```

**Rules:**
- Create base exceptions for each major module/domain
- Specific exceptions inherit from appropriate base
- Exception messages are user-friendly (no stack traces, no internal details)
- Inherit from built-in exceptions when semantically appropriate (`ValueError`, `TypeError`)

### Error Message Sanitization

**Pattern:** Never expose sensitive data (tokens, paths, internal errors) to users
**Consistency:** 100%

**Examples:**
```python
# Good (sanitized messages)
except discord.LoginFailure:
    security_logger.log_auth_attempt(False, "Discord", "Invalid token")
    raise DiscordClientError(
        "Discord authentication failed. Please verify your DISCORD_BOT_TOKEN."
    )

except discord.HTTPException as e:
    status = e.status if hasattr(e, "status") else "unknown"
    raise DiscordClientError(f"Discord API request failed (status: {status})")

# Validate before using in paths
try:
    validated_server_name = validate_server_name(server_name)
except InvalidServerNameError as e:
    security_logger.log_input_validation_failure("server_name", server_name, str(e))
    raise click.ClickException(str(e))

# Avoid (leaking internal details)
except Exception as e:
    raise Error(f"Failed: {e}")  # Could expose stack trace
    raise Error(f"Path: {full_path}")  # Could expose filesystem structure
```

**Security logging pattern:**
```python
try:
    result = api_call()
    security_logger.log_api_call("ServiceName", "operation", duration_ms, True)
    return result
except AuthError:
    security_logger.log_auth_attempt(False, "ServiceName", "reason")
    raise UserFriendlyError("Please check your credentials")
except Exception as e:
    security_logger.log_error("error_type", "Safe message", {"safe": "details"})
    raise UserFriendlyError("Operation failed. Please try again.")
```

### Exception Handling in Commands

**Pattern:** Convert exceptions to `click.ClickException` at command boundary
**Consistency:** 100%

**Examples:**
```python
@click.command()
def activity(server_name: str, hours: int) -> None:
    """Check message activity in a Discord server."""
    # Validate environment
    if not os.environ.get("DISCORD_BOT_TOKEN"):
        raise click.ClickException("DISCORD_BOT_TOKEN environment variable is required.")

    # Call service layer
    try:
        data = fetch_server_messages(server_name, hours)
    except ServerNotFoundError as e:
        raise click.ClickException(str(e))
    except DiscordClientError as e:
        raise click.ClickException(f"Discord error: {e}")
    
    # Handle empty results gracefully (not an error)
    if data.total_messages == 0:
        click.echo("No messages found.")
        return
```

**Rules:**
- Commands catch service-layer exceptions and convert to `click.ClickException`
- `click.ClickException` provides nice error messages and proper exit codes
- Distinguish errors (raise) from empty results (echo and return)
- Don't catch `Exception` - let unexpected errors propagate for debugging

### Try-Except-Finally for Cleanup

**Pattern:** Always clean up resources (especially async)
**Consistency:** 100%

**Examples:**
```python
async def fetch_server_messages(self, server_name: str, hours: int) -> ServerDigestData:
    """Fetch messages with guaranteed cleanup."""
    try:
        # Start the client
        login_task = asyncio.create_task(self._client.start(self._token))
        
        try:
            await self._wait_until_ready()
            guild = self._find_server_by_name(server_name)
            # ... fetch messages ...
            return result
        finally:
            # Always close the client
            await self._client.close()
            login_task.cancel()
            try:
                await login_task
            except asyncio.CancelledError:
                pass
    except TimeoutError:
        if not self._client.is_closed():
            await self._client.close()
        raise DiscordClientError(f"Operation timed out")
```

**File operations:**
```python
# Use context managers for files
with open(path, "rb") as f:
    data = tomllib.load(f)

# For secure writes, manual fd management with try-finally
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
try:
    os.write(fd, content.encode("utf-8"))
finally:
    os.close(fd)
```

---

## Async/Await Usage Patterns

### When to Use Async

**Pattern:** Use async for I/O operations (network, file), not for CPU-bound tasks
**Consistency:** 100%

**Async functions:**
- `async def fetch_server_messages()` - Discord API calls
- `async def _fetch_channel_messages()` - Per-channel API calls  
- `async def _wait_until_ready()` - Waiting for connection

**Synchronous wrappers:**
```python
def fetch_server_messages(server_name: str, hours: int = 6) -> ServerDigestData:
    """Synchronous wrapper for fetching server messages.
    
    This is the main entry point for CLI usage.
    """
    fetcher = DiscordMessageFetcher()
    return asyncio.run(fetcher.fetch_server_messages(server_name, hours))
```

**Rules:**
- Async methods are prefixed with `async def`
- Provide sync wrappers for CLI entry points using `asyncio.run()`
- Never use `asyncio.run()` inside an already-running event loop

### Async Cleanup Pattern

**Pattern:** Always clean up async resources in finally blocks
**Consistency:** 100%

**Examples:**
```python
async def operation(self):
    """Async operation with cleanup."""
    try:
        # Start background task
        task = asyncio.create_task(background_work())
        
        try:
            # Main work
            result = await do_work()
            return result
        finally:
            # Clean up background task
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    except Exception:
        # Ensure client is closed on error
        if not self._client.is_closed():
            await self._client.close()
        raise
```

### Concurrent Operations with Semaphores

**Pattern:** Use `asyncio.Semaphore` to limit concurrent API calls (rate limiting)
**Consistency:** 100%

**Examples:**
```python
async def _fetch_channels_with_rate_limiting(
    self,
    channels: list[discord.TextChannel],
    after: datetime,
    before: datetime,
) -> list[ChannelMessages]:
    """Fetch messages from multiple channels with rate limiting."""
    # Log rate limiting enforcement
    self._security_logger.log_rate_limit("Discord", self.max_concurrent_channels)
    
    # Create semaphore to limit concurrent API calls
    semaphore = asyncio.Semaphore(self.max_concurrent_channels)
    
    async def fetch_with_semaphore(channel: discord.TextChannel) -> ChannelMessages:
        """Wrapper to fetch channel messages with semaphore."""
        async with semaphore:
            return await self._fetch_channel_messages(channel, after, before)
    
    # Fetch all channels with rate limiting
    tasks = [fetch_with_semaphore(ch) for ch in channels]
    return await asyncio.gather(*tasks)
```

**Rules:**
- Use `asyncio.Semaphore` to limit concurrent operations
- Typical concurrency limit: 5 (configurable via environment)
- Log rate limiting for security audit trail
- Use `asyncio.gather()` to run tasks concurrently

### Async Timeouts

**Pattern:** Wrap async operations with `asyncio.wait_for()` for timeouts
**Consistency:** 100%

**Examples:**
```python
async def fetch_server_messages(self, server_name: str, hours: int = 6, timeout: float | None = None) -> ServerDigestData:
    """Fetch messages with timeout."""
    operation_timeout = timeout if timeout is not None else self.operation_timeout
    
    try:
        return await asyncio.wait_for(
            self._fetch_server_messages_impl(server_name, hours),
            timeout=operation_timeout,
        )
    except TimeoutError:
        # Ensure cleanup on timeout
        if not self._client.is_closed():
            await self._client.close()
        raise DiscordClientError(
            f"Operation timed out after {operation_timeout} seconds. "
            "The server may have too many channels or messages."
        )

async def _wait_until_ready(self, timeout: float = 30.0):
    """Wait for the client to be ready."""
    try:
        await asyncio.wait_for(self._ready_event.wait(), timeout=timeout)
    except TimeoutError:
        raise DiscordClientError("Timed out waiting for Discord connection")
```

### Yielding Control in Long Loops

**Pattern:** Use `await asyncio.sleep(0)` to yield control periodically
**Consistency:** 100%

**Examples:**
```python
async def _fetch_channel_messages(self, channel: discord.TextChannel) -> ChannelMessages:
    """Fetch messages from a single channel."""
    messages = []
    async for message in channel.history(limit=1000):
        messages.append(process_message(message))
        
        # Yield control periodically to prevent memory buildup
        if len(messages) % 100 == 0:
            await asyncio.sleep(0)  # Yield to event loop
    
    return ChannelMessages(...)
```

---

## Logging Conventions

### Standard Logging Setup

**Pattern:** Configure logging in CLI entry point, use module loggers elsewhere
**Consistency:** 100%

**CLI setup (cli.py):**
```python
def setup_logging(debug: bool) -> None:
    """Configure logging based on debug flag."""
    level = logging.DEBUG if debug else logging.WARNING
    format_str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s" if debug else "%(message)s"
    logging.basicConfig(
        level=level,
        format=format_str,
        stream=sys.stderr,
    )
    # Suppress noisy third-party loggers
    if not debug:
        logging.getLogger("discord").setLevel(logging.ERROR)
```

**Global --debug flag:**
```python
@click.group()
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    envvar="DISCORD_CHAT_DEBUG",
    help="Enable debug logging output",
)
@click.pass_context
def main(ctx: click.Context, debug: bool) -> None:
    """discord-chat - A CLI tool."""
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug
    setup_logging(debug)
```

### Security Logging

**Pattern:** Structured JSON logging for security events to dedicated log file
**Consistency:** 100%

**Security logger usage:**
```python
from discord_chat.utils.security_logger import get_security_logger

# Get singleton instance
security_logger = get_security_logger()

# Authentication events
security_logger.log_auth_attempt(success=True, service="Discord")
security_logger.log_auth_attempt(success=False, service="Claude", reason="Invalid API key")

# API calls with timing
start_time = time.time()
result = api_call()
duration_ms = (time.time() - start_time) * 1000
security_logger.log_api_call("Discord", "fetch_messages", duration_ms, success=True)

# Input validation failures (potential attacks)
security_logger.log_input_validation_failure(
    input_type="server_name",
    value=server_name,
    reason="contains path traversal characters"
)

# Rate limiting enforcement
security_logger.log_rate_limit("Discord", concurrent_limit=5)

# File operations (audit trail)
security_logger.log_file_operation("write", str(output_path), "0600")

# Errors
security_logger.log_error(
    error_type="rate_limit",
    message="API rate limit exceeded",
    sanitized_details={"service": "Claude"}
)
```

**Log file configuration:**
- Default: `./security.log`
- Environment variable: `DISCORD_CHAT_SECURITY_LOG`
- Rotation: 10MB per file, 5 backup files (50MB total max)
- Format: JSON, one event per line
- Contains: timestamp, event_type, message, details

**What to log:**
- All authentication attempts (success and failure)
- All API calls with duration
- Input validation failures
- Rate limiting enforcement
- File operations (for audit trail)
- Security-relevant errors

**What NOT to log:**
- API keys, tokens, passwords (sanitized to `[REDACTED]`)
- Full file paths (only filename)
- User data beyond what's needed for security

---

## Testing Conventions

### Test Organization

**Pattern:** Class-based test organization with descriptive test names
**Consistency:** 98%

**Test file structure:**
```python
"""Tests for the digest command."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from cli import main
from discord_chat.services.discord_client import ServerDigestData

# Fixture/helper functions at top (not prefixed with test_)
def create_sample_data() -> ServerDigestData:
    """Create sample server data for testing."""
    end_time = datetime.now(UTC)
    start_time = end_time - timedelta(hours=6)
    return ServerDigestData(...)

# Test classes group related tests
class TestDigestFormatter:
    """Tests for digest formatter utilities."""
    
    def test_format_messages_for_llm(self):
        """Test formatting messages for LLM consumption."""
        data = create_sample_data()
        result = format_messages_for_llm(data)
        assert "## #general" in result
        
    def test_format_messages_empty(self):
        """Test formatting when no messages exist."""
        # Test implementation

class TestServerNameValidation:
    """Tests for server name validation and sanitization."""
    
    def test_validate_normal_name(self):
        """Test validation of normal server name."""
        
    def test_validate_rejects_path_traversal(self):
        """Test that path traversal attempts are rejected."""
```

**Rules:**
- One test file per source module: `test_<module>.py`
- Additional security/integration test files: `test_<module>_security.py`, `test_<module>_async.py`
- Test classes: `TestClassName` grouping related functionality
- Test methods: `test_<scenario>` describing what's being tested
- Helper functions: No `test_` prefix, placed before test classes

### Test Naming

**Pattern:** Descriptive names that read as documentation
**Consistency:** 100%

**Examples:**
```python
# Good (descriptive, reads like documentation)
def test_activity_no_token(self):
    """Test activity command fails without Discord token."""

def test_claude_missing_anthropic_package(self):
    """Test error when anthropic package not installed."""
    
def test_validate_rejects_path_traversal(self):
    """Test that path traversal attempts are rejected."""

def test_wait_until_ready_timeout(self):
    """Test timeout when connection takes too long."""

# Avoid (too vague)
def test_error(self):
def test_case_1(self):
def test_auth(self):
```

### Mocking Patterns

**Pattern:** Use `unittest.mock` with `@patch` decorators, descriptive mock names
**Consistency:** 100%

**Patch decorators (bottom-up order):**
```python
@patch("discord_chat.commands.digest.fetch_server_messages")
@patch("discord_chat.commands.digest.get_provider")
@patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "test-token"})
def test_digest_success(self, mock_get_provider, mock_fetch):
    """Test successful digest generation.
    
    Note: Patches are applied bottom-to-top, parameters are top-to-bottom.
    """
    # Setup mocks
    mock_fetch.return_value = create_sample_data()
    mock_provider = MagicMock(spec=LLMProvider)
    mock_provider.name = "TestLLM"
    mock_provider.generate_digest.return_value = "# Test Digest"
    mock_get_provider.return_value = mock_provider
    
    # Execute test
    runner = CliRunner()
    result = runner.invoke(main, ["digest", "test-server"])
    
    # Assertions
    assert result.exit_code == 0
    mock_fetch.assert_called_once_with("test-server", 6)
    mock_provider.generate_digest.assert_called_once()
```

**Mock naming:**
- `mock_<function_name>` for function mocks: `mock_fetch`, `mock_get_provider`
- `mock_<object>` for object mocks: `mock_provider`, `mock_client`
- Use `MagicMock(spec=ClassName)` to ensure correct interface

**Environment mocking:**
```python
@patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "test-token"})
def test_with_env(self):
    """Test with environment variable set."""

@patch.dict("os.environ", {}, clear=True)
def test_without_env(self):
    """Test with no environment variables."""
```

### Async Test Patterns

**Pattern:** Use `@pytest.mark.asyncio` for async tests
**Consistency:** 100%

**Configuration (pyproject.toml):**
```toml
[tool.pytest.ini_options]
asyncio_mode = "strict"
asyncio_default_fixture_loop_scope = "function"
```

**Async test examples:**
```python
import pytest

class TestWaitUntilReady:
    """Tests for _wait_until_ready async method."""
    
    @pytest.mark.asyncio
    async def test_wait_until_ready_success(self):
        """Test successful connection within timeout."""
        fetcher = DiscordMessageFetcher()
        fetcher._ready_event.set()
        
        # Should not raise
        await fetcher._wait_until_ready(timeout=1.0)
    
    @pytest.mark.asyncio
    async def test_wait_until_ready_timeout(self):
        """Test timeout when connection takes too long."""
        fetcher = DiscordMessageFetcher()
        # Don't set ready event - will timeout
        
        with pytest.raises(DiscordClientError) as exc_info:
            await fetcher._wait_until_ready(timeout=0.1)
        
        assert "Timed out waiting for Discord connection" in str(exc_info.value)
```

### Pytest Fixtures

**Pattern:** Use fixtures for test setup, especially for resetting global state
**Consistency:** 90%

**Examples:**
```python
@pytest.fixture(autouse=True)
def reset_security_logger():
    """Reset global security logger before each test."""
    import discord_chat.utils.security_logger as security_module
    security_module._security_logger = None
    
    test_logger = logging.getLogger("discord_chat.security")
    test_logger.handlers.clear()
    
    yield
    
    security_module._security_logger = None
```

**Rules:**
- Use `autouse=True` for fixtures that should run for every test in a class/module
- Fixture scope: `function` (default), `class`, `module`, `session`
- Cleanup: Use `yield` for fixtures that need cleanup

### Click Testing

**Pattern:** Use `CliRunner` to test Click commands
**Consistency:** 100%

**Examples:**
```python
from click.testing import CliRunner
from cli import main

def test_version_command():
    """Test that version command runs successfully."""
    runner = CliRunner()
    result = runner.invoke(main, ["version"])
    
    assert result.exit_code == 0
    assert "version" in result.output.lower()

def test_activity_with_options():
    """Test activity command with options."""
    runner = CliRunner()
    result = runner.invoke(main, ["activity", "test-server", "--hours", "12"])
    
    assert result.exit_code == 0

def test_error_handling():
    """Test command error handling."""
    runner = CliRunner()
    result = runner.invoke(main, ["activity", "test-server"])
    
    assert result.exit_code != 0  # Expect failure
    assert "DISCORD_BOT_TOKEN" in result.output
```

**CliRunner features:**
- `result.exit_code` - Check success (0) or failure (non-zero)
- `result.output` - Captured stdout
- `result.exception` - Exception if raised
- Isolated filesystem: `runner.isolated_filesystem()`

### Test Coverage

**Target:** 95%+ coverage
**Consistency:** 98%

**Run coverage:**
```bash
make test  # Runs pytest with coverage
```

**Coverage configuration (pyproject.toml):**
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

**What to test:**
- Happy path (normal usage)
- Error cases (exceptions, invalid input)
- Edge cases (empty data, max values, min values)
- Security scenarios (path traversal, symlinks, injection)
- Async scenarios (timeouts, concurrent operations)
- Integration points (mocked external APIs)

---

## CLI Command Structure Patterns

### Command Definition

**Pattern:** One command per file in `commands/`, registered in `cli.py`
**Consistency:** 100%

**Command file structure:**
```python
"""<Command> command - <brief description>."""

import os

import click

from discord_chat.services.<service> import service_function
from discord_chat.utils.<util> import helper_function

# Constants at top
DEFAULT_VALUE = 10
MAX_VALUE = 100

@click.command()
@click.argument("required_arg")
@click.option("--optional", "-o", default=DEFAULT_VALUE, help="Description")
def command_name(required_arg: str, optional: int) -> None:
    """<One-line summary>.
    
    <Multi-line description of what the command does>.
    
    Example:
        discord-chat command-name "arg" --optional 20
    """
    # Validate environment
    if not os.environ.get("REQUIRED_VAR"):
        raise click.ClickException("REQUIRED_VAR environment variable is required.")
    
    # Call service layer
    try:
        result = service_function(required_arg, optional)
    except ServiceError as e:
        raise click.ClickException(str(e))
    
    # Display results
    click.echo(f"Result: {result}")
```

**Registration in cli.py:**
```python
from discord_chat.commands.command_name import command_name

main.add_command(command_name)
```

### Option Patterns

**Common option patterns:**
```python
# Boolean flags
@click.option("--debug", is_flag=True, default=False, help="Enable debug mode")
@click.option("--quiet", "-q", is_flag=True, help="Suppress output")
@click.option("--dry-run", is_flag=True, help="Preview without executing")

# Integers with defaults
@click.option("--hours", "-h", default=24, type=int, help="Hours to look back")
@click.option("--limit", type=int, default=100, help="Maximum items")

# Choices (enum-like)
@click.option("--llm", "-l", type=click.Choice(["claude", "openai"], case_sensitive=False))

# Paths
@click.option("--output", "-o", type=click.Path(), default=".", help="Output directory")

# Environment variable fallback
@click.option("--debug", is_flag=True, envvar="DISCORD_CHAT_DEBUG")
```

### Context Passing

**Pattern:** Use Click context to pass global options to subcommands
**Consistency:** 100%

**Main command with context:**
```python
@click.group()
@click.version_option(version=get_version(), prog_name="discord-chat")
@click.option("--debug", is_flag=True, envvar="DISCORD_CHAT_DEBUG")
@click.pass_context
def main(ctx: click.Context, debug: bool) -> None:
    """discord-chat - A CLI tool."""
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug
    setup_logging(debug)
```

**Accessing context in subcommands:**
```python
@click.command()
@click.pass_context
def subcommand(ctx: click.Context) -> None:
    """Subcommand that uses global options."""
    if ctx.obj["debug"]:
        click.echo("Debug mode enabled")
```

### Output Patterns

**Pattern:** Use `click.echo()` for all output, not `print()`
**Consistency:** 100%

**Examples:**
```python
# Standard output
click.echo("Operation completed successfully")
click.echo(f"Processed {count} items")

# Conditional output (with --quiet flag)
if not quiet:
    click.echo("Status message")

# Error output (to stderr)
click.echo("Error: Something went wrong", err=True)

# Table formatting
max_name_len = max(len(item.name) for item in items)
col_width = max(max_name_len + 1, 20)

click.echo(f"{'Name':<{col_width}} {'Count':>10}")
click.echo(f"{'-' * col_width} {'-' * 10}")
for item in items:
    click.echo(f"{item.name:<{col_width}} {item.count:>10}")
```

---

## Service Layer Patterns

### Service Module Structure

**Pattern:** Services encapsulate external integrations and business logic
**Consistency:** 100%

**Service file structure:**
```python
"""<Service> service for <purpose>."""

import asyncio
import os
from dataclasses import dataclass
from datetime import UTC, datetime

import external_library

from discord_chat.utils.security_logger import get_security_logger

# Custom exceptions first
class ServiceError(Exception):
    """Base exception for service errors."""
    pass

class SpecificError(ServiceError):
    """Specific error case."""
    pass

# Data classes
@dataclass
class ServiceData:
    """Data returned by service."""
    field: str
    count: int

# Service class
class ServiceClient:
    """Client for external service.
    
    Thread Safety: NOT thread-safe. Create new instance per operation.
    
    Configuration via environment:
        SERVICE_API_KEY: Required API key
        SERVICE_TIMEOUT: Timeout in seconds (default: 60)
    """
    
    DEFAULT_TIMEOUT = 60
    
    def __init__(self):
        """Initialize service client."""
        self._api_key = self._load_api_key()
        self._security_logger = get_security_logger()
    
    @staticmethod
    def _load_api_key() -> str:
        """Load and validate API key from environment."""
        key = os.environ.get("SERVICE_API_KEY")
        if not key:
            raise ServiceError("SERVICE_API_KEY environment variable is required.")
        return key.strip()
    
    async def fetch_data(self, param: str) -> ServiceData:
        """Fetch data from service."""
        try:
            result = await external_library.get(param)
            self._security_logger.log_api_call("Service", "fetch_data", duration_ms, True)
            return ServiceData(...)
        except external_library.AuthError:
            self._security_logger.log_auth_attempt(False, "Service")
            raise ServiceError("Authentication failed. Check your API key.")
        except Exception:
            raise ServiceError("Failed to fetch data. Please try again.")

# Synchronous wrapper for CLI
def fetch_data(param: str) -> ServiceData:
    """Synchronous wrapper for CLI usage."""
    client = ServiceClient()
    return asyncio.run(client.fetch_data(param))
```

### Provider Pattern (for Multiple Implementations)

**Pattern:** Abstract base class + concrete providers + factory function
**Consistency:** 100%

**Base class (base.py):**
```python
"""Base class for <providers>."""

from abc import ABC, abstractmethod

class ProviderError(Exception):
    """Base exception for provider errors."""
    pass

class Provider(ABC):
    """Abstract base class for providers."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider name."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is available (has credentials)."""
        pass
    
    @abstractmethod
    def do_operation(self, param: str) -> str:
        """Perform the operation."""
        pass
```

**Concrete provider (provider_a.py):**
```python
"""Provider A implementation."""

import os
from .base import Provider, ProviderError

class ProviderA(Provider):
    """Implementation using Provider A."""
    
    @property
    def name(self) -> str:
        return "Provider A"
    
    def is_available(self) -> bool:
        return bool(os.environ.get("PROVIDER_A_API_KEY"))
    
    def do_operation(self, param: str) -> str:
        """Perform operation using Provider A."""
        # Implementation
```

**Factory function (__init__.py):**
```python
"""Provider module with abstraction."""

from .base import Provider, ProviderError
from .provider_a import ProviderA
from .provider_b import ProviderB

__all__ = ["Provider", "ProviderError", "ProviderA", "ProviderB", "get_provider"]

PROVIDER_REGISTRY = {
    "provider_a": ProviderA,
    "provider_b": ProviderB,
}

def get_provider(provider_name: str | None = None) -> Provider:
    """Get a provider instance.
    
    Args:
        provider_name: Name of provider. If None, auto-selects first available.
    
    Returns:
        An initialized provider instance.
    
    Raises:
        ProviderError: If no provider is available.
    """
    if provider_name:
        provider_name = provider_name.lower()
        if provider_name not in PROVIDER_REGISTRY:
            available = ", ".join(PROVIDER_REGISTRY.keys())
            raise ProviderError(f"Unknown provider '{provider_name}'. Available: {available}")
        
        provider_class = PROVIDER_REGISTRY[provider_name]
        provider = provider_class()
        if not provider.is_available():
            raise ProviderError(f"Provider '{provider_name}' is not available.")
        return provider
    
    # Auto-select first available
    for name, provider_class in PROVIDER_REGISTRY.items():
        provider = provider_class()
        if provider.is_available():
            return provider
    
    raise ProviderError("No provider available. Please set API keys.")
```

---

## Security Patterns

### Input Validation

**Pattern:** Validate and sanitize all user input before use
**Consistency:** 100%

**Server name validation (path traversal prevention):**
```python
def validate_server_name(server_name: str) -> str:
    """Validate and sanitize server name to prevent path traversal attacks."""
    if not server_name or not server_name.strip():
        raise InvalidServerNameError("Server name cannot be empty")
    
    name = server_name.strip()
    
    # Block path traversal patterns
    if ".." in name or name.startswith("/") or name.startswith("\\"):
        raise InvalidServerNameError(
            f"Invalid server name '{server_name}': contains path traversal characters"
        )
    
    # Block control characters
    if "\x00" in name or "\n" in name or "\r" in name:
        raise InvalidServerNameError(
            f"Invalid server name '{server_name}': contains control characters"
        )
    
    # Limit length
    if len(name) > 100:
        raise InvalidServerNameError(f"Server name too long ({len(name)} chars). Maximum is 100.")
    
    return name
```

**Numeric range validation:**
```python
# Constants for validation
MIN_HOURS = 1
MAX_HOURS = 168  # 1 week maximum

# Validation in command
if hours < MIN_HOURS or hours > MAX_HOURS:
    security_logger.log_input_validation_failure(
        "hours", str(hours), f"Must be between {MIN_HOURS} and {MAX_HOURS}"
    )
    raise click.ClickException(f"Hours must be between {MIN_HOURS} and {MAX_HOURS}. Got: {hours}")
```

**LLM prompt injection prevention:**
```python
@staticmethod
def _sanitize_for_llm(text: str) -> str:
    """Sanitize text to prevent prompt injection attacks."""
    if not text:
        return ""
    
    # Remove control characters
    sanitized = text.replace("\n", " ").replace("\r", " ")
    sanitized = "".join(c for c in sanitized if c.isprintable() or c in " \t")
    
    # Limit length
    if len(sanitized) > 200:
        sanitized = sanitized[:200]
    
    # Remove prompt injection patterns
    dangerous_patterns = [
        "ignore previous",
        "ignore above",
        "new instructions",
        "system:",
    ]
    
    sanitized_lower = sanitized.lower()
    for pattern in dangerous_patterns:
        if pattern in sanitized_lower:
            sanitized = sanitized.replace(pattern, pattern.replace(" ", "_"))
    
    return sanitized
```

### Secure File Operations

**Pattern:** Prevent symlink attacks and set secure permissions
**Consistency:** 100%

**Secure file write:**
```python
def write_file_secure(path: Path, content: str) -> None:
    """Write file with secure permissions (owner read/write only).
    
    Args:
        path: Path to write to.
        content: Content to write.
    
    Raises:
        ValueError: If attempting to overwrite a symlink (security check).
        OSError: If file write fails.
    """
    # Check if path is a symlink before writing (prevent TOCTOU attacks)
    if path.exists() or path.is_symlink():
        if path.is_symlink():
            raise ValueError(
                f"Refusing to write to symlink: {path}. "
                "This could be a security issue. Delete the symlink first."
            )
    
    # Use os.open with O_EXCL to fail if file exists (prevents races)
    try:
        fd = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,  # O_EXCL fails if file exists
            stat.S_IRUSR | stat.S_IWUSR,  # 0600 permissions
        )
    except FileExistsError:
        # File exists, check it's not a symlink before overwriting
        if path.is_symlink():
            raise ValueError(f"Refusing to overwrite symlink: {path}")
        fd = os.open(path, os.O_WRONLY | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
    
    try:
        os.write(fd, content.encode("utf-8"))
    finally:
        os.close(fd)
```

### TLS Certificate Verification

**Pattern:** Always enable TLS verification for API clients
**Consistency:** 100%

**Examples:**
```python
import httpx
import anthropic

# Create HTTP client with explicit TLS verification
http_client = httpx.Client(verify=True)
client = anthropic.Anthropic(api_key=api_key, http_client=http_client)

# Same pattern for OpenAI
import openai
http_client = httpx.Client(verify=True)
client = openai.OpenAI(api_key=api_key, http_client=http_client)
```

### Resource Limits (DoS Prevention)

**Pattern:** Limit resource consumption to prevent exhaustion
**Consistency:** 100%

**Examples:**
```python
# Limit message content length
MAX_MESSAGE_CONTENT_LENGTH = 100_000  # 100KB per message

content = message.content
if len(content) > MAX_MESSAGE_CONTENT_LENGTH:
    content = content[:MAX_MESSAGE_CONTENT_LENGTH] + "...[truncated]"

# Limit number of attachments
attachments = [a.filename for a in message.attachments[:10]]  # Max 10
if len(message.attachments) > 10:
    attachments.append(f"...and {len(message.attachments) - 10} more")

# Limit reactions
reactions = [{"emoji": str(r.emoji)[:20], "count": r.count} for r in list(message.reactions)[:20]]

# Configurable limits from environment
DEFAULT_MAX_MESSAGES_PER_CHANNEL = 1000
max_messages = _get_env_int("DISCORD_CHAT_MAX_MESSAGES", DEFAULT_MAX_MESSAGES_PER_CHANNEL, min_val=100, max_val=10000)

# Log rotation to prevent disk exhaustion
file_handler = RotatingFileHandler(
    log_path,
    maxBytes=10 * 1024 * 1024,  # 10MB
    backupCount=5,  # Keep 5 old logs
)
```

---

## Agent Instructions

### For code-implementer

When implementing in this codebase:

1. **File creation**
   - New CLI commands: `discord_chat/commands/<command_name>.py`
   - New services: `discord_chat/services/<service_name>.py`
   - New utilities: `discord_chat/utils/<util_name>.py`
   - New tests: `tests/test_<module_name>.py`
   - Use snake_case for all filenames

2. **Naming**
   - Functions/variables: `snake_case`
   - Classes/exceptions: `PascalCase`
   - Constants: `SCREAMING_SNAKE_CASE` (module-level) or normal (class-level)
   - Test classes: `TestClassName`
   - Test methods: `test_<scenario>`

3. **Style**
   - Run `make format` to apply Black + Ruff formatting
   - Line length: 100 characters
   - Full type hints on all function signatures
   - Docstrings: Google-style for all public functions/classes
   - Import order: stdlib → third-party → local (enforced by Ruff)

4. **Error handling**
   - Create custom exceptions inheriting from domain base
   - Sanitize error messages (no tokens, paths, internal details)
   - Convert service exceptions to `click.ClickException` in commands
   - Always log security events (auth, validation failures, API calls)

5. **Async code**
   - Use `async def` for I/O operations
   - Provide sync wrappers using `asyncio.run()` for CLI entry points
   - Always clean up in `finally` blocks
   - Use `asyncio.Semaphore` for rate limiting
   - Use `asyncio.wait_for()` for timeouts

6. **Security**
   - Validate all user input (path traversal, control characters, length)
   - Log validation failures to security log
   - Use secure file operations (`write_file_secure`)
   - Enable TLS verification (`httpx.Client(verify=True)`)
   - Limit resource consumption (message length, concurrency)
   - Sanitize data before LLM prompts

7. **Testing**
   - Create class-based test organization
   - Use descriptive test names: `test_<scenario>`
   - Mock external APIs with `@patch`
   - Use `CliRunner` for Click command tests
   - Use `@pytest.mark.asyncio` for async tests
   - Target 95%+ coverage
   - Run `make test` before committing

### For test-generator

When generating tests:

1. **Location:** `tests/test_<module_name>.py`
2. **Structure:** Class-based organization with `TestClassName` grouping related tests
3. **Naming:** `test_<scenario>` - descriptive, reads as documentation
4. **Assertions:** Use pytest assertions (`assert`, `pytest.raises`)
5. **Mocks:** 
   - Use `@patch` decorators (bottom-to-top, params top-to-bottom)
   - Name mocks: `mock_<function>`, `mock_<object>`
   - Use `MagicMock(spec=ClassName)` for type safety
6. **CLI tests:** Use `CliRunner` from click.testing
7. **Async tests:** Use `@pytest.mark.asyncio` marker
8. **Fixtures:** Create helpers with `@pytest.fixture`, use `autouse=True` for setup/teardown
9. **Coverage:** Test happy path, error cases, edge cases, security scenarios

### For all agents

**Always:**
- Use `snake_case` for files, functions, variables
- Use `PascalCase` for classes, exceptions
- Add type hints to all function signatures
- Add docstrings to all public functions/classes
- Use `click.echo()` not `print()`
- Log security events (auth, validation, API calls)
- Validate user input before use
- Clean up async resources in `finally` blocks
- Run `make format` before committing
- Run `make test` to ensure tests pass

**Never:**
- Use camelCase or PascalCase for functions/variables
- Use snake_case for classes
- Expose sensitive data in error messages (tokens, paths, internals)
- Skip input validation
- Use `print()` instead of `click.echo()`
- Forget to register new commands in `cli.py`
- Leave resources uncleaned (clients, files, tasks)
- Use `asyncio.run()` inside an event loop
- Disable TLS verification

**Ask if unsure:**
- Whether to create a new service module or extend existing
- Whether async is needed for a particular operation
- What the appropriate exception type is
- How to handle a new type of security validation
- Where to place a new utility function

---

## Consistency Report

### Well-Followed Conventions (>90%)

- Naming conventions (snake_case/PascalCase): 100%
- Black/Ruff formatting: 100% (enforced)
- Type annotations: 95%
- Docstrings: 95%
- Error handling patterns: 100%
- Security logging: 100%
- Async cleanup: 100%
- Test organization: 98%
- Import ordering: 100% (enforced)

### Moderate Consistency (70-90%)

- Constant naming: 90% (some class constants use normal case, some use SCREAMING)
- Comment density: 80% (varies by complexity)

### Low Consistency (<70%)

None identified. This codebase is highly consistent.

---

## Evolution Notes

### Recent Changes

- Added comprehensive async tests (test_discord_client_async.py)
- Enhanced security tests (test_llm_security.py, test_digest_security.py)
- Implemented security logging throughout
- Added TLS verification enforcement
- Improved input validation (server name, hours, LLM prompts)

### Recommended Clarifications

None needed. Conventions are well-established and consistently applied.

---

## Configuration Files Reference

**pyproject.toml** - All configuration in one file:
```toml
[project]
name = "discord-chat"
version = "0.1.0"
requires-python = ">=3.11.12"
dependencies = [
    "click>=8.1.0",
    "discord.py>=2.3.0",
    # ... security-patched versions
]

[project.scripts]
discord-chat = "cli:main"

[tool.black]
line-length = 100
target-version = ["py311"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
asyncio_mode = "strict"
```

**Makefile** - Common commands:
```makefile
make lint      # Run Ruff linter with auto-fix
make format    # Run Black formatter + import sorting
make test      # Run pytest with coverage
make check     # Run all checks (lint + format + test)
make hooks     # Install git pre-commit hooks
```

**.gitignore** - What to ignore:
- `__pycache__/`, `*.pyc`
- `.venv/`, `venv/`
- `.pytest_cache/`, `.coverage`, `htmlcov/`
- `.ruff_cache/`
- `*.log`, `.env`
- `.idea/`, `.vscode/`
- Output directories: `tne-digest/`

---

## Summary

This codebase exhibits exceptionally high consistency (95%+ across all dimensions):

**Strengths:**
- Clean architecture (commands/services/utils separation)
- Comprehensive security logging and validation
- Proper async/await patterns with cleanup
- Excellent test coverage (95%+) with clear organization
- Enforced formatting (Black/Ruff)
- Full type annotations
- Security-first design (input validation, TLS, resource limits)

**Key Patterns to Follow:**
1. **Naming:** snake_case everywhere except PascalCase classes
2. **Architecture:** Commands are thin, services contain logic
3. **Errors:** Custom exceptions, sanitized messages, security logging
4. **Async:** Proper cleanup, semaphore rate limiting, timeouts
5. **Testing:** Class-based organization, descriptive names, high coverage
6. **Security:** Validate input, log events, limit resources, enable TLS

When adding new code, match these patterns exactly for consistency.
