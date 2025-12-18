"""Claude (Anthropic) LLM provider implementation."""

import os

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
        try:
            import anthropic
        except ImportError:
            raise LLMError("anthropic package not installed. Run: pip install anthropic")

        api_key = os.environ.get(self.required_env_var)
        if not api_key:
            raise LLMError(f"API key not found. Set {self.required_env_var} environment variable.")

        client = anthropic.Anthropic(api_key=api_key)

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
                return response.content[0].text

            raise LLMError("Empty response from Claude API")

        except anthropic.APIError as e:
            raise LLMError(f"Claude API error: {e}")
        except Exception as e:
            raise LLMError(f"Error generating digest with Claude: {e}")
