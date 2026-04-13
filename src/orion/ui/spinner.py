import asyncio
import itertools
from rich.console import Console
from rich.text import Text

BRAILLE = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

_ACTIVE_SPINNER = None

async def stop_active_spinner():
    global _ACTIVE_SPINNER
    if _ACTIVE_SPINNER is not None:
        await _ACTIVE_SPINNER.stop()

def update_label(label: str):
    global _ACTIVE_SPINNER
    if _ACTIVE_SPINNER is not None:
        _ACTIVE_SPINNER.update(label)

class Spinner:
    """Asyncio-native spinner using Rich for theme-aware rendering."""

    def __init__(self, console: Console):
        self.console = console
        self._label = "thinking"
        self._task: asyncio.Task | None = None

    def start(self, label: str = "thinking"):
        """Call from async context. Creates a background asyncio task."""
        global _ACTIVE_SPINNER
        if self._task and not self._task.done():
            return
        self._label = label
        self._task = asyncio.create_task(self._spin())
        _ACTIVE_SPINNER = self

    def update(self, label: str):
        self._label = label

    def _render_frame(self, frame: str) -> Text:
        text = Text()
        text.append("◆ ", style="accent")
        text.append(frame + " ", style="dim")
        text.append(self._label, style="dim italic")
        padding = max(0, self.console.width - len(text.plain))
        if padding:
            text.append(" " * padding)
        return text

    async def stop(self):
        global _ACTIVE_SPINNER
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        if _ACTIVE_SPINNER is self:
            _ACTIVE_SPINNER = None
            
        # Cleanly clear the line
        self.console.print("\r" + " " * self.console.width + "\r", end="")

    async def _spin(self):
        try:
            for frame in itertools.cycle(BRAILLE):
                # Pad to console width so shorter labels fully overwrite longer ones.
                self.console.print(self._render_frame(frame), end="\r")
                await asyncio.sleep(0.08)
        except asyncio.CancelledError:
            pass
