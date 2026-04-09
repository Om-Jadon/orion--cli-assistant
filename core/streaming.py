import asyncio
from typing import AsyncGenerator
from pydantic_ai import Agent
from ui.renderer import console, stream_response
from ui.spinner import Spinner

spinner = Spinner(console)


async def run_with_streaming(agent: Agent, prompt: str, context: str = "") -> str:
    """
    Run the agent and stream tokens live to the terminal.
    Shows tool activity in the spinner while tools are called.
    Returns the full assembled response text.
    """
    full_prompt = f"{context}\n\n{prompt}" if context else prompt
    full_response = ""
    spinner.start("thinking")

    try:
        async with agent.run_stream(full_prompt) as result:
            async def live_tokens() -> AsyncGenerator[str, None]:
                await spinner.stop()
                async for delta in result.stream_text(delta=True):
                    yield delta

            full_response = await stream_response(live_tokens())

    except Exception as e:
        await spinner.stop()
        console.print(f"[error]Error: {e}[/error]")

    return full_response
