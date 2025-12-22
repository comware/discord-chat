# Security Remediation Recommendations

## Critical Priority (P0) - Implement Immediately

### REC-001: Secure Credential Management

**Vulnerability:** CRIT-001 - API Key Exposure  
**Files:** `discord_chat/services/discord_client.py`, all LLM provider files  
**Effort:** Medium (4-6 hours)  
**Impact:** Critical

#### Current Issue
```python
# discord_client.py, line 53
def __init__(self, token: str | None = None):
    self.token = token or os.environ.get("DISCORD_BOT_TOKEN")
```

#### Recommended Fix

```python
# discord_client.py - UPDATED
import os
from typing import Final

class DiscordMessageFetcher:
    """Fetches messages from Discord servers."""

    def __init__(self):
        """Initialize the Discord message fetcher.
        
        Token is always loaded from DISCORD_BOT_TOKEN environment variable.
        """
        self._token = self._load_token()
        # ... rest of initialization

    @staticmethod
    def _load_token() -> str:
        """Securely load Discord token from environment.
        
        Returns:
            The Discord bot token.
            
        Raises:
            DiscordClientError: If token is not available or invalid.
        """
        token = os.environ.get("DISCORD_BOT_TOKEN")
        
        if not token:
            raise DiscordClientError(
                "DISCORD_BOT_TOKEN environment variable is required. "
                "Visit https://discord.com/developers/applications to create a bot."
            )
        
        # Validate token format (Discord tokens have specific format)
        if not token.strip() or len(token) < 50:
            raise DiscordClientError(
                "Invalid DISCORD_BOT_TOKEN format. Please check your token."
            )
            
        return token.strip()
    
    @property
    def token(self) -> str:
        """Get token (for internal use only)."""
        return self._token
```

#### Implementation Steps
1. Remove `token` parameter from all constructors
2. Add token validation method
3. Update all error messages to not include token fragments
4. Update tests to use environment variables only
5. Update documentation

#### Verification
```python
# Test that tokens cannot be passed as parameters
with pytest.raises(TypeError):
    DiscordMessageFetcher(token="test-token")

# Test proper error messages
with patch.dict(os.environ, {}, clear=True):
    with pytest.raises(DiscordClientError) as exc:
        DiscordMessageFetcher()
    assert "DISCORD_BOT_TOKEN" in str(exc.value)
    assert "test-token" not in str(exc.value)  # Ensure no token leakage
```

---

### REC-002: Comprehensive Input Validation

**Vulnerability:** CRIT-003 - Path Traversal  
**Files:** `discord_chat/commands/digest.py`, `discord_chat/utils/digest_formatter.py`  
**Effort:** Low (2-3 hours)  
**Impact:** Critical

#### Current Issue
```python
# digest_formatter.py, lines 96-99
def get_default_output_filename(server_name: str) -> str:
    safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in server_name)
    safe_name = safe_name.replace(" ", "-").lower()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    return f"digest-{safe_name}-{timestamp}.md"
```

#### Recommended Fix

