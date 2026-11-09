"""The one answer function: the typed route and the voice route both call it.

The chatbot itself is not built yet, so this answers from the course example's
profile (Sam Rivera) while the refusal points at Nadia. The prompt is
name-agnostic and asks the model for OUT_OF_SCOPE instead of the refusal text:
the refusal is written by code, so it is the same message every time, and the
model cannot splice it into a sentence of its own.

    python answer.py --ask "What broke in your receipt reader project?" --out answer.txt
"""
import argparse
import json
import os
import pathlib
import re
import sys

import refusal
from openrouter import OpenRouter

HERE = pathlib.Path(__file__).resolve().parent
STAND_IN = HERE.parent.parent / "ai-integration-course" / "examples" / "voice-loop" / "profile.json"
DEFAULT_MODEL = "minimax/minimax-m3"
MAX_TOKENS = 1500
OUT_OF_SCOPE = "OUT_OF_SCOPE"

SYSTEM = """You answer a visitor's questions about one person, from the profile below and nothing else.
Rules: shipped work is in "projects" and "skills_shipped"; anything in "not_yet" is something the
person has deliberately not done, and you say so plainly. If the profile does not cover the
question, reply with exactly OUT_OF_SCOPE and nothing else. Never claim experience the profile
does not record. Answer in two or three spoken sentences: this answer will be read aloud, so no
lists, no markdown, no URLs.

PROFILE:
"""

_URL = re.compile(r"https?://\S+")
_MARKDOWN = re.compile(r"[*_`]+")
_LIST_MARK = re.compile(r"^\s*[-•]\s+", re.MULTILINE)


def system_prompt() -> str:
    """The stand-in's system prompt, with the stand-in's profile inlined."""
    profile = json.loads(STAND_IN.read_text(encoding="utf-8"))
    return SYSTEM + json.dumps(profile, indent=1)


def _client() -> OpenRouter:
    """The client is built when a call is about to be made, never at import: the no-key
    tests import this module and fake the call."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set; nothing was billed.")
    return OpenRouter(api_key=key)


def chat(messages: list[dict], model: str = DEFAULT_MODEL, client=None) -> tuple[str, float | None]:
    """One chat call: the reply, and what it cost."""
    reply = (client or _client()).chat.send(model=model, max_tokens=MAX_TOKENS, messages=messages)
    text = (reply.choices[0].message.content or "").strip()
    return text, getattr(reply.usage, "cost", None)


def apply_refusal(reply: str) -> str:
    """A reply containing OUT_OF_SCOPE anywhere is replaced whole by the refusal.

    Never spliced: the model does not write the message, so it cannot end up in
    the middle of a sentence of its own.
    """
    return refusal.screen() if OUT_OF_SCOPE in reply else reply


def for_speaking(text: str) -> str:
    """What the speech call says.

    The refusal loses its URL — a URL cannot be heard, and the link is on the
    page. Any other answer loses its markdown and its URLs for the same reason.
    """
    if text == refusal.screen():
        return refusal.spoken()
    return _LIST_MARK.sub("", _MARKDOWN.sub("", _URL.sub("the link is on screen", text))).strip()


def answer(question: str, model: str = DEFAULT_MODEL, client=None) -> tuple[str, float | None]:
    """The chatbot's answer: one chat call, then the refusal if the model said OUT_OF_SCOPE."""
    reply, cost = chat([{"role": "system", "content": system_prompt()},
                        {"role": "user", "content": question}], model, client)
    if not reply:
        reply = "I couldn't put an answer together. Please ask again."
    return apply_refusal(reply), cost


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ask the stand-in chatbot one question.")
    parser.add_argument("--ask", required=True, help="the question")
    parser.add_argument("--out", type=pathlib.Path, help="write the answer text here")
    args = parser.parse_args()
    try:
        text, cost = answer(args.ask)
    except RuntimeError as error:
        sys.exit(str(error))
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text)
    print(f"cost ${cost}")
