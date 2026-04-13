from __future__ import annotations

# Fixed in-code Groq fallback order for token-limit exhaustion handling.
GROQ_TOKEN_LIMIT_FALLBACK_MODELS: tuple[str, ...] = (
    "groq:openai/gpt-oss-120b",
    "groq:qwen/qwen3-32b",
    "groq:llama-3.3-70b-versatile",

)

# Project-wide recommended models (used for onboarding defaults).
RECOMMENDED_MODELS: dict[str, str] = {
    "openai":    "openai:gpt-4o",
    "anthropic": "anthropic:claude-3-5-sonnet-latest",
    "groq":      GROQ_TOKEN_LIMIT_FALLBACK_MODELS[0],
    "gemini":    "gemini:gemini-3.0-flash",
    "mistral":   "mistral:mistral-large-latest",
}


def get_groq_token_limit_fallback_models() -> tuple[str, ...]:
    return GROQ_TOKEN_LIMIT_FALLBACK_MODELS


def get_recommended_model(provider: str) -> str:
    """Returns the primary recommended model for a given provider."""
    return RECOMMENDED_MODELS.get(provider.lower(), "")
