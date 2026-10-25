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

**Approved by:** Nadia Boudhaim Maguire
