"""The tool loop: the model asks, the program decides, the model answers from what it got back.

The loop takes the conversation so far, sends it to the model, takes the tool
calls the model asks for, validates them against the registered schema, runs
the handler or returns an error result, and feeds the result back to the
model as the next message. The loop stops when the model answers without
calling a tool, or at `MAX_STEPS`, whichever comes first.

`check_answer` is the named function that scans the answer for short shas
and repository names the tools did not return; the verdict field in the
trace is its return value.

The typed and voice paths call this loop through `voice/answer.py`'s `answer()`.
"""
import json
import os
import re
import time

import registry

DEFAULT_MODEL = "minimax/minimax-m3"
MAX_STEPS = 4


def run(messages: list[dict], *, tools: list[dict] | None = None,
        model: str = DEFAULT_MODEL, max_steps: int = MAX_STEPS,
        client=None, allow_side_effects: bool = False
        ) -> tuple[str, float, dict]:
    """Run the loop. Returns `(answer_text, total_cost, trace)`.

    The trace carries every step's tool name, arguments, and result or error;
    the list of tools called; any pending records; how the loop stopped; and
    the verdict from `check_answer`. `run()` does not know about refusals —
    that substitution happens in `voice/answer.py`.
    """
    if tools is None:
        tools = registry.TOOLS
    if client is None:
        from openrouter import OpenRouter
        client = OpenRouter(api_key=os.environ["OPENROUTER_API_KEY"])

    working = [dict(m) for m in messages]            # do not mutate the caller's list
    cost = 0.0
    pending: list[dict] = []
    steps: list[dict] = []
    stopped_by = "answer"
    answer_text = ""

    for step in range(1, max_steps + 1):
        t0 = time.time()
        response = client.chat.send(model=model, messages=working,
                                    tools=tools, max_tokens=1500)
        cost += getattr(response.usage, "cost", None) or 0.0
        msg = response.choices[0].message
        calls = msg.tool_calls or []
        if not calls:                                # the model answered: the loop is done
            answer_text = (msg.content or "").strip()
            steps.append({"step": step, "answer": answer_text,
                          "seconds": round(time.time() - t0, 2),
                          "finish": response.choices[0].finish_reason})
            stopped_by = "answer"
            break
        # the model asked for one or more tools: record the request exactly as it was made
        working.append({"role": "assistant", "content": msg.content or "",
                        "tool_calls": [{"id": tc.id, "type": "function",
                                        "function": {"name": tc.function.name,
                                                     "arguments": tc.function.arguments}}
                                       for tc in calls]})
        for tc in calls:
            result = registry.run_tool(tc.function.name, tc.function.arguments,
                                       allow_side_effects=allow_side_effects)
            if "pending" in result:
                pending.append(result["pending"])
            steps.append({"step": step, "tool": tc.function.name,
                          "arguments": tc.function.arguments, "result": result,
                          "seconds": round(time.time() - t0, 2)})
            working.append({"role": "tool", "tool_call_id": tc.id,
                            "content": json.dumps(result)})
    else:
        # the cap: the model never stopped asking. The answer is what the program says.
        answer_text = f"I couldn't finish answering that in {max_steps} steps."
        stopped_by = "cap"

    trace = {"steps": steps,
             "calls": [s["tool"] for s in steps if "tool" in s],
             "pending": pending,
             "stopped_by": stopped_by,
             "verdict": check_answer(answer_text, steps)}
    return answer_text, round(cost, 6), trace


# ---- the named check: every short sha and repository name in the answer must have come back --
_SHORT_SHA = re.compile(r"\b([0-9a-f]{7})\b")
_REPO_NAME = re.compile(r"\b(cpsc415-(?:portfolio|week0[1-5]))\b")


def check_answer(answer_text: str, steps: list[dict]) -> dict:
    """Plain code looking for claims the tools did not support.

    A short sha (7 hex chars, GitHub's short format) or a repository name
    (one of the six on record) in the answer must have come back from a tool
    result; a repository name in a not-on-record error's `repos_on_record`
    list counts as returned. The check cannot see an invented commit
    subject, and `tools/CHECKS.md` says so.
    """
    seen_shas: set[str] = set()
    seen_repos: set[str] = set()
    for step in steps:
        if step.get("tool") != "recent_commits":
            continue
        result = step.get("result", {})
        for commit in result.get("commits", []):
            sha = commit.get("sha", "")
            if len(sha) >= 7:
                seen_shas.add(sha[:7])
        repo = result.get("repo")
        if repo:
            _, _, bare = repo.partition("/")
            if bare:
                seen_repos.add(bare)
        for bare in result.get("repos_on_record", []):
            seen_repos.add(bare)

    unsupported = []
    for name in _REPO_NAME.findall(answer_text):
        if name not in seen_repos:
            unsupported.append(f"repository {name!r} mentioned without a tool result")
    for sha in _SHORT_SHA.findall(answer_text):
        if sha not in seen_shas:
            unsupported.append(f"sha {sha!r} mentioned without a tool result")

    return {"supported": not unsupported, "unsupported": unsupported}
