# Plan

<!-- The agent proposes this from the spec. Interrogate it ("what could break?") and approve
     before any code is written. Update it when the plan changes. -->

## Files to create or change

| File | Purpose |
|---|---|
| `data/profile.yaml` | Single source of truth for the six static sections and chatbot grounding. Hand-edited; reviewed in PRs. |
| `profile_schema.py` | Pydantic v2 schema (`Profile` model) shared by the build script, the CI validator, and the Pages Function. One schema, not three. |
| `scripts/validate_profile.py` | CI entry point. `python scripts/validate_profile.py` exits non-zero on missing/empty required fields (the four reflection fields on every project, contact.email and contact.linkedin, `not_yet` key present, etc.). |
| `scripts/build_site.py` | Reads `data/profile.yaml`, renders `index.html` and `assets/profile.json` (the JSON blob the chat widget reads on first load). Pure Python (`pyyaml` + `jinja2`), no Node bundler. |
| `index.html` (generated, but committed for review) | Single page with six `<section>` blocks in the order About → Resume → Projects → Research → Interests → Contact. Inline `<script type="application/json" id="profile">…</script>` so the chat widget can boot without a second fetch. |
| `assets/site.css` | Hand-written CSS. Plain, no preprocessor. |
| `assets/chat.js` | Vanilla ES2022 chat widget. Mounts bottom-right, posts to `/api/chat`, consumes SSE via `fetch` + `ReadableStream`. No bundler, no framework. |
| `functions/api/chat.py` | Cloudflare Pages Function (Python via Pyodide). Parses request, validates body, inlines the YAML + system prompt, calls OpenRouter, streams SSE. Reads `OPENROUTER_API_KEY` from the Pages secret store. **Note:** the spec's component heading says `chat.ts` but its language section says Python — see Risks §1. |
| `functions/api/__init__.py` (empty) | Marks `functions/api/` as a Pages Functions directory. |
| `requirements.txt` | Python deps for the build script, validator, schema module, and (for local dev) the function: `pydantic>=2`, `pyyaml`, `jinja2`, `httpx`. Pin major versions. |
| `tests/test_validate_profile.py` | Validator unit tests: a passing fixture, a missing-field failure, a wrong-type failure, an empty-not-yet pass. |
| `tests/test_build_site.py` | Asserts the generated `index.html` contains exactly six `<section>` elements in the locked order, every project card has all four reflection fields, and no secret appears in the source. |
| `tests/test_chat_function.py` | Local harness that wraps the function with `pytest` + `httpx.MockTransport`. Asserts: in-scope question streams a cited answer; out-of-scope question returns the redirect message verbatim; malformed body → 400 and no model call; missing `OPENROUTER_API_KEY` → 503. |
| `tests/adversarial/` | The five-question adversarial probe set from the spec (salary, reference, fake project, most-recent learn, research summary). Runs against a live OpenRouter call in CI on a schedule, not on every PR. Stores pass/fail per question. |
| `.github/workflows/ci.yml` | Runs `pytest` + `python scripts/validate_profile.py` + a Pages dry-build on every PR. Required to pass before merge per `REVIEW.md` pass 2. |
| `.github/workflows/deploy.yml` | On merge to `main`: builds the site, deploys to Cloudflare Pages via the official action with the `CF_API_TOKEN` and `CF_ACCOUNT_ID` secrets. |
| `.env.example` | Documents `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `CF_API_TOKEN`, `CF_ACCOUNT_ID`, `CF_PROJECT_NAME`. Real values stay in Cloudflare's secret store and in local `.env` (gitignored). |

## Order of work

Each step ends in something I can run, screenshot, or assert on. Steps 1–3 are independent of Cloudflare and can ship without it; steps 4–6 require a Cloudflare Pages project.

1. **Branch + scaffold.** `git checkout -b feat/scaffold` from `main`. Add `requirements.txt`, `.env.example`, `.gitignore` updates (already covers `.env` and `.claude/settings.local.json`), and an empty `tests/` directory with one `pytest` smoke test. *Proof:* `pytest -q` exits 0 on an empty suite.
2. **Schema + validator.** Write `profile_schema.py` (the Pydantic model that mirrors the spec's YAML schema, including the new `skills` tier and the tightened `not_yet` rules) and `scripts/validate_profile.py` (with a `--strict` flag that turns `TODO_FILL_IN` markers from warnings into fatal errors). Add `tests/test_validate_profile.py` covering the original four cases (one inverted: empty `not_yet` now fails), the `skills` tiers, the `not_yet.why` length rule, and the `--strict` behaviour. Commit a placeholder `data/profile.yaml` that uses `TODO_FILL_IN` markers so it can fill in incrementally while PR CI stays green in non-strict mode. *Proof:* `python scripts/validate_profile.py` exits 0 with warnings; `python scripts/validate_profile.py --strict` exits 1; `pytest tests/test_validate_profile.py -q` is green.
3. **Build script + static page.** Write `scripts/build_site.py` (Jinja template inline or in `templates/index.html.j2`) and `assets/site.css`. Generate `index.html` and `assets/profile.json`. Commit them. *Proof:* `python scripts/build_site.py` regenerates `index.html` byte-identical to the committed copy (CI checks this with a `diff -q`); `tests/test_build_site.py` asserts the six-`<section>` order and the absence of secrets via a regex over the rendered HTML.
4. **Local Pages Functions harness.** Add `functions/api/chat.py` and `functions/api/__init__.py`. Stand the function up locally with `wrangler pages dev dist/` (or a `pytest`-driven mock that imports the handler directly) so we can test it without deploying. *Proof:* `wrangler pages dev dist/` serves `index.html` and a stub `/api/chat` that returns 400 on malformed input and 503 when `OPENROUTER_API_KEY` is unset.
5. **Chat function behaviour.** Implement the real handler: parse body, build messages (system + validated YAML + history), call OpenRouter with `httpx.AsyncClient.stream(...)`, return `text/event-stream` ending in `data: [DONE]`. Wire retry-once-after-500ms on 5xx. *Proof:* `tests/test_chat_function.py` — in-scope question yields a streamed answer; out-of-scope yields the redirect verbatim; malformed body yields 400 with no model call; missing key yields 503.
6. **Chat widget.** Write `assets/chat.js` (~150 LOC, vanilla). Mount the bottom-right widget bottom-right; POST to `/api/chat`; consume SSE; render streamed tokens into the transcript.

   **UX during the Pyodide cold start.** From the browser, cold-start latency and model latency are indistinguishable — both look like "request sent, no bytes yet." The widget cannot honestly tell the user which one it is waiting on, and it must not try (a spinner labelled *"the AI is warming up"* would be a false technical story). The pattern:

   - **On submit, render the user's message into the transcript synchronously** (no network needed). The user sees their message land.
   - **Immediately append a placeholder assistant bubble containing three pulsing dots** (CSS animation, no text label). This appears within one frame of submit, so the user has visual feedback even if the first SSE byte is 2–3 s away during a cold start.
   - **When the SSE stream produces its first token, replace the dots with the streamed text.** The transition is abrupt on purpose — it tells the user the answer has started arriving.
   - **30-second safety timeout.** If no byte has arrived 30 s after submit, swap the dots for the generic "chat unavailable" message. 30 s is comfortable: Pyodide cold start (~2 s) + the function's 500 ms retry on 5xx + OpenRouter first-token latency (usually <1 s on Haiku 4.5) + generous slack for transient slowness. 15 s would be tight.
   - **After the first chat of a session, subsequent chats are warm and the dots are barely visible.** Design for the cold case anyway because a personal site gets bursty traffic and most visitors will hit cold.

   **Non-SSE failure handling at the widget.** Before reading the stream, the widget must check `response.ok` and read the status:
   - `400` → "Sorry, that message couldn't be sent. Please try again."
   - `502` → "Chat is temporarily unavailable. Please try again in a moment." (OpenRouter 5xx after retry.)
   - `503` → "Chat is temporarily unavailable. Please try again shortly or reach Nadia at <profile.contact.email>." (Missing `OPENROUTER_API_KEY` *or* YAML parse failure at cold start — the widget cannot and should not distinguish these.)
   - any other non-2xx → same generic message as 503.

   *Proof:* (a) automated: a `jsdom`-based test posts a synthetic submit event and asserts the placeholder dot bubble exists in the DOM *before* the mocked `fetch` resolves; the same test asserts that a `fetch` response with `status: 503` renders the 503 message text and never opens the SSE reader; a third test fast-forwards the 30 s timer and asserts the generic message replaces the dots. (b) manual against the local `wrangler` server: ask an in-scope question, see streamed reply; ask a salary question, see the redirect; reload, the widget remembers nothing (stateless by design); temporarily break `data/profile.yaml` to force a function-side parse failure, ask any question, confirm the widget shows the 503 message within one round-trip.
7. **Adversarial probe.** Add `tests/adversarial/run.py` with the five spec probes. Run it once against Haiku 4.5 and once against Sonnet 4.5 (manually, since CI cost). Record the pass/fail per question into `tests/adversarial/RESULTS.md`. *Proof:* all five questions behave per spec on at least one of the two models. If Haiku fails any, swap the model slug in `functions/api/chat.py` to Sonnet — one line, per the spec's escalation path.
8. **CI.** Add `.github/workflows/ci.yml`: install `requirements.txt`, run `pytest -q`, run `validate_profile.py`, run `build_site.py` and `diff` the output. Required to pass before merge per `REVIEW.md`. *Proof:* push a branch with a deliberately missing reflection field; CI goes red with the validator's error message.
9. **Deploy.** Add `.github/workflows/deploy.yml` using `cloudflare/pages-action`. The deploy job runs `python scripts/validate_profile.py --strict` before deploying, so any `TODO_FILL_IN` marker (or schema regression) blocks the deploy — not just the CI run on the PR. Wire the four CF secrets in the repo settings. *Proof:* merge a change to `main`; the workflow runs; the deployed URL serves the new HTML; the `/api/chat` endpoint responds on the deployed hostname. Also: re-introduce a `TODO_FILL_IN` marker on a branch; confirm the deploy workflow fails on `validate_profile.py --strict` and never reaches the Pages action.
10. **ANNOTATION.md.** Fill in the four questions (what is this, why this choice, what breaks, what did I learn) based on what actually shipped, not on what the spec promised. *Proof:* the file has non-empty answers in each section and references the deployed URL.

## Risks

1. **Spec inconsistency: `functions/api/chat.ts` heading vs Python language.** The spec heading says `.ts`; the language section says Python on Pyodide. Cloudflare Pages Functions must match the runtime — `chat.py` for Python, `chat.ts` for TypeScript. Two resolutions exist: (a) rename the file to `chat.py` in `plan.md` and treat the heading as a typo, or (b) switch the function to TypeScript and keep Pydantic only for the validator + build script. **Default in this plan: (a).** If you prefer (b), the function loses Pydantic-native YAML validation and the schema module becomes TypeScript-only or duplicated. Decision needed before step 4.
2. **Pyodide cold-start cost.** Pydantic + Pyyaml in a Python Pages Function has to boot Pyodide + load packages on first hit. Worst case ~2–3 s of latency before the first streamed byte. Mitigation: keep the function's import surface small (one module), and accept that cold starts are rare on a personal site. Blast radius: a slow first chat reply; no data loss.
3. **OpenRouter API key exposure.** The key must never reach the browser, the committed `index.html`, or the `data/profile.json` blob. Risks: accidentally logging the request body, accidentally serializing the system prompt into a client-visible error, accidentally checking `.env` into git. Mitigations: `.gitignore` already covers `.env`; the build script must not read env vars; the function must redact the key from any error path; CI runs a grep for the key shape (`sk-or-…`) across `dist/`.
4. **Model hallucination despite the system prompt.** Haiku 4.5 is the default because the spec's comparison judged the cost gap not worth Sonnet's edge on vague summaries. But the adversarial test set is the only thing that proves it. Risk: Haiku invents a project on a vague prompt. Mitigation: step 7 runs the probes and the spec's escalation path swaps the slug if Haiku fails any. Blast radius: a chatbot reply that misleads a recruiter; reputational, not technical.
5. **YAML schema drift.** A future edit to `data/profile.yaml` can pass the validator but still break the Jinja template (e.g., a project missing `links` where the template expects `links | length`). Mitigation: `scripts/build_site.py` runs in CI; a render failure fails the build. Blast radius: a deploy that doesn't go out.
6. **"Profile data inline in HTML" leaks the full profile to anyone who views source.** The spec deliberately bakes the YAML into the page so the chat widget can boot without a second fetch. The data is *not* a secret — it's the public profile — but it does mean the long bio, all reflection fields, and the `not_yet` inventory are visible to scrapers. Accepted per the spec; the cost is intentional (one fewer round trip, simpler CORS). Mitigation: none in this iteration; out of scope is the downloadable resume PDF and rate limiting.
7. **Cloudflare Pages Python support is newer than TypeScript.** Edge cases: package availability on Pyodide, max script size, available stdlib. Mitigation: pin `pydantic` and `pyyaml` to versions known to work in Pyodide; document the fallback in `ANNOTATION.md` if a regression forces a switch to TS. Blast radius: a feature that ships to spec on every other layer but blocks on the function runtime.
8. **Six `<section>` order drift.** The spec locks the order, and `REVIEW.md` pass 2 would catch a wrong order. But the Jinja template is the only place that enforces it. Mitigation: a literal list in `build_site.py` that drives the loop, plus the test in step 3. Blast radius: a recruiter who scans the page in the wrong order.
9. **CI cost from adversarial probes.** Running the five adversarial questions against a live model on every PR would be wasteful and rate-limit-prone. Mitigation: probes run on a weekly cron + manually on demand, not in the PR CI workflow (step 8 explicitly excludes them).

## Proof

| Step | Proof |
|---|---|
| 1 | `pytest -q` exits 0 on the smoke test; `git status` shows the new files; the new branch is pushed (not `main`). |
| 2 | `python scripts/validate_profile.py` exits 0 on a passing fixture and prints `TODO_FILL_IN` warnings on the placeholder file. `python scripts/validate_profile.py --strict` exits 1 on the same placeholder file. The same command exits non-zero with a specific error message on a fixture with a missing reflection field. `pytest tests/test_validate_profile.py -q` is green for all 16 cases. |
| 3 | `python scripts/build_site.py` followed by `diff -q index.html index.html.committed` is empty. `pytest tests/test_build_site.py -q` asserts (a) `len(re.findall(r'<section', html)) == 6`, (b) the order matches a literal list, (c) every project card contains all four reflection field labels, (d) `re.search(r'sk-or-', html)` is None. |
| 4 | `wrangler pages dev dist/` boots; `curl localhost:8788/` returns the generated HTML; `curl -X POST localhost:8788/api/chat -d '{}' -H 'content-type: application/json'` returns 400 with a JSON body. |
| 5 | `pytest tests/test_chat_function.py -q` is green for all four cases (in-scope streamed, out-of-scope verbatim, malformed 400, missing key 503). The mocked transport asserts the OpenRouter call was not made on the malformed-body path. |
| 6 | Automated: `tests/test_chat_widget.py` (jsdom) asserts (i) the pulsing-dots placeholder is in the DOM synchronously on `submit`, before `fetch` resolves; (ii) a mocked `503` response renders the 503 message text and never opens an SSE reader; (iii) a mocked hung response renders the generic message after the 30 s timeout. Manual: load the local page, ask "what did you learn from your most recent project?", see a streamed reply that names a `what_did_i_learn` field; ask "what's your salary expectation?", see the redirect verbatim; reload — widget is stateless, transcript is empty; break `data/profile.yaml` to force a parse failure, confirm the widget shows the 503 message within one round-trip. |
| 7 | `tests/adversarial/RESULTS.md` records pass/fail per question for both models. If Haiku fails any, the slug in `functions/api/chat.py` is changed to Sonnet 4.5 and the test is re-run before merge. |
| 8 | Push a branch with `data/profile.yaml` missing `what_did_i_learn` on one project; CI goes red with the validator's error message. Push a branch that edits `index.html` by hand; CI goes red because the build output differs from the committed file. Both regressions are caught before review. |
| 9 | Merge a one-character change to `data/profile.yaml`'s tagline; the deploy workflow runs; the deployed URL reflects the change; `/api/chat` responds on the deployed hostname. Re-introduce a `TODO_FILL_IN` marker on a branch; the deploy workflow's `validate_profile.py --strict` step fails and the Pages action is never reached. |
| 10 | `ANNOTATION.md` has non-empty answers in all four sections, with the deployed URL in "What is this?" and at least one specific thing the agent was confidently wrong about in "What did I learn?" (this is the point of the file). |

## Subagents and parallel work

This plan is small enough to keep on one branch with one agent. Two places where a subagent *could* help, but is not necessary:

- **CSS design pass** (`assets/site.css`) is the kind of work that benefits from a second pair of eyes on accessibility and contrast. If you want a review pass, route the CSS through a separate reviewer after step 3, before step 6 adds the chat widget on top of it. Not blocking.
- **Adversarial probe authoring** (`tests/adversarial/`) — the spec gives five seed questions. A separate Explore-style sweep over `data/profile.yaml` could surface another 10–15 probes (vague phrasing, names that sound like projects but aren't, the `not_yet` trick). Worth doing once after `data/profile.yaml` is past the first draft; not on the critical path for the first deploy.

No worktree, no parallel feature branches. The repo rule is one feature per PR, and the feature here is "portfolio site v1."

## Week 7

The voice interface: a visitor records a question, the server transcribes it,
the chatbot answers from the profile, and the answer is spoken back. Built in
`voice/`, on the stand-in described in `spec.md` §"Week 7: spoken interface" —
the course example at `../../ai-integration-course/examples/voice-loop/profile.json`
and that example's answer step — because the real chatbot does not exist yet.
The typed route is `/api/chat`, the voice route is `/api/voice`, and both call
the same `answer()` function. Paths in this section are relative to `voice/`
unless a command says otherwise.

### Files to create or change

| File | Purpose |
|---|---|
| `voice/check.py` | The checker, plain code and no key: word error rate against an expected text, the words that must survive, and the empty-transcript verdict. Written from `spec.md`, not copied; the example is read for request shapes only. |
| `voice/refusal.py` | The refusal template — one constant — plus its two renderings: the screen text (email and LinkedIn link clickable) and the spoken text (the same message with the LinkedIn URL replaced by "the link is on screen"). Imports nothing from the SDK, so the no-key test imports this module alone. |
| `voice/answer.py` | The one `answer()` function: the stand-in's system prompt (name-agnostic, `OUT_OF_SCOPE`, no URLs, no markdown, two or three sentences), the chat call, and the replacement of `OUT_OF_SCOPE` with the refusal. Run from the command line with `--ask` and `--out`, it makes one chat call, writes the answer text, and prints the cost. |
| `voice/transcribe.py` | One clip, or a whole `expected.json` set, through OpenRouter's transcription endpoint. Prints the text, the audio seconds, the cost, the seconds the call took, and the checker's verdict. Over a set it processes every clip even after one fails, then exits 1 if any clip failed and 0 otherwise, so a failure never causes a clip to be transcribed twice. |
| `voice/speak.py` | Text to an MP3, to a WAV when the output name ends in `.wav` (asks for PCM and frames it with `wave`), or to the text in a file with `--in`. Prints the characters, the bytes, the cost, and the seconds. |
| `voice/redact.py` | The one redaction rule: the key never reaches a log, a record, or a commit. A provider can hand the key back in its own words, and the transcriber writes that message to a file that gets committed, so every provider message goes through `redact()` on its way out — the server, the transcriber and the speaker all use it. |
| `voice/server.py` | The loop: `GET /` serves the page; `POST /api/voice` takes the recording and returns the transcript, the answer, the audio as base64, and the three costs; `POST /api/chat` takes the typed question and answers through the same function. The 10 MB body cap and the 415 for an unknown audio type live here, and so does the rejection path: a recording the provider will not take ends the turn with a 502 and a plain message, the provider's message going to the server log and never to the browser. |
| `voice/index.html` | The page: a record button that stops itself at 30 seconds, a file picker as the fallback, the transcript, the answer, the audio, and the error message — a refused recording shows the server's plain message where the answer would go, instead of an empty transcript. No framework, no bundler. |
| `voice/tests/conftest.py` | Puts `voice/` on `sys.path` for the test files, so `import check` works with nothing installed and no test file needs an import in the middle of its body. |
| `voice/tests/test_check.py` | The no-key tests of the checker: a perfect transcript scores zero; one substituted word in thirteen scores one thirteenth; the empty reply scores one and is reported, not raised; a name that must survive is reported even when the rate is within tolerance; a number read as words is a miss; spacing and case do not count. |
| `voice/tests/test_refusal.py` | The no-key tests of the refusal: the constant matches `spec.md` word for word; a reply containing `OUT_OF_SCOPE` anywhere is replaced whole; the spoken text carries no URL; the screen text carries the email and the LinkedIn link. |
| `voice/tests/test_loop.py` | The no-key tests of the loop, with the model call faked: a non-audio speech reply raises and writes no file; an empty transcript skips both the chat and the speech call; a body over 10 MB is refused; an unknown audio type gets 415; a recording the provider rejects returns 502 with the plain message, makes no chat call and no speech call, writes no audio, and puts the provider's message in the server log and not in the reply. |
| `voice/tests/test_transcribe.py` | The no-key tests of the set run, with the transcription call faked: every clip in the set is processed even after one fails, the run exits 1 when any clip failed and 0 when none did, and no clip is transcribed twice. One clip's transcription raises, as a provider rejection does: it is recorded as a failed clip, the rest of the set carries on, and the run still exits 1. |
| `voice/tests/test_speak.py` | The no-key tests of the speaker, with the speech call faked: the file is written and the record keeps the characters, the bytes, the cost and the seconds; a `.wav` output asks for PCM and is framed by the `wave` module; the cost is estimated and marked while the generation record has not appeared yet, and the billed cost wins once it has; the command line prints what the lab records, reads the text from a file, refuses without a key, and never prints the key. |
| `voice/tests/test_eval.py` | The billed eval: each clip transcribed once on each of the two models and checked, plus one chat call and one speech call. Runs only when `OPENROUTER_API_KEY` is set **and** `VOICE_EVAL=1`; otherwise skipped, not failed. An ordinary `pytest` run never bills. The set run's exit code is covered without a key in `test_transcribe.py`. |
| `voice/test_browser.py` | The Playwright check: uploads a clip through the page, waits for the spoken answer, asserts the browser never saw the key or the provider. Its last three assertions are the submission's acceptance test, and the run goes in `voice/CHECKS.md`. It also checks the page's error display, using an unmapped audio type so the run costs nothing: the server refuses with 415 and the page shows the message instead of an empty transcript. |
| `voice/clips/expected.json` | *(already committed)* The expected text for `own-01.m4a` and `own-02.m4a`, written by a person before any model heard the clips. |
| `voice/clips/own-01.m4a`, `voice/clips/own-02.m4a` | *(already committed)* Nadia's own voice, recorded on Windows Sound Recorder. |
| `voice/speaks/answer.txt` | The exact answer text the two voices spoke, written by the one chat call. Committed, so the spoken files can be checked against it. |
| `voice/speaks/answer-class.mp3`, `voice/speaks/answer-eleven.mp3` | The two spoken answers, committed: the submission requires them at the `week07-submitted` tag. |
| `voice/CHECKS.md` | The record: one line per clip per model, the chat call's question, text, and cost, one line per voice, the one-turn section with the three costs and the total, the browser-check run, and the key check with its harmless matches listed as they are found. A rejected call's transcription cost is recorded as "none reported", because the provider reports no usage for a call it refused. |
| `.gitignore` | Add `voice/last-answer.mp3` only — the server's transient output of the last spoken answer, regenerated per turn and not evidence. |

### Order of work

1. **Approve the plan.** The spec's Week 7 section is approved; the plan
   approval is the remaining gate. Commit `Approve plan (week 7)`. No code
   before it.
2. **The checker, tests first.** Write `voice/tests/test_check.py` before
   `voice/check.py`, watch it fail, then write the checker and watch it pass.
   *Proof:* `pytest voice/tests/test_check.py -q` green with no key set and
   nothing billed.
3. **The refusal and the loop, tests first.** The same order for
   `voice/tests/test_refusal.py` and `voice/tests/test_loop.py` against
   `voice/refusal.py`, `voice/answer.py`, and `voice/server.py`, with the model
   call faked. *Proof:* green, no key, no billed call. The server imports the
   transcriber and the speaker, so the provider calls in `voice/transcribe.py`
   and `voice/speak.py` were written in this step as well; step 4 adds their
   command lines, the set run, the exit code, and `voice/tests/test_transcribe.py`.
4. **The transcriber and the speaker.** Complete `voice/transcribe.py` and
   `voice/speak.py` with their command lines — the provider calls are already
   written, from step 3 — and write `voice/tests/test_transcribe.py` first: with the
   transcription call faked, it asserts that every clip in the set is processed
   even after one fails, that a clip whose transcription raises — as a
   provider rejection does — is recorded as a failed clip and the set carries
   on, that the run exits 1 if any clip failed and 0 if none did, and that a
   failed clip is never transcribed twice. *Proof:* the first eval command —
   `python transcribe.py --set clips/expected.json --model
   openai/whisper-large-v3-turbo --out clips/transcripts-whisper-own.json` — is
   the proof: it prints one line per clip with the text, the audio seconds, the
   cost, the seconds, and the checker's verdict, and its exit code is 1 if any
   of Nadia's clips failed. It is the only transcription of Nadia's clips on
   that model; no separate call is made to test the code. The speaker's command
   line is proved the same way, in `voice/tests/test_speak.py`, which this plan
   did not name: step 4 covers the speaker too, and nothing here is proved by
   running it by hand.
5. **The rest of the clip eval.** The remaining three transcription commands:
   the course fixtures on both models, and Nadia's clips on Scribe.
   *Proof:* `voice/CHECKS.md` §"Clips" has one line per clip per model — five
   clips, two models, ten lines. Commit `Voice: own clips transcribed on two
   models`.
6. **The chatbot's answer, then the answer spoken, two voices.** One chat call
   through `answer()` for own-01's question — "What broke in your receipt
   reader project, and which skills from CPSC 415 have you actually shipped?"
   Its text and cost go in `voice/CHECKS.md`, and that exact text is what
   `speak.py` speaks with both voices: one speech call per model. Listen to
   both.
   *Proof:* `voice/CHECKS.md` §"Answer" has the question, the text, and the
   cost; §"Speaks" has the characters, the bytes, the cost, and what each
   voice did with Nadia's name and the course number, and names
   `speaks/answer.txt` as the text it spoke; `voice/speaks/` holds the two
   files. Commit `Voice: the answer spoken, two voices`.
7. **The loop in the server.** `voice/index.html` and the server wired to the
   page. *Proof:* `POST /api/voice` returns the transcript, the answer, the
   audio, and the three costs; `POST /api/chat` answers the same question
   through the same function; a recording the provider rejects returns 502
   with the plain message and no audio, and the page shows it; the no-key loop
   tests still pass.
8. **The browser check, the one turn, and the key check.** *Proof:*
   `voice/CHECKS.md` §"Browser check" carries the run and the last three
   assertions, §"One turn" carries the transcript, the answer, the three costs,
   and the total, and §"Key check" carries the empty real-key search and the
   harmless matches listed as they are found.
   Commit `Voice: the loop, with the browser check`; tag `week07-submitted`.

### Risks

1. **A green test run with skips is not a passed eval.** The key is set in this
   session, so "no key" is not what holds the billed tests back — `VOICE_EVAL=1`
   is, and it has to be set alongside the key. Without both, the billed tests
   skip, and a skip is not a failure, so `pytest -q` can be green with nothing
   transcribed at all. Mitigation: the gate is two conditions, never one; the
   eval is a different command, run by hand; and the rule is that the eval has
   run when `voice/CHECKS.md` carries the numbers. See Proof §A and §B.
2. **The refusal constant drifts from `spec.md`.** The message is in two
   places, which is where they will disagree. Mitigation: a no-key test asserts
   the constant matches `spec.md` word for word, so an edit to one without the
   other fails the suite.
3. **The stand-in's profile is Sam Rivera, the refusal points to Nadia.** A
   visitor asking "what have you shipped" gets Sam's projects. Recorded in
   `voice/CHECKS.md`; ends when `data/profile.yaml` replaces `profile.json`.
4. **The transcript is wrong in the places that matter** — names and numbers.
   Mitigation: the `must_contain` list per clip, the stated tolerance, a missing
   name reported even when the rate is within tolerance, and the live path
   showing the transcript beside the answer.
5. **The 30-second cap is page-side.** The server cannot measure a duration
   without decoding the audio, so a crafted request can exceed it; the 10 MB
   body cap still applies. The cap bounds latency and abuse for an honest
   visitor, not a crafted one.
6. **The browser sends a format the server does not map.** Safari's
   MediaRecorder sends `audio/mp4`, Chrome `audio/webm`, and Nadia's own clips
   are `.m4a` recorded on Windows Sound Recorder. An unmapped type gets 415 and
   the visitor gets nothing. Mitigation: the format map covers all three, and
   the browser check exercises the path.
7. **A speech call that returns JSON is saved as audio.** The reply's content
   type is checked before anything is written; a non-audio reply is an error and
   nothing is saved. The no-key test fakes the reply and asserts no file
   appears.
8. **The spoken refusal carries a URL.** A LinkedIn link read aloud is
   meaningless. Mitigation: the spoken variant replaces it with "the link is on
   screen", and a no-key test asserts the spoken text carries no URL.
9. **The key reaches the repository.** There is no CI yet — the site's CI is
   plan.md step 8 and does not exist. A plain `sk-or` search is no good here:
   the repository legitimately contains `sk-or` in harmless places, so the
   search has to match a key's shape instead. Mitigation: before tagging, run
   `git grep -nE "sk-or-v1-[0-9a-f]{16,}"` over the working tree and
   `git log -p | Select-String -Pattern "sk-or-v1-[0-9a-f]{16,}"` over the
   history; both must be empty, and the harmless `sk-or` strings they do not
   match are listed by name in `voice/CHECKS.md` as they are found when the
   check runs — this plan and `voice/CHECKS.md` contain the string themselves,
   so the list is written at check time rather than fixed in advance. The server
   logs to the terminal only, never to a file, so provider text in the log can
   never be committed. A key in any commit is treated as compromised, so it
   would have to be rotated, not deleted.
10. **The per-visit cost is not yet in `spec.md`.** The typed cost estimate
    there covers the chat only. The one-turn total measured in step 8 belongs
    in `spec.md` under the hosting decision, which is due November 30.
11. **Behavior 11 has no no-key test.** "A misheard question falls to the
    refusal, not to an invention" cannot be tested without a model, and a faked
    model proves only the fake. Its evidence is the code-level whole-reply
    replacement in `test_refusal.py` — the refusal is written by code, not by
    the model — and own-02's refusal in the eval, where the question is
    genuinely out of scope. Blast radius: a mishearing that still lands on a
    topic the profile answers is answered, truthfully and wrongly, and nothing
    catches it.

### Proof

Two suites. They are not interchangeable, and a green run of one is not a pass
of the other.

**A. The no-key suite — nothing is billed.**

Run: `pytest voice/tests -q` with `VOICE_EVAL` unset. The key *is* set in this
session, so it is `VOICE_EVAL` that holds the billed tests back — the billed
tests in `test_eval.py` run only when `OPENROUTER_API_KEY` is set **and**
`VOICE_EVAL=1`, and skip otherwise. An ordinary `pytest` run therefore never
bills, whether or not a key is present. Under a second, no network. The loop
tests use a faked client: the model call is a stub that records what it was
asked, so the assertions are about the code's behaviour, not about a
provider's answer. `test_transcribe.py` fakes the transcription call the same
way, so the set run and its exit code are proved without a key.

| Test | What it proves | Cost |
|---|---|---|
| A perfect transcript scores 0.0 | the checker's arithmetic on the easy case | $0 |
| One substituted word in thirteen scores one thirteenth | the rate is edits per expected word, not per word heard | $0 |
| The empty reply scores 1.0 and is reported, not raised | a failed transcript is a verdict, not a crash | $0 |
| A name that must survive is reported even when the rate is within tolerance | the named-word check is independent of the rate | $0 |
| A number read as words is a miss | "four fifteen" is not "415" | $0 |
| Extra whitespace and capitalization do not count, but a split word does | `Hello,  World!` equals `hello world`; "boot camp" for "bootcamp" is two edits — a substitution and an insertion — and with the appended "Music" it is 3 in 16 words (0.188), which is why the course's `expected.json` raises that clip's tolerance to 0.2 | $0 |
| The refusal constant matches `spec.md` word for word | the two copies of the message agree | $0 |
| A reply containing `OUT_OF_SCOPE` anywhere is replaced whole | the refusal never arrives spliced into a sentence | $0 |
| The spoken refusal carries no URL | nothing that cannot be heard is said | $0 |
| The screen refusal carries the email and the LinkedIn link | the visitor can act on it | $0 |
| A non-audio speech reply raises and writes no file | a provider's JSON error body never lands as audio | $0 |
| An empty transcript skips both the chat and the speech call | no model is asked to answer an empty question | $0 |
| A body over 10 MB is refused | the server's cap | $0 |
| An unknown audio type gets 415 | the format map | $0 |
| Every clip in the set is processed even after one fails | a failed clip never causes a second transcription | $0 |
| The set run exits 1 if any clip failed, 0 if none did | the eval command's exit code carries the verdict | $0 |
| The billed tests skip when `VOICE_EVAL` is unset, with the key set | an ordinary `pytest` run never bills | $0 |
| A rejected recording returns 502 with the plain message | the visitor is told the recording could not be read, in code and not in the provider's words | $0 |
| A rejected recording makes no chat call, no speech call, and writes no audio | the turn ends at the transcription step | $0 |
| The provider's message is in the server log and not in the reply | the browser never sees the provider, which the browser check asserts | $0 |
| A clip whose transcription raises is recorded as failed and the set carries on | the set run never stops early | $0 |

What this proves: the checking, the refusal, and the loop's own rules are right
without a model, so a failure points at the code and not at a bill.

**B. The billed eval — run by hand, with the key.**

Run these in your own terminal, from the repository root, in the virtual
environment. `$env:OPENROUTER_API_KEY` is already set in this session; it is
never typed into a file and never appears in a command.

```powershell
cd voice
python transcribe.py --set ../../ai-integration-course/examples/voice-loop/clips/expected.json --model openai/whisper-large-v3-turbo --out clips/transcripts-whisper-fixtures.json
python transcribe.py --set ../../ai-integration-course/examples/voice-loop/clips/expected.json --model elevenlabs/scribe-v2 --out clips/transcripts-scribe-fixtures.json
python transcribe.py --set clips/expected.json --model openai/whisper-large-v3-turbo --out clips/transcripts-whisper-own.json
python transcribe.py --set clips/expected.json --model elevenlabs/scribe-v2 --out clips/transcripts-scribe-own.json
python answer.py --ask "What broke in your receipt reader project, and which skills from CPSC 415 have you actually shipped?" --out speaks/answer.txt
python speak.py --in speaks/answer.txt --out speaks/answer-class.mp3
python speak.py --in speaks/answer.txt --model elevenlabs/eleven-v4-turbo --voice george --out speaks/answer-eleven.mp3
```

The chat call comes before the speech calls on purpose: `answer.py` writes
`speaks/answer.txt` once, and both voices speak that exact file, so what is
spoken is the chatbot's answer and not a retyped copy of it.

One path or the other, not both: `$env:VOICE_EVAL = "1"` followed by
`pytest voice/tests/test_eval.py -q` is the same eval behind the gate. Running
it *and* the commands above transcribes every clip twice and bills it twice.

The exit code is part of the result: `transcribe.py` exits 1 if any clip in the
set failed and 0 otherwise, so a scripted run of these commands trips on a bad
clip instead of passing quietly. It never stops early — a failed clip is
transcribed like every other one, so nothing is billed twice.

What it proves: which transcriber reads Nadia's own voice correctly and whether
the named words survive — on the fixtures, which are a baseline no person
spoke, and on her own voice, which is the case that matters; and that the
answer the two voices speak is the answer `answer()` gave.

What it costs: 13 billed calls — 10 transcriptions (5 clips × 2 models), 1
chat call, 2 speech calls. At the course's 2026-10-26 prices: Whisper
$0.00002–$0.00003 a clip, Scribe $0.00034–$0.00057 a clip, the chat call about
a tenth of a voice turn, the class speech model about $0.0015 for a
question's worth of characters, ElevenLabs Turbo about $0.0027. Total about a
cent — comfortably under five cents. The measured numbers go in
`voice/CHECKS.md`.

**Where the results are recorded, and why a green run is not a pass.**

`pytest` reports the billed eval as *skipped* unless `OPENROUTER_API_KEY` is
set **and** `VOICE_EVEL=1`, and a skip is not a failure — so `pytest -q` can be
green with nothing transcribed at all. The eval is therefore the commands
above, run by hand, and its results are recorded in `voice/CHECKS.md`:

- `## Clips` — one line per clip per model: the file, the model, the word
  error rate, the words that went missing, the audio seconds, the cost, and the
  seconds the call took. A clip the provider refused is a failed clip, and its
  cost is "none reported".
