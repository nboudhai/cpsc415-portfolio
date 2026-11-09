"""The key never reaches a log, a record, or a commit.

One rule, one place. A provider can hand back the key in its own words, and
this code writes those words to the terminal and to files that get committed —
so every provider message goes through redact() on its way out.
"""
import os
import re

REDACTED = "[redacted]"
_KEY = re.compile(r"sk-or-v1-[0-9a-fA-F]{16,}")


def redact(text: str) -> str:
    """The key out of the text, whatever shape it arrived in.

    The key in the environment is replaced exactly, and anything that looks
    like an OpenRouter key is replaced whatever the environment says, so a
    message that arrives on a machine without the key is still clean.
    """
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        text = text.replace(key, REDACTED)
    return _KEY.sub(REDACTED, text)
