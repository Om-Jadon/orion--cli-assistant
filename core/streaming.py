import re
from typing import AsyncGenerator
from pydantic_ai import Agent
from ui.renderer import console, stream_response
from ui.spinner import Spinner

spinner = Spinner(console)

_TOOL_RETRY_HINT = (
    "\n\n[Important: Use tool calls directly — do not write function syntax in text.]"
)

_TEXTUAL_TOOL_CALL_RETRY_HINT = (
    "\n\n[Important: Your previous reply included literal function/tool-call text. "
    "Do NOT output any <function...>, tool_call, or JSON call payload in plain text. "
    "Execute tools via tool-calling and then return a normal user-facing answer.]"
)

_TEXTUAL_TOOL_CALL_PATTERNS = (
    re.compile(r"<\s*/?\s*function", re.IGNORECASE),
    re.compile(r"<\s*/?\s*tool_call", re.IGNORECASE),
)


def _looks_like_textual_tool_call(text: str) -> bool:
    """Detect obvious tool-call markup leaked into assistant text output."""
    return any(pattern.search(text) for pattern in _TEXTUAL_TOOL_CALL_PATTERNS)


async def run_with_streaming(agent: Agent, prompt: str, context: str = "") -> str:
    """
    Run the agent and stream tokens live to the terminal.
    Shows tool activity in the spinner while tools are called.
    Returns the full assembled response text.
    Retries when providers return failed_generation errors or when the model
    leaks literal tool-call syntax (e.g. <function/...>) into plain text output.
    """
    full_prompt = f"{context}\n\n{prompt}" if context else prompt
    full_response = ""

    for attempt in range(3):
        spinner.start("thinking")
        try:
            async with agent.run_stream(full_prompt) as result:
                await spinner.stop()

                async def live_tokens() -> AsyncGenerator[str, None]:
                    async for delta in result.stream_text(delta=True):
                        yield delta

                full_response = await stream_response(live_tokens())

            if _looks_like_textual_tool_call(full_response) and attempt < 2:
                console.print("\n[dim]⟳ retrying...[/dim]")
                full_prompt = full_prompt + _TEXTUAL_TOOL_CALL_RETRY_HINT
                continue

            break  # success — exit retry loop

        except Exception as e:
            await spinner.stop()
            err_str = str(e)
            if "failed_generation" in err_str and attempt < 2:
                # Groq XML/tool-call hallucination — retry with an explicit hint
                full_prompt = full_prompt + _TOOL_RETRY_HINT
                continue
            console.print(f"[error]Error: {e}[/error]")
            break

    return full_response
