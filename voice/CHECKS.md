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

### Ruff run — 2026-11-08 (step 4: the transcriber and the speaker)

`python -m ruff check voice/`, ruff 0.17.4 from `.venv`, run after step 4 was
written. Still no configuration file is inherited.

**3 findings in the new code, all fixed.**

| File | Line | Rule | Fix |
| --- | --- | --- | --- |
| `voice/server.py` | 15 | F401 | `import os` removed; the redaction moved to `voice/redact.py` |
| `voice/speak.py` | 15 | I001 | import block sorted |
| `voice/transcribe.py` | 11 | I001 | import block sorted |

`ruff check voice/` passes clean. The 14 findings that predate the lab are
unchanged and are still listed above.

## The test suite

`pytest voice/tests -q` runs 52 tests with no key set and nothing billed. The
command lines ask for the key before they do anything, so the tests give them
a fake one — `test-not-a-real-key`, set for every test in `voice/tests/conftest.py` —
and the one test that wants no key removes it again with `monkeypatch.delenv`.

No test reads the shell's key, so the suite passes the same on a machine that
has one and on a machine that has none. Verified on 2026-11-08 with the key
removed from the command itself: `pytest voice/tests -q` → 52 passed, and
`pytest -q` → 82 passed.

## The set run

`voice/transcribe.py --set clips/expected.json` is the run that transcribes a
whole set, once each, and checks every clip in code. Its exit codes:

| Code | Meaning |
| --- | --- |
| 0 | every clip passed the check |
| 1 | at least one clip failed: a mishearing, or a clip the provider refused |
| 2 | the run could not start: there is no key, so nothing was billed |

Exit 1 is not a crash. The run transcribes every clip even after one fails,
writes the records to `--out`, says which clip failed and why, and exits 1. A
clip the provider refused is recorded with its cost as "none reported", because
the provider reports no usage for a call it refused.

The first of the four eval commands, run by hand because it bills:

```
python transcribe.py --set clips/expected.json --model openai/whisper-large-v3-turbo --out clips/transcripts-whisper-own.json
```

It is the only transcription of Nadia's clips on that model. The other three runs are in § Clips below.

## Clips

The four eval commands, run by hand on 2026-11-08 from `voice/`. Each one transcribes its clips once and checks every clip in code:

```
python transcribe.py --set ../../ai-integration-course/examples/voice-loop/clips/expected.json --model openai/whisper-large-v3-turbo --out clips/transcripts-whisper-fixtures.json
python transcribe.py --set ../../ai-integration-course/examples/voice-loop/clips/expected.json --model elevenlabs/scribe-v2 --out clips/transcripts-scribe-fixtures.json
python transcribe.py --set clips/expected.json --model openai/whisper-large-v3-turbo --out clips/transcripts-whisper-own.json
python transcribe.py --set clips/expected.json --model elevenlabs/scribe-v2 --out clips/transcripts-scribe-own.json
```

| Run | Model | Exit | Records |
| --- | --- | --- | --- |
| fixtures | openai/whisper-large-v3-turbo | 0 | `clips/transcripts-whisper-fixtures.json` |
| fixtures | elevenlabs/scribe-v2 | 0 | `clips/transcripts-scribe-fixtures.json` |
| own | openai/whisper-large-v3-turbo | 1 | `clips/transcripts-whisper-own.json` |
| own | elevenlabs/scribe-v2 | 1 | `clips/transcripts-scribe-own.json` |

The two own-clip runs exit 1 because own-02 failed the check on both models; the three fixture clips passed on both. The fixture runs used the course's `expected.json`, whose clip-02 carries the raised tolerance of 0.2 — the run that scored 0.1875 could not have passed without it. The own-clip runs used `voice/clips/expected.json`, the texts Nadia wrote before any model heard the clips.

### One line per clip per model

Whisper is `openai/whisper-large-v3-turbo`, Scribe is `elevenlabs/scribe-v2`. Rates are shown to four places; the JSON files hold them at full precision.