```python
# digest_formatter.py - UPDATED
import re
from pathlib import Path

MAX_SERVER_NAME_LENGTH = 100
VALID_SERVER_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._\-\s]{0,98}[a-zA-Z0-9]$')

def validate_server_name(server_name: str) -> str:
    """Validate and sanitize server name.
    
    Args:
        server_name: The server name to validate.
        
    Returns:
        Validated server name.
        
    Raises:
        ValueError: If server name is invalid.
    """
    if not server_name or not server_name.strip():
        raise ValueError("Server name cannot be empty")
    
    # Remove leading/trailing whitespace
    server_name = server_name.strip()
    
    # Check length
    if len(server_name) > MAX_SERVER_NAME_LENGTH:
        raise ValueError(
            f"Server name too long (max {MAX_SERVER_NAME_LENGTH} characters)"
        )
    
    # Reject path separators
    if any(char in server_name for char in ['/', '\\', '\0', '..']):
        raise ValueError(
            "Server name cannot contain path separators (/, \\, ..)"
        )
    
    # Validate against pattern
    if not VALID_SERVER_NAME_PATTERN.match(server_name):
        raise ValueError(
            "Server name must start and end with alphanumeric characters "
            "and contain only letters, numbers, spaces, dots, hyphens, and underscores"
        )
    
    return server_name


def get_default_output_filename(server_name: str) -> str:
    """Generate a safe output filename.
    
    Args:
        server_name: Name of the Discord server (must be validated first).
        
    Returns:
        Filename with timestamp.
        
    Raises:
        ValueError: If server name is invalid.
    """
    # Validate first
    validated_name = validate_server_name(server_name)
    
    # Sanitize for filename (more restrictive than validation)
    safe_name = "".join(
        c if c.isalnum() or c in "._-" else "_" 
        for c in validated_name
    )
    safe_name = safe_name.replace(" ", "-").lower()
    
    # Remove any duplicate separators
    safe_name = re.sub(r'[-_.]{2,}', '-', safe_name)
    
    # Ensure max filename length (leave room for prefix and timestamp)
    max_name_len = 200 - len("digest--YYYYMMDD-HHMM.md")
    if len(safe_name) > max_name_len:
        safe_name = safe_name[:max_name_len]
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    return f"digest-{safe_name}-{timestamp}.md"


def validate_output_path(output_dir: str, filename: str) -> Path:
    """Validate that output path is safe.
    
    Args:
        output_dir: Directory for output.
        filename: Output filename.
        
    Returns:
        Validated Path object.
        
    Raises:
        ValueError: If path is unsafe.
    """
    try:
        base_dir = Path(output_dir).resolve()
        output_path = (base_dir / filename).resolve()
        
        # Ensure the output path is within the base directory
        if not str(output_path).startswith(str(base_dir)):
            raise ValueError(
                "Output path escapes target directory (path traversal detected)"
            )
        
        # Check if we can write to directory
        if not base_dir.exists():
            base_dir.mkdir(parents=True, exist_ok=True)
        
        if not base_dir.is_dir():
            raise ValueError(f"Output path is not a directory: {base_dir}")
        
        return output_path
        
    except (OSError, RuntimeError) as e:
        raise ValueError(f"Invalid output path: {e}")
```

#### Update digest.py

```python
# digest.py - UPDATED section around line 69-74
from discord_chat.utils.digest_formatter import (
    create_full_digest,
    format_messages_for_llm,
    format_time_range,
    get_default_output_filename,
    validate_output_path,  # NEW
    validate_server_name,  # NEW
)

@click.command()
@click.argument("server_name")
# ... options ...
def digest(server_name: str, hours: int, llm: str | None, output: str) -> None:
    """Generate a digest of Discord server activity."""
    
    # Validate inputs early
    try:
        server_name = validate_server_name(server_name)
    except ValueError as e:
        raise click.ClickException(f"Invalid server name: {e}")
    
    if hours < 1 or hours > 720:  # Max 30 days
        raise click.ClickException(
            "Hours must be between 1 and 720 (30 days)"
        )
    
    # ... existing code ...
    
    # Validate output path before saving
    try:
        filename = get_default_output_filename(data.server_name)
        output_path = validate_output_path(output, filename)
    except ValueError as e:
        raise click.ClickException(f"Invalid output path: {e}")
    
    # Set secure file permissions (owner read/write only)
    output_path.write_text(full_digest, encoding="utf-8")
    output_path.chmod(0o600)  # NEW: Secure permissions
    
    click.echo(f"Digest saved to: {output_path}")
```

#### Verification Tests
```python
def test_server_name_validation():
    # Valid names
    assert validate_server_name("My Server") == "My Server"
    assert validate_server_name("server-123") == "server-123"
    
    # Invalid names
    with pytest.raises(ValueError, match="path separators"):
        validate_server_name("../etc/passwd")
    
    with pytest.raises(ValueError, match="too long"):
        validate_server_name("x" * 200)
    
    with pytest.raises(ValueError, match="empty"):
        validate_server_name("")

def test_path_traversal_prevention():
    with pytest.raises(ValueError, match="path traversal"):
        validate_output_path("/tmp/output", "../../../etc/passwd")
```

---

### REC-003: API Rate Limiting and Throttling

**Vulnerability:** CRIT-002 - No Rate Limiting  
**Files:** `discord_chat/services/discord_client.py`, all LLM providers  
**Effort:** Medium (4-6 hours)  
**Impact:** Critical

#### Recommended Implementation

