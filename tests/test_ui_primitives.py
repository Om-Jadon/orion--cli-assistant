import asyncio
import pytest
from unittest.mock import MagicMock

# --- Renderer Tests ---

def test_mocha_theme_has_required_keys():
    from orion.ui.renderer import MOCHA
    required = {"user", "assistant", "orion", "dim", "thinking", "success", "warning", "error", "accent", "border", "muted"}
    assert required.issubset(set(MOCHA.styles.keys()))


def test_console_width_capped_at_100():
    from orion.ui.renderer import console
    assert console.width <= 100


def test_print_user_does_not_raise():
    from orion.ui.renderer import print_user
    print_user("hello world")  # should not raise


def test_print_separator_does_not_raise():
    from orion.ui.renderer import print_separator
    print_separator()  # should not raise


@pytest.mark.asyncio
async def test_stream_response_returns_full_content():
    from orion.ui.renderer import stream_response

    async def gen():
        for word in ["Hello", " ", "world"]:
            yield word

    result = await stream_response(gen())
    assert result == "Hello world"


@pytest.mark.asyncio
async def test_stream_response_empty_gen_returns_empty_string():
    from orion.ui.renderer import stream_response

    async def gen():
        return
        yield  # make it an async generator

    result = await stream_response(gen())
    assert result == ""


# --- Spinner Tests ---

def test_spinner_initial_state():
    from orion.ui.spinner import Spinner
    console = MagicMock()
    s = Spinner(console)
    assert s._task is None
    assert s._label == "thinking"


@pytest.mark.asyncio
async def test_spinner_start_creates_task():
    from orion.ui.spinner import Spinner
    console = MagicMock()
    s = Spinner(console)
    s.start("loading")
    assert s._task is not None
    assert not s._task.done()
    await s.stop()


@pytest.mark.asyncio
async def test_spinner_stop_cancels_task():
    from orion.ui.spinner import Spinner
    console = MagicMock()
    s = Spinner(console)
    s.start()
    await s.stop()
    assert s._task.cancelled()


@pytest.mark.asyncio
async def test_spinner_update_changes_label():
    from orion.ui.spinner import Spinner
    console = MagicMock()
    s = Spinner(console)
    s.start()
    s.update("processing")
    assert s._label == "processing"
    await s.stop()


@pytest.mark.asyncio
async def test_spinner_stop_without_start_is_safe():
    from orion.ui.spinner import Spinner
    console = MagicMock()
    s = Spinner(console)
    await s.stop()  # should not raise


def test_spinner_render_frame_pads_shorter_labels():
    from orion.ui.spinner import Spinner

    console = MagicMock()
    console.width = 30
    s = Spinner(console)
    s.update("thinking")

    frame = s._render_frame("⠋")

    assert frame.plain.startswith("◆ ⠋ thinking")
    assert len(frame.plain) >= console.width
