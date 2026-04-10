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
            model_settings={"parallel_tool_calls": False},
        )

    from tools.files import find_files, list_directory, read_file, open_file, move_file, delete_file
    from tools.shell import run_shell
    from tools.browser import open_url, fetch_page
    from tools.search import web_search
    from tools.media import open_media

    for tool in [find_files, list_directory, read_file, open_file, move_file, delete_file, run_shell, open_url, fetch_page, web_search, open_media]:
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

TOOLS:
- find_files(query) — locate files by name
- list_directory(path) — list folder contents; use '~' for home
- read_file(path) — read file contents
- open_file(path) — open in default app
- move_file(source, destination) — move or rename
- delete_file(path) — trash a file
- run_shell(command) — run any shell command
- open_url(url) — open a URL in the browser
- web_search(query, max_results) — search the web via DuckDuckGo
- fetch_page(url) — extract readable text from a web page
- open_media(query, site) — find and open media (YouTube etc.) in browser

RULES:
- Answer factual, conversational, and knowledge questions DIRECTLY — do NOT call any tools.
- Only call tools when the task requires filesystem access, shell execution, or opening a URL.
- Always use find_files first to locate a file before reading, opening, or deleting it.
- Never output literal function/tool call syntax in plain text (for example: <function/...>, tool_call blocks, or JSON call payloads).
- For destructive operations (delete, overwrite), confirm with the user first.
- Never run sudo. Never touch paths outside {home}.
- Be concise. No "As an AI..." disclaimers.
- Respond in plain Markdown. No HTML.
- For web research, use web_search first then fetch_page for detail.
"""
