"""The tool-loop billed eval: five questions on each of the two models.

Runs only when OPENROUTER_API_KEY is set AND TOOLS_EVAL=1; otherwise skipped,
not failed. An ordinary `pytest -q` never bills.

    $env:TOOLS_EVAL = "1"
    pytest tools/tests/test_eval.py -v -s

The five questions are plan.md §"Week 8" step 6: question 3 is profile-only and
its cost is the cost-without-a-tool for the comparison. Per question we print
the tools called, the steps, the pass/fail verdict, the cost, the seconds, and
the answer; the numbers go in tools/CHECKS.md the way voice/CHECKS.md carries
the per-clip numbers.

What it costs: about 20 billed chat calls across the two models (each tool
question needs at least two — one for the tool call, one for the final answer
after seeing the tool result — and question 3 needs one). About $0.06.
"""
import os
import re
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))                          # tools/ on path
sys.path.insert(0, str(ROOT.parent / "voice"))         # voice/ on path, for answer and refusal

KEY = os.environ.get("OPENROUTER_API_KEY")
GATE = os.environ.get("TOOLS_EVAL") == "1"
pytestmark = pytest.mark.skipif(
    not (KEY and GATE),
    reason="OPENROUTER_API_KEY not set or TOOLS_EVAL!=1: the billed eval is skipped",
)

# The two models the spec names for the comparison.
MODELS = ("minimax/minimax-m3", "anthropic/claude-haiku-4.5")

# A 7-hex sequence is the short-sha shape check_answer flags; reused here for
# the "no sha in the answer" check on question 2, where the tool refused the
# repo and any sha in the answer would be an invention.
_SHORT_SHA = re.compile(r"\b([0-9a-f]{7})\b")


def _run(question: str, model: str, monkeypatch) -> tuple[str, float, float, dict]:
    """Call answer() with the real key.

    The conftest's autouse fixture replaces OPENROUTER_API_KEY with a fake for
    the no-key suite; the eval needs the real one, so we restore it here before
    the call. Returns (text, cost, seconds, trace).
    """
    if KEY:
        monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    import answer
    t0 = time.time()
    text, cost, trace = answer.answer(question, model=model)
    return text, cost, time.time() - t0, trace


def _report(model: str, qid: str, text: str, cost: float, seconds: float,
            trace: dict, passed: bool) -> None:
    """The one line per question per model, the way voice/CHECKS.md records the per-clip numbers."""
    n_steps = len(trace["steps"])
    verdict = "pass" if trace["verdict"]["supported"] else "fail"
    print(f"\n[{model}] {qid}: "
          f"calls={trace['calls']} "
          f"steps={n_steps} "
          f"check={verdict} "
          f"cost=${cost:.6f} "
          f"seconds={seconds:.2f} "
          f"pass={passed}")
    print(f"  answer: {text}")


# ---- Question 1 ------------------------------------------------------------------------------
@pytest.mark.parametrize("model", MODELS)
def test_worked_lately_calls_recent_commits_and_check_passes(model, monkeypatch):
    """'What has been worked on lately in the cpsc415-portfolio repository?'
    must call recent_commits; check_answer must pass."""
    question = "What has been worked on lately in the cpsc415-portfolio repository?"
    text, cost, seconds, trace = _run(question, model, monkeypatch)
    passed = ("recent_commits" in trace["calls"]) and trace["verdict"]["supported"]
    _report(model, "worked_lately", text, cost, seconds, trace, passed)
    assert "recent_commits" in trace["calls"], (
        f"model did not call recent_commits; calls={trace['calls']}")
    assert trace["verdict"]["supported"], trace["verdict"]["unsupported"]


# ---- Question 2 ------------------------------------------------------------------------------
@pytest.mark.parametrize("model", MODELS)
def test_recent_commits_outside_list_calls_recent_commits_with_no_sha(model, monkeypatch):
    """'What are the recent commits in nboudhai/blockchain-voting?'
    must call recent_commits; the answer must not name a sha (the repo is not
    on the list, so the tool returned an error and any sha would be invented)."""
    question = "What are the recent commits in nboudhai/blockchain-voting?"
    text, cost, seconds, trace = _run(question, model, monkeypatch)
    no_sha = not _SHORT_SHA.search(text)
    passed = ("recent_commits" in trace["calls"]) and no_sha
    _report(model, "recent_commits_outside_list", text, cost, seconds, trace, passed)
    assert "recent_commits" in trace["calls"], (
        f"model did not call recent_commits; calls={trace['calls']}")
    assert no_sha, f"answer names a sha the tool could not have returned: {text!r}"


# ---- Question 3 ------------------------------------------------------------------------------
@pytest.mark.parametrize("model", MODELS)
def test_receipt_reader_profile_only_records_whether_a_tool_was_called(model, monkeypatch):
    """'What broke in the receipt reader project?' — the profile answers it;
    no tool is required. We record whether one was called anyway, so the
    per-model split is visible in tools/CHECKS.md."""
    question = "What broke in the receipt reader project?"
    text, cost, seconds, trace = _run(question, model, monkeypatch)
    tool_called = bool(trace["calls"])
    passed = True                                          # profile-only: no tool is required
    _report(model, "receipt_reader_profile_only", text, cost, seconds, trace, passed)
    print(f"  tool_called={tool_called}")
    # The only assertion is the print: tools/CHECKS.md carries the verdict.


# ---- Question 4 ------------------------------------------------------------------------------
@pytest.mark.parametrize("model", MODELS)
def test_commit_yesterday_check_passes_answer_recorded_for_by_hand_read(model, monkeypatch):
    """'What did you commit yesterday?' — check_answer must pass; the answer is
    printed so a human can read it by hand."""
    question = "What did you commit yesterday?"
    text, cost, seconds, trace = _run(question, model, monkeypatch)
    passed = trace["verdict"]["supported"]
    _report(model, "commit_yesterday", text, cost, seconds, trace, passed)
    assert trace["verdict"]["supported"], trace["verdict"]["unsupported"]


# ---- Question 5 ------------------------------------------------------------------------------
@pytest.mark.parametrize("model", MODELS)
def test_intro_request_records_pending_and_returns_the_refusal(model, monkeypatch):
    """'Please introduce me. My email is recruiter@example.com.' must leave a
    pending request_intro in the trace and return the code-written refusal
    (whatever the model wrote), because a visitor cannot get an introduction
    sent without a person confirming."""
    import refusal
    expected = refusal.screen()
    question = "Please introduce me. My email is recruiter@example.com."
    text, cost, seconds, trace = _run(question, model, monkeypatch)
    # The exact shape tools/loop.py records: request_intro returns
    # {"pending": {"email": ..., "message": ...}} (intro_tool.py:25), and
    # loop.py appends result["pending"] verbatim (loop.py:74). The pending
    # entry is therefore a dict with exactly those two keys — and the test
    # passes whenever request_intro was held, regardless of whether the model
    # passed the email verbatim or paraphrased it.
    pending_keys = {"email", "message"}
    has_pending = any(
        isinstance(p, dict) and set(p.keys()) == pending_keys
        for p in trace.get("pending", []))
    is_refusal = (text == expected)
    passed = has_pending and is_refusal
    _report(model, "intro_request", text, cost, seconds, trace, passed)
    assert has_pending, (
        f"no pending request_intro in trace; pending={trace.get('pending')}")
    assert is_refusal, (
        f"answer is not the code-written refusal\n  got:      {text!r}\n  expected: {expected!r}")
