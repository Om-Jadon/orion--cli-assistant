import pytest
import httpx
import os
import time

OLLAMA_API_BASE = "http://localhost:11434"
OLLAMA_V1_BASE  = "http://localhost:11434/v1"
TEST_MODEL = os.getenv("ORION_TEST_MODEL", "gemma4:latest")


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
    assert any(TEST_MODEL == m for m in models), (
        f"{TEST_MODEL} not found. Available: {models}\n"
        f"Run: ollama pull {TEST_MODEL}"
    )


@requires_ollama
async def test_streaming_produces_tokens():
    """Tokens arrive incrementally — not as a single blob after a delay."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(base_url=OLLAMA_V1_BASE, api_key="ollama")
    tokens = []

    stream = await client.chat.completions.create(
        model=TEST_MODEL,
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
        model=TEST_MODEL,
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


@requires_ollama
async def test_realistic_prompt_response_timing():
    """Measure response latency for a realistic end-user Orion prompt."""
    from openai import AsyncOpenAI

    max_ttfb_sec = float(os.getenv("ORION_MAX_TTFB_SEC", "10"))
    max_total_sec = float(os.getenv("ORION_MAX_TOTAL_SEC", "90"))

    client = AsyncOpenAI(base_url=OLLAMA_V1_BASE, api_key="ollama")
    prompt = (
        "Open the latest Markiplier video and explain what steps you would take "
        "to find it safely on Linux. Keep it concise and actionable."
    )

    start = time.perf_counter()
    first_token_at: float | None = None
    token_count = 0

    stream = await client.chat.completions.create(
        model=TEST_MODEL,
        messages=[{"role": "user", "content": prompt}],
        stream=True,
        extra_body={"think": False, "keep_alive": "10m"}
    )

    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            token_count += 1
            if first_token_at is None:
                first_token_at = time.perf_counter()

    end = time.perf_counter()

    assert first_token_at is not None, "Model produced no output tokens"

    ttfb_sec = first_token_at - start
    total_sec = end - start

    print(
        "\n"
        f"Model: {TEST_MODEL}\n"
        f"Prompt length: {len(prompt)} chars\n"
        f"Token chunks: {token_count}\n"
        f"Time to first token: {ttfb_sec:.2f}s\n"
        f"Total response time: {total_sec:.2f}s\n"
    )

    assert token_count > 0, "Expected at least one token chunk"
    assert ttfb_sec <= max_ttfb_sec, (
        f"TTFB {ttfb_sec:.2f}s exceeded ORION_MAX_TTFB_SEC={max_ttfb_sec:.2f}s"
    )
    assert total_sec <= max_total_sec, (
        f"Total {total_sec:.2f}s exceeded ORION_MAX_TOTAL_SEC={max_total_sec:.2f}s"
    )
