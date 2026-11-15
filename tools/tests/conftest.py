"""Makes the modules in tools/ importable from tools/tests/ without installing anything.

sys.path is set here rather than in the test files, so that no test file needs
an import in the middle of its body. The fake key is set here too, so a
machine with no real key runs the same tests as one that has a real key in
the shell.

`FakeURLOpener` and `FakeResponse` are fakes for `urllib.request.urlopen`: they
record every call and return whatever the test scripted, so the no-key suite
never reaches GitHub.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FAKE_KEY = "test-not-a-real-key"


@pytest.fixture(autouse=True)
def a_fake_key(monkeypatch):
    """A value, not a credential: tests get this, and no provider call is ever made."""
    monkeypatch.setenv("OPENROUTER_API_KEY", FAKE_KEY)


class FakeResponse:
    """A fake HTTP response: supports the context manager and `.read()` interface."""

    def __init__(self, body: bytes = b"[]") -> None:
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self) -> bytes:
        return self._body


class FakeURLOpener:
    """A fake `urllib.request.urlopen`: records every call and returns whatever the test
    scripted. Install with `monkeypatch.setattr("urllib.request.urlopen", opener)`.
    """

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.response = None
        self.error: Exception | None = None

    def __call__(self, request, timeout=None, **kwargs):
        self.calls.append({
            "url": request.full_url,
            "headers": dict(request.headers),
            "timeout": timeout,
        })
        if self.error is not None:
            raise self.error
        return self.response
