# Threat Model - discord-chat CLI

## Overview

This document identifies potential threats, attack vectors, and security risks for the discord-chat CLI application.

---

## System Architecture

```
┌─────────────────────────────────────────────────────┐
│                   User Environment                   │
│  ┌──────────────────────────────────────────────┐  │
│  │           discord-chat CLI                    │  │
│  │  ┌────────────┐  ┌──────────────┐           │  │
│  │  │  Commands  │  │   Services   │           │  │
│  │  │  - digest  │──│  - Discord   │           │  │
│  │  │  - version │  │  - LLM       │           │  │
│  │  └────────────┘  └──────────────┘           │  │
│  └────────┬──────────────────┬──────────────────┘  │
│           │                  │                      │
│  ┌────────▼────────┐ ┌──────▼──────────┐          │
│  │  Environment    │ │  File System    │          │
│  │  Variables      │ │  (Digests)      │          │
│  │  - Bot Token    │ │                 │          │
│  │  - API Keys     │ │                 │          │
│  └─────────────────┘ └─────────────────┘          │
└─────────────┬──────────────────┬──────────────────┘
              │                  │
              │                  │
    ┌─────────▼─────────┐ ┌─────▼──────────┐
    │  Discord API      │ │  LLM APIs      │
    │  - Bot Gateway    │ │  - Anthropic   │
    │  - Message Fetch  │ │  - OpenAI      │
    └───────────────────┘ └────────────────┘
```

---

## Assets & Trust Boundaries

### Critical Assets

1. **Credentials**
   - Discord bot tokens
   - Anthropic API keys
   - OpenAI API keys
   - Trust Level: CRITICAL

2. **User Data**
   - Discord messages (may contain PII, sensitive discussions)
   - Server metadata (names, member info)
   - Trust Level: HIGH

3. **Generated Digests**
   - Summarized conversations
   - May contain business-sensitive information
   - Trust Level: HIGH

4. **Application Code**
   - CLI logic
   - API integrations
   - Trust Level: MEDIUM

### Trust Boundaries

```
┌────────────────────────────────────────────┐
│  Trusted: User's Local Environment         │
│  - CLI application                         │
│  - Environment variables                   │
│  - File system                             │
└──────────────┬─────────────────────────────┘
               │ Network Boundary
               │ (TLS/HTTPS)
┌──────────────▼─────────────────────────────┐
│  Untrusted: External Services              │
│  - Discord API (third-party)               │
│  - LLM APIs (third-party)                  │
│  - DNS/Network infrastructure              │
└────────────────────────────────────────────┘
```

---

## Threat Actors

### 1. External Attacker (High Capability)
**Motivation:** Financial gain, data theft, disruption  
**Capabilities:** Network attacks, API exploitation, social engineering  
**Access:** None initially, seeks unauthorized access

### 2. Malicious Insider (Medium-High Capability)
**Motivation:** Data exfiltration, sabotage  
**Capabilities:** Has system access, knows codebase  
**Access:** Authorized user access

### 3. Compromised User Account (Medium Capability)
**Motivation:** Varies based on attacker  
**Capabilities:** User-level access to system  
**Access:** User's credentials and permissions

### 4. Opportunistic Attacker (Low-Medium Capability)
**Motivation:** Opportunistic data theft  
**Capabilities:** Automated scanning, known exploits  
**Access:** None, seeks easy targets

---

## Attack Trees

### Attack Goal: Steal Discord Bot Token

```
                    [Steal Bot Token]
                           |
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   [Extract from        [Man-in-       [Social
    Process]           the-Middle]     Engineering]
        │                  │                  │
    ┌───┴───┐          [Intercept          [Phish
    │       │           TLS]                User]
[ps/top] [Memory      (Unlikely -
 Dump]     Dump]      TLS enabled)

Likelihood: MEDIUM (ps/top), LOW (others)
Impact: CRITICAL
Risk Score: HIGH
```

### Attack Goal: Inject Malicious Server Name

