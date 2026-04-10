import asyncio
import sys
import uuid
from ui.renderer import console, print_user, print_separator
from ui.input import build_session, get_input
from ui.startup import show_startup, prewarm_model
from core.agent import build_agent
from core.streaming import run_with_streaming
from core.context import build_context
from memory.db import get_connection
from memory.store import save_turn
from memory.extractor import extract_and_store
from config import MODEL, MODEL_STRING

think_mode = False
agent = build_agent(think=think_mode)
session_id = str(uuid.uuid4())
conn = get_connection()


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

    if "--init" in sys.argv:
        from memory.indexer import scan_home
        console.print("[accent]Building file index...[/accent]")
        scan_home(conn, verbose=True)
        console.print("[success]Done.[/success]")
        return

    display_model = MODEL_STRING or MODEL
    show_startup(console, display_model)
    await prewarm_model(MODEL)
    session = build_session()

    while True:
        try:
            user_input = await get_input(session)
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

    save_turn(conn, session_id, "user", query)
    extract_and_store(conn, query)

    context = await build_context(conn, query, session_id)
    response = await run_with_streaming(agent, query, context=context)

    if response:
        save_turn(conn, session_id, "assistant", response)

    print_separator()


async def handle_slash(cmd: str):
    parts = cmd.strip().split()
    command = parts[0].lower()

    if command == "/help":
        console.print()
        console.print("  [accent]Slash commands[/accent]")
        console.print()
        console.print("  [dim]/help[/dim]       show this message")
        console.print("  [dim]/think[/dim]      toggle chain-of-thought reasoning")
        console.print("  [dim]/clear[/dim]      clear conversation history")
        console.print("  [dim]/exit[/dim]       quit orion")
        console.print()
    elif command == "/clear":
        global session_id
        session_id = str(uuid.uuid4())
        console.print("[dim]Conversation cleared.[/dim]")
    else:
        console.print(f"[error]Unknown command:[/error] {cmd}. Type /help for available commands.")


if __name__ == "__main__":
    asyncio.run(main())