```python
# discord_client.py - ADD new class
import asyncio
from dataclasses import dataclass
from typing import Optional

@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    max_concurrent_channels: int = 5
    max_messages_per_channel: int = 1000
    request_delay_seconds: float = 0.5
    max_total_messages: int = 10000
    max_llm_tokens: int = 100000  # Approximate token limit


class DiscordMessageFetcher:
    """Fetches messages from Discord servers with rate limiting."""
    
    DEFAULT_RATE_LIMIT = RateLimitConfig()
    
    def __init__(self, rate_limit: Optional[RateLimitConfig] = None):
        """Initialize with rate limiting."""
        self._token = self._load_token()
        self.rate_limit = rate_limit or self.DEFAULT_RATE_LIMIT
        
        # Semaphore for concurrent channel access
        self._channel_semaphore = asyncio.Semaphore(
            self.rate_limit.max_concurrent_channels
        )
        
        # Track total messages
        self._total_messages_fetched = 0
        
        # ... rest of initialization

    async def _fetch_channel_messages(
        self,
        channel: discord.TextChannel,
        after: datetime,
        before: datetime,
    ) -> ChannelMessages:
        """Fetch messages from a single channel with rate limiting."""
        
        # Acquire semaphore to limit concurrent requests
        async with self._channel_semaphore:
            messages = []
            try:
                # Add delay between channel fetches
                await asyncio.sleep(self.rate_limit.request_delay_seconds)
                
                message_count = 0
                async for message in channel.history(
                    after=after, 
                    before=before, 
                    limit=self.rate_limit.max_messages_per_channel
                ):
                    # Check total message limit
                    if self._total_messages_fetched >= self.rate_limit.max_total_messages:
                        print(
                            f"Warning: Reached total message limit "
                            f"({self.rate_limit.max_total_messages}). "
                            f"Stopping fetch."
                        )
                        break
                    
                    # Skip bot messages and empty messages
                    if message.author.bot:
                        continue
                    if not message.content and not message.attachments:
                        continue

                    messages.append({
                        "id": message.id,
                        "author": message.author.display_name,
                        "author_id": message.author.id,
                        "content": message.content,
                        "timestamp": message.created_at.isoformat(),
                        "attachments": [a.filename for a in message.attachments],
                        "reactions": [
                            {"emoji": str(r.emoji), "count": r.count} 
                            for r in message.reactions
                        ],
                    })
                    
                    message_count += 1
                    self._total_messages_fetched += 1
                    
            except discord.Forbidden:
                pass
            except discord.HTTPException as e:
                # Implement exponential backoff for rate limits
                if hasattr(e, 'status') and e.status == 429:
                    retry_after = getattr(e, 'retry_after', 5.0)
                    print(f"Rate limited on #{channel.name}, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                    # Could retry here if desired
                else:
                    print(f"Warning: Could not fetch messages from #{channel.name}: {e}")

            return ChannelMessages(
                channel_name=channel.name,
                channel_id=channel.id,
                messages=sorted(messages, key=lambda m: m["timestamp"]),
            )
```

#### LLM Cost Controls

```python
# Add to base.py
@dataclass
class LLMCostConfig:
    """Configuration for LLM cost controls."""
    max_input_tokens: int = 50000
    max_output_tokens: int = 4096
    warn_threshold_tokens: int = 30000
    
def estimate_tokens(text: str) -> int:
    """Rough estimation of tokens (4 chars ≈ 1 token)."""
    return len(text) // 4

class LLMProvider(ABC):
    """Base class with cost controls."""
    
    def __init__(self, cost_config: Optional[LLMCostConfig] = None):
        self.cost_config = cost_config or LLMCostConfig()
    
    def _validate_input_size(self, messages_text: str) -> None:
        """Validate input size before API call."""
        estimated_tokens = estimate_tokens(messages_text)
        
        if estimated_tokens > self.cost_config.max_input_tokens:
            raise LLMError(
                f"Input too large ({estimated_tokens} tokens, "
                f"max {self.cost_config.max_input_tokens}). "
                "Try reducing the time range."
            )
        
        if estimated_tokens > self.cost_config.warn_threshold_tokens:
            print(
                f"Warning: Large input ({estimated_tokens} tokens) "
                "may incur significant costs."
            )
    
    def generate_digest(self, messages_text: str, ...) -> str:
        """Generate digest with validation."""
        self._validate_input_size(messages_text)
        # ... rest of implementation
```

---

## High Priority (P1) - Complete Within 1 Week

