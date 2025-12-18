"""Base class for LLM providers."""

from abc import ABC, abstractmethod


class LLMError(Exception):
    """Base exception for LLM-related errors."""

    pass


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    All LLM providers must implement this interface to ensure
    consistent behavior across different providers.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider name."""
        pass

    @property
    @abstractmethod
    def required_env_var(self) -> str:
        """Return the required environment variable for API key."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is available (has required credentials)."""
        pass

    @abstractmethod
    def generate_digest(
        self,
        messages_text: str,
        server_name: str,
        channel_count: int,
        message_count: int,
        time_range: str,
    ) -> str:
        """Generate a digest from Discord messages.

        Args:
            messages_text: Formatted text of all messages to summarize.
            server_name: Name of the Discord server.
            channel_count: Number of channels included.
            message_count: Total number of messages.
            time_range: Human-readable time range string.

        Returns:
            Markdown-formatted digest string.

        Raises:
            LLMError: If there's an error generating the digest.
        """
        pass

    def _get_system_prompt(self) -> str:
        """Return the system prompt for digest generation."""
        return (
            "You are a helpful assistant that creates concise, well-organized "
            "digests of Discord server conversations.\n\n"
            "Your task is to analyze the provided Discord messages and create a "
            "comprehensive yet readable digest in Markdown format.\n\n"
            "Guidelines:\n"
            "1. Organize by themes/topics rather than by channel when possible\n"
            "2. Highlight important discussions, decisions, and announcements\n"
            "3. Note any questions that were asked but not answered\n"
            "4. Identify action items or follow-ups mentioned\n"
            "5. Keep the digest concise but informative\n"
            "6. Use bullet points and headers for readability\n"
            "7. Include relevant usernames when attributing specific statements\n"
            "8. If there are no messages or minimal activity, state that clearly\n\n"
            "Output format should be clean Markdown suitable for reading."
        )

    def _get_user_prompt(
        self,
        messages_text: str,
        server_name: str,
        channel_count: int,
        message_count: int,
        time_range: str,
    ) -> str:
        """Return the user prompt with message data."""
        return f"""Please create a digest for the Discord server "{server_name}".

Time period: {time_range}
Channels with activity: {channel_count}
Total messages: {message_count}

Here are the messages organized by channel:

{messages_text}

Please create a well-organized digest of this activity."""
