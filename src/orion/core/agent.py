import os
import time
import inspect
import functools
from pathlib import Path
from pydantic_ai import Agent
from orion import config
from orion.core import trace_logging as trace_logging
from orion.ui.spinner import update_label


def build_agent(model_string_override: str | None = None) -> Agent:
    """
    Build a cloud provider-backed PydanticAI agent.

    selected_model_string is required; model_string_override is used for
    controlled model switching flows (for example Groq fallback attempts).
    """
    selected_model_string = model_string_override or config.MODEL_STRING
    if not selected_model_string:
        raise ValueError("Cloud agent build requires a model string.")
    agent = Agent(
        selected_model_string,
        system_prompt=_build_system_prompt(),
        model_settings={"parallel_tool_calls": False},
    )

    from orion.tools.files import find_files, list_directory, read_file, open_file, move_file, delete_file, write_file
    from orion.tools.shell import run_shell
    from orion.tools.browser import open_url, fetch_page
    from orion.tools.search import web_search
    from orion.tools.memory_tool import manage_user_memory
    from orion.tools.media import open_media

    for tool in [find_files, list_directory, read_file, open_file, move_file, delete_file, write_file, run_shell, open_url, fetch_page, web_search, manage_user_memory, open_media]:
        agent.tool_plain(_wrap_tool_for_trace(tool))

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

SLASH COMMANDS:
- /help    (prints availability)
- /clear   (clears screen)
- /undo    (reverses last file action)
- /history (shows session history)
- /reset   (clears session context)
- /memory  (shows stored facts)
- /scan    (re-indexes files)
- /exit    (quits orion)

RULES:
- [MANDATORY] NEVER promise that you have performed any operation (memory update, file write, delete, move, shell execution, etc.) in plain text unless the tool call was successful.
- [MANDATORY] If you do not call the appropriate tool, the action HAS NOT HAPPENED and you must never tell the user it has.
- [MANDATORY] You MUST use manage_user_memory(action='upsert', ...) to create or update facts, and manage_user_memory(action='delete', ...) to remove them.
- Answer factual, conversational, and knowledge questions DIRECTLY — do NOT call any tools.
- Only call tools when the task requires filesystem access, shell execution, web search, or browsing.
- Always use find_files first to locate a file before reading, opening, or deleting it.
- Use write_file instead of shell redirection (for example, '>' or '>>') to create or update files.
- Never output literal function/tool call syntax in plain text (for example: <function/...> or JSON payloads).
- For destructive operations (delete, overwrite), let tools handle confirmations. 
- Do not ask follow-up confirmation questions in plain text; tools handle confirmations.
- If user cancels a destructive confirmation, treat it as final for this turn: do not retry and do not ask again.
- Tool outputs explicitly state whether confirmation was approved or denied; treat that as authoritative user intent.
- Never run sudo. Never touch paths outside {home}.
- Be concise. No "As an AI..." disclaimers.
- Respond in plain Markdown. No HTML.
- For web research, use web_search first then fetch_page for detail.
"""


TOOL_LABELS = {
    "find_files": "Searching files...",
    "list_directory": "Listing directory contents...",
    "read_file": "Reading file contents...",
    "open_file": "Opening file...",
    "move_file": "Moving file...",
    "delete_file": "Moving to trash...",
    "write_file": "Writing file...",
    "run_shell": "Running command...",
    "open_url": "Opening browser...",
    "fetch_page": "Reading website...",
    "web_search": "Searching web...",
    "manage_user_memory": "Managing memory...",
    "open_media": "Searching media...",
}


def _wrap_tool_for_trace(tool):
    if inspect.iscoroutinefunction(tool):
        @functools.wraps(tool)
        async def _wrapped(*args, **kwargs):
            tool_name = tool.__name__
            label = TOOL_LABELS.get(tool_name, f"calling {tool_name}")
            update_label(label)
            
            tool_call_id = trace_logging.log_tool_call_start(
                tool_name=tool_name,
                args=args,
                kwargs=kwargs,
            )
            started = time.perf_counter()
            try:
                result = await tool(*args, **kwargs)
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                trace_logging.log_tool_call_end(
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    status="ok",
                    result=result,
                    elapsed_ms=elapsed_ms,
                )
                return result
            except Exception as e:
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                trace_logging.log_tool_call_end(
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    status="error",
                    error=str(e),
                    elapsed_ms=elapsed_ms,
                )
                raise
            finally:
                update_label("thinking")

        return _wrapped

    @functools.wraps(tool)
    def _wrapped_sync(*args, **kwargs):
        tool_name = tool.__name__
        label = TOOL_LABELS.get(tool_name, f"calling {tool_name}")
        update_label(label)

        tool_call_id = trace_logging.log_tool_call_start(
            tool_name=tool_name,
            args=args,
            kwargs=kwargs,
        )
        started = time.perf_counter()
        try:
            result = tool(*args, **kwargs)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            trace_logging.log_tool_call_end(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                status="ok",
                result=result,
                elapsed_ms=elapsed_ms,
            )
            return result
        except Exception as e:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            trace_logging.log_tool_call_end(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                status="error",
                error=str(e),
                elapsed_ms=elapsed_ms,
            )
            raise
        finally:
            update_label("thinking")

    return _wrapped_sync
