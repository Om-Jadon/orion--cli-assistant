import os
from pathlib import Path
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from config import OLLAMA_BASE, MODEL, KEEP_ALIVE_ACTIVE


def build_agent(think: bool = False) -> Agent:
    model = OpenAIChatModel(
        MODEL,
        provider=OpenAIProvider(
            base_url=OLLAMA_BASE,
            api_key="ollama"
        )
    )

    agent = Agent(
        model=model,
        system_prompt=_build_system_prompt(),
        model_settings={
            "extra_body": {
                "think": think,
                "keep_alive": KEEP_ALIVE_ACTIVE
            }
        }
    )

    from tools.files import manage_files
    from tools.shell import run_shell
    from tools.browser import open_url, fetch_page
    from tools.search import web_search
    from tools.media import open_media

    for tool in [manage_files, run_shell, open_url, fetch_page, web_search, open_media]:
        agent.tool_plain(tool)

    return agent


def _build_system_prompt() -> str:
    cwd   = os.getcwd()
    shell = os.environ.get("SHELL", "bash")
    home  = Path.home()
    return f"""You are Orion, a local AI assistant running entirely offline on Linux.

ENVIRONMENT:
- Current directory: {cwd}
- Shell: {shell}
- Home: {home}
- OS: Linux

RULES:
- Never guess file paths. Always call manage_files(action="find") first to locate files.
- For destructive operations (delete, overwrite), always confirm with the user first.
- Never run sudo commands. Never touch paths outside {home}.
- Be concise. No padding. No "As an AI..." disclaimers.
- Respond in plain Markdown. No HTML.
- When opening media or YouTube content, use open_media — not a raw URL.
"""
