import pytest
from orion.core.model_fallback import get_groq_token_limit_fallback_models


@pytest.fixture(autouse=True)
def mock_default_provider(monkeypatch):
    from orion import config
    monkeypatch.setattr(config, "PROVIDER", "openai")


class _FakeResult:
    def __init__(self, text: str):
        self._text = text

    async def stream_text(self, delta: bool = True):
        yield self._text


class _FakeRunStreamContext:
    def __init__(self, item):
        self._item = item

    async def __aenter__(self):
        if isinstance(self._item, Exception):
            raise self._item
        return _FakeResult(self._item)

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeAgent:
    def __init__(self, outputs):
        self._outputs = list(outputs)
        self.prompts = []

    def run_stream(self, prompt: str):
        self.prompts.append(prompt)
        if not self._outputs:
            raise RuntimeError("No fake outputs left")
        return _FakeRunStreamContext(self._outputs.pop(0))


class _FakeSpinner:
    def __init__(self):
        self.labels = []

    def start(self, label: str = "thinking"):
        self.labels.append(label)

    async def stop(self):
        return None


@pytest.mark.asyncio
async def test_run_with_streaming_retries_on_textual_tool_call(monkeypatch):
    from orion.core import streaming as cs

    async def _capture(gen):
        out = ""
        async for token in gen:
            out += token
        return out

    monkeypatch.setattr(cs.config, "PROVIDER", "openai")
    monkeypatch.setattr(cs, "stream_response", _capture)
    monkeypatch.setattr(cs, "spinner", _FakeSpinner())
    monkeypatch.setattr(cs.trace_logging, "start_llm_request", lambda **_: "req-1")
    monkeypatch.setattr(cs.trace_logging, "log_llm_response", lambda **_: None)
    monkeypatch.setattr(cs.trace_logging, "log_llm_retry", lambda **_: None)
    monkeypatch.setattr(cs.trace_logging, "log_llm_error", lambda **_: None)
    monkeypatch.setattr(cs.trace_logging, "clear_request_id", lambda: None)

    agent = _FakeAgent([
        '<function/run_shell>{"command": "echo hello"}',
        "TOOL_SHELL_OK",
    ])

    result = await cs.run_with_streaming(agent, "run shell command echo hello")

    assert result == "TOOL_SHELL_OK"
    assert len(agent.prompts) == 2
    assert "literal function/tool-call text" in agent.prompts[1]


@pytest.mark.asyncio
async def test_run_with_streaming_retries_on_failed_generation(monkeypatch):
    from orion.core import streaming as cs

    async def _capture(gen):
        out = ""
        async for token in gen:
            out += token
        return out

    monkeypatch.setattr(cs.config, "PROVIDER", "openai")
    monkeypatch.setattr(cs, "stream_response", _capture)
    monkeypatch.setattr(cs, "spinner", _FakeSpinner())
    monkeypatch.setattr(cs.trace_logging, "start_llm_request", lambda **_: "req-1")
    monkeypatch.setattr(cs.trace_logging, "log_llm_response", lambda **_: None)
    monkeypatch.setattr(cs.trace_logging, "log_llm_retry", lambda **_: None)
    monkeypatch.setattr(cs.trace_logging, "log_llm_error", lambda **_: None)
    monkeypatch.setattr(cs.trace_logging, "clear_request_id", lambda: None)

    agent = _FakeAgent([
        Exception("failed_generation: tool call XML invalid"),
        "normal response",
    ])

    result = await cs.run_with_streaming(agent, "read CLAUDE.md")

    assert result == "normal response"
    assert len(agent.prompts) == 2
    assert "Use tool calls directly" in agent.prompts[1]


