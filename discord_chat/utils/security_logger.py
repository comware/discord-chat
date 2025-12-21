"""Security-focused logging utilities.

This module provides security logging capabilities to track authentication,
API usage, and security events for audit and incident response purposes.
"""

import json
import logging
import os
from datetime import UTC, datetime
from enum import Enum
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


class SecurityEventType(Enum):
    """Types of security events to log."""

    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"
    API_CALL = "api_call"
    RATE_LIMIT = "rate_limit"
    INPUT_VALIDATION_FAILED = "input_validation_failed"
    FILE_OPERATION = "file_operation"
    ERROR = "error"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"


class SecurityLogger:
    """Security-focused logger with structured JSON output."""

    def __init__(self, log_file: str | None = None):
        """Initialize security logger.

        Args:
            log_file: Optional path to log file. Defaults to ./security.log
        """
        self.logger = logging.getLogger("discord_chat.security")
        self.logger.setLevel(logging.INFO)
        # Don't propagate to root logger (we have our own handlers)
        self.logger.propagate = False

        # Avoid adding handlers multiple times
        if not self.logger.handlers:
            # Console handler for errors
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.ERROR)
            console_formatter = logging.Formatter(
                "%(asctime)s - SECURITY - %(levelname)s - %(message)s"
            )
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)

            # File handler for all security events with rotation (HIGH-005 fix)
            if log_file is None:
                log_file = os.environ.get("DISCORD_CHAT_SECURITY_LOG", "security.log")

            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            # Use RotatingFileHandler to prevent disk exhaustion
            # Max 10MB per file, keep 5 backup files (50MB total max)
            file_handler = RotatingFileHandler(
                log_path,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,  # Keep 5 old logs
                encoding="utf-8",
            )
            file_handler.setLevel(logging.INFO)
            self.logger.addHandler(file_handler)

    def log_event(
        self,
        event_type: SecurityEventType,
        message: str,
        details: dict[str, Any] | None = None,
        level: int = logging.INFO,
    ) -> None:
        """Log a security event with structured data.

        Args:
            event_type: Type of security event.
            message: Human-readable event description.
            details: Additional event details (will be sanitized).
            level: Logging level (default: INFO).
        """
        # Create structured log entry
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": event_type.value,
            "message": message,
        }

        # Add sanitized details
        if details:
            log_entry["details"] = self._sanitize_details(details)

        # Log as JSON for easy parsing
        self.logger.log(level, json.dumps(log_entry))

    def log_auth_attempt(self, success: bool, service: str, reason: str | None = None) -> None:
        """Log authentication attempt.

        Args:
            success: Whether authentication succeeded.
            service: Service being authenticated to (Discord, Claude, OpenAI).
            reason: Optional failure reason.
        """
        event_type = SecurityEventType.AUTH_SUCCESS if success else SecurityEventType.AUTH_FAILURE
        message = f"{service} authentication {'succeeded' if success else 'failed'}"
        details = {"service": service}
        if reason:
            details["reason"] = reason

        level = logging.INFO if success else logging.WARNING
        self.log_event(event_type, message, details, level)

    def log_api_call(
        self,
        service: str,
        operation: str,
        duration_ms: float | None = None,
        success: bool = True,
    ) -> None:
        """Log API call for monitoring.

        Args:
            service: Service being called (Discord, Claude, OpenAI).
            operation: Operation being performed.
            duration_ms: Optional call duration in milliseconds.
            success: Whether the call succeeded.
        """
        message = f"{service} API call: {operation}"
        details = {
            "service": service,
            "operation": operation,
            "success": success,
        }
        if duration_ms is not None:
            details["duration_ms"] = duration_ms

        self.log_event(SecurityEventType.API_CALL, message, details)

    def log_rate_limit(self, service: str, concurrent_limit: int) -> None:
        """Log rate limiting enforcement.

        Args:
            service: Service being rate limited.
            concurrent_limit: Concurrent request limit applied.
        """
        message = f"Rate limiting applied to {service}"
        details = {"service": service, "concurrent_limit": concurrent_limit}
        self.log_event(SecurityEventType.RATE_LIMIT, message, details)

    def log_input_validation_failure(self, input_type: str, value: str, reason: str) -> None:
        """Log input validation failure (potential attack).

        Args:
            input_type: Type of input being validated (server_name, hours, etc).
            value: The invalid value (will be truncated if too long).
            reason: Reason for validation failure.
        """
        message = f"Input validation failed for {input_type}"
        # Truncate value to prevent log injection
        safe_value = value[:100] if len(value) > 100 else value
        details = {"input_type": input_type, "value": safe_value, "reason": reason}
        self.log_event(SecurityEventType.INPUT_VALIDATION_FAILED, message, details, logging.WARNING)

    def log_file_operation(self, operation: str, path: str, permissions: str | None = None) -> None:
        """Log file operation for audit trail.

        Args:
            operation: Operation type (create, write, read, delete).
            path: File path (will be sanitized to remove sensitive parts).
            permissions: Optional file permissions set.
        """
        message = f"File {operation}: {Path(path).name}"
        details = {"operation": operation, "filename": Path(path).name}
        if permissions:
            details["permissions"] = permissions

        self.log_event(SecurityEventType.FILE_OPERATION, message, details)

    def log_error(self, error_type: str, message: str, sanitized_details: dict[str, Any]) -> None:
        """Log security-relevant error.

        Args:
            error_type: Type of error.
            message: Error message (should be pre-sanitized).
            sanitized_details: Error details (must not contain sensitive info).
        """
        details = {"error_type": error_type, **sanitized_details}
        self.log_event(SecurityEventType.ERROR, message, details, logging.ERROR)

    @staticmethod
    def _sanitize_details(details: dict[str, Any]) -> dict[str, Any]:
        """Remove sensitive information from log details.

        Args:
            details: Raw details dictionary.

        Returns:
            Sanitized details safe for logging.
        """
        sanitized = {}
        sensitive_keys = {
            "token",
            "api_key",
            "password",
            "secret",
            "credential",
            "auth",
        }

        for key, value in details.items():
            # Check if key contains sensitive term
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = "[REDACTED]"
            # Truncate very long strings
            elif isinstance(value, str) and len(value) > 500:
                sanitized[key] = value[:500] + "...[truncated]"
            else:
                sanitized[key] = value

        return sanitized


# Global security logger instance
_security_logger: SecurityLogger | None = None


def get_security_logger() -> SecurityLogger:
    """Get or create the global security logger instance.

    Returns:
        SecurityLogger instance.
    """
    global _security_logger
    if _security_logger is None:
        _security_logger = SecurityLogger()
    return _security_logger