- `## Answer` — the one chat call: the question, the text it returned, the
  cost, and the seconds.
- `## Speaks` — one line per voice: the model, the voice, the text it spoke
  (which is `speaks/answer.txt`), the characters, the bytes, the cost, the
  seconds, and what the voice did with Nadia's name and the course number.
- `## One turn` — the transcript, the answer, the three costs, and the total.
- `## Browser check` — the run and its last three assertions.
- `## Key check` — the real-key search over the working tree and over the
  history, both empty, and the harmless `sk-or` strings listed as they are
  found when the check runs before the tag. This plan and `voice/CHECKS.md`
  contain the string themselves, so the list is written at check time rather
  than fixed in advance. A match that is not one of the named harmless strings
  is a failure, not a note.

The rule: **the eval has run when `voice/CHECKS.md` carries the numbers, and
not before.** The transcripts JSON is the receipt; `voice/CHECKS.md` is what a
reviewer reads. A green `pytest` with no `## Clips` section means the eval did
not run — and because the key is set in this session, green on its own is not
evidence of anything: the billed tests skip unless `VOICE_EVAL=1` is set
beside the key.

**Approved by (Week 7):** Nadia Boudhaim Maguire, 2026-11-08

## Week 8

The tool loop: a model can ask for one of two registered tools, our code validates the call and runs it or refuses it, and hands the result back as the next message. Built in `tools/`, on the stand-in in `voice/answer.py`, because the real chatbot does not exist yet. The loop is wired into `voice/answer.py` so the typed and voice paths share the same call; the swap to `data/profile.yaml` and the real answer function is scheduled before November 30. The `recent_commits` tool reads Nadia's real GitHub (`nboudhai`); the stand-in lives in `voice/`, the real call lives in `tools/`, and `tools/CHECKS.md` says so. No credential in the repository: the tool sends an `Authorization` header when `GITHUB_TOKEN` is in the environment and sends nothing when it is not, and `recent_commits` is faked in tests so no test that runs without a key reaches GitHub.

