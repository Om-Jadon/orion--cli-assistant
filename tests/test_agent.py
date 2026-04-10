import importlib
import pytest
from unittest.mock import patch, MagicMock


def _reload_agent():
    import core.agent as ca
    importlib.reload(ca)
    return ca


def test_build_agent_ollama_uses_openai_provider():
    """PROVIDER='ollama' -> OpenAIChatModel + OpenAIProvider with Ollama base URL."""
    ca = _reload_agent()
    with patch("core.agent.PROVIDER", "ollama"), \
         patch("core.agent.MODEL_STRING", None), \
         patch("core.agent.OpenAIChatModel") as mock_mc, \
         patch("core.agent.OpenAIProvider") as mock_pc, \
         patch("core.agent.Agent") as mock_ac:
        mock_ac.return_value = MagicMock()
        ca.build_agent(think=False)
        mock_mc.assert_called_once()
        mock_pc.assert_called_once()
        call_kwargs = mock_pc.call_args.kwargs
        assert "localhost:11434" in call_kwargs.get("base_url", "")


def test_build_agent_ollama_passes_think_in_extra_body():
    """PROVIDER='ollama', think=True -> 'think': True in extra_body model_settings."""
    ca = _reload_agent()
    with patch("core.agent.PROVIDER", "ollama"), \
         patch("core.agent.MODEL_STRING", None), \
         patch("core.agent.OpenAIChatModel") as mock_mc, \
         patch("core.agent.OpenAIProvider"), \
         patch("core.agent.Agent") as mock_ac:
        mock_mc.return_value = MagicMock()
        mock_ac.return_value = MagicMock()
        ca.build_agent(think=True)
        agent_kwargs = mock_ac.call_args.kwargs
        extra_body = agent_kwargs.get("model_settings", {}).get("extra_body", {})
        assert extra_body.get("think") is True


def test_build_agent_cloud_passes_model_string_to_agent():
    """PROVIDER='openai' -> Agent('openai:gpt-4o') directly, OpenAIChatModel NOT called."""
    ca = _reload_agent()
    with patch("core.agent.PROVIDER", "openai"), \
         patch("core.agent.MODEL_STRING", "openai:gpt-4o"), \
         patch("core.agent.OpenAIChatModel") as mock_mc, \
         patch("core.agent.Agent") as mock_ac:
        mock_ac.return_value = MagicMock()
        ca.build_agent(think=False)
        mock_mc.assert_not_called()
        first_positional = mock_ac.call_args.args[0] if mock_ac.call_args.args else None
        first_keyword = mock_ac.call_args.kwargs.get("model")
        model_arg = first_positional or first_keyword
        assert model_arg == "openai:gpt-4o"


def test_build_agent_cloud_think_does_not_raise():
    """think=True with a cloud provider must not raise — it is silently ignored."""
    ca = _reload_agent()
    with patch("core.agent.PROVIDER", "anthropic"), \
         patch("core.agent.MODEL_STRING", "anthropic:claude-sonnet-4-5"), \
         patch("core.agent.Agent") as mock_ac:
        mock_ac.return_value = MagicMock()
        ca.build_agent(think=True)  # must not raise


def test_build_agent_cloud_no_extra_body():
    """Cloud path must NOT pass extra_body (Ollama-specific) to Agent()."""
    ca = _reload_agent()
    with patch("core.agent.PROVIDER", "groq"), \
         patch("core.agent.MODEL_STRING", "groq:llama-3.3-70b-versatile"), \
         patch("core.agent.Agent") as mock_ac:
        mock_ac.return_value = MagicMock()
        ca.build_agent(think=False)
        call_kwargs = mock_ac.call_args.kwargs
        model_settings = call_kwargs.get("model_settings", {})
        assert "extra_body" not in model_settings


def test_system_prompt_instructs_no_retry_after_cancelled_confirmation():
    ca = _reload_agent()
    with patch("core.agent.PROVIDER", "openai"), \
         patch("core.agent.MODEL_STRING", "openai:gpt-4o"), \
         patch("core.agent.Agent") as mock_ac:
        mock_ac.return_value = MagicMock()
        ca.build_agent(think=False)

        system_prompt = mock_ac.call_args.kwargs.get("system_prompt", "")
        assert "do not retry" in system_prompt.lower()
        assert "user cancels" in system_prompt.lower()
        assert "do not ask follow-up confirmation questions" in system_prompt.lower()
        assert "tools handle confirmations" in system_prompt.lower()
        assert "tool outputs explicitly state whether confirmation was approved or denied" in system_prompt.lower()
        assert "confirmation denied" in system_prompt.lower()
