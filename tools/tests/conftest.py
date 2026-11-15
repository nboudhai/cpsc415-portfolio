"""Makes the modules in tools/ importable from tools/tests/ without installing anything.

sys.path is set here rather than in the test files, so that no test file needs
an import in the middle of its body. The fake key is set here too, so a
machine with no real key runs the same tests as one that has a real key in
the shell.
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