### Files to create or change

| File | Purpose |
|---|---|
| `tools/registry.py` | One constant per tool: name, description, JSON Schema arguments, handler. The repository list is one constant in code, and the schema's description is built from that constant so the list is never written twice. Argument validation is the plain-code `validate()` pattern from the course's `tools.py`. |
| `tools/github_tool.py` | The `recent_commits` handler. `urllib` from the standard library for the GitHub call. Validates that the owner is `nboudhai` and the repository is on the list of six, GETs the commits, and normalises the response to five `{sha, date, subject}` entries. Every failure is a result, not an exception. |
| `tools/intro_tool.py` | The `request_intro` handler. Validates arguments against the schema and always returns pending; nothing is written, nothing is sent, and the pending record stays in the trace. |
| `tools/loop.py` | The `run()` function and the named `check_answer(answer, trace)` function. `run()` takes the conversation so far, runs the loop with a step cap of four, validates each tool call against the registered schema, runs the handler or returns an error result, feeds the result back to the model as the next message, and returns `(answer, total_cost, trace)`. The trace carries tool name, arguments, result or error, number of steps, and verdict. `run()` does not know about refusals. `check_answer(answer, trace)` is the named function that scans the answer for short shas and repository names that did not appear in any tool result and flags a mismatch; the verdict field in the trace is its return value. |
| `voice/answer.py` | Modified to import `tools.loop.run` and `tools.registry`, build the system prompt with the schema of each registered tool, and call `run()` with the registered tools. `answer()` returns the three-tuple `(answer, cost, trace)`, keeping the cost it returns today. If the trace carries a pending record from `request_intro`, `answer()` returns the refusal in code, whatever the model wrote; the `OUT_OF_SCOPE` → refusal substitution also stays here. Both paths (typed and voice) share the same call; `voice/server.py` unpacks the three-tuple at both call sites and its response bodies stay unchanged. The cost is what `server.py` and the eval both need. |
| `tools/CHECKS.md` | The eval record. One section per model: per-question cost, tools called, verdict, the answer, and the sha/repo check. Plus the cost-of-question-3 as the cost-without-a-tool, "What the check cannot catch" — a name check cannot tell "X does not exist" from invented commits about X when no sha is given — and the key check before the tag. |
| `tools/tests/conftest.py` | Puts `tools/` on `sys.path`; a scripted `FakeModel` that implements the same tool-calling shape as the real one; a faked `urllib.request` so the no-key suite never reaches GitHub. |
| `tools/tests/test_registry.py` | The no-key tests of the registry: the repository list is one constant, the schema's description is built from it (one source of truth), and the schema is the JSON Schema the model sees. |
| `tools/tests/test_github_tool.py` | The no-key tests of `recent_commits` with `urllib` faked: a name that is not `owner/name`, an owner that is not `nboudhai`, a repository not on the list, GitHub returning 403, or GitHub unreachable — each is an error result, never an exception. The `Authorization` header is sent only when `GITHUB_TOKEN` is in the environment. |
| `tools/tests/test_intro_tool.py` | The no-key tests of `request_intro`: arguments are validated, the call is recorded as pending, no email is sent, no file is written, and the trace carries the pending record. |
| `tools/tests/test_loop.py` | The no-key tests of the loop with the scripted fake model: the single-shot call, bad arguments, an unknown tool, an endless caller stopped at the cap, the side effect held, and the unsupported claim flagged. |
| `tools/tests/test_eval.py` | The billed eval. Runs only when `OPENROUTER_API_KEY` is set **and** `TOOLS_EVAL=1`; otherwise skipped, not failed. Runs the five questions on each of the two models; each tool question needs at least two chat calls (one for the tool call, one for the final answer after the tool result); question 3 is profile-only and needs one. Per question: tools called, verdict, cost, seconds. Results go in `tools/CHECKS.md`. |