| File | Model | WER | Missing | Audio s | Cost | Call s | Transcript |
| --- | --- | --- | --- | --- | --- | --- | --- |
| own-01.m4a | Whisper | 0.1176 | — | 10.000 | $0.000111 | 1.5 | "What broke in your receipt reader project and which scales from CPSCA 415 have you actually shipped?" |
| own-01.m4a | Scribe | 0.0 | — | 7.211 | $0.000441 | 1.5 | "What broke in your receipt reader project and which skills from CPSC 415 have you actually shipped?" |
| own-02.m4a | Whisper | 0.1333 | `Boudhaim`, `Maguire` | 6.484 | $0.000022 | 3.0 | "My name is Nadia Botheim-McGuire. What salary would you expect for your first job?" |
| own-02.m4a | Scribe | 0.1333 | `Boudhaim`, `Maguire` | 6.485 | $0.000396 | 1.1 | "My name is Nadia Boatime McGuire. What salary would you expect for your first job?" |
| clip-01.wav | Whisper | 0.0 | — | 6.380 | $0.000021 | 3.0 | "What programming languages have you shipped code in, and which one would you choose for a new web service?" |
| clip-01.wav | Scribe | 0.0 | — | 6.380 | $0.000390 | 1.4 | "What programming languages have you shipped code in, and which one would you choose for a new web service?" |
| clip-02.wav | Whisper | 0.1875 | — | 8.061 | $0.000027 | 1.2 | "Have you ever deployed anything with Kubernetes? Be honest, I'm comparing you with a boot camp graduate. Music" |
| clip-02.wav | Scribe | 0.125 | — | 8.062 | $0.000493 | 1.2 | "Have you ever deployed anything with Kubernetes? Be honest, I'm comparing you with a boot camp graduate" |
| clip-03.wav | Whisper | 0.0 | — | 7.708 | $0.000026 | 1.3 | "Tell me about the RAG project from CPSC 415. How many chunks did the index have and what did a query cost?" |
| clip-03.wav | Scribe | 0.0 | — | 7.708 | $0.000471 | 1.1 | "Tell me about the RAG project from CPSC 415. How many chunks did the index have, and what did a query cost?" |

The missing list is empty for the fixture clips even where a word was split: `must_contain` compares with the spacing folded away, so "boot camp" still satisfies "bootcamp", while the rate still counts the split as an edit.

### Findings

1. **Neither model got the name right.** Whisper wrote "Botheim-McGuire"; Scribe wrote "Boatime McGuire"; the text says "Boudhaim Maguire". Both scored the same rate, 0.1333, inside the 0.15 default, so the word-error rate passed own-02 and only the `must_contain` check failed it, on `Boudhaim` and `Maguire`. The sentence still sounded right and the rate said 0.133 — only looking for the name caught it.

2. **Scribe was exact on own-01; Whisper was not.** Scribe read own-01 perfectly (0.0). Whisper heard "scales" for "skills" and "CPSCA" for "CPSC" — two substitutions in 17 words, 0.1176 — inside the 0.15 tolerance, so own-01 passed on both models.

3. **Unexplained: Whisper's own-01 timing and price.** Whisper reported own-01 as 10.0 s of audio and charged $0.000111; Scribe measured the same file at 7.211 s. The file sizes predict Scribe's figure — own-01.m4a is 185,492 bytes and own-02.m4a is 167,043, and 185,492 / 167,043 × 6.485 s is about 7.20 s. Whisper's price per second on own-01 is $0.0000111, against $0.0000033 on the other four clips, 3.3 times as much; at its own rate that charge is about 33 s of audio against a file that is 7.2 s long by every other measure. Nothing in the records explains it, so it is recorded rather than explained away.

4. **clip-02 reproduced the course's 0.188.** Whisper scored 0.1875 on clip-02 — the same mishearing the course recorded on Oct 26: "bootcamp" split into "boot camp" plus a stray "Music" on the trailing silence, three edits in 16 words. The course's `expected.json` raised that clip's tolerance to 0.2 for exactly this. Scribe split "bootcamp" too this time ("a boot camp graduate"), two edits, 0.125, where the Oct 26 run read it exactly. The fixture is not a fixed reference: both models misread it, and the course's file is the record of that.

