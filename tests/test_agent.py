import pytest
from unittest.mock import patch
from pathlib import Path


def test_build_agent_returns_agent():
    from core.agent import build_agent
    from pydantic_ai import Agent
    agent = build_agent()
    assert isinstance(agent, Agent)


def test_build_agent_think_false_by_default():
    from core.agent import build_agent
    agent = build_agent()
    settings = agent.model_settings or {}
    extra = (settings.get("extra_body") or {})
    assert extra.get("think") is False


def test_build_agent_think_true_when_requested():
    from core.agent import build_agent
    agent = build_agent(think=True)
    settings = agent.model_settings or {}
    extra = (settings.get("extra_body") or {})
    assert extra.get("think") is True


def test_system_prompt_contains_environment_info():
    from core.agent import _build_system_prompt
    prompt = _build_system_prompt()
    assert str(Path.home()) in prompt
    assert "Linux" in prompt
    assert "Orion" in prompt
