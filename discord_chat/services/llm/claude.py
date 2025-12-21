"""Claude (Anthropic) LLM provider implementation."""

import os
import time

from discord_chat.utils.security_logger import get_security_logger

from .base import LLMError, LLMProvider


class ClaudeProvider(LLMProvider):
    """LLM provider using Anthropic's Claude API."""

    MODEL = "claude-sonnet-4-20250514"
    MAX_TOKENS = 4096

    @property
    def name(self) -> str:
        return "Claude"

    @property
    def required_env_var(self) -> str:
        return "ANTHROPIC_API_KEY"

    def is_available(self) -> bool:
        return bool(os.environ.get(self.required_env_var))

    def generate_digest(
        self,
        messages_text: str,
        server_name: str,
        channel_count: int,
        message_count: int,
        time_range: str,
    ) -> str:
        """Generate a digest using Claude."""
        security_logger = get_security_logger()

        try:
            import anthropic
            import httpx
        except ImportError:
            raise LLMError(
                "anthropic and httpx packages required. Run: pip install anthropic httpx"
            )

        api_key = os.environ.get(self.required_env_var)
        if not api_key:
            security_logger.log_auth_attempt(False, "Claude", "API key not found")
            raise LLMError(f"API key not found. Set {self.required_env_var} environment variable.")

        # CRIT-006 fix: Ensure TLS certificate verification is enabled
        # Create client with explicit TLS verification
        http_client = httpx.Client(verify=True)
        client = anthropic.Anthropic(api_key=api_key, http_client=http_client)
        start_time = time.time()

        try:
            response = client.messages.create(
                model=self.MODEL,
                max_tokens=self.MAX_TOKENS,
                system=self._get_system_prompt(),
                messages=[
                    {
                        "role": "user",
                        "content": self._get_user_prompt(
                            messages_text,
                            server_name,
                            channel_count,
                            message_count,
                            time_range,
                        ),
                    }
                ],
            )

            # Extract text from response
            if response.content and len(response.content) > 0:
                duration_ms = (time.time() - start_time) * 1000
                security_logger.log_api_call("Claude", "generate_digest", duration_ms, True)
                security_logger.log_auth_attempt(True, "Claude")
                return response.content[0].text

            raise LLMError("Empty response from Claude API")

        except anthropic.AuthenticationError:
            duration_ms = (time.time() - start_time) * 1000
            security_logger.log_api_call("Claude", "generate_digest", duration_ms, False)
            security_logger.log_auth_attempt(False, "Claude", "Invalid API key")
            raise LLMError(
                "Claude authentication failed. Please verify your ANTHROPIC_API_KEY is valid."
            )
        except anthropic.RateLimitError:
            duration_ms = (time.time() - start_time) * 1000
            security_logger.log_api_call("Claude", "generate_digest", duration_ms, False)
            security_logger.log_error("rate_limit", "Claude API rate limit exceeded", {})
            raise LLMError("Claude API rate limit exceeded. Please wait a moment and try again.")
        except anthropic.APIConnectionError:
            duration_ms = (time.time() - start_time) * 1000
            security_logger.log_api_call("Claude", "generate_digest", duration_ms, False)
            security_logger.log_error("connection", "Failed to connect to Claude API", {})
            raise LLMError("Unable to connect to Claude API. Please check your network connection.")
        except anthropic.BadRequestError as e:
            duration_ms = (time.time() - start_time) * 1000
            security_logger.log_api_call("Claude", "generate_digest", duration_ms, False)
            security_logger.log_error("bad_request", "Invalid request to Claude API", {})
            # Check for content-related errors (too long, etc.)
            error_str = str(e).lower()
            if "token" in error_str or "length" in error_str or "too long" in error_str:
                raise LLMError(
                    "Message content too long for Claude API. "
                    "Try reducing the time range with --hours."
                )
            raise LLMError("Invalid request to Claude API. Please try again.")
        except anthropic.InternalServerError:
            duration_ms = (time.time() - start_time) * 1000
            security_logger.log_api_call("Claude", "generate_digest", duration_ms, False)
            security_logger.log_error("server_error", "Claude API server error", {})
            raise LLMError("Claude API is experiencing issues. Please try again in a few minutes.")
        except anthropic.APIError as e:
            duration_ms = (time.time() - start_time) * 1000
            security_logger.log_api_call("Claude", "generate_digest", duration_ms, False)
            if hasattr(e, "status_code") and e.status_code in (401, 403):
                security_logger.log_auth_attempt(False, "Claude", f"API error {e.status_code}")
            status = getattr(e, "status_code", "unknown")
            security_logger.log_error("api_error", f"Claude API error (status: {status})", {})
            raise LLMError("Claude API error occurred. Please try again.")
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            security_logger.log_api_call("Claude", "generate_digest", duration_ms, False)
            security_logger.log_error("unknown", f"Unexpected error: {type(e).__name__}", {})
            raise LLMError(
                "Failed to generate digest with Claude. "
                "Please verify your API key and network connection."
            )
