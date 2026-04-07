import pytest
import httpx

OLLAMA_API_BASE = "http://localhost:11434"
OLLAMA_V1_BASE  = "http://localhost:11434/v1"


def ollama_running() -> bool:
    try:
        r = httpx.get(f"{OLLAMA_API_BASE}/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def available_models() -> list[str]:
    try:
        r = httpx.get(f"{OLLAMA_API_BASE}/api/tags", timeout=2)
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []


requires_ollama = pytest.mark.skipif(
    not ollama_running(),
    reason="Ollama not running — start with: systemctl start ollama"
)


@requires_ollama
def test_ollama_reachable():
    r = httpx.get(f"{OLLAMA_API_BASE}/api/tags", timeout=2)
    assert r.status_code == 200


@requires_ollama
def test_model_available():
    models = available_models()
    assert any("qwen3:4b" in m for m in models), (
        f"qwen3:4b not found. Available: {models}\n"
        "Run: ollama pull qwen3:4b"
    )


@requires_ollama
async def test_streaming_produces_tokens():
    """Tokens arrive incrementally — not as a single blob after a delay."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(base_url=OLLAMA_V1_BASE, api_key="ollama")
    tokens = []

    stream = await client.chat.completions.create(
        model="qwen3:4b",
        messages=[{"role": "user", "content": "Say hello in 5 words"}],
        stream=True,
        extra_body={"think": False, "keep_alive": "10m"}
    )

    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            tokens.append(delta)

    assert len(tokens) > 1, (
        "Expected multiple token chunks but got one blob — streaming may be off. "
        "Check OLLAMA_NUM_PARALLEL=1 is set."
    )
    assert "".join(tokens).strip() != "", "Response was empty"


@requires_ollama
async def test_keep_alive_accepted():
    """Ollama accepts keep_alive in extra_body without raising an error."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(base_url=OLLAMA_V1_BASE, api_key="ollama")

    stream = await client.chat.completions.create(
        model="qwen3:4b",
        messages=[{"role": "user", "content": "Say yes"}],
        stream=True,
        extra_body={"think": False, "keep_alive": "10m"}
    )

    got_response = False
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            got_response = True
            break

    assert got_response
