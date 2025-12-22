# Discord-Chat: Progressive Architecture Guide

**Target Audience:** New developers, architects, maintainers  
**Security Score:** 85/100 (Low Risk)  
**Language:** Python 3.11+  
**Architecture:** Clean Architecture with Command-Service-Util layers

---

## Table of Contents

1. [Quick Overview](#1-quick-overview)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Data Flow: Command to Output](#3-data-flow-command-to-output)
4. [Key Abstractions & Responsibilities](#4-key-abstractions--responsibilities)
5. [Entry Points & Extension Points](#5-entry-points--extension-points)
6. [Critical Paths](#6-critical-paths)
7. [Security Architecture](#7-security-architecture)
8. [Common Tasks & Change Guides](#8-common-tasks--change-guides)

---

## 1. Quick Overview

### What Is This?

Discord-Chat is a CLI tool that fetches messages from Discord servers and generates AI-powered activity digests. It's designed for teams who want to quickly catch up on server activity without manually reading hundreds of messages.

**Core Value Proposition:**  
Transform 6 hours of Discord conversations across 20+ channels into a 2-minute readable summary.

### Tech Stack Summary

| Layer | Technology | Purpose |
|-------|------------|---------|
| CLI Framework | Click 8.1+ | Command-line interface & argument parsing |
| Discord API | discord.py 2.3+ | Async message fetching from Discord servers |
| LLM Integration | Anthropic SDK, OpenAI SDK | AI-powered digest generation |
| Security | Custom security logger | Audit logging, input validation |
| Testing | pytest, pytest-asyncio | Comprehensive test coverage |
| Package Management | uv | Fast dependency resolution & env management |

### Project Statistics

- **Total Lines of Code:** ~1,228 lines
- **Commands:** 3 (version, activity, digest)
- **LLM Providers:** 2 (Claude, OpenAI)
- **Test Coverage:** 85%+ (see TEST_COVERAGE_SUMMARY.md)
- **Security Audit Score:** 85/100

---

## 2. High-Level Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI Layer (cli.py)                      │
│  Entry point, logging setup, command registration              │
└────────────────────┬────────────────────────────────────────────┘
                     │
         ┌───────────┼───────────┐
         │           │           │
         ▼           ▼           ▼
    ┌────────┐  ┌────────┐  ┌─────────┐
    │version │  │activity│  │ digest  │  ← Commands Layer
    │        │  │        │  │         │     (Click commands)
    └────────┘  └───┬────┘  └────┬────┘
                    │            │
                    └────────┬───┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
    ┌──────────┐      ┌───────────┐      ┌──────────┐
    │ Discord  │      │    LLM    │      │Formatter │  ← Services & Utils
    │ Client   │      │ Providers │      │ Logger   │
    │(async)   │      │ (Claude,  │      │          │
    │          │      │  OpenAI)  │      │          │
    └─────┬────┘      └─────┬─────┘      └──────────┘
          │                 │
          ▼                 ▼
    ┌──────────┐      ┌───────────┐
    │ Discord  │      │Anthropic/ │  ← External APIs
    │   API    │      │ OpenAI    │
    │          │      │   APIs    │
    └──────────┘      └───────────┘
```

### Architecture Pattern: Clean Architecture

The codebase follows **Clean Architecture** principles with clear separation of concerns:

```
discord_chat/
├── commands/          # Use cases (CLI command handlers)
│   ├── version.py     # Simple: read package version
│   ├── activity.py    # Medium: fetch & display stats
│   └── digest.py      # Complex: orchestrate fetching + LLM generation
│
├── services/          # Business logic & external integrations
│   ├── discord_client.py    # Discord API abstraction
│   └── llm/                 # LLM provider abstraction
│       ├── base.py          # Abstract interface (Strategy pattern)
│       ├── claude.py        # Claude implementation
│       └── openai_provider.py  # OpenAI implementation
│
└── utils/             # Pure functions & helpers
    ├── digest_formatter.py  # Text formatting, validation
    └── security_logger.py   # Security event logging
```

**Why This Structure?**

1. **Testability:** Pure business logic in services, easy to mock
2. **Extensibility:** Add new commands or LLM providers without touching existing code
3. **Maintainability:** Clear boundaries, easy to reason about
4. **Security:** Validation at edges (commands), sanitization in services

---

## 3. Data Flow: Command to Output

### Complete Request Lifecycle (Digest Command)

```
┌──────────────────────────────────────────────────────────────────┐
│ 1. USER INPUT                                                    │
│    $ discord-chat digest "MyServer" --hours 6 --llm claude       │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│ 2. CLI LAYER (cli.py)                                            │
│    • Load .env file (python-dotenv)                              │
│    • Setup logging (debug/warning levels)                        │
│    • Parse arguments (Click)                                     │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│ 3. COMMAND LAYER (digest.py)                                     │
│    • Validate server_name (path traversal check)                 │
│    • Validate hours (1-168 range check)                          │
│    • Check DISCORD_BOT_TOKEN exists                              │
│    • Log validation failures to security.log                     │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│ 4. DISCORD SERVICE (discord_client.py)                           │
│    ┌─────────────────────────────────────────────────────────┐  │
│    │ 4a. Initialize DiscordMessageFetcher                    │  │
│    │     • Create Discord.Client with intents                │  │
│    │     • Validate bot token format                         │  │
│    └─────────────────────┬───────────────────────────────────┘  │
│                          ▼                                        │
│    ┌─────────────────────────────────────────────────────────┐  │
│    │ 4b. Async Operations (asyncio.run)                      │  │
│    │     • Connect to Discord (with timeout)                 │  │
│    │     • Find server by name (case-insensitive)            │  │
│    │     • Get all text channels                             │  │
│    │     • Fetch messages (rate-limited: 5 concurrent max)   │  │
│    │     • Filter: skip bots, empty messages                 │  │
│    │     • Truncate: max 100KB per message                   │  │
│    │     • Cleanup: close connection, cancel tasks           │  │
│    └─────────────────────┬───────────────────────────────────┘  │
└──────────────────────────┼──────────────────────────────────────┘
                           │
                           ▼ Returns ServerDigestData
┌──────────────────────────────────────────────────────────────────┐
│ 5. DATA FORMATTING (digest_formatter.py)                         │
│    • Convert ServerDigestData to text                            │
│    • Format: "## #channel-name\n[timestamp] **author**: msg"    │
│    • Include attachments, reactions                              │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼ Formatted text (~50KB max)
┌──────────────────────────────────────────────────────────────────┐
│ 6. LLM PROVIDER SELECTION (llm/__init__.py)                      │
│    • If --llm specified: use that provider                       │
│    • Else: auto-select (prefer Claude > OpenAI)                  │
│    • Check API key availability                                  │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼ LLMProvider instance
┌──────────────────────────────────────────────────────────────────┐
│ 7. LLM GENERATION (claude.py or openai_provider.py)              │
│    ┌─────────────────────────────────────────────────────────┐  │
│    │ 7a. Prepare Prompt                                      │  │
│    │     • System prompt (digest guidelines)                 │  │
│    │     • User prompt with sanitized inputs                 │  │
│    │     • Sanitization: remove control chars, injection     │  │
│    │       patterns ("ignore previous instructions")         │  │
│    └─────────────────────┬───────────────────────────────────┘  │
│                          ▼                                        │
│    ┌─────────────────────────────────────────────────────────┐  │
│    │ 7b. API Call                                            │  │
│    │     • Create HTTP client with TLS verification          │  │
│    │     • Call LLM API (Claude: claude-sonnet-4)            │  │
│    │     • Handle errors: auth, rate limit, network          │  │
│    │     • Log API timing and success/failure                │  │
│    └─────────────────────┬───────────────────────────────────┘  │
└──────────────────────────┼──────────────────────────────────────┘
                           │
                           ▼ Markdown digest string
┌──────────────────────────────────────────────────────────────────┐
│ 8. OUTPUT GENERATION (digest.py + digest_formatter.py)           │
│    • Create header with metadata                                 │
│    • Combine header + LLM digest                                 │
│    • Generate safe filename (digest-servername-timestamp.md)     │
│    • Write file with 0600 permissions (owner-only)               │
│    • Log file operation to security.log                          │
│    • Print to console (unless --quiet)                           │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│ 9. OUTPUT                                                        │
│    • File: ./digest-myserver-20241222-1430.md                    │
│    • Console: Full digest with separator lines                   │
│    • Logs: security.log with JSON events                         │
└──────────────────────────────────────────────────────────────────┘
```

### Data Structures

**Core Data Flow:**

```python
# Step 4 → 5: Discord returns structured data
ServerDigestData {
    server_name: str,
    server_id: int,
    channels: [ChannelMessages {
        channel_name: str,
        channel_id: int,
        messages: [{
            id: int,
            author: str,
            content: str,
            timestamp: str (ISO),
            attachments: [str],
            reactions: [{emoji: str, count: int}]
        }]
    }],
    start_time: datetime,
    end_time: datetime,
    total_messages: int
}

# Step 5 → 7: Formatted as text
"""
## #general
[2024-12-22 14:30] **Alice**: Hey team, quick question...
[2024-12-22 14:32] **Bob**: Sure, what's up?

## #dev-chat
[2024-12-22 14:15] **Charlie**: PR is ready for review...
"""

# Step 7 → 9: LLM-generated digest
"""
## Channel Activity Summary
- **#general**: Team coordination and quick questions...
- **#dev-chat**: Code review discussions for PR #42...

## Key Highlights
- **Feature Release**: v2.0 shipped with...
"""
```

---

## 4. Key Abstractions & Responsibilities

### 4.1 LLM Provider Abstraction (Strategy Pattern)

**File:** `/Users/jima/comware/workspace/discord-chat/discord_chat/services/llm/base.py`

**Design Pattern:** Strategy Pattern (polymorphic LLM providers)

```python
# Abstract interface
class LLMProvider(ABC):
    @property
    def name(self) -> str: ...
    
    @property
    def required_env_var(self) -> str: ...
    
    def is_available(self) -> bool: ...
    
    def generate_digest(...) -> str: ...
```

**Responsibilities:**
1. **API Key Management:** Check availability without exposing keys
2. **Prompt Engineering:** Standardized system/user prompts
3. **Input Sanitization:** Prevent prompt injection attacks
4. **Error Handling:** Translate provider-specific errors to generic `LLMError`
5. **Security Logging:** Track auth attempts, API calls, failures

**Concrete Implementations:**

| Provider | Model | Max Tokens | File |
|----------|-------|------------|------|
| Claude | claude-sonnet-4-20250514 | 4,096 | `/Users/jima/comware/workspace/discord-chat/discord_chat/services/llm/claude.py` |
| OpenAI | gpt-4-turbo-preview | 4,096 | `/Users/jima/comware/workspace/discord-chat/discord_chat/services/llm/openai_provider.py` |

**Extension Point:** To add a new provider (e.g., Gemini):

```python
# 1. Create discord_chat/services/llm/gemini.py
class GeminiProvider(LLMProvider):
    MODEL = "gemini-pro"
    
    @property
    def name(self) -> str:
        return "Gemini"
    
    # ... implement abstract methods

# 2. Register in discord_chat/services/llm/__init__.py
PROVIDER_REGISTRY = {
    "claude": ClaudeProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,  # Add here
}
```

### 4.2 Discord Client (Async Message Fetcher)

**File:** `/Users/jima/comware/workspace/discord-chat/discord_chat/services/discord_client.py`

**Responsibilities:**
1. **Authentication:** Validate and use Discord bot token
2. **Server Discovery:** Find servers by name (case-insensitive, partial match)
3. **Message Fetching:** Async fetch with rate limiting and timeouts
4. **Resource Management:** Prevent memory exhaustion, handle cleanup
5. **Error Translation:** Convert discord.py exceptions to `DiscordClientError`

**Key Security Features:**

| Feature | Implementation | Location |
|---------|----------------|----------|
| Rate Limiting | Semaphore(5) for concurrent channel fetches | Line 304 |
| Timeout | 60s default (configurable) | Line 87 |
| Memory Protection | Truncate messages >100KB | Line 237 |
| Token Validation | Length check (min 50 chars) | Line 165 |
| Async Cleanup | Always close client, cancel tasks | Line 401-408 |

**Configuration via Environment Variables:**

```bash
# All optional, have safe defaults
DISCORD_CHAT_TIMEOUT=60           # Operation timeout (10-300s)
DISCORD_CHAT_MAX_MESSAGES=1000    # Per-channel limit (100-10000)
DISCORD_CHAT_MAX_CONCURRENT=5     # Concurrent fetches (1-20)
```

### 4.3 Security Logger (Audit Trail)

**File:** `/Users/jima/comware/workspace/discord-chat/discord_chat/utils/security_logger.py`

**Responsibilities:**
1. **Structured Logging:** JSON format for SIEM integration
2. **Event Tracking:** Auth, API calls, validation failures, file ops
3. **Sensitive Data Sanitization:** Auto-redact tokens, keys, passwords
4. **Log Rotation:** Prevent disk exhaustion (10MB/file, 5 backups)
5. **Security Events:** Dedicated event types for monitoring

**Event Types:**

| Event | When Logged | Severity |
|-------|-------------|----------|
| `AUTH_SUCCESS` | Successful Discord/LLM auth | INFO |
| `AUTH_FAILURE` | Failed auth attempt | WARNING |
| `API_CALL` | Every external API call with timing | INFO |
| `RATE_LIMIT` | Rate limiter engaged | INFO |
| `INPUT_VALIDATION_FAILED` | Invalid user input (potential attack) | WARNING |
| `FILE_OPERATION` | File create/write/read | INFO |
| `ERROR` | Security-relevant errors | ERROR |

**Log Format:**

```json
{
  "timestamp": "2024-12-22T14:30:45.123Z",
  "event_type": "auth_success",
  "message": "Discord authentication succeeded",
  "details": {
    "service": "Discord"
  }
}
```

**Configuration:**

```bash
# Optional: custom log location
export DISCORD_CHAT_SECURITY_LOG="/var/log/discord-chat/security.log"
```

### 4.4 Input Validation (Defense Layer)

**File:** `/Users/jima/comware/workspace/discord-chat/discord_chat/utils/digest_formatter.py`

**Responsibilities:**
1. **Server Name Validation:** Block path traversal, control chars
2. **Safe Filename Generation:** Sanitize for filesystem operations
3. **Length Limits:** Prevent DOS via excessive input

**Validation Rules:**

```python
# Server name validation
validate_server_name(name):
    ✓ Max 100 chars
    ✗ Path traversal: "..", "/", "\"
    ✗ Control chars: \x00, \n, \r
    ✓ Whitespace trimming

# Filename generation
get_default_output_filename(name):
    ✓ Alphanumeric + hyphen/underscore only
    ✓ Replace spaces with hyphens
    ✓ Lowercase normalization
    ✓ Timestamp suffix: YYYYMMDD-HHMM
    ✗ No dots (prevent hidden files, extension tricks)
    ✗ No path separators (final safety check)
```

---

## 5. Entry Points & Extension Points

### 5.1 Entry Points (How to Run the Application)

**Main Entry Point:**  
`/Users/jima/comware/workspace/discord-chat/cli.py`

```bash
# Direct execution
python cli.py --help

# Via uv (recommended)
uv run python cli.py digest "MyServer" --hours 6

# Installed as package (if packaged)
discord-chat digest "MyServer" --hours 6
```

**Command Registration:**

```python
# cli.py (lines 51-54)
main.add_command(activity)   # Simple stats
main.add_command(digest)     # Full LLM digest
main.add_command(version)    # Version info
```

### 5.2 Extension Points

#### A. Adding a New Command

**Example: Add a "export" command to export raw messages as JSON**

1. **Create:** `/Users/jima/comware/workspace/discord-chat/discord_chat/commands/export.py`

```python
import click
from discord_chat.services.discord_client import fetch_server_messages

@click.command()
@click.argument("server_name")
@click.option("--hours", "-h", default=6, type=int)
@click.option("--output", "-o", type=click.Path(), default="export.json")
def export(server_name: str, hours: int, output: str) -> None:
    """Export messages as JSON."""
    data = fetch_server_messages(server_name, hours)
    # ... format as JSON, write file
```

2. **Register:** In `/Users/jima/comware/workspace/discord-chat/cli.py`

```python
from discord_chat.commands.export import export

main.add_command(export)  # Add this line
```

3. **Test:** Create `/Users/jima/comware/workspace/discord-chat/tests/test_export.py`

#### B. Adding a New LLM Provider

**Example: Add Google Gemini**

1. **Create:** `/Users/jima/comware/workspace/discord-chat/discord_chat/services/llm/gemini.py`

```python
from .base import LLMProvider, LLMError

class GeminiProvider(LLMProvider):
    @property
    def name(self) -> str:
        return "Gemini"
    
    @property
    def required_env_var(self) -> str:
        return "GOOGLE_API_KEY"
    
    def is_available(self) -> bool:
        return bool(os.environ.get("GOOGLE_API_KEY"))
    
    def generate_digest(self, messages_text: str, ...) -> str:
        # Implement using google-generativeai SDK
        pass
```

2. **Register:** In `/Users/jima/comware/workspace/discord-chat/discord_chat/services/llm/__init__.py`

```python
from .gemini import GeminiProvider

PROVIDER_REGISTRY = {
    "claude": ClaudeProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,  # Add here
}
```

3. **Add Dependency:** In `/Users/jima/comware/workspace/discord-chat/pyproject.toml`

```toml
dependencies = [
    # ...existing...
    "google-generativeai>=0.3.0",
]
```

4. **Test:** Create `/Users/jima/comware/workspace/discord-chat/tests/test_gemini_provider.py`

#### C. Adding a New Formatter

**Example: Add Slack-compatible output format**

1. **Create:** `/Users/jima/comware/workspace/discord-chat/discord_chat/utils/slack_formatter.py`

```python
def format_messages_for_slack(data: ServerDigestData) -> str:
    """Format messages in Slack's mrkdwn format."""
    # ... convert to Slack blocks format
```

2. **Use in Command:** Modify digest command to accept `--format` option

```python
@click.option("--format", type=click.Choice(["markdown", "slack"]))
def digest(..., format: str):
    if format == "slack":
        from discord_chat.utils.slack_formatter import format_messages_for_slack
        # ... use slack formatter
```

### 5.3 Configuration Extension Points

**Environment Variables (All Optional):**

```bash
# Discord Service
DISCORD_BOT_TOKEN=required           # Bot authentication
DISCORD_CHAT_TIMEOUT=60              # Operation timeout (10-300s)
DISCORD_CHAT_MAX_MESSAGES=1000       # Per-channel message limit
DISCORD_CHAT_MAX_CONCURRENT=5        # Concurrent channel fetches

# LLM Services
ANTHROPIC_API_KEY=optional           # Claude provider
OPENAI_API_KEY=optional              # OpenAI provider

# Security & Logging
DISCORD_CHAT_DEBUG=false             # Enable debug logging
DISCORD_CHAT_SECURITY_LOG=./security.log  # Security log path
```

---

## 6. Critical Paths

### 6.1 Authentication Flow

**Path:** User → Discord API → LLM API

```
┌─────────────────────────────────────────────────────────────┐
│ 1. DISCORD AUTHENTICATION                                   │
│    Location: discord_client.py:148-170                      │
├─────────────────────────────────────────────────────────────┤
│ Steps:                                                      │
│   a. Load token from env: DISCORD_BOT_TOKEN                 │
│   b. Validate format: min 50 chars                          │
│   c. Create Discord.Client(token, intents)                  │
│   d. Wait for on_ready event (30s timeout)                  │
│   e. Log success/failure to security.log                    │
├─────────────────────────────────────────────────────────────┤
│ Error Handling:                                             │
│   • Missing token → DiscordClientError (user-friendly msg)  │
│   • Invalid format → DiscordClientError (hint: verify)      │
│   • LoginFailure → Sanitized error (no token in logs)       │
│   • Timeout → DiscordClientError (connection issue)         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 2. LLM AUTHENTICATION                                       │
│    Location: claude.py:47-55 (similar in openai_provider)  │
├─────────────────────────────────────────────────────────────┤
│ Steps:                                                      │
│   a. Get provider via get_provider(name)                    │
│   b. Check API key: os.environ.get(required_env_var)        │
│   c. Create HTTP client with TLS verification               │
│   d. Make test/actual API call                              │
│   e. Log auth success/failure with timing                   │
├─────────────────────────────────────────────────────────────┤
│ Error Handling:                                             │
│   • No API key → LLMError with env var name                 │
│   • AuthenticationError → LLMError (verify key)             │
│   • RateLimitError → LLMError (wait and retry)              │
│   • ConnectionError → LLMError (check network)              │
└─────────────────────────────────────────────────────────────┘
```

**Security Considerations:**

- Tokens NEVER logged (sanitized in logger)
- No tokens in exception messages
- No tokens in command-line args (env vars only)
- Auth failures logged separately for monitoring

### 6.2 Message Fetching Flow

**Path:** Discord Server → Channels → Messages → Structured Data

```
┌────────────────────────────────────────────────────────────────┐
│ PHASE 1: SERVER DISCOVERY                                      │
│ Location: discord_client.py:179-205                            │
├────────────────────────────────────────────────────────────────┤
│ 1. Find server by name (case-insensitive)                      │
│    • Exact match first: "MyServer" == "myserver"               │
│    • Partial match fallback: "my" in "MyServer"                │
│ 2. If not found → ServerNotFoundError with available list      │
└────────────────────────────────────────────────────────────────┘
                              ▼
┌────────────────────────────────────────────────────────────────┐
│ PHASE 2: CHANNEL ENUMERATION                                   │
│ Location: discord_client.py:380                                │
├────────────────────────────────────────────────────────────────┤
│ 1. Filter: guild.channels → only TextChannel types             │
│ 2. Calculate time window: end_time - timedelta(hours)          │
│ 3. Prepare for concurrent fetching                             │
└────────────────────────────────────────────────────────────────┘
                              ▼
┌────────────────────────────────────────────────────────────────┐
│ PHASE 3: RATE-LIMITED MESSAGE FETCHING                         │
│ Location: discord_client.py:284-319                            │
├────────────────────────────────────────────────────────────────┤
│ Rate Limiting (Semaphore):                                     │
│   • Max 5 concurrent channel fetches                           │
│   • Prevents API quota exhaustion                              │
│   • Prevents memory overload                                   │
│                                                                 │
│ Per-Channel Fetch (lines 207-282):                             │
│   1. channel.history(after, before, limit=1000)                │
│   2. Filter: skip bot messages, empty messages                 │
│   3. Truncate: content > 100KB → truncate with notice          │
│   4. Limit: max 10 attachments per message                     │
│   5. Yield: every 100 messages (allow GC)                      │
│   6. Sort: by timestamp ascending                              │
│   7. Return: ChannelMessages dataclass                         │
│                                                                 │
│ Error Handling:                                                │
│   • Forbidden (no perms) → skip channel silently               │
│   • HTTPException → log warning, continue                      │
└────────────────────────────────────────────────────────────────┘
                              ▼
┌────────────────────────────────────────────────────────────────┐
│ PHASE 4: AGGREGATION & CLEANUP                                 │
│ Location: discord_client.py:389-408                            │
├────────────────────────────────────────────────────────────────┤
│ 1. Filter: remove channels with 0 messages                     │
│ 2. Calculate: total_messages = sum(len(ch.messages))           │
│ 3. Return: ServerDigestData                                    │
│ 4. Cleanup: client.close(), cancel login_task                  │
└────────────────────────────────────────────────────────────────┘
```

**Performance & Security:**

| Metric | Value | Reason |
|--------|-------|--------|
| Concurrent Fetches | 5 channels | Balance speed vs rate limits |
| Messages per Channel | 1,000 max | Prevent memory exhaustion |
| Message Content | 100KB max | Prevent DOS via large msgs |
| Operation Timeout | 60s default | Fail fast if server has 100+ channels |
| Memory Yield | Every 100 msgs | Allow garbage collection |

### 6.3 Digest Generation Flow

**Path:** Formatted Messages → LLM Prompt → API Call → Markdown Output

```
┌────────────────────────────────────────────────────────────────┐
│ STEP 1: FORMAT MESSAGES FOR LLM                                │
│ Location: digest_formatter.py:53-85                            │
├────────────────────────────────────────────────────────────────┤
│ Input: ServerDigestData                                        │
│ Output: Plain text with structure:                             │
│                                                                 │
│   ## #channel-name                                             │
│   [2024-12-22 14:30] **Alice**: Message content...             │
│   [2024-12-22 14:32] **Bob**: Reply...                         │
│     _Attachments: image.png_                                   │
│                                                                 │
│   ## #another-channel                                          │
│   ...                                                           │
└────────────────────────────────────────────────────────────────┘
                              ▼
┌────────────────────────────────────────────────────────────────┐
│ STEP 2: SANITIZE INPUTS (Prompt Injection Prevention)          │
│ Location: llm/base.py:119-159                                  │
├────────────────────────────────────────────────────────────────┤
│ Sanitization Rules:                                            │
│   • Remove: \n, \r, \x00 (control chars)                       │
│   • Keep: printable chars + space/tab                          │
│   • Limit: 200 chars for metadata (server name, time range)    │
│   • Block: "ignore previous", "system:", "new instructions"    │
│   • Truncate: messages_text to 50KB max                        │
│                                                                 │
│ Applied To:                                                    │
│   ✓ server_name                                                │
│   ✓ time_range                                                 │
│   ✗ messages_text (truncated but not pattern-filtered)         │
└────────────────────────────────────────────────────────────────┘
                              ▼
┌────────────────────────────────────────────────────────────────┐
│ STEP 3: BUILD PROMPT                                           │
│ Location: llm/base.py:62-117                                   │
├────────────────────────────────────────────────────────────────┤
│ System Prompt (same for all providers):                        │
│   "You are a helpful assistant that creates concise,           │
│    well-organized digests of Discord conversations..."         │
│                                                                 │
│   Guidelines:                                                  │
│     1. Channel Activity Summary (1-2 sentences per channel)    │
│     2. Key Highlights (organized by theme)                     │
│     3. Important discussions, decisions, announcements         │
│     4. Unanswered questions                                    │
│     5. Action items / follow-ups                               │
│                                                                 │
│ User Prompt:                                                   │
│   "Please create a digest for '{server_name}'.                 │
│    Time period: {time_range}                                   │
│    Channels: {channel_count}                                   │
│    Messages: {message_count}                                   │
│                                                                 │
│    Here are the messages organized by channel:                 │
│    {messages_text}"                                            │
└────────────────────────────────────────────────────────────────┘
                              ▼
┌────────────────────────────────────────────────────────────────┐
│ STEP 4: LLM API CALL                                           │
│ Location: claude.py:59-75 (OpenAI similar)                     │
├────────────────────────────────────────────────────────────────┤
│ Claude Specifics:                                              │
│   • Model: claude-sonnet-4-20250514                            │
│   • Max tokens: 4,096                                          │
│   • HTTP client: TLS verification enabled (verify=True)        │
│   • Timeout: Provider default (~60s)                           │
│                                                                 │
│ Error Handling (lines 86-135):                                 │
│   • AuthenticationError → "verify API key"                     │
│   • RateLimitError → "wait and retry"                          │
│   • ConnectionError → "check network"                          │
│   • BadRequestError → check for "too long" → suggest --hours   │
│   • All errors logged with timing, sanitized details           │
└────────────────────────────────────────────────────────────────┘
                              ▼
┌────────────────────────────────────────────────────────────────┐
│ STEP 5: ASSEMBLE FINAL DIGEST                                  │
│ Location: digest_formatter.py:129-145                          │
├────────────────────────────────────────────────────────────────┤
│ Header (create_digest_header):                                │
│   # Discord Digest: {server_name}                             │
│   **Generated:** {timestamp}                                   │
│   **Time Period:** {start} to {end}                            │
│   **Channels with activity:** {count}                          │
│   **Total messages:** {total}                                  │
│   **Generated by:** Claude/OpenAI                              │
│   ---                                                          │
│                                                                 │
│ Body: LLM-generated markdown                                   │
└────────────────────────────────────────────────────────────────┘
                              ▼
┌────────────────────────────────────────────────────────────────┐
│ STEP 6: SECURE FILE WRITE                                      │
│ Location: digest.py:65-104                                     │
├────────────────────────────────────────────────────────────────┤
│ Security Checks:                                               │
│   1. Check if path is symlink → refuse (prevent TOCTOU)        │
│   2. Use os.open() with O_CREAT|O_EXCL for atomic create       │
│   3. Set permissions: 0600 (owner read/write only)             │
│   4. Write content atomically                                  │
│   5. Log file operation to security.log                        │
│                                                                 │
│ Filename Format:                                               │
│   digest-{safe_server_name}-{YYYYMMDD-HHMM}.md                 │
│   Example: digest-myserver-20241222-1430.md                    │
└────────────────────────────────────────────────────────────────┘
```

**Prompt Engineering Strategy:**

The system prompt is carefully designed to:
1. **Structure Output:** Consistent format across providers
2. **Prioritize Information:** Channel summaries → Key highlights
3. **Capture Actionables:** Unanswered questions, action items
4. **Maintain Context:** Include usernames for attribution

---

## 7. Security Architecture

### 7.1 Threat Model

**Attack Vectors Addressed:**

| Vector | Mitigation | Location |
|--------|------------|----------|
| **Path Traversal** | Input validation, safe filename gen | digest_formatter.py:14-50 |
| **Prompt Injection** | Input sanitization, pattern blocking | llm/base.py:119-159 |
| **Token Exposure** | Env vars only, log sanitization | security_logger.py:196-226 |
| **DOS (Memory)** | Message truncation, GC yields | discord_client.py:237-263 |
| **DOS (Disk)** | Log rotation, file size checks | security_logger.py:64-71 |
| **DOS (API)** | Rate limiting, timeouts | discord_client.py:304 |
| **Symlink Attacks** | Symlink detection before write | digest.py:78-84 |
| **TOCTOU Races** | O_CREAT|O_EXCL atomic ops | digest.py:89-99 |
| **TLS MITM** | Enforce verify=True in HTTP clients | claude.py:54 |

### 7.2 Security Layers (Defense in Depth)

```
┌──────────────────────────────────────────────────────────────┐
│ LAYER 1: INPUT VALIDATION (First Line of Defense)           │
├──────────────────────────────────────────────────────────────┤
│ • Server name: max 100 chars, no ../ or control chars       │
│ • Hours: 1-168 range                                         │
│ • Output path: validated for traversal attempts             │
│ • All failures logged to security.log                        │
│ Files: digest.py:159-173, digest_formatter.py:14-50         │
└──────────────────────────────────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ LAYER 2: RESOURCE LIMITS (DOS Prevention)                   │
├──────────────────────────────────────────────────────────────┤
│ • Max 1000 messages/channel                                  │
│ • Max 100KB/message content                                  │
│ • Max 5 concurrent channel fetches                           │
│ • 60s operation timeout                                      │
│ • GC yield every 100 messages                                │
│ Files: discord_client.py:87-111, 237-263                     │
└──────────────────────────────────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ LAYER 3: CREDENTIAL PROTECTION                              │
├──────────────────────────────────────────────────────────────┤
│ • Environment variables only (no CLI args)                   │
│ • Token format validation                                    │
│ • Auto-sanitization in logs                                  │
│ • No tokens in exception messages                            │
│ Files: discord_client.py:148-170, security_logger.py:207    │
└──────────────────────────────────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ LAYER 4: PROMPT INJECTION PREVENTION                        │
├──────────────────────────────────────────────────────────────┤
│ • Sanitize metadata inputs (server name, time range)        │
│ • Block patterns: "ignore previous", "system:", etc.         │
│ • Limit metadata to 200 chars                                │
│ • Truncate messages to 50KB                                  │
│ Files: llm/base.py:119-159                                   │
└──────────────────────────────────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ LAYER 5: SECURE FILE OPERATIONS                             │
├──────────────────────────────────────────────────────────────┤
│ • Symlink detection (TOCTOU prevention)                      │
│ • Atomic file creation (O_EXCL)                              │
│ • 0600 permissions (owner-only)                              │
│ • Safe filename generation                                   │
│ Files: digest.py:65-104, digest_formatter.py:148-182         │
└──────────────────────────────────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ LAYER 6: AUDIT & MONITORING                                 │
├──────────────────────────────────────────────────────────────┤
│ • All security events logged (JSON)                          │
│ • Log rotation (50MB max, 5 backups)                         │
│ • SIEM-ready format                                          │
│ • Sensitive data auto-redacted                               │
│ Files: security_logger.py (entire file)                      │
└──────────────────────────────────────────────────────────────┘
```

### 7.3 Security Audit Results (December 2024)

**Overall Score:** 85/100 (Low Risk)

**Vulnerabilities Fixed:**

| Severity | Count | Examples |
|----------|-------|----------|
| Critical | 3 | Token exposure, path traversal, prompt injection |
| High | 4 | Memory DOS, disk DOS, symlink attacks, TOCTOU |
| Medium | 2 | Rate limiting, timeout handling |

**See:** `/Users/jima/comware/workspace/discord-chat/SECURITY.md` for complete details

---

## 8. Common Tasks & Change Guides

### 8.1 How to Add a New Command

**Scenario:** You want to add a "stats" command that shows aggregate statistics.

**Files to Touch:**

1. `/Users/jima/comware/workspace/discord-chat/discord_chat/commands/stats.py` (create)
2. `/Users/jima/comware/workspace/discord-chat/cli.py` (modify line 51-54)
3. `/Users/jima/comware/workspace/discord-chat/tests/test_stats.py` (create)

**Step-by-Step:**

```python
# 1. Create discord_chat/commands/stats.py
import click
from discord_chat.services.discord_client import fetch_server_messages

@click.command()
@click.argument("server_name")
@click.option("--hours", "-h", default=24, type=int)
def stats(server_name: str, hours: int) -> None:
    """Show aggregate statistics for a server."""
    data = fetch_server_messages(server_name, hours)
    
    # Calculate stats
    avg_per_channel = data.total_messages / len(data.channels) if data.channels else 0
    most_active = max(data.channels, key=lambda c: len(c.messages))
    
    # Display
    click.echo(f"Total messages: {data.total_messages}")
    click.echo(f"Avg per channel: {avg_per_channel:.1f}")
    click.echo(f"Most active: #{most_active.channel_name}")

# 2. Register in cli.py
from discord_chat.commands.stats import stats

main.add_command(stats)  # Add after line 54

# 3. Test in tests/test_stats.py
import pytest
from click.testing import CliRunner
from discord_chat.commands.stats import stats

def test_stats_command(mocker):
    # Mock fetch_server_messages
    # Assert output contains expected stats
    pass
```

### 8.2 How to Modify LLM Prompt

**Scenario:** You want to add a "Sentiment Analysis" section to digests.

**Files to Touch:**

1. `/Users/jima/comware/workspace/discord-chat/discord_chat/services/llm/base.py` (modify lines 62-82)

**Change:**

```python
# In base.py, _get_system_prompt() method
def _get_system_prompt(self) -> str:
    return (
        "You are a helpful assistant that creates concise, well-organized "
        "digests of Discord server conversations.\n\n"
        # ... existing guidelines ...
        "7. Use bullet points and headers for readability\n"
        "8. Include relevant usernames when attributing specific statements\n"
        "9. Add a '## Sentiment Analysis' section with overall mood/tone\n"  # NEW
        "10. If there are no messages or minimal activity, state that clearly\n\n"
        "Output format should be clean Markdown suitable for reading."
    )
```

**Testing:** Run digest command and verify new section appears in output.

### 8.3 How to Change Rate Limits

**Scenario:** Your bot is hitting rate limits, need to reduce concurrent fetches.

**Files to Touch:**

1. Environment variable (preferred)
2. `/Users/jima/comware/workspace/discord-chat/discord_chat/services/discord_client.py` (default values)

**Option A: Via Environment Variable (Recommended)**

```bash
# In .env file
DISCORD_CHAT_MAX_CONCURRENT=3  # Reduce from 5 to 3
```

**Option B: Change Default in Code**

```python
# In discord_client.py, line 89
DEFAULT_MAX_CONCURRENT_CHANNELS = 3  # Changed from 5
```

### 8.4 How to Add Custom Formatting

**Scenario:** Output digests in HTML format instead of Markdown.

**Files to Touch:**

1. `/Users/jima/comware/workspace/discord-chat/discord_chat/utils/html_formatter.py` (create)
2. `/Users/jima/comware/workspace/discord-chat/discord_chat/commands/digest.py` (modify)

**Implementation:**

```python
# 1. Create html_formatter.py
def create_html_digest(data: ServerDigestData, llm_digest: str, llm_name: str) -> str:
    """Convert markdown digest to HTML."""
    import markdown
    
    header = f"""
    <html>
    <head><title>Digest: {data.server_name}</title></head>
    <body>
        <h1>Discord Digest: {data.server_name}</h1>
        <p><strong>Generated:</strong> {datetime.now()}</p>
        <p><strong>Messages:</strong> {data.total_messages}</p>
    """
    
    body = markdown.markdown(llm_digest)
    return f"{header}{body}</body></html>"

# 2. Modify digest.py to add --format option
@click.option("--format", type=click.Choice(["markdown", "html"]), default="markdown")
def digest(..., format: str):
    # ... existing code ...
    
    if format == "html":
        from discord_chat.utils.html_formatter import create_html_digest
        full_digest = create_html_digest(data, llm_digest, provider.name)
        filename = filename.replace(".md", ".html")
    else:
        full_digest = create_full_digest(data, llm_digest, provider.name)
```

### 8.5 How to Debug Issues

**Common Scenarios:**

#### A. "Server not found" Error

```bash
# Problem: Case sensitivity or typo
$ discord-chat digest "MyServer" --hours 6
Error: Server 'MyServer' not found. Available: ['myserver', 'TestServer']

# Solution: Use exact name from "Available" list
$ discord-chat digest "myserver" --hours 6
```

#### B. Authentication Failures

```bash
# Check logs
$ tail -f security.log | grep auth_failure

# Verify token
$ echo $DISCORD_BOT_TOKEN | wc -c  # Should be 70+
$ python -c "import os; print(len(os.environ.get('DISCORD_BOT_TOKEN', '')))"
```

#### C. Enable Debug Logging

```bash
# Option 1: Environment variable
export DISCORD_CHAT_DEBUG=1
discord-chat digest "MyServer" --hours 6

# Option 2: CLI flag
discord-chat --debug digest "MyServer" --hours 6
```

**Debug Output Includes:**
- Discord.py connection details
- Message fetch progress
- LLM API request/response timing
- Full exception tracebacks

---

## 9. Gotchas & Tribal Knowledge

### 9.1 Discord API Quirks

**1. Message Content Intent Required**

If you get: `PrivilegedIntentsRequired` error

**Fix:** Enable in Discord Developer Portal:
1. Go to https://discord.com/developers/applications
2. Select your bot → Bot → Privileged Gateway Intents
3. Enable: "MESSAGE CONTENT INTENT"
4. Save changes, restart bot

**2. Partial Server Name Matching**

Server names are matched case-insensitively with partial matching. This means:
- Input: "my" → Matches: "My Cool Server"
- Input: "test" → Matches: "TestServer", "Test-123", etc.

**Best Practice:** Use full, exact server names to avoid ambiguity.

**3. Bot vs User Messages**

Bot messages are automatically filtered out (line 230 in discord_client.py). This includes:
- Your own bot's messages
- Other bots (webhooks, integrations)

**Why:** Reduces noise in digests, prevents circular references.

### 9.2 LLM Provider Differences

**Claude vs OpenAI:**

| Aspect | Claude | OpenAI |
|--------|--------|--------|
| Default Model | claude-sonnet-4-20250514 | gpt-4-turbo-preview |
| Max Tokens | 4,096 | 4,096 |
| Context Window | ~200K | ~128K |
| Speed | Faster (~2-3s) | Slower (~5-7s) |
| Cost | Lower | Higher |
| Digest Style | More structured | More conversational |

**Auto-Selection Logic:**  
Preference order: Claude → OpenAI (set in `/Users/jima/comware/workspace/discord-chat/discord_chat/services/llm/__init__.py:10-13`)

### 9.3 File Permission Issues

**Digest Files Created with 0600**

This means:
- Owner can read/write
- No one else can access

**Problem:** If you need to share digests:

```bash
# Make readable by group
chmod 640 digest-*.md

# Make world-readable (be careful with sensitive data!)
chmod 644 digest-*.md
```

**Security Note:** See `/Users/jima/comware/workspace/discord-chat/SECURITY.md:73-77` for rationale.

### 9.4 Async/Sync Boundary

**Where Sync Becomes Async:**

```python
# Synchronous wrapper (CLI entry point)
def fetch_server_messages(server_name: str, hours: int) -> ServerDigestData:
    fetcher = DiscordMessageFetcher()
    return asyncio.run(fetcher.fetch_server_messages(server_name, hours))
    #      ^^^^^^^^^^^ Sync → Async boundary
```

**Implication:** The entire Discord fetch is async internally, but exposed as sync to CLI.

**Why:** Click doesn't natively support async commands. Using `asyncio.run()` allows us to write async code while maintaining a sync CLI interface.

**Testing:** Use `pytest-asyncio` for testing async methods directly.

### 9.5 Known Limitations

**1. Message History Limit**

- Max 1,000 messages per channel (configurable)
- For very active channels, may not capture all messages in time window

**Workaround:** Reduce `--hours` or increase `DISCORD_CHAT_MAX_MESSAGES`

**2. Attachment Content Not Analyzed**

- Only attachment filenames are included
- Image/video content not sent to LLM

**Future Enhancement:** Add OCR or image description via multimodal LLMs

**3. Thread Messages**

Currently, only top-level channel messages are fetched. Thread replies are not included.

**Status:** Tracked as future enhancement (requires additional Discord API calls)

**4. Reaction Context**

Reactions are counted but not analyzed for sentiment or context.

**Example:**  
```
"reactions": [{"emoji": "👍", "count": 5}]
```

LLM sees this but may not interpret significance.

---

## 10. Quick Reference

### Environment Variables Cheat Sheet

```bash
# Required
DISCORD_BOT_TOKEN=your_token_here

# LLM (at least one required)
ANTHROPIC_API_KEY=sk-ant-...     # For Claude
OPENAI_API_KEY=sk-...            # For OpenAI

# Optional Tuning
DISCORD_CHAT_TIMEOUT=60          # Operation timeout (10-300s)
DISCORD_CHAT_MAX_MESSAGES=1000   # Per-channel limit (100-10000)
DISCORD_CHAT_MAX_CONCURRENT=5    # Concurrent fetches (1-20)
DISCORD_CHAT_DEBUG=0             # Enable debug logging (0 or 1)
DISCORD_CHAT_SECURITY_LOG=./security.log  # Security log path
```

### File Structure Map

```
/Users/jima/comware/workspace/discord-chat/
├── cli.py                              # Main entry point ⭐
├── discord_chat/
│   ├── commands/                       # CLI commands
│   │   ├── version.py                  # Simple: get version
│   │   ├── activity.py                 # Medium: message counts
│   │   └── digest.py                   # Complex: full digest ⭐
│   ├── services/
│   │   ├── discord_client.py           # Discord API client ⭐
│   │   └── llm/
│   │       ├── base.py                 # LLM interface ⭐
│   │       ├── claude.py               # Claude provider
│   │       ├── openai_provider.py      # OpenAI provider
│   │       └── __init__.py             # Provider registry
│   └── utils/
│       ├── digest_formatter.py         # Text formatting ⭐
│       └── security_logger.py          # Security logging ⭐
├── tests/                              # Comprehensive tests
├── SECURITY.md                         # Security guidelines ⭐
├── pyproject.toml                      # Dependencies
└── uv.lock                             # Locked dependencies

⭐ = Critical files for understanding architecture
```

### Key Code Locations

| Feature | File | Lines |
|---------|------|-------|
| Command registration | cli.py | 51-54 |
| Input validation | digest.py | 159-173 |
| Server discovery | discord_client.py | 179-205 |
| Message fetching | discord_client.py | 207-282 |
| Rate limiting | discord_client.py | 284-319 |
| LLM provider selection | llm/__init__.py | 16-53 |
| Prompt engineering | llm/base.py | 62-117 |
| Prompt injection prevention | llm/base.py | 119-159 |
| Secure file write | digest.py | 65-104 |
| Security logging | security_logger.py | 73-100 |

### Testing Commands

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_digest.py

# Run with coverage
pytest --cov=discord_chat --cov-report=html

# Run security tests only
pytest tests/test_digest_security.py tests/test_llm_security.py

# Run with debug output
pytest -v -s

# Run async tests specifically
pytest tests/test_discord_client_async.py
```

---

## Appendix A: Design Decisions

### Why Clean Architecture?

**Rationale:**
- **Testability:** Services can be unit tested without Discord/LLM APIs
- **Extensibility:** New commands or providers don't affect existing code
- **Clarity:** Clear boundaries between layers

**Trade-off:** Slightly more boilerplate (abstract classes, dataclasses)

### Why Click for CLI?

**Alternatives Considered:** argparse, Typer, Fire

**Choice:** Click

**Reasons:**
1. Industry standard (widely known)
2. Excellent documentation
3. Built-in support for complex options
4. Testing utilities (`CliRunner`)

### Why Strategy Pattern for LLM Providers?

**Rationale:**
- Each LLM API has different SDK, error types, models
- Need consistent interface for digest generation
- Easy to add new providers (Gemini, Llama, etc.)

**Implementation:**  
Abstract base class (`LLMProvider`) with concrete implementations (`ClaudeProvider`, `OpenAIProvider`)

### Why JSON for Security Logs?

**Rationale:**
- SIEM integration (Splunk, ELK, CloudWatch)
- Machine-readable for alerting
- Structured querying

**Trade-off:** Less human-readable than plain text, but tools exist for viewing.

---

## Appendix B: Future Enhancements

**Planned:**
1. Support for Discord threads
2. Image analysis via multimodal LLMs
3. Configurable digest templates
4. Webhook output (Slack, Teams)
5. Scheduled digest generation (cron-style)
6. Interactive mode (select channels to include)

**See:** GitHub Issues for tracking

---

**Document Version:** 1.0  
**Last Updated:** December 22, 2024  
**Maintained By:** Development Team  
**Next Review:** March 2025 or after major architectural changes

---

## Need Help?

- **Quick Questions:** Check this document first
- **Bug Reports:** GitHub Issues
- **Security Issues:** See SECURITY.md for responsible disclosure
- **Contributing:** See README.md for development setup

**Happy Coding!** 🚀
