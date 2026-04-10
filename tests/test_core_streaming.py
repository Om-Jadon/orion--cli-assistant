import pytest


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
    import core.streaming as cs

    async def _capture(gen):
        out = ""
        async for token in gen:
            out += token
        return out

    monkeypatch.setattr(cs, "stream_response", _capture)
    monkeypatch.setattr(cs, "spinner", _FakeSpinner())

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
    import core.streaming as cs

    async def _capture(gen):
        out = ""
        async for token in gen:
            out += token
        return out

    monkeypatch.setattr(cs, "stream_response", _capture)
    monkeypatch.setattr(cs, "spinner", _FakeSpinner())

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
    import core.streaming as cs

    async def _capture(gen):
        out = ""
        async for token in gen:
            out += token
        return out

    monkeypatch.setattr(cs, "stream_response", _capture)
    monkeypatch.setattr(cs, "spinner", _FakeSpinner())

    agent = _FakeAgent([
        "Understood. Operation cancelled by user confirmation.",
    ])

    result = await cs.run_with_streaming(agent, "move it back")

    assert result == "Understood. Operation cancelled by user confirmation."