5. **Totals.** Whisper $0.000207, Scribe $0.002191, all ten $0.002398. These are the sums of the per-clip costs as displayed above; the raw values in the four JSON files sum to $0.000206459, $0.002190585 and $0.002397044. The two differ only by rounding in the sixth decimal.

## What I heard myself

I could argue for why they spelt Boudhaim as they did, though if I really had to pick one I'd say Boatime. Personally I don't hear 'Mc' in how I say Maguire; it would be very soft if it's there. But McGuire is a common name, so it is very close compared to the Boudhaim versions.

## Answer

One chat call through `answer()` — the same function the typed route and the
voice route both call — run by hand on 2026-11-08. The question is own-01's:

> What broke in your receipt reader project, and which skills from CPSC 415 have you actually shipped?

The model is `minimax/minimax-m3`, the one `answer()` uses.

### The first call was lost

The command line made the chat call and then crashed writing the answer:
`voice/speaks/` did not exist, and the write came after the call. The answer
was paid for and lost with the traceback. **Its cost is unknown** — the
command line prints the cost only after the write — and the answer was never
printed or kept.

Both bugs are fixed, and the fix is proved by `voice/tests/test_answer.py`
with the call faked:

- the output folder is created, and the file proved writable, before the model
  is asked; a run whose answer cannot be written never calls the model at all;
- `--out` holds the **spoken** rendering, and the screen rendering goes next
  to it as `answer-screen.txt`.

### The second call

| | |
| --- | --- |
| Question | What broke in your receipt reader project, and which skills from CPSC 415 have you actually shipped? |
| Model | `minimax/minimax-m3` |
| Cost | $0.00080076 |
| The answer | the refusal |

The answer as the visitor reads it — this is what the second run wrote to
`voice/speaks/answer.txt`, and it was wrong, because the file the speaker
reads must not carry a URL:

> That's beyond what I have here, but it's exactly the kind of thing Nadia likes answering in her own words. Email is the best way to reach her at [her email] — she'd be happy to write back. You can also connect with her on LinkedIn at [her LinkedIn link].

The spoken rendering — no URL, because a URL cannot be heard — is what
`voice/speaks/answer.txt` holds now, and what the two voices will speak:

> That's beyond what I have here, but it's exactly the kind of thing Nadia likes answering in her own words. Email is the best way to reach her at [her email] — she'd be happy to write back. You can also connect with her on LinkedIn — the link is on screen.

The two contact details are elided above; they are in `data/profile.yaml`, and
the exact texts are in `voice/speaks/answer-screen.txt` and
`voice/speaks/answer.txt`. Both files were written by code from that one
answer — `answer.for_speaking()` and `answer.refusal.screen()` — not by a
second billed call. The screen rendering is in `answer-screen.txt`, which is
where the fixed command line writes it from now on.

The refused answer still cost $0.00080076: the system prompt inlines the
stand-in's profile, 2250 characters of it, so every call pays for the prompt.
The command line prints the cost but not the seconds the call took, so the
seconds are not recorded for this call.

### Finding — the question is half answerable, and the prompt refuses all of it

The stand-in's profile answers half of the question. The Receipt reader's
`breaks` field says: "A discount printed as a negative number; every model
copied the sign and the total failed." That is the answer to "what broke in
your receipt reader project".

The other half the profile cannot answer: nothing in it mentions CPSC 415 or
a skill from it. `skills_shipped` lists Python, Java, Git and GitHub pull
requests, pytest and the OpenRouter APIs — skills with no course attached —
and the stand-in is a Trinity College senior, so CPSC 415 is not even his
course.

The prompt's rule is whole-question: "If the profile does not cover the
question, reply with exactly OUT_OF_SCOPE and nothing else." A question with
one covered half and one uncovered half is not covered, so the model refuses
the whole thing — including the half it could have answered, and including
the `breaks` field, which is what a visitor would most want to hear.

There is no rule for a partly covered question: answer the part the profile
covers, say plainly that the rest is not in there, and refuse only that. That
is a prompt decision for the real chatbot, and it is in `TODO.md`.

## Speaks

