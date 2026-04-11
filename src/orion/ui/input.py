from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings
from orion.config import HISTORY_FILE

def build_session() -> PromptSession:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    bindings = KeyBindings()

    @bindings.add("c-l")
    def clear_screen(event):
        event.app.renderer.clear()

    @bindings.add("c-c")
    def interrupt(event):
        event.app.exit(exception=KeyboardInterrupt())

    return PromptSession(
        history=FileHistory(str(HISTORY_FILE)),
        auto_suggest=AutoSuggestFromHistory(),
        key_bindings=bindings,
        multiline=False,
        enable_open_in_editor=True,
    )

def get_prompt_text() -> HTML:
    return HTML('<ansiblue>❯</ansiblue> ')

async def get_input(session: PromptSession) -> str:
    return await session.prompt_async(get_prompt_text())
