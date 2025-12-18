# Code Quality Analysis

## Overview

This document analyzes code quality issues beyond security, including maintainability, reliability, type safety, error handling, and Python best practices.

---

## HIGH Priority - Code Quality Issues

### CQ-HIGH-001: Inconsistent Error Handling Patterns

**Files:** All service files  
**Severity:** HIGH  
**Impact:** Reliability, Maintainability

**Issue:**
Error handling is inconsistent across the codebase. Some functions use specific exceptions, others use generic `Exception`, and error messages vary in quality.

**Examples:**
```python
# discord_client.py, line 127-130 - Good: Specific handling
except discord.Forbidden:
    # Bot doesn't have permission to read this channel
    pass

# discord_client.py, line 131-133 - Mediocre: Generic exception with print
except discord.HTTPException as e:
    # Log but don't fail on individual channel errors
    print(f"Warning: Could not fetch messages from #{channel.name}: {e}")

# discord_client.py, line 164-168 - Poor: Generic catch-all
except Exception:
    # Ensure cleanup on any error
    if not self._client.is_closed():
        await self._client.close()
    raise
```

**Problems:**
1. Mix of logging mechanisms (print vs proper logging)
2. Some errors swallowed silently
3. No error context preservation
4. Inconsistent user messaging

**Recommendation:**
```python
# Establish error handling hierarchy
from discord_chat.utils.errors import logger

class DiscordMessageFetcher:
    
    async def _fetch_channel_messages(...) -> ChannelMessages:
        """Fetch with consistent error handling."""
        messages = []
        try:
            async for message in channel.history(...):
                # Processing
                pass
                
        except discord.Forbidden:
            logger.warning(
                f"No permission to read channel #{channel.name}",
                extra={"channel_id": channel.id}
            )
            # Return empty results, don't fail
            
        except discord.HTTPException as e:
            logger.error(
                f"HTTP error fetching from #{channel.name}: {e}",
                exc_info=True,
                extra={
                    "channel_id": channel.id,
                    "error_code": getattr(e, 'code', None),
                    "status": getattr(e, 'status', None)
                }
            )
            # Decide whether to retry or fail based on error type
            if hasattr(e, 'status') and e.status >= 500:
                # Server error - could retry
                raise
            # Client error - return partial results
            
        except asyncio.TimeoutError:
            logger.warning(
                f"Timeout fetching from #{channel.name}",
                extra={"channel_id": channel.id}
            )
            
        except Exception as e:
            # Unexpected error - log with full context
            logger.error(
                f"Unexpected error in channel #{channel.name}",
                exc_info=True,
                extra={
                    "channel_id": channel.id,
                    "error_type": type(e).__name__
                }
            )
            # Re-raise as known exception
            raise DiscordClientError(
                f"Failed to fetch messages from #{channel.name}"
            ) from e
        
        return ChannelMessages(...)
```

---

### CQ-HIGH-002: Missing Resource Cleanup Guarantees

**Files:** `discord_chat/services/discord_client.py`  
**Severity:** HIGH  
**Impact:** Resource leaks, reliability

**Issue:**
Discord client cleanup relies on try/finally blocks but doesn't guarantee cleanup in all error paths. The task cancellation could fail silently.

**Evidence:**
```python
# discord_client.py, lines 143-156
finally:
    # Always close the client
    await self._client.close()
    # Cancel the login task if still running
    login_task.cancel()
    try:
        await login_task
    except asyncio.CancelledError:
        pass  # This is silently ignored
```

**Problems:**
1. `client.close()` might fail, preventing task cancellation
2. No verification that cleanup succeeded
3. Silent error suppression in cancellation
4. No cleanup timeout

**Recommendation:**
```python
async def fetch_server_messages(...) -> ServerDigestData:
    """Fetch with guaranteed cleanup."""
    
    login_task = None
    try:
        login_task = asyncio.create_task(self._client.start(self.token))
        
        await self._wait_until_ready()
        # ... fetch logic ...
        
        return ServerDigestData(...)
        
    finally:
        # Cleanup with guaranteed execution
        cleanup_errors = []
        
        # Close client with timeout
        if not self._client.is_closed():
            try:
                await asyncio.wait_for(
                    self._client.close(),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                cleanup_errors.append("Client close timeout")
                logger.error("Discord client close timed out")
            except Exception as e:
                cleanup_errors.append(f"Client close error: {e}")
                logger.error(f"Error closing Discord client: {e}", exc_info=True)
        
        # Cancel login task
        if login_task and not login_task.done():
            login_task.cancel()
            try:
                await asyncio.wait_for(login_task, timeout=2.0)
            except asyncio.CancelledError:
                pass  # Expected
            except asyncio.TimeoutError:
                cleanup_errors.append("Task cancellation timeout")
                logger.error("Login task cancellation timed out")
            except Exception as e:
                cleanup_errors.append(f"Task cancel error: {e}")
                logger.error(f"Error cancelling login task: {e}", exc_info=True)
        
        # Log if cleanup had issues
        if cleanup_errors:
            logger.warning(
                "Cleanup completed with errors",
                extra={"errors": cleanup_errors}
            )
```