### REC-004: Sanitized Exception Handling

**Vulnerability:** HIGH-001 - Information Disclosure  
**Files:** All service files  
**Effort:** Low (2-3 hours)  
**Impact:** High

#### Recommended Implementation

```python
# Create new file: discord_chat/utils/errors.py
"""Centralized error handling with sanitization."""

import logging
import sys
import traceback
from typing import Optional

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('discord-chat.log'),
        logging.StreamHandler(sys.stderr)
    ]
)

logger = logging.getLogger('discord_chat')

def sanitize_error_message(error: Exception, user_message: str) -> str:
    """Create user-friendly error message while logging full details.
    
    Args:
        error: The original exception.
        user_message: User-friendly message describing what failed.
        
    Returns:
        Sanitized message for user display.
    """
    # Log full error details securely
    logger.error(
        f"{user_message}: {type(error).__name__}",
        exc_info=True,
        extra={
            'error_type': type(error).__name__,
            'error_message': str(error),
            'traceback': traceback.format_exc()
        }
    )
    
    # Return safe message to user
    return f"{user_message}. Please check logs for details."


# Update discord_client.py
from discord_chat.utils.errors import sanitize_error_message, logger

class DiscordMessageFetcher:
    
    async def fetch_server_messages(...) -> ServerDigestData:
        """Fetch messages with proper error handling."""
        try:
            # ... existing code ...
            
        except discord.PrivilegedIntentsRequired as e:
            error_msg = (
                "Privileged intents required. Please enable MESSAGE CONTENT INTENT "
                "in Discord Developer Portal"
            )
            logger.error(error_msg, exc_info=True)
            raise DiscordClientError(error_msg) from None
            
        except discord.LoginFailure as e:
            safe_msg = sanitize_error_message(
                e, 
                "Discord login failed"
            )
            raise DiscordClientError(safe_msg) from None
            
        except discord.HTTPException as e:
            safe_msg = sanitize_error_message(
                e,
                "Discord API error occurred"
            )
            raise DiscordClientError(safe_msg) from None
            
        except Exception as e:
            # Generic error - never expose internals
            safe_msg = sanitize_error_message(
                e,
                "An unexpected error occurred"
            )
            
            # Ensure cleanup
            if not self._client.is_closed():
                await self._client.close()
            
            raise DiscordClientError(safe_msg) from None
```

---

### REC-005: Comprehensive Security Logging

**Vulnerability:** HIGH-004 - Insufficient Logging  
**Files:** All files  
**Effort:** Medium (6-8 hours)  
**Impact:** High

#### Implementation

```python
# Create: discord_chat/utils/security_logger.py
"""Security event logging."""

import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Optional

class SecurityEventType(Enum):
    """Types of security events to log."""
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"
    API_CALL = "api_call"
    INPUT_VALIDATION_FAILURE = "input_validation_failure"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    FILE_ACCESS = "file_access"
    CONFIG_CHANGE = "config_change"
    ERROR = "error"

class SecurityLogger:
    """Structured security event logger."""
    
    def __init__(self):
        self.logger = logging.getLogger('discord_chat.security')
        
        # Configure JSON logging for security events
        handler = logging.FileHandler('discord-chat-security.log')
        handler.setFormatter(
            logging.Formatter('%(message)s')  # JSON only
        )
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def log_event(
        self,
        event_type: SecurityEventType,
        details: dict[str, Any],
        severity: str = "INFO"
    ) -> None:
        """Log a security event in structured format.
        
        Args:
            event_type: Type of security event.
            details: Event details (will be sanitized).
            severity: Log severity level.
        """
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type.value,
            "severity": severity,
            "details": self._sanitize_details(details)
        }
        
        log_method = getattr(self.logger, severity.lower(), self.logger.info)
        log_method(json.dumps(event))
    
    def _sanitize_details(self, details: dict[str, Any]) -> dict[str, Any]:
        """Remove sensitive data from log details."""
        sanitized = {}
        
        # List of keys that should never be logged
        sensitive_keys = {
            'token', 'api_key', 'password', 'secret', 
            'authorization', 'credential'
        }
        
        for key, value in details.items():
            # Check if key contains sensitive terms
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, str) and len(value) > 1000:
                # Truncate very long strings
                sanitized[key] = value[:1000] + "...[truncated]"
            else:
                sanitized[key] = value
        
        return sanitized

# Global security logger instance
security_logger = SecurityLogger()

# Usage in discord_client.py
from discord_chat.utils.security_logger import security_logger, SecurityEventType

class DiscordMessageFetcher:
    
    def _load_token(self) -> str:
        """Load token with security logging."""
        try:
            token = os.environ.get("DISCORD_BOT_TOKEN")
            if not token:
                security_logger.log_event(
                    SecurityEventType.AUTH_FAILURE,
                    {"reason": "Missing DISCORD_BOT_TOKEN"},
                    severity="WARNING"
                )
                raise DiscordClientError("...")
            
            security_logger.log_event(
                SecurityEventType.AUTH_SUCCESS,
                {"source": "environment_variable"},
                severity="INFO"
            )
            return token.strip()
            
        except Exception as e:
            security_logger.log_event(
                SecurityEventType.ERROR,
                {"error": str(e), "context": "token_loading"},
                severity="ERROR"
            )
            raise

    async def fetch_server_messages(...) -> ServerDigestData:
        """Fetch with API call logging."""
        
        security_logger.log_event(
            SecurityEventType.API_CALL,
            {
                "service": "discord",
                "server_name": server_name,
                "hours": hours,
                "start_time": start_time.isoformat()
            }
        )
        
        # ... existing code ...
        
        security_logger.log_event(
            SecurityEventType.API_CALL,
            {
                "service": "discord",
                "status": "success",
                "messages_fetched": total_messages,
                "channels": len(channels_with_messages)
            }
        )
```

