import asyncio
import sys
from ui.renderer import console, print_user, print_separator, stream_response
from ui.input import build_session, get_input
from ui.startup import show_startup, prewarm_model
from config import MODEL

async def main():
    # One-shot mode: orion open the latest markiplier video
    if len(sys.argv) > 1 and sys.stdin.isatty():
        query = " ".join(sys.argv[1:])
        await run_once(query)
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

            await run_once(user_input)

        except KeyboardInterrupt:
            console.print("\n[#6C7086]Interrupted.[/#6C7086]")
        except EOFError:
            break

async def run_once(query: str):
    print_user(query)

    # Stages 1–2: echo back. Replaced with real agent in Stage 3.
    async def fake_stream():
        for word in f"You said: {query}".split():
            yield word + " "

    await stream_response(fake_stream())
    print_separator()

if __name__ == "__main__":
    asyncio.run(main())
