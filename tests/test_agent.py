import importlib
import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.asyncio
async def test_wrap_tool_for_trace_logs_start_and_end(monkeypatch):
    import core.agent as ca

    events = []

    async def sample_tool(query: str) -> str:
        return f"ok:{query}"

    monkeypatch.setattr(
        ca.trace_logging,
        "log_tool_call_start",
        lambda **kwargs: events.append(("start", kwargs)) or "call-1",
    )
    monkeypatch.setattr(
        ca.trace_logging,
        "log_tool_call_end",
        lambda **kwargs: events.append(("end", kwargs)),
    )

    wrapped = ca._wrap_tool_for_trace(sample_tool)
    result = await wrapped("abc")

    assert result == "ok:abc"
    assert events[0][0] == "start"
    assert events[1][0] == "end"
    assert events[1][1]["status"] == "ok"


def _reload_agent():
    import core.agent as ca
    importlib.reload(ca)
    return ca


def test_build_agent_cloud_passes_model_string_to_agent():
    """Cloud builder passes model string directly to Agent()."""
    ca = _reload_agent()
    with patch("core.agent.MODEL_STRING", "openai:gpt-4o"), \
         patch("core.agent.Agent") as mock_ac:
        mock_ac.return_value = MagicMock()
        ca.build_agent()
        first_positional = mock_ac.call_args.args[0] if mock_ac.call_args.args else None
        first_keyword = mock_ac.call_args.kwargs.get("model")
        model_arg = first_positional or first_keyword
        assert model_arg == "openai:gpt-4o"


def test_build_agent_cloud_with_empty_model_string_raises_value_error():
    ca = _reload_agent()
    with patch("core.agent.MODEL_STRING", ""), \
         pytest.raises(ValueError):
        ca.build_agent()


def test_build_agent_cloud_no_extra_body():
    """Cloud path must keep only cloud model_settings and avoid local extra_body."""
    ca = _reload_agent()
    with patch("core.agent.MODEL_STRING", "groq:llama-3.3-70b-versatile"), \
         patch("core.agent.Agent") as mock_ac:
        mock_ac.return_value = MagicMock()
        ca.build_agent()
        call_kwargs = mock_ac.call_args.kwargs
        model_settings = call_kwargs.get("model_settings", {})
        assert "extra_body" not in model_settings


def test_build_agent_cloud_uses_model_override_when_provided():
    """Cloud path must honor explicit model override for fallback attempts."""
    ca = _reload_agent()
    with patch("core.agent.MODEL_STRING", "groq:openai/gpt-oss-120b"), \
         patch("core.agent.Agent") as mock_ac:
        mock_ac.return_value = MagicMock()
        ca.build_agent(model_string_override="groq:qwen/qwen3-32b")
        first_positional = mock_ac.call_args.args[0] if mock_ac.call_args.args else None
        first_keyword = mock_ac.call_args.kwargs.get("model")
        model_arg = first_positional or first_keyword
        assert model_arg == "groq:qwen/qwen3-32b"


def test_system_prompt_instructs_no_retry_after_cancelled_confirmation():
    ca = _reload_agent()
    with patch("core.agent.MODEL_STRING", "openai:gpt-4o"), \
         patch("core.agent.Agent") as mock_ac:
        mock_ac.return_value = MagicMock()
        ca.build_agent()

        system_prompt = mock_ac.call_args.kwargs.get("system_prompt", "")
        assert "do not retry" in system_prompt.lower()
        assert "user cancels" in system_prompt.lower()
        assert "do not ask follow-up confirmation questions" in system_prompt.lower()
        assert "tools handle confirmations" in system_prompt.lower()
        assert "tool outputs explicitly state whether confirmation was approved or denied" in system_prompt.lower()
        # Rule was consolidated into the above line
        assert "authoritative user intent" in system_prompt.lower()