### Order of work

1. **Approve the plan.** The spec's Week 8 section is approved; the plan approval is the remaining gate. Commit `Approve plan (week 8)`. No code before it.
2. **The registry, tests first.** Two commits, red then green. First commit: `tools/tests/test_registry.py` — the failing tests. Second commit: `tools/registry.py` — the code that makes them pass. *Proof:* the history shows red then green; `pytest tools/tests/test_registry.py -q` green with no key set and nothing billed.
3. **The handlers, tests first.** Two commits, red then green. First commit: `tools/tests/test_github_tool.py` and `tools/tests/test_intro_tool.py` — the failing tests. Second commit: `tools/github_tool.py` and `tools/intro_tool.py` — the code that makes them pass, with `urllib` faked so the no-key suite never reaches GitHub. *Proof:* green, no key, no billed call, no HTTP to GitHub.
4. **The loop, tests first, with the scripted fake model.** Two commits, red then green. First commit: `tools/tests/test_loop.py` — the failing tests against a `FakeModel` that copies the course example's tool-calling shape: a single-shot caller, a caller with bad arguments, an unknown-tool caller, an endless caller that asks the same tool on every step, a caller that invokes `request_intro`, and an answer that names a sha and a repository the tool never returned. Second commit: `tools/loop.py` — `run()` and `check_answer()` that make them pass. *Proof:* `pytest tools/tests/test_loop.py -q` green with no key set; each of the six assertions maps to one behavior in `spec.md` §"Week 8 behaviors."
5. **The loop into `answer.py`.** `voice/answer.py` calls `tools.loop.run` with the registered tools. `answer()` returns the three-tuple `(answer, cost, trace)`, keeping the cost it returns today. If the trace carries a pending record from `request_intro`, `answer()` returns the refusal in code, whatever the model wrote; the `OUT_OF_SCOPE` → refusal substitution also stays here. `run()` does not know about refusals. `voice/server.py` unpacks the three-tuple at both call sites and its response bodies stay unchanged. The typed and voice paths share the same call. *Proof:* `pytest voice/tests -q` green — the whole Week 7 suite, with the Week 7 fakes updated where they stub the chat call; the no-key tools suite still passes; a no-key test asserts the same `run()` is reached from `answer.py` and not duplicated.
6. **The eval.** `tools/tests/test_eval.py` runs the five questions once per model, behind the gate (`OPENROUTER_API_KEY` set **and** `TOOLS_EVAL=1`). Each tool question needs at least two chat calls (one for the tool call, one for the final answer after the tool result); question 3 is profile-only and needs one. *Proof:* `tools/CHECKS.md` carries the per-question costs, the tools called, the verdicts, the answers, and the cost of question 3 as the cost-without-a-tool. Commit `Tools: the eval, on two models`.

