"""Security tests for LLM providers - ImportError handling and TLS verification.

These tests verify critical security features:
- MT-004: ImportError when anthropic package not installed
- MT-005: ImportError when openai package not installed
- MT-015: TLS certificate verification enabled for Claude
- MT-016: TLS certificate verification enabled for OpenAI
"""

import builtins
import logging
from unittest.mock import MagicMock, patch

import pytest

import discord_chat.utils.security_logger as security_module
from discord_chat.services.llm import LLMError

# Environment vars for tests requiring API keys
CLAUDE_ENV = {
    "ANTHROPIC_API_KEY": "test-key",
    "DISCORD_CHAT_SECURITY_LOG": "/tmp/test_sec.log",
}
OPENAI_ENV = {
    "OPENAI_API_KEY": "test-key",
    "DISCORD_CHAT_SECURITY_LOG": "/tmp/test_sec.log",
}


@pytest.fixture(autouse=True)
def reset_security_logger():
    """Reset global security logger before each test."""
    security_module._security_logger = None
    test_logger = logging.getLogger("discord_chat.security")
    test_logger.handlers.clear()
    yield
    security_module._security_logger = None


class TestImportErrorHandling:
    """Tests for missing package scenarios (MT-004, MT-005).

    These tests verify that users get clear error messages when
    required packages (anthropic, openai, httpx) are not installed.
    """

    def test_claude_missing_anthropic_package(self):
        """MT-004: Test error when anthropic package not installed.

        This tests the ImportError path in claude.py:42-43.
        """
        # Create a mock that raises ImportError
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "anthropic":
                raise ImportError("No module named 'anthropic'")
            return original_import(name, *args, **kwargs)

        # Need to reload the module to trigger the import
        with patch.dict("os.environ", CLAUDE_ENV):
            with patch.object(builtins, "__import__", mock_import):
                # Import fresh to trigger the error
                from discord_chat.services.llm.claude import ClaudeProvider

                provider = ClaudeProvider()

                with pytest.raises(LLMError) as exc_info:
                    provider.generate_digest("messages", "server", 1, 1, "time")

                error_msg = str(exc_info.value).lower()
                assert "anthropic" in error_msg
                assert "pip install" in error_msg or "required" in error_msg

    def test_claude_missing_httpx_package(self):
        """Test error when httpx package not installed for Claude."""
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "httpx":
                raise ImportError("No module named 'httpx'")
            return original_import(name, *args, **kwargs)

        with patch.dict("os.environ", CLAUDE_ENV):
            with patch.object(builtins, "__import__", mock_import):
                from discord_chat.services.llm.claude import ClaudeProvider

                provider = ClaudeProvider()

                with pytest.raises(LLMError) as exc_info:
                    provider.generate_digest("messages", "server", 1, 1, "time")

                error_msg = str(exc_info.value).lower()
                assert "httpx" in error_msg or "anthropic" in error_msg
                assert "pip install" in error_msg or "required" in error_msg

    def test_openai_missing_openai_package(self):
        """MT-005: Test error when openai package not installed.

        This tests the ImportError path in openai_provider.py:42-43.
        """
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "openai":
                raise ImportError("No module named 'openai'")
            return original_import(name, *args, **kwargs)

        with patch.dict("os.environ", OPENAI_ENV):
            with patch.object(builtins, "__import__", mock_import):
                from discord_chat.services.llm.openai_provider import OpenAIProvider

                provider = OpenAIProvider()

                with pytest.raises(LLMError) as exc_info:
                    provider.generate_digest("messages", "server", 1, 1, "time")

                error_msg = str(exc_info.value).lower()
                assert "openai" in error_msg
                assert "pip install" in error_msg or "required" in error_msg

    def test_openai_missing_httpx_package(self):
        """Test error when httpx package not installed for OpenAI."""
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "httpx":
                raise ImportError("No module named 'httpx'")
            return original_import(name, *args, **kwargs)

        with patch.dict("os.environ", OPENAI_ENV):
            with patch.object(builtins, "__import__", mock_import):
                from discord_chat.services.llm.openai_provider import OpenAIProvider

                provider = OpenAIProvider()

                with pytest.raises(LLMError) as exc_info:
                    provider.generate_digest("messages", "server", 1, 1, "time")

                error_msg = str(exc_info.value).lower()
                assert "httpx" in error_msg or "openai" in error_msg
                assert "pip install" in error_msg or "required" in error_msg


