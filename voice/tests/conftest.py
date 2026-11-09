"""Makes the modules in voice/ importable from voice/tests/ without installing anything.

sys.path is set here rather than in the test files, so that no test file needs an
import in the middle of its body.

The fake key is set here too, for the same reason: no test may depend on the
shell. A machine with no key set runs the same tests as one that has a key,
and a test that wants no key at all removes this one again. No provider call
is ever made — every one of them is faked — so the key is never used.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FAKE_KEY = "test-not-a-real-key"


@pytest.fixture(autouse=True)
def a_fake_key(monkeypatch):
    """The key the command lines ask for before they do anything.

    It is a value, not a credential: the tests that need a key get this one,
    and the test that needs no key removes it with monkeypatch.delenv.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", FAKE_KEY)