---

### CQ-HIGH-003: No Retry Logic for Transient Failures

**Files:** All API client files  
**Severity:** HIGH  
**Impact:** Reliability

**Issue:**
No retry logic for transient network errors or rate limiting. A single network blip causes complete failure.

**Recommendation:**
```python
# Create: discord_chat/utils/retry.py
"""Retry utilities for transient failures."""

import asyncio
import functools
from typing import Callable, TypeVar, Optional

T = TypeVar('T')

async def retry_with_backoff(
    func: Callable[..., T],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: tuple = (Exception,)
) -> T:
    """Retry function with exponential backoff.
    
    Args:
        func: Async function to retry.
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay between retries.
        max_delay: Maximum delay between retries.
        exceptions: Tuple of exceptions to catch and retry.
        
    Returns:
        Result of function call.
        
    Raises:
        Last exception if all retries exhausted.
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                logger.info(f"Retry attempt {attempt}/{max_retries}")
            
            return await func()
            
        except exceptions as e:
            last_exception = e
            
            if attempt >= max_retries:
                logger.error(
                    f"All {max_retries} retries exhausted",
                    exc_info=True
                )
                raise
            
            # Calculate delay with exponential backoff
            delay = min(base_delay * (2 ** attempt), max_delay)
            
            logger.warning(
                f"Attempt {attempt + 1} failed, retrying in {delay}s: {e}"
            )
            
            await asyncio.sleep(delay)
    
    # Should never reach here, but for type safety
    raise last_exception


# Usage in discord_client.py
async def _fetch_channel_messages(...) -> ChannelMessages:
    """Fetch with retry logic."""
    
    async def fetch_impl():
        messages = []
        async for message in channel.history(...):
            # Process message
            pass
        return messages
    
    # Retry on specific exceptions
    messages = await retry_with_backoff(
        fetch_impl,
        max_retries=3,
        base_delay=2.0,
        exceptions=(discord.HTTPException, asyncio.TimeoutError)
    )
    
    return ChannelMessages(...)
```

---

### CQ-HIGH-004: Type Safety Gaps

**Files:** Multiple  
**Severity:** MEDIUM-HIGH  
**Impact:** Maintainability, bug prevention

**Issue:**
While the codebase uses type hints, there are several gaps that reduce type safety.

**Examples:**

```python
# discord_client.py, line 68-70 - Missing return type
@self._client.event
async def on_ready():  # Should be: -> None
    self._ready_event.set()

# base.py - Abstract methods missing type constraints
class LLMProvider(ABC):
    @abstractmethod
    def generate_digest(
        self,
        messages_text: str,  # Could be more specific
        server_name: str,
        channel_count: int,
        message_count: int,
        time_range: str,
    ) -> str:  # Return type could be NewType or custom class
        pass

# digest_formatter.py, line 13 - Dict could be TypedDict
def format_messages_for_llm(data: ServerDigestData) -> str:
    # Messages are dict but could be typed
    for msg in channel.messages:  # msg is dict[str, Any]
        timestamp = msg["timestamp"]  # No type safety here
```

**Recommendations:**

```python
# Define typed structures
from typing import TypedDict, NewType

class DiscordMessage(TypedDict):
    """Type definition for Discord message dict."""
    id: int
    author: str
    author_id: int
    content: str
    timestamp: str
    attachments: list[str]
    reactions: list[dict[str, Any]]

# Use NewType for semantic type safety
DigestMarkdown = NewType('DigestMarkdown', str)
ServerName = NewType('ServerName', str)
TimeRange = NewType('TimeRange', str)

# Update signatures
class LLMProvider(ABC):
    @abstractmethod
    def generate_digest(
        self,
        messages_text: str,
        server_name: ServerName,
        channel_count: int,
        message_count: int,
        time_range: TimeRange,
    ) -> DigestMarkdown:
        """Generate a digest from Discord messages."""
        pass

# Update data structures
@dataclass
class ChannelMessages:
    """Messages from a single channel."""
    channel_name: str
    channel_id: int
    messages: list[DiscordMessage]  # Now typed!
```

---

## MEDIUM Priority - Code Quality Issues

### CQ-MED-001: Hardcoded Configuration Values

