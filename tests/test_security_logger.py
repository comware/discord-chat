"""Tests for the security logger."""

import logging
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

import discord_chat.utils.security_logger as security_module
from discord_chat.utils.security_logger import (
    SecurityEventType,
    SecurityLogger,
    get_security_logger,
)


@pytest.fixture(autouse=True)
def reset_security_logger():
    """Reset global security logger before each test."""
    security_module._security_logger = None
    yield
    security_module._security_logger = None


class TestSecurityEventType:
    """Tests for SecurityEventType enum."""

    def test_event_types_exist(self):
        """Test that all expected event types exist."""
        assert SecurityEventType.AUTH_SUCCESS.value == "auth_success"
        assert SecurityEventType.AUTH_FAILURE.value == "auth_failure"
        assert SecurityEventType.API_CALL.value == "api_call"
        assert SecurityEventType.RATE_LIMIT.value == "rate_limit"
        assert SecurityEventType.INPUT_VALIDATION_FAILED.value == "input_validation_failed"
        assert SecurityEventType.FILE_OPERATION.value == "file_operation"
        assert SecurityEventType.ERROR.value == "error"
        assert SecurityEventType.SUSPICIOUS_ACTIVITY.value == "suspicious_activity"


class TestSecurityLogger:
    """Tests for SecurityLogger class."""

    def test_propagate_is_false(self):
        """Test that logger does not propagate to root logger."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test_security.log"
            # Clear any existing handlers from previous tests
            test_logger = logging.getLogger("discord_chat.security")
            test_logger.handlers.clear()

            logger = SecurityLogger(str(log_file))
            assert logger.logger.propagate is False

    def test_sanitize_details_redacts_sensitive_keys(self):
        """Test that sensitive keys are redacted."""
        details = {
            "api_key": "secret123",
            "token": "mytoken",
            "password": "hunter2",
            "normal_key": "visible",
        }

        sanitized = SecurityLogger._sanitize_details(details)

        assert sanitized["api_key"] == "[REDACTED]"
        assert sanitized["token"] == "[REDACTED]"
        assert sanitized["password"] == "[REDACTED]"
        assert sanitized["normal_key"] == "visible"

    def test_sanitize_details_truncates_long_strings(self):
        """Test that long string values are truncated."""
        details = {"content": "x" * 600}

        sanitized = SecurityLogger._sanitize_details(details)

        assert len(sanitized["content"]) == 500 + len("...[truncated]")
        assert sanitized["content"].endswith("...[truncated]")


class TestGetSecurityLogger:
    """Tests for get_security_logger function."""

    def test_returns_singleton(self):
        """Test that get_security_logger returns the same instance."""
        # Clear handlers from previous tests
        test_logger = logging.getLogger("discord_chat.security")
        test_logger.handlers.clear()

        with patch.dict("os.environ", {"DISCORD_CHAT_SECURITY_LOG": "/tmp/test_security.log"}):
            logger1 = get_security_logger()
            logger2 = get_security_logger()

            assert logger1 is logger2
