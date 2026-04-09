import os
from pathlib import Path
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from config import OLLAMA_BASE, MODEL, MODEL_STRING, PROVIDER, KEEP_ALIVE_ACTIVE


def build_agent(think: bool = False) -> Agent:
    """
    Build a PydanticAI agent for the configured provider.

    Ollama path (PROVIDER == 'ollama'):
        Uses OpenAIChatModel + OpenAIProvider pointed at local Ollama.
        Supports think=True (Qwen3 chain-of-thought) and keep_alive.

    Cloud path (any other PROVIDER):
        Passes MODEL_STRING directly to Agent().
        PydanticAI handles provider routing and reads the API key from env.
        think=True is silently ignored (cloud models don't support it).
    """
    if PROVIDER == "ollama":
        model = OpenAIChatModel(
            MODEL,
            provider=OpenAIProvider(
                base_url=OLLAMA_BASE,
                api_key="ollama",
            )
        )
        agent = Agent(
            model=model,
            system_prompt=_build_system_prompt(),
            model_settings={
                "extra_body": {
                    "think": think,
                    "keep_alive": KEEP_ALIVE_ACTIVE,
                }
            },
        )
    else:
        # Cloud: PydanticAI resolves the provider from the model string prefix.
        # e.g. "openai:gpt-4o", "anthropic:claude-sonnet-4-5", "gemini-2.0-flash"
        agent = Agent(
            MODEL_STRING,
            system_prompt=_build_system_prompt(),
        )

    from tools.files import manage_files
    from tools.shell import run_shell
    from tools.browser import open_url

    for tool in [manage_files, run_shell, open_url]:
        agent.tool_plain(tool)

    return agent


def _build_system_prompt() -> str:
    cwd   = os.getcwd()
    shell = os.environ.get("SHELL", "bash")
    home  = Path.home()
    return f"""You are Orion, a versatile AI assistant running on Linux.

ENVIRONMENT:
- Current directory: {cwd}
- Shell: {shell}
- Home: {home}
- OS: Linux

RULES:
- Answer factual, conversational, and knowledge questions DIRECTLY — do NOT call any tools.
- Only use tools when the user explicitly asks to: access files, run a command, or open a URL.
- Never guess file paths. Use manage_files(action="find") to locate files before operating on them.
- For destructive operations (delete, overwrite), always confirm with the user first.
- Never run sudo commands. Never touch paths outside {home}.
- Be concise. No padding. No "As an AI..." disclaimers.
- Respond in plain Markdown. No HTML.
"""
