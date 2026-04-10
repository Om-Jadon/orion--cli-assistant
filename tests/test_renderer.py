import pytest


def test_mocha_theme_has_required_keys():
    from ui.renderer import MOCHA
    required = {"user", "assistant", "orion", "dim", "thinking", "success", "warning", "error", "accent", "border", "muted"}
    assert required.issubset(set(MOCHA.styles.keys()))


def test_console_width_capped_at_100():
    from ui.renderer import console
    assert console.width <= 100


def test_print_user_does_not_raise():
    from ui.renderer import print_user
    print_user("hello world")  # should not raise


def test_print_separator_does_not_raise():
    from ui.renderer import print_separator
    print_separator()  # should not raise


@pytest.mark.asyncio
async def test_stream_response_returns_full_content():
    from ui.renderer import stream_response

    async def gen():
        for word in ["Hello", " ", "world"]:
            yield word

    result = await stream_response(gen())
    assert result == "Hello world"


@pytest.mark.asyncio
async def test_stream_response_empty_gen_returns_empty_string():
    from ui.renderer import stream_response

    async def gen():
        return
        yield  # make it an async generator

    result = await stream_response(gen())
    assert result == ""