```
              [Execute Path Traversal]
                       |
        ┌──────────────┼──────────────┐
        │              │              │
  [Overwrite     [Read Sensitive  [Command
   Files]          Files]         Injection]
        │              │              │
  [../../../    [../../../../     [;rm -rf
   config]        etc/passwd]       /tmp/*]

Likelihood: MEDIUM (current code)
Impact: HIGH
Risk Score: HIGH
```

### Attack Goal: Cause Financial Damage via API Abuse

```
                [Exhaust API Quotas]
                        |
            ┌───────────┼───────────┐
            │           │           │
       [Spam Large   [Long Time  [Many
        Servers]      Ranges]    Concurrent
            │           │         Requests]
            │           │           │
        [No Rate    [No Input  [No Concurrent
         Limit]      Validation] Limit]

Likelihood: HIGH (no controls)
Impact: MEDIUM (financial)
Risk Score: MEDIUM-HIGH
```

---

## STRIDE Analysis

### Spoofing

| Threat | Attack Vector | Current Control | Risk | Mitigation |
|--------|--------------|-----------------|------|------------|
| **Fake Discord Bot** | Attacker creates bot with similar name | None | MEDIUM | Bot verification, unique identifiers |
| **API Key Spoofing** | Stolen key used by attacker | Environment variables only | HIGH | Key rotation, usage monitoring |

### Tampering

| Threat | Attack Vector | Current Control | Risk | Mitigation |
|--------|--------------|-----------------|------|------------|
| **Message Modification** | Attacker modifies fetched messages before digest | None | MEDIUM | Message signing/verification |
| **Digest Tampering** | Attacker modifies output file | File permissions (default) | MEDIUM-HIGH | Secure file permissions (0600) |
| **Code Injection via Server Name** | Malicious server name | Basic sanitization | HIGH | Comprehensive input validation |

### Repudiation

| Threat | Attack Vector | Current Control | Risk | Mitigation |
|--------|--------------|-----------------|------|------------|
| **Deny API Usage** | User denies running commands | No audit logging | MEDIUM | Implement audit logs |
| **Deny Data Access** | User denies accessing messages | No access logs | MEDIUM | Log all Discord API calls |

### Information Disclosure

| Threat | Attack Vector | Current Control | Risk | Mitigation |
|--------|--------------|-----------------|------|------------|
| **Token in Process List** | `ps aux` shows token | Token in constructor param | CRITICAL | Force environment variables |
| **Token in Error Messages** | Exception includes token | Generic error handling | HIGH | Sanitize all error messages |
| **Sensitive Data in Logs** | Logs contain PII | No logging controls | HIGH | Implement log sanitization |
| **Digest File Exposure** | World-readable output | Default permissions | MEDIUM-HIGH | Set 0600 permissions |
| **Memory Dump** | Core dump contains credentials | Plain text in memory | MEDIUM | Secure memory, clear after use |

### Denial of Service

| Threat | Attack Vector | Current Control | Risk | Mitigation |
|--------|--------------|-----------------|------|------------|
| **API Rate Limit Exhaustion** | Fetch too many messages | None | HIGH | Implement rate limiting |
| **Resource Exhaustion** | Very large time ranges | None | MEDIUM | Add input validation |
| **Hung Process** | No operation timeout | Partial (30s ready timeout) | MEDIUM | Add overall timeout |
| **Concurrent Request DoS** | Multiple parallel fetches | None | MEDIUM | Add concurrency limits |

### Elevation of Privilege

| Threat | Attack Vector | Current Control | Risk | Mitigation |
|--------|--------------|-----------------|------|------------|
| **Path Traversal** | Malicious output path | Basic sanitization | HIGH | Comprehensive path validation |
| **File System Access** | Write to arbitrary locations | Path joining | MEDIUM-HIGH | Validate final paths |

---

## Attack Scenarios

### Scenario 1: Credential Theft via Process Listing

**Attacker Goal:** Steal Discord bot token  
**Attack Steps:**
1. Attacker gains user-level access to system (malware, compromised account)
2. Runs `ps aux | grep discord-chat`
3. If token passed as CLI arg, sees full token in process list
4. Uses token to access Discord as bot

**Current Vulnerability:** Token can be passed as constructor parameter  
**Likelihood:** MEDIUM (requires system access)  
**Impact:** CRITICAL (full bot compromise)  
**Risk Score:** HIGH

