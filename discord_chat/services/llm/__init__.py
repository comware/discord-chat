"""LLM service module with provider abstraction."""

from .base import LLMError, LLMProvider
from .claude import ClaudeProvider
from .openai_provider import OpenAIProvider

__all__ = ["LLMProvider", "LLMError", "ClaudeProvider", "OpenAIProvider", "get_provider"]

# Default provider preference order
PROVIDER_REGISTRY = {
    "claude": ClaudeProvider,
    "openai": OpenAIProvider,
}


def get_provider(provider_name: str | None = None) -> LLMProvider:
    """Get an LLM provider instance.

    Args:
        provider_name: Name of the provider ('claude' or 'openai').
                      If None, auto-selects based on available API keys.

    Returns:
        An initialized LLM provider instance.

    Raises:
        LLMError: If no provider is available or the specified provider is invalid.
    """
    if provider_name:
        provider_name = provider_name.lower()
        if provider_name not in PROVIDER_REGISTRY:
            available = ", ".join(PROVIDER_REGISTRY.keys())
            raise LLMError(f"Unknown provider '{provider_name}'. Available: {available}")

        provider_class = PROVIDER_REGISTRY[provider_name]
        provider = provider_class()
        if not provider.is_available():
            raise LLMError(
                f"Provider '{provider_name}' is not available. "
                f"Please set the required API key: {provider.required_env_var}"
            )
        return provider

    # Auto-select: try providers in preference order
    for name, provider_class in PROVIDER_REGISTRY.items():
        provider = provider_class()
        if provider.is_available():
            return provider

    raise LLMError(
        "No LLM provider available. Please set one of: "
        "ANTHROPIC_API_KEY (for Claude) or OPENAI_API_KEY (for OpenAI)"
    )
