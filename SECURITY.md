# Security Guidelines for Discord Chat CLI

## Overview

This document provides security guidelines for developers and users of the discord-chat CLI application. Following these guidelines will help maintain the security posture of the application.

## For Users

### Secure Setup

#### 1. Environment Variables (Required)

Never hardcode or pass credentials as command-line arguments. Always use environment variables:

```bash
# .env file (recommended)
DISCORD_BOT_TOKEN=your_discord_bot_token_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here  # For Claude
OPENAI_API_KEY=your_openai_api_key_here       # For OpenAI
```

**Important:**
- Never commit `.env` files to version control
- Set file permissions: `chmod 600 .env`
- Keep `.env` in `.gitignore`

#### 2. Discord Bot Token Security

**Obtaining a Secure Token:**
1. Visit https://discord.com/developers/applications
2. Create a new application or select existing
3. Go to "Bot" section → "Reset Token"
4. Copy token immediately (shown only once)
5. Store in `.env` file, never in code

**Token Best Practices:**
- Rotate tokens quarterly or after suspected compromise
- Use different tokens for dev/staging/production
- Enable 2FA on Discord developer account
- Limit bot permissions to minimum required

**Required Bot Permissions:**
- Read Messages/View Channels
- Read Message History
- View Server Insights (optional, for better context)

**Required Intents:**
- Message Content Intent (must be enabled in Discord Developer Portal)
- Server Members Intent
- Guild Intent

#### 3. API Key Management

**For Anthropic (Claude):**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."  # Starts with sk-ant-
```

**For OpenAI:**
```bash
export OPENAI_API_KEY="sk-..."  # Starts with sk-
```

**Best Practices:**
- Use project-specific API keys (not account keys)
- Set spending limits in API dashboards
- Monitor usage regularly
- Rotate keys every 90 days

#### 4. File Security

**Digest Output Files:**
- Files are automatically created with `0600` permissions (owner read/write only)
- Store digest files in secure locations
- Be aware digests may contain sensitive Discord conversations
- Consider encrypting digest files for long-term storage

**Security Log:**
```bash
# Default location
./security.log

# Custom location (recommended for production)
export DISCORD_CHAT_SECURITY_LOG="/var/log/discord-chat/security.log"

# Ensure log directory has proper permissions
chmod 700 /var/log/discord-chat
```

### Safe Usage

#### Command Examples

✅ **Safe:**
```bash
# Good - credentials from environment
discord-chat digest "MyServer" --hours 6 --llm claude

# Good - reasonable time range
discord-chat digest "DevTeam" --hours 24
```

❌ **Unsafe:**
```bash
# BAD - Never pass tokens as arguments
discord-chat digest "MyServer" --token "my_secret_token"  # Blocked by design

# BAD - Excessive time range
discord-chat digest "MyServer" --hours 1000  # Rejected (max 168)

# BAD - Path traversal attempt
discord-chat digest "../../../etc/passwd"  # Blocked by validation
```

#### Input Validation

The application validates all inputs:
- Server names: Max 100 chars, no path traversal
- Hours: Min 1, Max 168 (1 week)
- Output paths: Validated for safety

Invalid inputs will be rejected with clear error messages and logged for security monitoring.

---

## For Developers

### Security Architecture

#### Defense Layers

1. **Input Validation** (First Line)
   - All user inputs validated before processing
   - Path traversal prevention
   - Range checks on numeric inputs

2. **Rate Limiting** (Resource Protection)
   - Max 5 concurrent Discord channel fetches
   - Prevents API quota exhaustion
   - Protects against cost overruns

3. **Credential Protection** (Data Security)
   - Environment variable only access
   - No command-line parameters
   - Token format validation

4. **Output Protection** (Data Confidentiality)
   - Secure file permissions (0600)
   - Safe filename generation
   - Path validation

5. **Error Handling** (Information Security)
   - Sanitized error messages
   - No internal details exposed
   - Separate security logging

6. **Audit & Monitoring** (Detection)
   - Comprehensive security logging
   - Structured JSON output
   - Automatic sensitive data sanitization

### Coding Guidelines

#### 1. Input Validation

Always validate inputs before processing:

```python
from discord_chat.utils.digest_formatter import validate_server_name, InvalidServerNameError

# Validate server name
try:
    safe_name = validate_server_name(user_input)