@pytest.mark.asyncio
async def test_run_with_streaming_keeps_model_response_after_cancelled_tool(monkeypatch):
    from orion.core import streaming as cs

    async def _capture(gen):
        out = ""
        async for token in gen:
            out += token
        return out

    monkeypatch.setattr(cs.config, "PROVIDER", "openai")
    monkeypatch.setattr(cs, "stream_response", _capture)
    monkeypatch.setattr(cs, "spinner", _FakeSpinner())
    monkeypatch.setattr(cs.trace_logging, "start_llm_request", lambda **_: "req-1")
    monkeypatch.setattr(cs.trace_logging, "log_llm_response", lambda **_: None)
    monkeypatch.setattr(cs.trace_logging, "log_llm_retry", lambda **_: None)
    monkeypatch.setattr(cs.trace_logging, "log_llm_error", lambda **_: None)
    monkeypatch.setattr(cs.trace_logging, "clear_request_id", lambda: None)

    agent = _FakeAgent([
        "Understood. Operation cancelled by user confirmation.",
    ])

    result = await cs.run_with_streaming(agent, "move it back")

    assert result == "Understood. Operation cancelled by user confirmation."


@pytest.mark.asyncio
async def test_run_with_streaming_emits_llm_request_and_response_events(monkeypatch):
    from orion.core import streaming as cs

    events = []

    async def _capture(gen):
        out = ""
        async for token in gen:
            out += token
        return out

    monkeypatch.setattr(cs, "stream_response", _capture)
    monkeypatch.setattr(cs, "spinner", _FakeSpinner())
    monkeypatch.setattr(cs.trace_logging, "start_llm_request", lambda **kwargs: events.append(("request", kwargs)) or "req-123")
    monkeypatch.setattr(cs.trace_logging, "log_llm_response", lambda **kwargs: events.append(("response", kwargs)))
    monkeypatch.setattr(cs.trace_logging, "log_llm_retry", lambda **kwargs: events.append(("retry", kwargs)))
    monkeypatch.setattr(cs.trace_logging, "log_llm_error", lambda **kwargs: events.append(("error", kwargs)))
    monkeypatch.setattr(cs.trace_logging, "clear_request_id", lambda: events.append(("clear", {})))

    agent = _FakeAgent(["normal response"])
    result = await cs.run_with_streaming(agent, "hello", context="ctx")

    assert result == "normal response"
    assert events[0][0] == "request"
    assert events[1][0] == "response"
    assert events[-1][0] == "clear"


def test_is_groq_token_limit_error_classifier():
    from orion.core import streaming as cs

    assert cs._is_groq_token_limit_error("rate_limit_exceeded: token quota exceeded") is True
    assert cs._is_groq_token_limit_error("Request too large for model") is True
    assert cs._is_groq_token_limit_error("rate_limit_exceeded: too many requests per minute") is False
    assert cs._is_groq_token_limit_error("network timeout") is False


@pytest.mark.asyncio
async def test_run_with_streaming_groq_falls_back_on_token_limit(monkeypatch):
    from orion.core import streaming as cs

    events = []

    async def _capture(gen):
        out = ""
        async for token in gen:
            out += token
        return out

    monkeypatch.setattr(cs.config, "PROVIDER", "groq")
    monkeypatch.setattr(cs.config, "MODEL_STRING", "groq:openai/gpt-oss-120b")
    monkeypatch.setattr(cs, "stream_response", _capture)
    monkeypatch.setattr(cs, "spinner", _FakeSpinner())
    monkeypatch.setattr(cs.trace_logging, "start_llm_request", lambda **kwargs: events.append(("request", kwargs)) or "req-1")
    monkeypatch.setattr(cs.trace_logging, "log_llm_response", lambda **kwargs: events.append(("response", kwargs)))
    monkeypatch.setattr(cs.trace_logging, "log_llm_retry", lambda **kwargs: events.append(("retry", kwargs)))
    monkeypatch.setattr(cs.trace_logging, "log_llm_error", lambda **kwargs: events.append(("error", kwargs)))
    monkeypatch.setattr(cs.trace_logging, "clear_request_id", lambda: events.append(("clear", {})))

    first_agent = _FakeAgent([Exception("rate_limit_exceeded: token quota exceeded")])
    second_agent = _FakeAgent(["fallback success"])
    monkeypatch.setattr(cs, "_build_agent_for_model", lambda model: second_agent)

    result = await cs.run_with_streaming(first_agent, "hello")

    assert result == "fallback success"
    retry_events = [payload for event, payload in events if event == "retry"]
    assert any(evt.get("reason") == "groq_token_limit_fallback" for evt in retry_events)
    assert first_agent.prompts
    assert second_agent.prompts