**Files:** All files  
**Severity:** MEDIUM  
**Impact:** Flexibility, testability

**Issue:**
Configuration values are hardcoded throughout the codebase, making it difficult to:
- Test with different configurations
- Adjust behavior without code changes
- Deploy to different environments

**Examples:**
```python
# claude.py, lines 12-13
MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4096

# discord_client.py, line 80
async def _wait_until_ready(self, timeout: float = 30.0):

# digest.py, line 19
default=6,
```

**Recommendation:**
Centralize configuration in a config module as shown in REC-008.

---

### CQ-MED-002: Lack of Progress Feedback

**Files:** `discord_chat/services/discord_client.py`, `discord_chat/commands/digest.py`  
**Severity:** MEDIUM  
**Impact:** User experience

**Issue:**
Long-running operations provide minimal feedback. Users don't know:
- How many channels are being processed
- Progress percentage
- Estimated time remaining
- What's currently happening

**Recommendation:**
```python
# Add progress tracking
from rich.progress import Progress, SpinnerColumn, TextColumn

class DiscordMessageFetcher:
    
    async def fetch_server_messages(...) -> ServerDigestData:
        """Fetch with progress tracking."""
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True
        ) as progress:
            
            # Connection phase
            task_connect = progress.add_task(
                "Connecting to Discord...", 
                total=None
            )
            
            login_task = asyncio.create_task(...)
            await self._wait_until_ready()
            progress.update(task_connect, completed=True)
            
            # Channel discovery
            task_discover = progress.add_task(
                "Finding channels...", 
                total=None
            )
            guild = self._find_server_by_name(server_name)
            text_channels = [...]
            progress.update(task_discover, completed=True)
            
            # Message fetching
            task_fetch = progress.add_task(
                f"Fetching messages from {len(text_channels)} channels",
                total=len(text_channels)
            )
            
            channel_results = []
            for idx, channel in enumerate(text_channels):
                progress.update(
                    task_fetch,
                    advance=1,
                    description=f"Fetching #{channel.name} ({idx+1}/{len(text_channels)})"
                )
                result = await self._fetch_channel_messages(...)
                channel_results.append(result)
            
            # ... return results
```

---

### CQ-MED-003: Limited Test Coverage for Edge Cases

**Files:** `tests/test_digest.py`  
**Severity:** MEDIUM  
**Impact:** Reliability

**Issue:**
Test coverage focuses on happy paths but lacks edge case testing.

**Missing Test Scenarios:**
1. Very large message volumes
2. Unicode and emoji in messages
3. Malformed message data
4. Network interruptions during fetch
5. Partial failures (some channels fail)
6. Rate limiting scenarios
7. Concurrent access
8. Memory constraints

**Recommendation:**
```python
# Add to tests/test_digest.py

class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_unicode_handling(self):
        """Test handling of Unicode characters."""
        data = create_sample_data()
        data.channels[0].messages[0]["content"] = "Testing 你好 🎉 emoji"
        
        result = format_messages_for_llm(data)
        assert "你好" in result
        assert "🎉" in result
    
    def test_very_long_messages(self):
        """Test handling of very long messages."""
        data = create_sample_data()
        data.channels[0].messages[0]["content"] = "x" * 10000
        
        # Should not crash
        result = format_messages_for_llm(data)
        assert len(result) > 0
    
    def test_empty_message_content(self):
        """Test messages with only attachments."""
        data = create_sample_data()
        data.channels[0].messages[0]["content"] = ""
        data.channels[0].messages[0]["attachments"] = ["file.pdf"]
        
        result = format_messages_for_llm(data)
        assert "file.pdf" in result
    
    @pytest.mark.asyncio
    async def test_partial_channel_failure(self):
        """Test handling when some channels fail."""
        # Mock scenario where some channels raise exceptions
        # Verify partial results are returned
        pass
    
    def test_message_limit_enforcement(self):
        """Test that message limits are enforced."""
        # Create data with 10,000+ messages
        # Verify limit is respected
        pass
```

---

### CQ-MED-004: Inconsistent Naming Conventions

**Files:** Multiple  
**Severity:** LOW-MEDIUM  
**Impact:** Readability

**Issue:**
Some naming is inconsistent with Python conventions:

```python
# Good: snake_case for functions/variables
def format_messages_for_llm(data: ServerDigestData) -> str:

# Good: PascalCase for classes
class DiscordMessageFetcher:

# Inconsistent: Some internal methods use leading underscore, others don't
def _find_server_by_name(self, server_name: str) -> discord.Guild:  # Private
async def on_ready():  # Public but looks private (no self)

# Constants should be UPPER_CASE
MODEL = "claude-sonnet-4-20250514"  # Good
MAX_TOKENS = 4096  # Good
```