class TestTLSVerification:
    """Tests for TLS certificate verification (MT-015, MT-016).

    These tests verify CRIT-006 fix: TLS verification must be enabled
    for all API communications to prevent MITM attacks.
    """

    @patch.dict("os.environ", CLAUDE_ENV)
    @patch("anthropic.Anthropic")
    @patch("httpx.Client")
    def test_claude_tls_verification_enabled(self, mock_httpx_client, mock_anthropic):
        """MT-015: Test that Claude provider enables TLS verification.

        Verifies that httpx.Client is created with verify=True (CRIT-006 fix).
        """
        from discord_chat.services.llm.claude import ClaudeProvider

        # Setup mock response
        mock_content = MagicMock()
        mock_content.text = "Test digest"
        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_anthropic.return_value.messages.create.return_value = mock_response

        provider = ClaudeProvider()
        provider.generate_digest("messages", "server", 1, 1, "time")

        # Verify httpx.Client was called with verify=True
        mock_httpx_client.assert_called_once()
        call_kwargs = mock_httpx_client.call_args[1]
        assert call_kwargs.get("verify") is True, (
            "TLS verification not enabled for Claude! "
            "This is a security vulnerability (CRIT-006)."
        )

    @patch.dict("os.environ", OPENAI_ENV)
    @patch("openai.OpenAI")
    @patch("httpx.Client")
    def test_openai_tls_verification_enabled(self, mock_httpx_client, mock_openai):
        """MT-016: Test that OpenAI provider enables TLS verification.

        Verifies that httpx.Client is created with verify=True (CRIT-006 fix).
        """
        from discord_chat.services.llm.openai_provider import OpenAIProvider

        # Setup mock response
        mock_message = MagicMock()
        mock_message.content = "Test digest"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_openai.return_value.chat.completions.create.return_value = mock_response

        provider = OpenAIProvider()
        provider.generate_digest("messages", "server", 1, 1, "time")

        # Verify httpx.Client was called with verify=True
        mock_httpx_client.assert_called_once()
        call_kwargs = mock_httpx_client.call_args[1]
        assert call_kwargs.get("verify") is True, (
            "TLS verification not enabled for OpenAI! "
            "This is a security vulnerability (CRIT-006)."
        )

    @patch.dict("os.environ", CLAUDE_ENV)
    @patch("anthropic.Anthropic")
    @patch("httpx.Client")
    def test_claude_httpx_client_passed_to_anthropic(self, mock_httpx_client, mock_anthropic):
        """Test that custom httpx client is passed to Anthropic client."""
        from discord_chat.services.llm.claude import ClaudeProvider

        mock_http_instance = MagicMock()
        mock_httpx_client.return_value = mock_http_instance

        # Setup mock response
        mock_content = MagicMock()
        mock_content.text = "Test"
        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_anthropic.return_value.messages.create.return_value = mock_response

        provider = ClaudeProvider()
        provider.generate_digest("messages", "server", 1, 1, "time")

        # Verify Anthropic client was created with our httpx client
        mock_anthropic.assert_called_once()
        call_kwargs = mock_anthropic.call_args[1]
        assert call_kwargs.get("http_client") == mock_http_instance

    @patch.dict("os.environ", OPENAI_ENV)
    @patch("openai.OpenAI")
    @patch("httpx.Client")
    def test_openai_httpx_client_passed_to_openai(self, mock_httpx_client, mock_openai):
        """Test that custom httpx client is passed to OpenAI client."""
        from discord_chat.services.llm.openai_provider import OpenAIProvider

        mock_http_instance = MagicMock()
        mock_httpx_client.return_value = mock_http_instance

        # Setup mock response
        mock_message = MagicMock()
        mock_message.content = "Test"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_openai.return_value.chat.completions.create.return_value = mock_response

        provider = OpenAIProvider()
        provider.generate_digest("messages", "server", 1, 1, "time")

        # Verify OpenAI client was created with our httpx client
        mock_openai.assert_called_once()
        call_kwargs = mock_openai.call_args[1]
        assert call_kwargs.get("http_client") == mock_http_instance


class TestSecurityRegression:
    """Regression tests for security fixes.

    These tests ensure that security fixes remain in place after refactoring.
    """

    @patch.dict("os.environ", CLAUDE_ENV)
    @patch("anthropic.Anthropic")
    @patch("httpx.Client")
    def test_claude_does_not_disable_tls(self, mock_httpx_client, mock_anthropic):
        """Ensure Claude never creates client with verify=False."""
        from discord_chat.services.llm.claude import ClaudeProvider

        mock_content = MagicMock()
        mock_content.text = "Test"
        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_anthropic.return_value.messages.create.return_value = mock_response

        provider = ClaudeProvider()
        provider.generate_digest("messages", "server", 1, 1, "time")

        call_kwargs = mock_httpx_client.call_args[1]
        # Must be True, not False, not None, not missing
        assert call_kwargs.get("verify") is True
        assert call_kwargs.get("verify") is not False
        assert "verify" in call_kwargs

    @patch.dict("os.environ", OPENAI_ENV)
    @patch("openai.OpenAI")
    @patch("httpx.Client")
    def test_openai_does_not_disable_tls(self, mock_httpx_client, mock_openai):
        """Ensure OpenAI never creates client with verify=False."""
        from discord_chat.services.llm.openai_provider import OpenAIProvider

        mock_message = MagicMock()
        mock_message.content = "Test"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_openai.return_value.chat.completions.create.return_value = mock_response

        provider = OpenAIProvider()
        provider.generate_digest("messages", "server", 1, 1, "time")

        call_kwargs = mock_httpx_client.call_args[1]
        # Must be True, not False, not None, not missing
        assert call_kwargs.get("verify") is True
        assert call_kwargs.get("verify") is not False
        assert "verify" in call_kwargs