@pytest.mark.asyncio
async def test_run_with_streaming_groq_does_not_fallback_on_non_token_errors(monkeypatch):
    from orion.core import streaming as cs

    events = []
    builds = []

    async def _capture(gen):
        out = ""
        async for token in gen:
            out += token
        return out

    monkeypatch.setattr(cs.config, "PROVIDER", "groq")
    monkeypatch.setattr(cs.config, "MODEL_STRING", "groq:openai/gpt-oss-120b")
    monkeypatch.setattr(cs, "stream_response", _capture)
    monkeypatch.setattr(cs, "spinner", _FakeSpinner())
    monkeypatch.setattr(cs.trace_logging, "start_llm_request", lambda **kwargs: events.append(("request", kwargs)) or "req-1")
    monkeypatch.setattr(cs.trace_logging, "log_llm_response", lambda **kwargs: events.append(("response", kwargs)))
    monkeypatch.setattr(cs.trace_logging, "log_llm_retry", lambda **kwargs: events.append(("retry", kwargs)))
    monkeypatch.setattr(cs.trace_logging, "log_llm_error", lambda **kwargs: events.append(("error", kwargs)))
    monkeypatch.setattr(cs.trace_logging, "clear_request_id", lambda: events.append(("clear", {})))

    first_agent = _FakeAgent([Exception("rate_limit_exceeded: too many requests per minute")])
    monkeypatch.setattr(cs, "_build_agent_for_model", lambda model: builds.append(model) or _FakeAgent(["unused"]))

    result = await cs.run_with_streaming(first_agent, "hello")

    assert result == ""
    assert builds == []
    retry_events = [payload for event, payload in events if event == "retry"]
    assert not any(evt.get("reason") == "groq_token_limit_fallback" for evt in retry_events)


@pytest.mark.asyncio
async def test_run_with_streaming_groq_reports_exhaustion_after_third_model(monkeypatch):
    from orion.core import streaming as cs

    events = []
    build_queue = [
        _FakeAgent([Exception("rate_limit_exceeded: token quota exceeded")]),
        _FakeAgent([Exception("rate_limit_exceeded: token quota exceeded")]),
    ]

    async def _capture(gen):
        out = ""
        async for token in gen:
            out += token
        return out

    monkeypatch.setattr(cs.config, "PROVIDER", "groq")
    monkeypatch.setattr(cs.config, "MODEL_STRING", "groq:openai/gpt-oss-120b")
    monkeypatch.setattr(cs, "stream_response", _capture)
    monkeypatch.setattr(cs, "spinner", _FakeSpinner())
    monkeypatch.setattr(cs.trace_logging, "start_llm_request", lambda **kwargs: events.append(("request", kwargs)) or "req-1")
    monkeypatch.setattr(cs.trace_logging, "log_llm_response", lambda **kwargs: events.append(("response", kwargs)))
    monkeypatch.setattr(cs.trace_logging, "log_llm_retry", lambda **kwargs: events.append(("retry", kwargs)))
    monkeypatch.setattr(cs.trace_logging, "log_llm_error", lambda **kwargs: events.append(("error", kwargs)))
    monkeypatch.setattr(cs.trace_logging, "clear_request_id", lambda: events.append(("clear", {})))

    first_agent = _FakeAgent([Exception("rate_limit_exceeded: token quota exceeded")])
    monkeypatch.setattr(cs, "_build_agent_for_model", lambda model: build_queue.pop(0))

    result = await cs.run_with_streaming(first_agent, "hello")

    assert result == ""
    error_payloads = [payload for event, payload in events if event == "error"]
    assert any(payload.get("error_type") == "groq_token_limit_exhausted" for payload in error_payloads)
    exhausted_payload = [payload for payload in error_payloads if payload.get("error_type") == "groq_token_limit_exhausted"][0]
    assert exhausted_payload.get("attempted_models") == list(get_groq_token_limit_fallback_models())