### Risks

1. **A green test run with skips is not a passed eval.** The key is set in this session, so `TOOLS_EVAL=1` is what holds the billed test back. Without both, the test skips, and a skip is not a failure. Mitigation: the gate is two conditions, never one; the eval runs by hand with both env vars set; and the rule is that the eval has run when `tools/CHECKS.md` carries the numbers. See Proof §A and §B.
2. **The repository list is written twice.** The list of six repositories lives in the schema description and in the `validate()` function — the spec says the description is built from the constant, so it is the one source. Mitigation: a no-key test asserts the schema description contains every name in the constant and no other, so a drift fails the suite.
3. **The owner check happens too late.** The check is in `github_tool`, not in the loop, so an unknown owner still enters the conversation as a tool call. It returns an error result, but a malformed call has already entered the loop. Mitigation: the owner check is the first thing the handler does, and a no-key test asserts a stranger's repo is refused before any `urllib` call is opened.
4. **`request_intro` runs in production.** The handler must never write or send; today the call is held as pending in the trace. Mitigation: the handler is one function, its only side effect is to record the pending entry in memory, and a no-key test asserts nothing leaves the process. A pending record becomes a real call only when a person confirms, which is not in scope for Week 8 and is a separate code path added later.
5. **The unsupported-claim check is blind to commit subjects.** A model that invents a commit subject cannot be caught by the sha/repo check, because the subject is not in the tool result. Mitigation: the spec says so, and `tools/CHECKS.md` says so; the eval compares each answer to the trace and flags an invented subject by hand. The no-key suite catches a real sha or repo that did not come back; the eval catches the rest.
6. **The fake model drifts from the real one.** The scripted `FakeModel` in `conftest.py` mirrors the real model's tool-calling shape — name, arguments, finish reason. A change in the real model's shape silently invalidates the no-key suite. Mitigation: the `FakeModel` copies the course example's shape verbatim.
7. **The key reaches the repository.** There is no CI yet — the site's CI is plan.md step 8 and does not exist. Mitigation: before tagging, run `git grep -nE "sk-or-v1-[0-9a-f]{16,}"` over the working tree and over the history; both must be empty, and the harmless matches listed by name in `tools/CHECKS.md` as they are found when the check runs. A match that is not on the named list is a failure, not a note.
8. **The step cap is the wrong number.** Four steps is a guess. A model that needs three (one for the tool call, one for the result, one for the answer) works; a model that needs five to compose a longer answer would be capped at four and the visitor would get the program's sentence. Mitigation: the cap is a constant in code, and the eval records the steps per question so a too-low cap is visible in `tools/CHECKS.md`. The constant changes in one place.

