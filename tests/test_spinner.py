import asyncio
import pytest
from unittest.mock import MagicMock


def test_spinner_initial_state():
    from ui.spinner import Spinner
    console = MagicMock()
    s = Spinner(console)
    assert s._task is None
    assert s._label == "thinking"


@pytest.mark.asyncio
async def test_spinner_start_creates_task():
    from ui.spinner import Spinner
    console = MagicMock()
    s = Spinner(console)
    s.start("loading")
    assert s._task is not None
    assert not s._task.done()
    await s.stop()


@pytest.mark.asyncio
async def test_spinner_stop_cancels_task():
    from ui.spinner import Spinner
    console = MagicMock()
    s = Spinner(console)
    s.start()
    await s.stop()
    assert s._task.cancelled()


@pytest.mark.asyncio
async def test_spinner_update_changes_label():
    from ui.spinner import Spinner
    console = MagicMock()
    s = Spinner(console)
    s.start()
    s.update("processing")
    assert s._label == "processing"
    await s.stop()


@pytest.mark.asyncio
async def test_spinner_stop_without_start_is_safe():
    from ui.spinner import Spinner
    console = MagicMock()
    s = Spinner(console)
    await s.stop()  # should not raise