except InvalidServerNameError as e:
    # Log the validation failure
    security_logger.log_input_validation_failure("server_name", user_input, str(e))
    raise
```

#### 2. Error Handling

Never expose internal details in exceptions:

```python
# ❌ BAD - Exposes internal information
except Exception as e:
    raise MyError(f"Failed: {e}")  # Might leak paths, API details

# ✅ GOOD - Sanitized error message
except SpecificAPIError as e:
    # Log detailed error internally
    security_logger.log_error("api_error", "API call failed", {
        "service": "ServiceName",
        "status": e.status_code if hasattr(e, "status_code") else "unknown"
    })
    # Show generic message to user
    raise MyError("Service unavailable. Please try again later.")
```

#### 3. Security Logging

Log all security-relevant events:

```python
from discord_chat.utils.security_logger import get_security_logger

security_logger = get_security_logger()

# Log authentication attempts
security_logger.log_auth_attempt(success=True, service="Discord")

# Log API calls with timing
start = time.time()
# ... make API call ...
duration_ms = (time.time() - start) * 1000
security_logger.log_api_call("Discord", "fetch_messages", duration_ms, success=True)

# Log input validation failures (potential attacks)
security_logger.log_input_validation_failure("parameter_name", value, reason)

# Log file operations
security_logger.log_file_operation("write", str(path), "0600")
```

#### 4. Rate Limiting

Implement rate limiting for all external API calls:

```python
import asyncio

# Create semaphore for rate limiting
MAX_CONCURRENT = 5
semaphore = asyncio.Semaphore(MAX_CONCURRENT)

async def rate_limited_operation(item):
    async with semaphore:
        return await perform_operation(item)

# Apply to all items
results = await asyncio.gather(*[rate_limited_operation(item) for item in items])
```

#### 5. Timeout Handling

Always set timeouts for operations:

```python
import asyncio

DEFAULT_TIMEOUT = 60.0  # seconds

try:
    result = await asyncio.wait_for(
        long_running_operation(),
        timeout=DEFAULT_TIMEOUT
    )
except TimeoutError:
    # Clean up resources
    await cleanup()
    raise OperationError(
        f"Operation timed out after {DEFAULT_TIMEOUT} seconds"
    )
```

#### 6. File Operations

Always use secure file operations:

```python
import os
import stat

def write_file_secure(path: Path, content: str) -> None:
    """Write file with secure permissions."""
    # Use os.open to set permissions atomically
    fd = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
        stat.S_IRUSR | stat.S_IWUSR  # 0600
    )
    try:
        os.write(fd, content.encode("utf-8"))
    finally:
        os.close(fd)
```

### Security Testing

#### Running Security Tests

```bash
# Run all tests including security tests
python -m pytest tests/ -v

# Run specific security test categories
python -m pytest tests/test_digest.py::TestServerNameValidation -v
python -m pytest tests/test_digest.py::TestHoursValidation -v
```

#### Adding Security Tests

When adding new features, include security tests:

```python
import pytest
from discord_chat.utils.digest_formatter import validate_server_name, InvalidServerNameError

class TestNewFeatureSecurity:
    def test_input_validation(self):
        """Test that invalid inputs are rejected."""
        with pytest.raises(InvalidServerNameError):
            validate_server_name("../../etc/passwd")

    def test_rate_limiting(self):
        """Test that rate limiting is enforced."""
        # Test rate limiting logic
        pass

    def test_timeout_handling(self):
        """Test that operations timeout correctly."""
        # Test timeout behavior
        pass
```

### Code Review Checklist

Before merging code, ensure:

- [ ] All user inputs are validated
- [ ] No credentials in code or logs
- [ ] Error messages are sanitized
- [ ] Rate limiting applied to external APIs
- [ ] Timeouts set for long operations
- [ ] Security events logged appropriately
- [ ] File operations use secure permissions
- [ ] Security tests added for new features
- [ ] No sensitive data in exception messages

### Security Constants

Current security limits (configurable in code):

```python
# discord_chat/services/discord_client.py
DEFAULT_TIMEOUT = 60.0              # Overall operation timeout
MAX_MESSAGES_PER_CHANNEL = 1000     # Prevent memory exhaustion
MAX_CONCURRENT_CHANNELS = 5         # Rate limiting