The two speech calls, run by hand on 2026-11-08, each spoke `voice/speaks/answer.txt` —
the spoken rendering of the refusal, with the email kept and the LinkedIn URL
replaced by "the link is on screen". Both exited 0.

```
speaks\answer-class.mp3  335520 bytes  269 chars  1.3s  cost $0.004035 (estimated)  [microsoft/mai-voice-2.1-flash / en-US-Harper:MAI-Voice-2.1-Flash]
speaks\answer-eleven.mp3  281329 bytes  269 chars  3.3s  cost $0.010760 (estimated)  [elevenlabs/eleven-v4-turbo / george]
```

- ElevenLabs cost 2.7x the class voice ($0.010760 vs $0.004035), matching the
  course's estimate, and took 2.5x as long (3.3s vs 1.3s).
- Both costs are estimated from the catalog price per character: the speech
  reply carries no usage object, so the real bill is in the generation record
  (~1 min after the call) and replaces the estimate then.
- The answer was the refusal, so the course number does not appear in it.
  The voices could be judged only on the name, the email, and "the link is
  on screen".

## What I heard myself

Class voice: the read aloud was great. It said Nadia well, read the email correctly with @ as 'at' and icloud too, and read 'the link is on screen'. ElevenLabs: everything sounded well pronounced and normal.

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

## Browser check

On 2026-11-08 I ran `pytest voice/test_browser.py` against the server
on http://127.0.0.1:8000, with `OPENROUTER_API_KEY` and `VOICE_EVAL=1`
set in the shell.

**First billed run failed.** The provider refused with `maximum cost
exceeds your available credits`. The server logged the provider's
message and returned 502 — behavior 17 observed live, the provider's
message appearing only in the server window. The test waited its
full 120 s because it watches only `#transcript`: a 502 leaves the
transcript empty, so the test never sees the error and times out
instead.

**After $10 of credit:** 2 passed in 12.55s; the server logged
`POST /api/voice 200` at 23:10:35.

The last three assertions of `test_a_recording_through_the_page_never_exposes_the_key_or_the_provider`,
which is the point of the check:

```python
assert all(auth is None for _, auth in requests), "an Authorization header left the browser"
assert all("openrouter" not in url for url, _ in requests), "the browser called the provider"
assert any(url.endswith("/api/voice") for url, _ in requests), "the browser did not call our server"
```

The first fails if the browser sent an `Authorization` header to any
URL — including its own origin, which it must not. The second fails
if the browser talked to the provider directly instead of through
the server. The third fails if it never reached our server at all.
All three pass on the live run.

## One turn

One visitor turn, by microphone in Firefox at http://127.0.0.1:8000,
recorded by hand on 2026-11-08.

| | |
| --- | --- |
| Question | What broke in your receipt reader project? |
| Transcript | "What broke in your receipt reader project?" |
| Answer | "A discount printed as a negative number broke it: every vision model copied the minus sign straight into the total, so the arithmetic check failed even though the OCR looked right. It taught me to treat edge cases like a negative discount as a specification question rather than a model bug, since the parser was faithfully reading what was on the receipt." |

| Step | Cost | Share |
| --- | --- | --- |
| Transcription | $0.00000976 | 0.2% |
| Chat | $0.0005127 | 9.7% |
| Speech | $0.00474 | 90.1% |
| **Total** | **$0.00526246** | **100%** |

Speech is about 90% of a turn. This total is the per-visitor cost
for the hosting decision in TODO.md (a site-only key with a credit
limit, route caps).

### Finding — the answer is grounded but embellished

The stand-in profile's receipt reader `breaks` field says only:
"A discount printed as a negative number; every model copied the sign
and the total failed." The `learned` field says: "Edge cases are
specification questions, not model bugs."

The answer paraphrases the `breaks` field (the minus sign, the
arithmetic failing) and quotes the `learned` field (specification
question, not a model bug). Two phrases are not in the profile:
"even though the OCR looked right" and "the parser was faithfully
reading what was on the receipt". Neither field in profile.json
mentions OCR looking right or the parser being faithful — they are
the model's additions to a profile that only said every model copied
the sign.

The refusal rule is whole-question, so a partly grounded
embellishment is not caught today; this is a prompt question for the
real chatbot.
