# Week 7

## Setup findings

### Checkpoints A and B — passed 2026-11-08

Checkpoints A and B from `weeks/07/setup.md` passed on 2026-11-08:

- `speak.py` produced a playable `hello.mp3`.
- `transcribe.py` on `clip-01.wav` returned `check ok: True, wer 0.0`.

### Guard test — 2026-11-08

Run by hand, piping JSON into `.claude/hooks/guard.py`:

| Command | Result | Exit | Message |
| --- | --- | --- | --- |
| `pip install numpy` | blocked | 2 | `numpy is not in spec.md` |
| `git push --force` | blocked | 2 | destructive-command message |
| `pip install openrouter` | **allowed** | 0 | — |

The third row is the finding below: the `openrouter` SDK is not yet listed
under Dependencies in `spec.md`, yet the guard allowed the install.

### Finding — the dependency check is a substring match, not an approval

**Cause confirmed** by reading `guard.py` lines 51-52.

The guard lowercases all of `spec.md` and checks whether the package name
appears anywhere in the text. `spec.md` already mentions the OpenRouter service
("via OpenRouter"), so the substring match passes. The guard checks that a word
is present, not that a dependency was approved.

**Impact:** the agent could install an SDK whose service is mentioned in prose
but never approved as a dependency.

**Status:** not fixed; lab step 1 adds `openrouter` under Dependencies anyway.

### Suspected — NOT tested — `guard.py` line 51 decodes `spec.md` with the platform default encoding

**This was not tested.** It is a reading of the code, not an observed failure.

`guard.py` line 51 calls `read_text()` without `encoding="utf-8"`. On Windows
that decodes `spec.md` as cp1252, and some UTF-8 characters (for example "←")
contain a byte cp1252 cannot decode. If such a character entered `spec.md`, the
guard would crash with exit 1, and a crashed guard fails open.

### Clip ordering

The clip text was drafted before recording. `voice/clips/expected.json` was
committed (1a52185) after the clips were recorded but before any model heard
them; no transcription had been run at that point.

### Agent model

`minimax/minimax-m3`, launched with `scripts/orclaude.bat`
(`../ai-integration-course/scripts/orclaude.bat` — the launcher lives in the
course repository). The Week 7 model was announced in class but not written in
the course materials; this is the slug documented in `weeks/01/setup.md`.

### Stand-in for the lab stage

The portfolio chatbot is not built yet. The Week 7 lab uses
`../ai-integration-course/examples/voice-loop/profile.json` and that example's
answer step as a stand-in, to be swapped for the real chatbot before
November 30.

## Linter

### Ruff run — 2026-11-08

`python -m ruff check .`, ruff 0.17.4 from `.venv`, run from the repository
root on 2026-11-08 after the step 2 checker was written.

**No configuration file is inherited.** There is no `ruff.toml`, `.ruff.toml`
or `pyproject.toml` in the repository or in any ancestor directory up to the
drive root, and no `RUFF_*` environment variable is set. `ruff check .
--isolated`, which ignores every configuration file, reports the identical 14
findings, so the rules that fired are ruff 0.17.4's own defaults, not a
configuration file's.

**One finding in the new code, fixed.** `voice/tests/test_check.py:14` —
I001, import block un-sorted or un-formatted. Fixed with `ruff check
voice/tests/test_check.py --fix`; `ruff check voice/` passes clean.

**14 findings that predate this lab, left alone.** They are in files Week 7
did not touch, so they are recorded here rather than changed:

| File | Line | Rule |
| --- | --- | --- |
| `.claude/hooks/guard.py` | 28 | PIE810 |
| `profile_schema.py` | 18 | I001 |
| `profile_schema.py` | 93 | UP037 |
| `profile_schema.py` | 228 | UP037 |
| `profile_schema.py` | 236 | UP037 |
| `profile_schema.py` | 244 | UP037 |
| `scripts/validate_profile.py` | 40 | UP035 |
| `scripts/validate_profile.py` | 48 | I001 |
| `scripts/validate_profile.py` | 48 | RUF100 |
| `scripts/validate_profile.py` | 49 | RUF100 |
| `scripts/validate_profile.py` | 51 | RUF100 |
| `scripts/validate_profile.py` | 106 | ISC004 |
| `tests/test_validate_profile.py` | 31 | I001 |
| `tests/test_validate_profile.py` | 31 | RUF100 |

### Ruff run — 2026-11-08 (step 3: the refusal and the loop)

`python -m ruff check voice/`, ruff 0.17.4 from `.venv`, run after step 3 was
written. Still no configuration file is inherited.

**8 findings in the new code, all fixed.** They were all in step 3's files:

| File | Line | Rule | Fix |
| --- | --- | --- | --- |
| `voice/tests/test_loop.py` | 10 | I001 | import block sorted |
| `voice/tests/test_loop.py` | 130 | RUF059 | `body` unused → `_body` |
| `voice/tests/test_loop.py` | 137 | RUF059 | `body` unused → `_body` |
| `voice/tests/test_loop.py` | 163 | RUF059 | `status` unused → the test now asserts `status == 502` |
| `voice/tests/test_loop.py` | 187 | RUF059 | `status` unused → the test now asserts `status == 200` |
| `voice/tests/test_loop.py` | 189 | RUF015 | `[…][0]` → `next(…)` |
| `voice/tests/test_loop.py` | 198 | RUF012 | `headers` annotated `ClassVar[dict]` |
| `voice/tests/test_refusal.py` | 10 | F401 | `import pytest` removed; the file does not use it |

The line numbers are as the run reported them; sorting the import block of
`test_loop.py` moved everything below it down by two lines.

Two of the four RUF059 findings were fixed by making the test say more rather
than by hiding the name: the rejected-recording test now asserts the 502, and
the refusal test now asserts the 200.

`ruff check voice/` passes clean. The 14 findings that predate the lab are
unchanged and are still listed above.

## Cost record

### Two stray chat calls — 2026-11-08

While timing the test suite I ran a probe against `POST /api/chat` on the
running server. The probe inherited `OPENROUTER_API_KEY` from the shell, so it
made two real chat calls on `minimax/minimax-m3` with the question "hi" — one
probe, then a second to compare the timings. **They are not part of the lab's
eval**: they are not in the ten clip lines, and they are not evidence of
anything. They are recorded here so the cost record is not quietly short two
calls.

`minimax/minimax-m3` is priced at $0.0000003 per prompt token and $0.0000012
per completion token, so the two calls together cost a fraction of a cent. The
exact figure is in the OpenRouter activity page; OpenRouter has no endpoint that
lists a generation without already knowing its id, so it could not be read back
here.

### Finding — "localhost" costs two seconds a request on this machine

Measured while timing the step 3 suite: every request to `http://localhost:…`
took 2.03 s, and the same request to `http://127.0.0.1:…` took 0.00 s. The
Windows resolver is the difference, not the server. The step 3 test fixture
therefore talks to `127.0.0.1`, which took the suite from 30 seconds to 6.

The lesson for the browser check in step 8: a page loaded from `localhost` may
pay the same two seconds, so the timings recorded there should say which name
was used.
