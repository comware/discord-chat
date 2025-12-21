"""OpenAI LLM provider implementation."""

import os
import time

from discord_chat.utils.security_logger import get_security_logger

from .base import LLMError, LLMProvider


class OpenAIProvider(LLMProvider):
    """LLM provider using OpenAI's API."""

    MODEL = "gpt-4o"
    MAX_TOKENS = 4096

    @property
    def name(self) -> str:
        return "OpenAI"

    @property
    def required_env_var(self) -> str:
        return "OPENAI_API_KEY"

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
        """Generate a digest using OpenAI."""
        security_logger = get_security_logger()

        try:
            import httpx
            import openai
        except ImportError:
            raise LLMError("openai and httpx packages required. Run: pip install openai httpx")

        api_key = os.environ.get(self.required_env_var)
        if not api_key:
            security_logger.log_auth_attempt(False, "OpenAI", "API key not found")
            raise LLMError(f"API key not found. Set {self.required_env_var} environment variable.")

        # CRIT-006 fix: Ensure TLS certificate verification is enabled
        # Create client with explicit TLS verification
        http_client = httpx.Client(verify=True)
        client = openai.OpenAI(api_key=api_key, http_client=http_client)
        start_time = time.time()

        try:
            response = client.chat.completions.create(
                model=self.MODEL,
                max_tokens=self.MAX_TOKENS,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {
                        "role": "user",
                        "content": self._get_user_prompt(
                            messages_text,
                            server_name,
                            channel_count,
                            message_count,
                            time_range,
                        ),
                    },
                ],
            )

            # Extract text from response
            if response.choices and len(response.choices) > 0:
                content = response.choices[0].message.content
                if content:
                    duration_ms = (time.time() - start_time) * 1000
                    security_logger.log_api_call("OpenAI", "generate_digest", duration_ms, True)
                    security_logger.log_auth_attempt(True, "OpenAI")
                    return content

            raise LLMError("Empty response from OpenAI API")

        except openai.AuthenticationError:
            duration_ms = (time.time() - start_time) * 1000
            security_logger.log_api_call("OpenAI", "generate_digest", duration_ms, False)
            security_logger.log_auth_attempt(False, "OpenAI", "Invalid API key")
            raise LLMError(
                "OpenAI authentication failed. Please verify your OPENAI_API_KEY is valid."
            )
        except openai.RateLimitError:
            duration_ms = (time.time() - start_time) * 1000
            security_logger.log_api_call("OpenAI", "generate_digest", duration_ms, False)
            security_logger.log_error("rate_limit", "OpenAI API rate limit exceeded", {})
            raise LLMError("OpenAI API rate limit exceeded. Please wait a moment and try again.")
        except openai.APIConnectionError:
            duration_ms = (time.time() - start_time) * 1000
            security_logger.log_api_call("OpenAI", "generate_digest", duration_ms, False)
            security_logger.log_error("connection", "Failed to connect to OpenAI API", {})
            raise LLMError("Unable to connect to OpenAI API. Please check your network connection.")
        except openai.BadRequestError as e:
            duration_ms = (time.time() - start_time) * 1000
            security_logger.log_api_call("OpenAI", "generate_digest", duration_ms, False)
            security_logger.log_error("bad_request", "Invalid request to OpenAI API", {})
            error_str = str(e).lower()
            if "token" in error_str or "length" in error_str or "too long" in error_str:
                raise LLMError(
                    "Message content too long for OpenAI API. "
                    "Try reducing the time range with --hours."
                )
            raise LLMError("Invalid request to OpenAI API. Please try again.")
        except openai.InternalServerError:
            duration_ms = (time.time() - start_time) * 1000
            security_logger.log_api_call("OpenAI", "generate_digest", duration_ms, False)
            security_logger.log_error("server_error", "OpenAI API server error", {})
            raise LLMError("OpenAI API is experiencing issues. Please try again in a few minutes.")
        except openai.APIError as e:
            duration_ms = (time.time() - start_time) * 1000
            security_logger.log_api_call("OpenAI", "generate_digest", duration_ms, False)
            if hasattr(e, "status_code") and e.status_code in (401, 403):
                security_logger.log_auth_attempt(False, "OpenAI", f"API error {e.status_code}")
            status = getattr(e, "status_code", "unknown")
            security_logger.log_error("api_error", f"OpenAI API error (status: {status})", {})
            raise LLMError("OpenAI API error occurred. Please try again.")
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            security_logger.log_api_call("OpenAI", "generate_digest", duration_ms, False)
            security_logger.log_error("unknown", f"Unexpected error: {type(e).__name__}", {})
            raise LLMError(
                "Failed to generate digest with OpenAI. "
                "Please verify your API key and network connection."
            )