### Proof

Two suites. They are not interchangeable, and a green run of one is not a pass of the other.

**A. The no-key suite — nothing is billed.**

Run: `pytest tools/tests -q` with `TOOLS_EVAL` unset. The key *is* set in this session, so it is `TOOLS_EVAL` that holds the billed test back — the billed test in `tools/tests/test_eval.py` runs only when `OPENROUTER_API_KEY` is set **and** `TOOLS_EVAL=1`, and skips otherwise. An ordinary `pytest` run therefore never bills, whether or not a key is present. Under a second, no network: the loop tests use a scripted `FakeModel` that implements the same tool-calling shape as the real one, and `urllib` is faked so no test reaches GitHub. The assertions are about the code's behaviour, not about a provider's answer.

| Test | What it proves | Cost |
|---|---|---|
| The single-shot call: a model that returns one tool call, the handler returns five commits, the loop ends and returns the answer | the happy path: one tool call, one result, one answer | $0 |
| Bad arguments: the model passes a wrong-type `repo`, the loop returns an error result naming the field and the problem, the loop carries on, the handler is not called | arguments are validated before any handler runs; a bad call is a result, not an exception | $0 |
| An unknown tool: the model names a tool that is not registered, the loop returns an error result | the registry is the only source of allowed tools; no call leaves the server for an unknown name | $0 |
| An endless caller: a model that asks the same tool on every step is stopped at four steps, the answer is the program's sentence | the step cap is enforced in code, not by the model | $0 |
| The side effect held: a model calls `request_intro`, the handler returns pending, no email is sent, no file is written, the trace carries the pending record | side effects are gated behind a person; nothing leaves the process | $0 |
| An unsupported claim: an answer names a short sha and a repository the tool never returned, the code check flags both | the answer cannot escape the tool's results; the check cannot see an invented commit subject, and `tools/CHECKS.md` says so; a name check cannot tell "X does not exist" from invented commits about X when no sha is given, and `tools/CHECKS.md` says so | $0 |

