import asyncio
import logging
import sys
import uuid
from ui.renderer import console, print_user, print_separator
from ui.input import build_session, get_input
from ui.startup import show_startup, prewarm_model
from ui import slash
from core.agent import build_agent
from core.streaming import run_with_streaming
from core.context import build_context
from memory.db import get_connection
from memory.store import save_turn
from memory.extractor import extract_and_store
from config import MODEL, MODEL_STRING, ORION_DIR
from tools import files as file_tools
from safety import confirm as safety_confirm

ORION_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(level=logging.DEBUG, filename=str(ORION_DIR / "debug.log"))

state = slash.RuntimeState(
    agent=build_agent(think=False),
    think_mode=False,
    session_id=str(uuid.uuid4()),
)
conn = get_connection()
file_tools.set_connection(conn)


def _run_background_scan():
    from memory.indexer import scan_home

    scan_conn = get_connection()
    try:
        scan_home(scan_conn)
    finally:
        scan_conn.close()


def _on_background_scan_done(task: asyncio.Task):
    try:
        task.result()
    except asyncio.CancelledError:
        logging.debug("Background home scan task cancelled.")
    except Exception:
        logging.exception("Background home scan task failed.")


async def main():
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
        safety_confirm.reset_turn_state()
        save_turn(conn, state.session_id, "user", full_query)
        extract_and_store(conn, full_query)
        context = await build_context(conn, full_query, state.session_id)
        response = await run_with_streaming(state.agent, full_query, context=context)
        if response:
            save_turn(conn, state.session_id, "assistant", response)
        print(response)
        return

    display_model = MODEL_STRING or MODEL
    show_startup(console, display_model)
    await prewarm_model(MODEL)
    session = build_session()

    scan_task = asyncio.create_task(asyncio.to_thread(_run_background_scan), name="background-home-scan")
    scan_task.add_done_callback(_on_background_scan_done)

    while True:
        try:
            user_input = await get_input(session)
            stripped = user_input.strip()
            if not stripped:
                continue
            if stripped in ("exit", "quit"):
                break
            if stripped.startswith("/"):
                await handle_slash(stripped)
                continue

            await run_once(stripped)

        except KeyboardInterrupt:
            console.print("\n[#6C7086]Interrupted.[/#6C7086]")
        except EOFError:
            break


async def run_once(query: str):
    safety_confirm.reset_turn_state()
    print_user(query)

    save_turn(conn, state.session_id, "user", query)
    extract_and_store(conn, query)

    context = await build_context(conn, query, state.session_id)
    response = await run_with_streaming(state.agent, query, context=context)

    if response:
        save_turn(conn, state.session_id, "assistant", response)

    print_separator()


async def handle_slash(cmd: str):
    await slash.handle_slash(
        cmd,
        state=state,
        conn=conn,
        console=console,
        build_agent=build_agent,
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        conn.close()
