import asyncio
import itertools
from rich.console import Console

BRAILLE = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

class Spinner:
    """Asyncio-native spinner — no threads, no race conditions with asyncio."""

    def __init__(self, console: Console):
        self.console = console
        self._label = "thinking"
        self._task: asyncio.Task | None = None

    def start(self, label: str = "thinking"):
        """Call from async context. Creates a background asyncio task."""
        if self._task and not self._task.done():
            return
        self._label = label
        self._task  = asyncio.create_task(self._spin())

    def update(self, label: str):
        self._label = label

    async def stop(self):
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.console.print("\r" + " " * 60 + "\r", end="")

    async def _spin(self):
        for frame in itertools.cycle(BRAILLE):
            self.console.print(
                f"\r[thinking]{frame} {self._label}[/thinking]",
                end="", highlight=False
            )
            await asyncio.sleep(0.08)