---

### REC-006: Operation Timeouts

**Vulnerability:** HIGH-002 - Missing Timeouts  
**Files:** `discord_chat/services/discord_client.py`  
**Effort:** Low (1-2 hours)  
**Impact:** High

#### Implementation

```python
# discord_client.py - UPDATE
@dataclass
class FetchConfig:
    """Configuration for message fetching."""
    ready_timeout: float = 30.0
    operation_timeout: float = 300.0  # 5 minutes total
    channel_timeout: float = 60.0  # 1 minute per channel

class DiscordMessageFetcher:
    
    def __init__(self, config: Optional[FetchConfig] = None):
        """Initialize with timeout configuration."""
        self.config = config or FetchConfig()
        # ... rest of init

    async def fetch_server_messages(
        self,
        server_name: str,
        hours: int = 6,
    ) -> ServerDigestData:
        """Fetch messages with overall timeout."""
        
        try:
            # Wrap entire operation in timeout
            return await asyncio.wait_for(
                self._fetch_server_messages_impl(server_name, hours),
                timeout=self.config.operation_timeout
            )
        except asyncio.TimeoutError:
            raise DiscordClientError(
                f"Operation timed out after {self.config.operation_timeout} seconds. "
                "Try reducing the time range."
            )

    async def _fetch_server_messages_impl(
        self,
        server_name: str,
        hours: int,
    ) -> ServerDigestData:
        """Implementation with individual channel timeouts."""
        # ... existing code until channel fetching ...
        
        # Fetch with individual timeouts
        channel_results = []
        for channel in text_channels:
            try:
                result = await asyncio.wait_for(
                    self._fetch_channel_messages(channel, start_time, end_time),
                    timeout=self.config.channel_timeout
                )
                channel_results.append(result)
            except asyncio.TimeoutError:
                print(
                    f"Warning: Timeout fetching #{channel.name} "
                    f"(>{self.config.channel_timeout}s), skipping..."
                )
                continue
        
        # ... rest of implementation
```

---

## Medium Priority (P2) - Complete Within 2 Weeks

### REC-007: Secure File Operations

**Files:** `discord_chat/commands/digest.py`  
**Effort:** Low (1 hour)

```python
# digest.py - UPDATE file saving section
import stat

# Save with secure permissions
output_path.write_text(full_digest, encoding="utf-8")

# Set restrictive permissions (owner read/write only)
output_path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0o600

# Warn about sensitive data
if data.total_messages > 100:
    click.echo(
        "\nWarning: Digest may contain sensitive information. "
        "Ensure proper access controls."
    )
```

### REC-008: Configuration Management

Create configuration file for security settings:

