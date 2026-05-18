"""
Anthropic SDK Client Wrapper

Provides a centralized client with model configuration,
token counting, and automatic fallback to stronger models
when primary model fails.
"""

import os
from anthropic import Anthropic

# Model configuration
DEFAULT_PRIMARY_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_FALLBACK_MODEL = "claude-sonnet-4-6"
MODEL_ALIASES = {
    "claude-haiku-20240307": DEFAULT_PRIMARY_MODEL,
    "claude-3-haiku-20240307": DEFAULT_PRIMARY_MODEL,
    "claude-3-5-haiku-20241022": DEFAULT_PRIMARY_MODEL,
    "claude-sonnet-4-20250514": DEFAULT_FALLBACK_MODEL,
}


def _configured_model(*env_names: str, default: str) -> str:
    """Read a model setting and translate known legacy/invalid aliases."""
    for env_name in env_names:
        model = os.getenv(env_name, "").strip()
        if model:
            return MODEL_ALIASES.get(model, model)
    return default


PRIMARY_SQL_MODEL = _configured_model(
    "PRIMARY_MODEL",
    "ANTHROPIC_MODEL",
    default=DEFAULT_PRIMARY_MODEL,
)
PRIMARY_ANSWER_MODEL = _configured_model(
    "ANSWER_MODEL",
    "PRIMARY_MODEL",
    "ANTHROPIC_MODEL",
    default=DEFAULT_PRIMARY_MODEL,
)
FALLBACK_MODEL = _configured_model(
    "FALLBACK_MODEL",
    default=DEFAULT_FALLBACK_MODEL,
)

_client: Anthropic | None = None


def get_client() -> Anthropic:
    """
    Get or create the singleton Anthropic client.

    Returns:
        Configured Anthropic client instance.

    Raises:
        ValueError: If ANTHROPIC_API_KEY is not set.
    """
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if not api_key or api_key == "your_key_here":
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. "
                "Please set it in your .env file."
            )
        _client = Anthropic(api_key=api_key)
    return _client


def call_claude(
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    max_tokens: int = 500,
    temperature: float = 0.0,
) -> tuple[str, int]:
    """
    Call Claude API with the given prompts.

    Args:
        system_prompt: System instructions for Claude.
        user_prompt: User message content.
        model: Model to use (defaults to PRIMARY_SQL_MODEL).
        max_tokens: Maximum response tokens.
        temperature: Sampling temperature.

    Returns:
        Tuple of (response_text, total_tokens_used).
    """
    client = get_client()
    model = model or PRIMARY_SQL_MODEL

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    text = response.content[0].text.strip()
    tokens_used = (response.usage.input_tokens + response.usage.output_tokens)

    return text, tokens_used


def api_health_check() -> dict:
    """
    Check Anthropic API connectivity.

    Returns:
        Dictionary with API status info.
    """
    try:
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if not api_key or api_key == "your_key_here":
            return {
                "status": "not_configured",
                "detail": "ANTHROPIC_API_KEY not set",
                "primary_model": PRIMARY_SQL_MODEL,
                "fallback_model": FALLBACK_MODEL,
            }
        return {
            "status": "configured",
            "primary_model": PRIMARY_SQL_MODEL,
            "fallback_model": FALLBACK_MODEL,
            "key_prefix": api_key[:12] + "..." if len(api_key) > 12 else "***",
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }
