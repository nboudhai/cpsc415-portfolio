"""Makes the modules in voice/ importable from voice/tests/ without installing anything.

sys.path is set here rather than in the test files, so that no test file needs an
import in the middle of its body.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