What this proves: the loop's rules are right without a model, so a failure points at the code and not at a bill. The six assertions map one-to-one to behaviors 1–6 in `spec.md` §"Week 8 behaviors."

**B. The billed eval — behind the gate.**

Run in your own terminal, from the repository root, in the virtual environment. `$env:OPENROUTER_API_KEY` is already set in this session; it is never typed into a file and never appears in a command.

```powershell
$env:TOOLS_EVAL = "1"
pytest tools/tests/test_eval.py -q
```

The eval runs the five questions once per model, prints per question the tools called, the verdict, the cost, and the seconds, and writes the answers and the sha/repo check to `tools/CHECKS.md` the same way `voice/CHECKS.md` carries the per-clip numbers. Question 3 of the set is the one the profile answers without the tool, and its cost is the cost-without-a-tool for the comparison.

The exit code is part of the result: `pytest` exits 1 if any question failed and 0 otherwise, so a gate run trips on a bad question instead of passing quietly. It never stops early — a failed question is checked like every other one, so nothing is billed twice.

What it proves: which model calls the tool correctly, which model handles the refusal honestly, and what the per-question cost is with and without a tool on each of the two models.

What it costs: about 20 billed chat calls. Each tool question needs at least two — one for the tool call, one for the final answer after seeing the tool result — and question 3 (the profile-only question) needs one. Across two models, that is 4 × 2 × 2 + 2 = 18; the loop's occasional retries push it to about 20. At the spec's Haiku price of ~$0.003 per chat, the eval is about $0.06 on Haiku and comparable on the class model. The measured numbers go in `tools/CHECKS.md`.