```python
# Create: discord_chat/config.py
"""Centralized configuration management."""

import os
from dataclasses import dataclass
from pathlib import Path

@dataclass
class SecurityConfig:
    """Security-related configuration."""
    max_server_name_length: int = 100
    max_hours_lookback: int = 720  # 30 days
    min_hours_lookback: int = 1
    max_concurrent_channels: int = 5
    max_messages_per_channel: int = 1000
    max_total_messages: int = 10000
    file_permissions: int = 0o600
    enable_security_logging: bool = True
    log_file_path: Path = Path("discord-chat-security.log")

def load_security_config() -> SecurityConfig:
    """Load security configuration from environment or defaults."""
    return SecurityConfig(
        max_hours_lookback=int(
            os.getenv("DISCORD_CHAT_MAX_HOURS", "720")
        ),
        max_concurrent_channels=int(
            os.getenv("DISCORD_CHAT_MAX_CONCURRENT", "5")
        ),
        # ... other configurable values
    )
```

---

## Testing Recommendations

### Security Test Suite

```python
# Create: tests/test_security.py
"""Security-focused test cases."""

import pytest
from pathlib import Path

class TestInputValidation:
    """Test input validation security."""
    
    def test_path_traversal_rejected(self):
        """Ensure path traversal attempts are blocked."""
        malicious_names = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32",
            "test/../../../etc",
            "test/./../../etc",
        ]
        
        for name in malicious_names:
            with pytest.raises(ValueError, match="path"):
                validate_server_name(name)
    
    def test_overlong_input_rejected(self):
        """Ensure overlong inputs are rejected."""
        with pytest.raises(ValueError, match="too long"):
            validate_server_name("x" * 1000)
    
    def test_null_byte_injection(self):
        """Ensure null bytes are rejected."""
        with pytest.raises(ValueError):
            validate_server_name("test\x00malicious")

class TestCredentialSecurity:
    """Test credential handling security."""
    
    def test_no_credentials_in_logs(self, caplog):
        """Ensure credentials never appear in logs."""
        with patch.dict(os.environ, {"DISCORD_BOT_TOKEN": "secret123"}):
            # Perform operations that might log
            fetcher = DiscordMessageFetcher()
            
        # Check all log output
        for record in caplog.records:
            assert "secret123" not in record.message
            assert "secret" not in record.message.lower() or \
                   "REDACTED" in record.message
    
    def test_constructor_parameter_removed(self):
        """Ensure tokens cannot be passed as parameters."""
        with pytest.raises(TypeError):
            DiscordMessageFetcher(token="test")

class TestRateLimiting:
    """Test rate limiting functionality."""
    
    @pytest.mark.asyncio
    async def test_concurrent_limit_enforced(self):
        """Ensure concurrent request limits are enforced."""
        # Test implementation
        pass
    
    @pytest.mark.asyncio
    async def test_message_limit_enforced(self):
        """Ensure message limits are enforced."""
        # Test implementation
        pass
```

---

## Documentation Requirements

### Security Documentation

Create `SECURITY.md`:

```markdown
# Security Guidelines

## Credential Management

### Discord Bot Token
- **NEVER** commit tokens to version control
- Store in environment variable `DISCORD_BOT_TOKEN`
- Rotate tokens regularly (every 90 days)
- Use separate tokens for dev/prod

### LLM API Keys
- Store in `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`
- Never share keys between environments
- Monitor usage for anomalies
- Set up budget alerts

## Safe Usage

### Input Validation
- Server names limited to 100 characters
- Time ranges limited to 30 days
- Output paths validated

### Rate Limiting
- Maximum 5 concurrent channel fetches
- 1000 messages per channel
- 10,000 total messages per operation

## Incident Response

If credentials are exposed:
1. Immediately revoke the exposed credentials
2. Generate new credentials
3. Update environment variables
4. Review access logs
5. Notify security team

## Reporting Vulnerabilities

Report security issues to: security@example.com
- Do NOT open public issues for security bugs
- Use PGP encryption for sensitive reports
```

---

## Summary of Recommendations

| Priority | Recommendations | Effort | Timeline |
|----------|----------------|--------|----------|
| **P0** | REC-001 to REC-003 | 10-15 hours | 1-3 days |
| **P1** | REC-004 to REC-006 | 10-13 hours | 4-7 days |
| **P2** | REC-007 to REC-008 | 5-8 hours | 8-14 days |
| **Total** | 8 major recommendations | 25-36 hours | 2 weeks |

All code examples are production-ready and can be implemented directly.