# discord_chat/commands/digest.py
MIN_HOURS = 1                       # Minimum time range
MAX_HOURS = 168                     # Maximum time range (1 week)

# discord_chat/utils/digest_formatter.py
MAX_SERVER_NAME_LENGTH = 100        # Maximum server name length
```

---

## Security Monitoring

### Log Analysis

Security logs are written in JSON format to `security.log` (or custom location):

```json
{
  "timestamp": "2024-12-19T14:23:45.123Z",
  "event_type": "auth_failure",
  "message": "Discord authentication failed",
  "details": {
    "service": "Discord",
    "reason": "Invalid token"
  }
}
```

### Key Events to Monitor

1. **Authentication Failures**
   - Alert on >5 failures in 10 minutes
   - Possible credential compromise

2. **Input Validation Failures**
   - Alert on >10 failures per hour
   - Possible attack attempt

3. **Rate Limit Hits**
   - Monitor frequency
   - May need limit adjustment

4. **API Call Failures**
   - Monitor error rates
   - Check for service issues

### SIEM Integration

Security logs can be ingested by:
- Splunk
- ELK Stack (Elasticsearch, Logstash, Kibana)
- AWS CloudWatch
- Azure Monitor
- Google Cloud Logging

Example Splunk query:
```
source="security.log" event_type="auth_failure"
| stats count by details.service
| where count > 5
```

---

## Incident Response

### If Credentials Are Compromised

1. **Immediate Actions:**
   ```bash
   # Rotate Discord bot token
   # 1. Go to Discord Developer Portal
   # 2. Reset token immediately
   # 3. Update .env file

   # Rotate API keys
   # Claude: Visit console.anthropic.com
   # OpenAI: Visit platform.openai.com
   ```

2. **Investigation:**
   - Check security logs for unauthorized access
   - Review recent API usage
   - Identify scope of compromise

3. **Prevention:**
   - Enable 2FA on all accounts
   - Review access permissions
   - Update security policies

### If Attack Detected

1. **Contain:**
   - Block suspicious IPs (if applicable)
   - Temporarily disable bot if necessary

2. **Investigate:**
   - Review security logs
   - Identify attack vector
   - Assess damage

3. **Recover:**
   - Apply patches/fixes
   - Restore from backups if needed
   - Monitor for persistence

4. **Learn:**
   - Update security measures
   - Add detection rules
   - Document incident

---

## Compliance

### GDPR Compliance

- ✅ Secure file permissions protect user data
- ✅ Audit logging for data access
- ✅ Data minimization (only fetch needed data)
- ✅ User control over data retention

### SOC 2 Compliance

- ✅ Access controls implemented
- ✅ Security monitoring and logging
- ✅ Audit trail for all operations
- ✅ Incident response procedures documented

### Best Practices

- Regular security audits (quarterly)
- Penetration testing (annually)
- Security training for team
- Keep dependencies updated

---

## Security Resources

### Documentation
- [SECURITY-FIXES-APPLIED.md](./SECURITY-FIXES-APPLIED.md) - Detailed fix documentation
- [security-review/](./security-review/) - Complete security audit

### External Resources
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Discord Security Best Practices](https://discord.com/developers/docs/topics/security)
- [Anthropic Security](https://www.anthropic.com/security)
- [OpenAI Security](https://platform.openai.com/docs/guides/safety-best-practices)

### Reporting Security Issues

If you discover a security vulnerability:

1. **Do NOT** open a public issue
2. Email: [security@your-domain.com]
3. Include:
   - Vulnerability description
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

**Response SLA:**
- Critical: 24 hours
- High: 72 hours
- Medium/Low: 1 week

---

## Changelog

### 2024-12-19 - Security Hardening Release
- ✅ Fixed all critical vulnerabilities (CRIT-001, CRIT-002, CRIT-003)
- ✅ Fixed all high severity vulnerabilities (HIGH-001, HIGH-002, HIGH-004)
- ✅ Implemented comprehensive security logging
- ✅ Added rate limiting and timeout handling
- ✅ Improved input validation and error handling
- ✅ Secure file permissions implemented

### Next Review
Scheduled for: Q2 2025 or after significant changes

---

**Last Updated:** December 19, 2024
**Security Score:** 85/100 (LOW RISK)
**Next Audit:** March 2025
