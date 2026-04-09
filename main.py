import asyncio
import sys
from ui.renderer import console, print_user, print_separator
from ui.input import build_session, get_input
from ui.startup import show_startup, prewarm_model
from core.agent import build_agent
from core.streaming import run_with_streaming
from config import MODEL

think_mode = False
agent = build_agent(think=think_mode)


async def main():
    global agent, think_mode

    # One-shot: orion open the latest markiplier video
    if len(sys.argv) > 1 and sys.stdin.isatty():
        query = " ".join(sys.argv[1:])
        await run_once(query)
        return

    # Pipe mode: cat log.txt | orion "what went wrong?"
    if not sys.stdin.isatty():
        piped_input = sys.stdin.read()
        user_query = sys.argv[1] if len(sys.argv) > 1 else "Analyze this:"
        full_query = f"{user_query}\n\n```\n{piped_input[:4000]}\n```"
        response = await run_with_streaming(agent, full_query)
        print(response)
        return

    show_startup(console, MODEL)
    await prewarm_model(MODEL)
    session = build_session()

    while True:
        try:
            user_input = await get_input(session, MODEL)
            if not user_input.strip():
                continue
            if user_input.strip() in ("/exit", "/quit", "exit", "quit"):
                break
            if user_input.startswith("/"):
                await handle_slash(user_input)
                continue

            await run_once(user_input)

        except KeyboardInterrupt:
            console.print("\n[#6C7086]Interrupted.[/#6C7086]")
        except EOFError:
            break


async def run_once(query: str):
    print_user(query)
    await run_with_streaming(agent, query)
    print_separator()


async def handle_slash(cmd: str):
    # Slash commands wired fully in Stage 7
    console.print(f"[dim]{cmd} — slash commands active in Stage 7[/dim]")


if __name__ == "__main__":
    asyncio.run(main())
