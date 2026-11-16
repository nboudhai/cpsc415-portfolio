# tools/CHECKS.md

## 1. Stand-in profile, real GitHub

The chatbot's profile is still the Sam Rivera stand-in from `voice/answer.py`
(the chatbot itself isn't built yet). The `recent_commits` tool reads Nadia's
real GitHub (owner `nboudhai`); the repo list is `cpsc415-portfolio,
cpsc415-week01 … cpsc415-week05` in `tools/registry.py`.

## 2. Run 2 eval

| Q | Model | Tools called | Steps | Pass/Fail | Cost | Seconds |
|---|---|---|---|---|---|---|
| 1 worked_lately          | M3    | recent_commits | 2 | pass | $0.000850 | 3.73 |
| 1 worked_lately          | Haiku | recent_commits | 2 | pass | $0.003917 | 3.21 |
| 2 outside_list           | M3    | (none)         | 1 | fail | $0.000444 | 1.36 |
| 2 outside_list           | Haiku | (none)         | 1 | fail | $0.001951 | 1.78 |
| 3 receipt_reader_profile | M3    | (none)         | 1 | pass | $0.000209 | 1.14 |
| 3 receipt_reader_profile | Haiku | (none)         | 1 | pass | $0.001830 | 3.60 |
| 4 commit_yesterday       | M3    | recent_commits | 2 | pass | $0.000695 | 4.67 |
| 4 commit_yesterday       | Haiku | (none)         | 1 | pass | $0.001778 | 1.63 |
| 5 intro_request          | M3    | request_intro  | 2 | pass | $0.000342 | 1.87 |
| 5 intro_request          | Haiku | (none)         | 1 | fail | $0.001686 | 1.35 |

Per-model averages, with vs. without a tool:

- **M3 with a tool (Q1, Q4, Q5):**  
  ($0.000850 + $0.000695 + $0.000342) / 3 = $0.001887 / 3 = **$0.000629**  
- **M3 without a tool (Q2, Q3):**  
  ($0.000444 + $0.000209) / 2 = $0.000653 / 2 = **$0.000327**  
  About **1.9×** higher with a tool.
- **Haiku with a tool (Q1):**  
  **$0.003917**  
- **Haiku without a tool (Q2–Q5):**  
  ($0.001951 + $0.001830 + $0.001778 + $0.001686) / 4 = $0.007245 / 4 = **$0.001811**  
  About **2.2×** higher with a tool.

- **Most steps any question took:** run 2 = **2**; run 1 = **the cap**, M3 Q4
  (8 tool calls across the 4-iteration step cap).

## 3. Run 1: what we found

The tool description in `registry.py` listed bare repo names (`cpsc415-portfolio`,
…) without the `nboudhai/` prefix. When the model called `recent_commits` with
the bare name from the description, the handler's first check rejected it;
the model's lookups failed, consistent with the bare-name error a direct call
of the tool reproduced. M3 retried; on Q4 M3 retried until the step cap.
Fixed by `d2b99b7` (tests for the full owner/name form in schema and error)
and `5b5e819` (schema and owner/name error guide the model to the full form).

## 4. Misuse cases

The six loop tests in `tools/tests/test_loop.py` cover the loop's contract
when a model misuses a tool or the loop itself is pushed:

1. `test_a_single_shot_tool_call_returns_the_answer_then_stops` — Behavior #1
   (the happy path): one tool call, one result, one answer.
2. `test_a_caller_with_bad_arguments_returns_an_error_result_and_carries_on`
   — Behavior #2: arguments are validated before any handler runs; a bad call
   comes back as an error result and the loop carries on.
3. `test_an_unknown_tool_returns_an_error_result` — Behavior #3: a tool name
   the registry does not know comes back as an error result; no handler runs.
4. `test_an_endless_caller_is_stopped_at_the_step_cap` — Behavior #4: a model
   that keeps calling is stopped at `MAX_STEPS`; the answer is the
   code-written cap message, not the model's.
5. `test_request_intro_is_held_as_pending_and_nothing_leaves_the_process`
   — Behavior #5: a side-effect call returns `{"pending": ...}`; no file is
   written, no email is sent.
6. `test_an_answer_naming_a_sha_or_repo_the_tool_did_not_return_is_flagged`
   — Behavior #6: `check_answer` flags shas and bare repo names that did not
   come back from a tool result.

Plus the live traces from the billed eval:

- **Endless caller** — run 1 Q4 M3: called `recent_commits` 8 times across
  the 4-iteration step cap; lookups failed, consistent with the bare-name
  error a direct call of the tool reproduced; the loop stopped at the cap.
- **Bad call** — run 1 Q1 both models: passed the bare name
  `cpsc415-portfolio` as the `repo` argument. M3 retried; Haiku gave up.
  Lookups failed, consistent with the bare-name error a direct call of the
  tool reproduced.

## 5. What `check_answer` cannot catch

- **"Sam" vs. "Nadia" attribution** — run 2 Q1 Haiku: "The commits show Sam
  has been adding browser checking…". The check looks for shas and bare repo
  names, not who the commits belong to. Catch: a person reading the trace, or
  a second model comparing the answer against `data/profile.yaml`.
- **Vague characterizations** — run 1 Q1 M3: "changes there are likely small
  or stylistic." No sha, no bare name — `check_answer` says supported. The
  model guessed when the tool returned nothing. Catch: a person reading the
  trace.
- **Invented commit messages** — the check flags shas the tools did not return,
  but a model that invents commit subjects (no shas, no repo names) passes.
  A name check cannot tell "X does not exist" from invented commits about X.
  Catch: a person reading the trace, or a second model.
- **False alarm from the tool description** — when the model recites the repo
  list from the description, `check_answer` matches the bare names inside and
  flags them as "mentioned without a tool result" (run 1 Q4 Haiku, run 2 Q2
  Haiku). Catch: the regex would need to know the source of the name (tool
  description vs. tool result), or the description would need to omit the names.

## 6. The cost of a tool

Per model, a tool question costs about twice a question without one: M3
$0.000629 vs. $0.000327 (~1.9×), Haiku $0.003917 vs. $0.001811 (~2.2×).
A tool question needs a second chat call (one to send the tool call, one to
read the result and write the answer), so the per-turn cost in the hosting
decision has to allow for roughly that ratio.

## 7. Linter

`ruff check .` found 28 findings (16 auto-fixable). All style: import order,
quoted annotations, unused `noqa`, one unused import and some unused unpacked
variables in `tools/tests/`. No correctness findings. Not fixed in this lab.

## Key check

2026-11-15, before tagging: `git grep -nE "sk-or-v1-[0-9a-f]{16,}"` over the
working tree and the same pattern over `git log -p --all`: no matches.