**Mitigation:**
- Remove token parameter from constructor (REC-001)
- Force environment variable usage
- Implement token rotation

---

### Scenario 2: Path Traversal Attack

**Attacker Goal:** Overwrite system files or read sensitive data  
**Attack Steps:**
1. Attacker runs: `discord-chat digest "../../../etc/passwd" -o /tmp`
2. Sanitization is incomplete, allowing traversal
3. Output file writes to unintended location
4. System files corrupted or sensitive data exposed

**Current Vulnerability:** Incomplete input validation  
**Likelihood:** MEDIUM (requires CLI access)  
**Impact:** HIGH (file system compromise)  
**Risk Score:** HIGH

**Mitigation:**
- Implement comprehensive input validation (REC-002)
- Validate final paths resolve within intended directory
- Reject all path separators in server names

---

### Scenario 3: API Cost Exploitation

**Attacker Goal:** Cause financial damage via excessive LLM API usage  
**Attack Steps:**
1. Attacker gains access to user's credentials
2. Runs commands with very large time ranges: `--hours 720`
3. Fetches hundreds of thousands of messages
4. Sends massive payloads to LLM API
5. Racks up thousands in API costs

**Current Vulnerability:** No rate limiting or cost controls  
**Likelihood:** MEDIUM (requires credential access)  
**Impact:** MEDIUM (financial damage)  
**Risk Score:** MEDIUM-HIGH

**Mitigation:**
- Implement rate limiting (REC-003)
- Add message count limits
- Validate input ranges
- Add cost estimation and warnings

---

### Scenario 4: Information Disclosure via Digest Files

**Attacker Goal:** Access sensitive Discord conversations  
**Attack Steps:**
1. User generates digest on shared system
2. Digest file created with default permissions (0644)
3. Other users on system can read file
4. Sensitive business discussions or PII exposed

**Current Vulnerability:** No secure file permissions  
**Likelihood:** HIGH (on shared systems)  
**Impact:** MEDIUM-HIGH (data breach)  
**Risk Score:** HIGH

**Mitigation:**
- Set 0600 permissions on output files (REC-007)
- Warn users about sensitive data
- Consider encryption option

---

### Scenario 5: Man-in-the-Middle on API Calls

**Attacker Goal:** Intercept API credentials or data  
**Attack Steps:**
1. Attacker on same network or compromised router
2. Performs MITM attack on HTTPS connections
3. If TLS verification not enforced, accepts invalid cert
4. Intercepts API keys and message data

**Current Vulnerability:** No explicit TLS verification  
**Likelihood:** LOW (libraries default to verification)  
**Impact:** CRITICAL (credential theft)  
**Risk Score:** MEDIUM

**Mitigation:**
- Explicitly enable TLS verification (MED-005)
- Pin certificates where possible
- Implement certificate validation

---

### Scenario 6: Resource Exhaustion DoS

**Attacker Goal:** Cause application to hang or crash  
**Attack Steps:**
1. Attacker runs: `discord-chat digest "large-server" --hours 720`
2. Attempts to fetch millions of messages
3. No timeout on overall operation
4. Process hangs indefinitely, consuming resources
5. System becomes unresponsive

**Current Vulnerability:** No operation timeout or message limits  
**Likelihood:** MEDIUM  
**Impact:** MEDIUM (availability)  
**Risk Score:** MEDIUM

**Mitigation:**
- Add overall operation timeout (REC-006)
- Implement message limits (REC-003)
- Add progress indicators and cancellation

---

## Data Flow Threats

### Data Flow 1: Credential Loading

```
Environment Variables → CLI → Discord/LLM APIs
```

**Threats:**
- T1.1: Token logged during loading (INFO DISCLOSURE)
- T1.2: Token visible in error messages (INFO DISCLOSURE)
- T1.3: Token stored in memory dumps (INFO DISCLOSURE)

**Controls:**
- Use environment variables only
- Sanitize all error messages
- Clear sensitive data after use

---

### Data Flow 2: Message Fetching

```
Discord API → CLI → LLM API → File System
```

