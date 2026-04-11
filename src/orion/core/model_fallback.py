from __future__ import annotations

# Fixed in-code Groq fallback order for token-limit exhaustion handling.
GROQ_TOKEN_LIMIT_FALLBACK_MODELS: tuple[str, ...] = (
    "groq:openai/gpt-oss-120b",
    "groq:qwen/qwen3-32b",
    "groq:llama-3.3-70b-versatile",

)


def get_groq_token_limit_fallback_models() -> tuple[str, ...]:
    return GROQ_TOKEN_LIMIT_FALLBACK_MODELS
