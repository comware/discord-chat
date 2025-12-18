"""OpenAI LLM provider implementation."""

import os

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
        try:
            import openai
        except ImportError:
            raise LLMError("openai package not installed. Run: pip install openai")

        api_key = os.environ.get(self.required_env_var)
        if not api_key:
            raise LLMError(f"API key not found. Set {self.required_env_var} environment variable.")

        client = openai.OpenAI(api_key=api_key)

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
                    return content

            raise LLMError("Empty response from OpenAI API")

        except openai.APIError as e:
            raise LLMError(f"OpenAI API error: {e}")
        except Exception as e:
            raise LLMError(f"Error generating digest with OpenAI: {e}")
