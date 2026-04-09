import asyncio
from typing import AsyncGenerator
from pydantic_ai import Agent
from ui.renderer import console, stream_response
from ui.spinner import Spinner

spinner = Spinner(console)

_TOOL_RETRY_HINT = (
    "\n\n[Important: Use tool calls directly — do not write function syntax in text.]"
)


async def run_with_streaming(agent: Agent, prompt: str, context: str = "") -> str:
    """
    Run the agent and stream tokens live to the terminal.
    Shows tool activity in the spinner while tools are called.
    Returns the full assembled response text.
    Automatically retries once on failed_generation errors (Groq XML hallucination).
    """
    full_prompt = f"{context}\n\n{prompt}" if context else prompt
    full_response = ""

    for attempt in range(2):
        spinner.start("thinking")
        try:
            async with agent.run_stream(full_prompt) as result:
                await spinner.stop()

                async def live_tokens() -> AsyncGenerator[str, None]:
                    async for delta in result.stream_text(delta=True):
                        yield delta

                full_response = await stream_response(live_tokens())
            break  # success — exit retry loop

        except Exception as e:
            await spinner.stop()
            err_str = str(e)
            if "failed_generation" in err_str and attempt == 0:
                # Groq XML hallucination — retry once with an explicit hint
                full_prompt = full_prompt + _TOOL_RETRY_HINT
                continue
            console.print(f"[error]Error: {e}[/error]")
            break

    return full_response
