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
            "1. Start with a '## Channel Activity Summary' section that lists each channel "
            "with a brief 1-2 sentence summary of what's happening there, helping readers "
            "understand which projects/topics are active\n"
            "2. Follow with a '## Key Highlights' section organized by themes/topics\n"
            "3. Highlight important discussions, decisions, and announcements\n"
            "4. Note any questions that were asked but not answered\n"
            "5. Identify action items or follow-ups mentioned\n"
            "6. Keep the digest concise but informative\n"
            "7. Use bullet points and headers for readability\n"
            "8. Include relevant usernames when attributing specific statements\n"
            "9. If there are no messages or minimal activity, state that clearly\n\n"
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
        """Return the user prompt with message data.

        Security: All user-controlled inputs are sanitized to prevent prompt injection.
        """
        # Sanitize server_name to prevent prompt injection attacks
        # Remove control characters and limit length
        safe_server_name = self._sanitize_for_llm(server_name)
        safe_time_range = self._sanitize_for_llm(time_range)

        # Limit messages_text to prevent excessive token usage
        max_message_length = 50000  # ~50KB max
        if len(messages_text) > max_message_length:
            truncate_notice = "\n\n[...messages truncated for length...]"
            messages_text = messages_text[:max_message_length] + truncate_notice

        return f"""Please create a digest for the Discord server "{safe_server_name}".

Time period: {safe_time_range}
Channels with activity: {channel_count}
Total messages: {message_count}

Here are the messages organized by channel:

{messages_text}

Please create a well-organized digest of this activity."""

    @staticmethod
    def _sanitize_for_llm(text: str) -> str:
        """Sanitize text to prevent prompt injection attacks.

        Args:
            text: Raw text from user input.

        Returns:
            Sanitized text safe for LLM prompts.
        """
        if not text:
            return ""

        # Remove control characters that could break prompt structure
        sanitized = text.replace("\n", " ").replace("\r", " ")
        sanitized = "".join(c for c in sanitized if c.isprintable() or c in " \t")

        # Limit length to prevent injection attacks
        max_length = 200
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]

        # Remove common prompt injection patterns
        dangerous_patterns = [
            "ignore previous",
            "ignore above",
            "ignore all",
            "disregard previous",
            "new instructions",
            "system:",
            "assistant:",
            "user:",
        ]

        sanitized_lower = sanitized.lower()
        for pattern in dangerous_patterns:
            if pattern in sanitized_lower:
                # Replace the dangerous pattern with a safe version
                sanitized = sanitized.replace(pattern, pattern.replace(" ", "_"))

        return sanitized