**Recommendation:**
Establish and document naming conventions in CONTRIBUTING.md.

---

### CQ-MED-005: No Validation of LLM Response Format

**Files:** LLM provider files  
**Severity:** MEDIUM  
**Impact:** Reliability

**Issue:**
LLM responses are assumed to be valid Markdown but there's no validation or sanitization.

**Recommendation:**
```python
def _validate_llm_response(self, response: str) -> str:
    """Validate and sanitize LLM response.
    
    Args:
        response: Raw response from LLM.
        
    Returns:
        Validated response.
        
    Raises:
        LLMError: If response is invalid.
    """
    if not response or not response.strip():
        raise LLMError("Empty response from LLM")
    
    # Check for reasonable length
    if len(response) < 10:
        raise LLMError("Response too short to be valid digest")
    
    if len(response) > 1_000_000:  # 1MB
        raise LLMError("Response suspiciously large")
    
    # Sanitize potentially dangerous content
    # (though Markdown is generally safe)
    
    return response.strip()
```

---

## LOW Priority - Style and Best Practices

### CQ-LOW-001: Missing Module-Level Docstrings

**Files:** `__init__.py` files  
**Severity:** LOW

Some `__init__.py` files lack module-level documentation.

**Recommendation:**
```python
# discord_chat/services/__init__.py
"""Service layer for external API integrations.

This module provides:
- Discord API client for message fetching
- LLM provider abstraction
"""

# discord_chat/commands/__init__.py
"""CLI command implementations.

All Click commands should be registered here.
"""
```

---

### CQ-LOW-002: Inconsistent String Formatting

**Files:** Multiple  
**Severity:** LOW

Mix of f-strings, .format(), and % formatting.

**Examples:**
```python
# Good: f-strings (modern, readable)
f"Server '{server_name}' not found."

# Inconsistent: .format() in some places
"Available servers: {}".format(', '.join(available_servers))
```

**Recommendation:**
Standardize on f-strings throughout (except for logging where lazy evaluation is needed).

---

### CQ-LOW-003: Magic Numbers

**Files:** Multiple  
**Severity:** LOW

Some magic numbers should be named constants.

**Examples:**
```python
# digest_formatter.py, line 14
timestamp = msg["timestamp"][:16]  # Why 16?

# discord_client.py, line 80
async def _wait_until_ready(self, timeout: float = 30.0):  # Why 30?
```

**Recommendation:**
```python
# Constants at module level
TIMESTAMP_MINUTE_PRECISION = 16  # "YYYY-MM-DDTHH:MM"
DEFAULT_READY_TIMEOUT_SECONDS = 30.0
DEFAULT_OPERATION_TIMEOUT_SECONDS = 300.0

# Usage
timestamp = msg["timestamp"][:TIMESTAMP_MINUTE_PRECISION]
```

---

### CQ-LOW-004: Could Use More Context Managers

**Files:** LLM provider files  
**Severity:** LOW

API clients could use context managers for resource management.

**Recommendation:**
```python
class ClaudeProvider(LLMProvider):
    """LLM provider using Anthropic's Claude API."""
    
    def __enter__(self):
        """Set up provider resources."""
        api_key = os.environ.get(self.required_env_var)
        self._client = anthropic.Anthropic(api_key=api_key)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up resources."""
        if hasattr(self, '_client'):
            # Close any open connections
            pass
    
    def generate_digest(...) -> str:
        """Generate using context-managed client."""
        if not hasattr(self, '_client'):
            raise LLMError("Provider not initialized. Use 'with' statement.")
        # ... use self._client ...

# Usage
with ClaudeProvider() as provider:
    digest = provider.generate_digest(...)
```

---

## Summary

### Issue Distribution

| Category | Critical | High | Medium | Low | Total |
|----------|----------|------|--------|-----|-------|
| **Error Handling** | 0 | 1 | 0 | 0 | 1 |
| **Resource Management** | 0 | 1 | 0 | 0 | 1 |
| **Reliability** | 0 | 1 | 2 | 0 | 3 |
| **Type Safety** | 0 | 1 | 0 | 0 | 1 |
| **Configuration** | 0 | 0 | 1 | 0 | 1 |
| **Testing** | 0 | 0 | 1 | 0 | 1 |
| **Style** | 0 | 0 | 0 | 4 | 4 |
| **Total** | 0 | 4 | 5 | 4 | 13 |

### Recommended Actions

1. **Immediate** (HIGH): Implement consistent error handling and retry logic
2. **Short-term** (MEDIUM): Add progress feedback and configuration management  
3. **Long-term** (LOW): Address style inconsistencies and add context managers

All issues have concrete, actionable recommendations with code examples.
