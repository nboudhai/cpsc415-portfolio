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