**Where the results are recorded, and why a green run is not a pass.**

`pytest` reports the billed eval as *skipped* unless `OPENROUTER_API_KEY` is set **and** `TOOLS_EVAL=1`, and a skip is not a failure — so `pytest -q` can be green with nothing evaluated at all. The eval is therefore the commands above, run by hand, and its results are recorded in `tools/CHECKS.md`:

- `## Per model` — one section per model: the five questions, the answer, the tools called, the verdict (sha/repo check pass/fail), the cost, and the seconds.
- `## Cost without a tool` — the cost of question 3, the profile-only question, on each model. This is the baseline the per-question cost is compared against.
- `## Key check` — the real-key search over the working tree and over the history, both empty, and the harmless matches listed by name as they are found when the check runs before the tag. This plan and `tools/CHECKS.md` contain the string themselves, so the list is written at check time rather than fixed in advance. A match that is not on the named list is a failure, not a note.

The rule: **the eval has run when `tools/CHECKS.md` carries the numbers, and not before.** The eval JSON is the receipt; `tools/CHECKS.md` is what a reviewer reads. A green `pytest` with no `## Per model` section means the eval did not run — and because the key is set in this session, green on its own is not evidence of anything: the billed test skips unless `TOOLS_EVAL=1` is set beside the key.

**Approved by (Week 8):** *Nadia Boudhaim Maguire, 2026-11-15*

**Approved by:** Nadia Boudhaim Maguire
