import pytest
from orion.core.model_fallback import get_groq_token_limit_fallback_models

def test_groq_token_limit_fallback_model_order_is_fixed():
    """Ensure Groq fallback model hierarchy is maintained for reliability."""
    assert get_groq_token_limit_fallback_models() == (
        "groq:openai/gpt-oss-120b",
        "groq:qwen/qwen3-32b",
        "groq:llama-3.3-70b-versatile",
    )
