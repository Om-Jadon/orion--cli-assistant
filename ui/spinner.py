import asyncio
import itertools
import sys
from rich.console import Console

BRAILLE = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
THINKING_COLOR = "\033[3;38;2;88;91;112m"  # italic #585B70 (Mocha thinking)
RESET = "\033[0m"

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
        sys.stdout.write("\r" + " " * 60 + "\r\n")
        sys.stdout.flush()

    async def _spin(self):
        for frame in itertools.cycle(BRAILLE):
            sys.stdout.write(f"\r{THINKING_COLOR}{frame} {self._label}{RESET}")
            sys.stdout.flush()
            await asyncio.sleep(0.08)
