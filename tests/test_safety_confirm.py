from safety.confirm import requires_confirmation


def test_requires_confirmation_detects_destructive_terms():
    assert requires_confirmation("delete this file") is True
    assert requires_confirmation("overwrite notes.txt") is True


def test_requires_confirmation_ignores_safe_text():
    assert requires_confirmation("list files in downloads") is False
    assert requires_confirmation("read this file") is False
