"""The loop's tests: spec.md §"Week 8 behaviors" #1-6 (the loop-shaped half).

A scripted `FakeClient` returns whatever replies the test scripted, in order,
so each test says exactly what the model "did" and checks what the program
did about it. That is how you test a loop without paying for it, and how you
test the cases a real model only produces now and then.

The six tests below map one-to-one to behaviors #1-#6.

No key, no network, nothing billed.
"""
import json

from conftest import FakeResponse, FakeURLOpener, FakeClient, tool_call, answer
from loop import MAX_STEPS, check_answer, run


# ---- a helper for a faked GitHub response ----------------------------------------------------
def _ok_commits(shas=("1111111", "2222222", "3333333", "4444444", "5555555")):
    """A `FakeResponse` with a fake commits payload using the given short shas."""
    payload = [{"sha": s + "0" * (40 - len(s)),
                "commit": {"author": {"date": "2026-01-01T00:00:00Z"},
                           "message": "real commit"}}
               for s in shas]
    return FakeResponse(json.dumps(payload).encode())


# ---- Test 1: a single-shot caller — Behavior #1 (the happy path) -----------------------------
def test_a_single_shot_tool_call_returns_the_answer_then_stops(monkeypatch):
    """Behavior #1: one tool call, one result, one answer."""
    opener = FakeURLOpener()
    opener.response = _ok_commits()
    monkeypatch.setattr("urllib.request.urlopen", opener)

    fake = FakeClient([tool_call("recent_commits", '{"repo": "nboudhai/cpsc415-portfolio"}'),
                       answer("Here is what I worked on lately.")])
    answer_text, cost, trace = run(
        [{"role": "user", "content": "what did you work on lately?"}], client=fake)

    assert trace["stopped_by"] == "answer"
    assert trace["calls"] == ["recent_commits"]
    assert answer_text == "Here is what I worked on lately."
    # the tool result was sent back to the model as a "tool" role message
    second_turn = fake.sent[1]["messages"]
    tool_msg = second_turn[-1]
    assert tool_msg["role"] == "tool"
    assert json.loads(tool_msg["content"])["repo"] == "nboudhai/cpsc415-portfolio"


# ---- Test 2: a caller with bad arguments — Behavior #2 ---------------------------------------
def test_a_caller_with_bad_arguments_returns_an_error_result_and_carries_on(monkeypatch):
    """Behavior #2: arguments are validated before any handler runs; a bad call is a result."""
    opener = FakeURLOpener()
    opener.response = _ok_commits()
    monkeypatch.setattr("urllib.request.urlopen", opener)

    fake = FakeClient([tool_call("recent_commits", '{"repo": 42}'),
                       tool_call("recent_commits", '{"repo": "nboudhai/cpsc415-portfolio"}', "call_2"),
                       answer("OK.")])
    answer_text, cost, trace = run(
        [{"role": "user", "content": "what did you work on?"}], client=fake)

    # the loop carried on and answered
    assert trace["stopped_by"] == "answer"
    assert trace["calls"] == ["recent_commits", "recent_commits"]
    # the error result was sent back to the model on the first tool turn
    first_tool_msg = fake.sent[1]["messages"][-1]
    assert first_tool_msg["role"] == "tool"
    assert "must be a string" in json.loads(first_tool_msg["content"])["error"]


# ---- Test 3: an unknown-tool caller — Behavior #3 --------------------------------------------
def test_an_unknown_tool_returns_an_error_result(monkeypatch):
    """Behavior #3: the registry is the only source of allowed tools."""

    def explode(*args, **kwargs):
        raise AssertionError("no handler must be called for an unknown tool")

    monkeypatch.setattr("urllib.request.urlopen", explode)

    fake = FakeClient([tool_call("nonexistent_tool", "{}"),
                       answer("I can't retrieve that.")])
    answer_text, cost, trace = run(
        [{"role": "user", "content": "send me the resume"}], client=fake)

    assert trace["stopped_by"] == "answer"
    first_tool_msg = fake.sent[1]["messages"][-1]
    assert "unknown tool" in json.loads(first_tool_msg["content"])["error"]


# ---- Test 4: an endless caller — Behavior #4 -------------------------------------------------
def test_an_endless_caller_is_stopped_at_the_step_cap(monkeypatch):
    """Behavior #4: a model that keeps calling is stopped at the step cap; the answer is the program's."""
    opener = FakeURLOpener()
    opener.response = _ok_commits()
    monkeypatch.setattr("urllib.request.urlopen", opener)

    fake = FakeClient([tool_call("recent_commits",
                                 '{"repo": "nboudhai/cpsc415-portfolio"}',
                                 f"call_{i}") for i in range(MAX_STEPS + 2)])
    answer_text, cost, trace = run(
        [{"role": "user", "content": "what did you work on?"}], client=fake)

    assert trace["stopped_by"] == "cap"
    assert len(trace["calls"]) == MAX_STEPS
    assert f"{MAX_STEPS} steps" in answer_text   # the program's sentence, not the model's


# ---- Test 5: a caller that invokes `request_intro` — Behavior #5 -----------------------------
def test_request_intro_is_held_as_pending_and_nothing_leaves_the_process(tmp_path, monkeypatch):
    """Behavior #5: side effects are gated behind a person; the trace carries the pending record."""
    monkeypatch.chdir(tmp_path)

    fake = FakeClient([tool_call("request_intro",
                                 '{"email": "v@x.com", "message": "hi"}'),
                       answer("Noted; Nadia will need to confirm.")])
    answer_text, cost, trace = run(
        [{"role": "user", "content": "introduce me"}], client=fake)

    assert trace["stopped_by"] == "answer"
    assert trace["pending"] == [{"email": "v@x.com", "message": "hi"}]
    # nothing was written to disk
    assert list(tmp_path.iterdir()) == []


# ---- Test 6: an answer that names a sha and repo the tool never returned — Behavior #6 ------
def test_an_answer_naming_a_sha_or_repo_the_tool_did_not_return_is_flagged(monkeypatch):
    """Behavior #6: the answer cannot escape the tool's results; both invented sha and repo are flagged."""
    opener = FakeURLOpener()
    opener.response = _ok_commits(shas=("1111111", "2222222", "3333333", "4444444", "5555555"))
    monkeypatch.setattr("urllib.request.urlopen", opener)

    # model invents a sha (abcdef1) and a repo (cpsc415-week03) the tool did not return
    fake = FakeClient([tool_call("recent_commits", '{"repo": "nboudhai/cpsc415-portfolio"}'),
                       answer("I shipped abcdef1 on nboudhai/cpsc415-week03.")])
    answer_text, cost, trace = run(
        [{"role": "user", "content": "what did you ship?"}], client=fake)

    assert trace["verdict"]["supported"] is False
    unsupported_text = " ".join(trace["verdict"]["unsupported"])
    assert "abcdef1" in unsupported_text
    assert "cpsc415-week03" in unsupported_text
