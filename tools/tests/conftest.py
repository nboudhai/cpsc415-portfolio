"""Makes the modules in tools/ importable from tools/tests/ without installing anything.

sys.path is set here rather than in the test files, so that no test file needs
an import in the middle of its body. The fake key is set here too, so a
machine with no real key runs the same tests as one that has a real key in
the shell.

`FakeURLOpener` and `FakeResponse` are fakes for `urllib.request.urlopen`: they
record every call and return whatever the test scripted, so the no-key suite
never reaches GitHub.

`FakeClient`, `tool_call`, and `answer` are a scripted fake model: they
implement the same tool-calling shape as the real one (a `chat.send` that
takes `model`, `messages`, `tools`, `max_tokens`, and returns a SimpleNamespace
with `choices[0].message.{content, tool_calls}`, `choices[0].finish_reason`,
and `usage.cost`), so the loop's tests run without paying for a chat call.
"""
import copy
import sys
from pathlib import Path
from types import SimpleNamespace as NS

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


# ---- the scripted fake model: same tool-calling shape as the real one -----------------------
def tool_call(name, arguments, call_id="call_1"):
    """One reply in which the model asks for one tool. `arguments` is a JSON string."""
    tc = NS(id=call_id, function=NS(name=name, arguments=arguments))
    msg = NS(content="", tool_calls=[tc])
    return NS(choices=[NS(message=msg, finish_reason="tool_calls")],
              usage=NS(cost=0.0001))


def answer(text):
    """One reply in which the model answers without calling a tool."""
    msg = NS(content=text, tool_calls=None)
    return NS(choices=[NS(message=msg, finish_reason="stop")],
              usage=NS(cost=0.0001))


class FakeClient:
    """A scripted fake client: returns the next reply in order and records every call.

    Mirrors the real client's shape: `client.chat.send(model=..., messages=..., tools=..., max_tokens=...)`.
    """

    def __init__(self, replies):
        self.replies = list(replies)
        self.sent: list[dict] = []

    @property
    def chat(self):
        return self

    def send(self, **kwargs):
        self.sent.append(copy.deepcopy(kwargs))
        if not self.replies:
            raise AssertionError("the loop asked the model again after the script ran out")
        return self.replies.pop(0)