**Threats:**
- T2.1: Messages intercepted in transit (INFO DISCLOSURE) - Mitigated by TLS
- T2.2: Excessive messages fetched (DOS)
- T2.3: Messages modified before digest (TAMPERING)
- T2.4: Sensitive messages in digest file (INFO DISCLOSURE)

**Controls:**
- Enforce TLS verification
- Implement rate limiting
- Set secure file permissions
- Warn about sensitive data

---

### Data Flow 3: Digest Generation

```
Messages → LLM → Digest → File System
```

**Threats:**
- T3.1: LLM API costs exploited (DOS/Financial)
- T3.2: Digest file world-readable (INFO DISCLOSURE)
- T3.3: Digest contains injection attacks (TAMPERING)

**Controls:**
- Implement cost controls
- Secure file permissions
- Validate LLM responses

---

## Risk Matrix

| Threat ID | Threat | Likelihood | Impact | Risk | Status |
|-----------|--------|------------|--------|------|--------|
| T-001 | Token exposure via process list | MEDIUM | CRITICAL | HIGH | OPEN |
| T-002 | Path traversal attack | MEDIUM | HIGH | HIGH | OPEN |
| T-003 | API cost exploitation | MEDIUM | MEDIUM | MED-HIGH | OPEN |
| T-004 | Digest file exposure | HIGH | MED-HIGH | HIGH | OPEN |
| T-005 | Man-in-the-middle on APIs | LOW | CRITICAL | MEDIUM | OPEN |
| T-006 | Resource exhaustion DoS | MEDIUM | MEDIUM | MEDIUM | OPEN |
| T-007 | Insufficient audit trail | HIGH | MEDIUM | MED-HIGH | OPEN |
| T-008 | Error message info disclosure | MEDIUM | MEDIUM | MEDIUM | OPEN |
| T-009 | Lack of input validation | HIGH | HIGH | HIGH | OPEN |
| T-010 | No rate limiting | HIGH | MEDIUM | MED-HIGH | OPEN |

---

## Security Controls Summary

| Control Type | Current State | Recommended |
|--------------|---------------|-------------|
| **Authentication** | Environment variables | ✅ Keep, add validation |
| **Authorization** | None (Discord bot permissions) | Document required perms |
| **Input Validation** | Partial | ❌ Need comprehensive validation |
| **Output Encoding** | Basic sanitization | ⚠️ Improve |
| **Cryptography** | TLS (via libraries) | ⚠️ Explicitly verify |
| **Error Handling** | Generic exceptions | ❌ Need sanitization |
| **Logging** | Minimal (print statements) | ❌ Need security logging |
| **Rate Limiting** | None | ❌ Critical need |
| **Timeout Controls** | Partial | ⚠️ Need overall timeout |
| **File Permissions** | Default | ❌ Need secure perms |

---

## Recommendations Priority

Based on threat model analysis:

### P0 - Critical (Within 24 Hours)
1. **Remove token parameter** (T-001)
2. **Implement input validation** (T-002, T-009)
3. **Add rate limiting** (T-003, T-010)

### P1 - High (Within 1 Week)
4. **Sanitize error messages** (T-008)
5. **Implement security logging** (T-007)
6. **Add operation timeouts** (T-006)
7. **Secure file permissions** (T-004)

### P2 - Medium (Within 2 Weeks)
8. **Explicit TLS verification** (T-005)
9. **Cost controls** (T-003)
10. **Validate LLM responses**

---

## Assumptions & Dependencies

### Assumptions
1. User's local environment is trusted
2. Discord and LLM APIs use valid TLS certificates
3. Users have legitimate access to Discord servers
4. Python runtime and dependencies are secure

### Dependencies
1. discord.py library security
2. anthropic/openai library security
3. Python runtime security
4. Operating system security
5. Network infrastructure security

### Out of Scope
- Discord server security
- LLM API security
- Supply chain attacks on dependencies
- Physical access to user's machine
- Social engineering attacks

---

## Review Schedule

This threat model should be reviewed:
- When new features are added
- After security incidents
- Quarterly (minimum)
- When threat landscape changes

**Next Review:** 2025-03-18
