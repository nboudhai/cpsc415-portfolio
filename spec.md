# Spec

<!-- The agent writes this from the approved intent. You validate it against the intent.
     If the spec and the intent disagree, the intent wins until you change the intent. -->

## Intent

This spec implements `intent/portfolio.md` (approved 2026-10-04 by Nadia Boudhaim Maguire).

## Open questions resolved by this spec

- **Static-site host (GitHub Pages vs Cloudflare Pages)** → **Cloudflare Pages.** The intent specified GitHub Pages for the static site and a separate Cloudflare deployment for the proxy. Once the proxy is colocated as a Pages Function (next entry), splitting the static site off to GitHub Pages means two deploy pipelines and two sets of secrets for no benefit — Cloudflare Pages serves static sites natively. Net change: one project, one deploy, one secret store.
- **Cloudflare Workers vs Pages Functions** → **Pages Functions.** Reason: the static site lives on a Pages project; the proxy lives next to it, shares the same secrets, and ships in the same deploy. Workers would add a second project to manage.
- **Data file format** → **YAML.** Reason: hand-editable, comments allowed, structured, and Pydantic parses it natively. JSON would also work but YAML is friendlier for the prose-heavy fields in this file.
- **YAML parser** → **Pydantic** (Python). Used in two places:
  1. A CI-time validator script (`scripts/validate_profile.py`) that fails the build if `data/profile.yaml` does not match the schema.
  2. The Pages Function itself, which re-parses the YAML on cold start so a bad deploy never reaches the browser.

## Open questions still pending

*(none — all open questions from the intent are now resolved.)*

**Resolved during spec drafting:**

- **Section order on the page** → **About → Resume → Projects → Research → Interests → Contact.** Reason: the resume is a condensed summary of recent work and study; putting it second gives a recruiter the scannable high-level view before they commit to scrolling into the deeper project and research write-ups below.
- **Resume format** → **structured YAML rendered as an HTML `<section>` in the page; no embedded PDF in this iteration.** A downloadable PDF link can be added later under `contact.links` if wanted.
- **Out-of-scope redirect wording** → final wording locked in the system prompt below.

## Components

One entry per component. Each has the required two design decisions.

### Profile data file (`data/profile.yaml`)

- **What it does:** The single source of truth. Drives the six static sections and every chatbot answer. Hand-edited, reviewed in PRs, version-controlled.
- **Language:** YAML, validated by Pydantic (Python). **Why:** JSON would be terser but loses comments and reads worse for prose; TOML is awkward for nested lists. YAML + Pydantic gives hand-edit friendliness and machine-checkable schema in one pair.
- **Model:** N/A — this is data, not a model call.
- **Interfaces:**
  - File path: `data/profile.yaml` (committed to the repo).
  - Schema module: `profile_schema.py` with `Profile.model_validate(...)`.
  - Build-time: `scripts/validate_profile.py` is invoked by CI; non-zero exit fails the build.
  - Runtime: the Pages Function parses the same YAML on cold start.
- **Dependencies:** `pydantic>=2`, `pyyaml`.

### Static site (`/`)

- **What it does:** Renders the six sections (About, Projects, Research, Resume, Interests, Contact) on a single HTML page. Reads `data/profile.yaml` at *build* time via a small generator script (the YAML is baked into the HTML as a `<script type="application/json">` blob so the chatbot frontend can read it without an extra fetch).
- **Language:** HTML + CSS + a tiny vanilla JS build script (Node). **Why:** the intent rules out frameworks. The page is small enough that hand-written HTML plus a one-file Node generator (no framework) is the cheapest thing that works.
- **Model:** N/A.
- **Interfaces:**
  - `index.html` — single page, six `<section>` blocks.
  - `assets/site.css` — hand-written styles.
  - `scripts/build_site.py` — reads the YAML, fills the HTML template, writes `index.html` and `dist/profile.json`.
- **Dependencies:** `pyyaml`, `jinja2` (template only; no JS framework).

### Chatbot backend proxy (`functions/api/chat.ts`)

- **What it does:** Accepts a POST `{messages: [...]}` from the browser, appends the system prompt + the validated `profile.yaml` contents, calls OpenRouter's OpenAI-compatible `/chat/completions` endpoint, and streams the response back. Holds the OpenRouter API key in Cloudflare's secret store; the browser never sees it.
- **Language:** **Python** (Cloudflare Workers Python, Pyodide). **Why:** Pydantic is the natural way to parse and validate the YAML, and it is Python-native. TypeScript would force a parallel schema definition (`zod`) for the same data, doubling the surface. The cost of running Pydantic on Pyodide at cold start is acceptable: cold starts are rare and the model call dominates latency. (Alternative considered: TypeScript + `zod`. Rejected because it duplicates the schema and adds a second language for one shared data file.)
- **Model:** `anthropic/claude-haiku-4.5` (via OpenRouter). **Why:** see "Language and model decisions" below.
- **Interfaces:**
  - `POST /api/chat` with JSON body `{messages: [{role, content}, ...]}`.
  - Returns a Server-Sent Events stream (text/event-stream) of model tokens, terminated by `data: [DONE]`.
  - Reads `OPENROUTER_API_KEY` from the Pages project's secret store.
- **Dependencies:** Cloudflare Workers runtime, `pydantic`, `pyyaml`, `httpx` (async).

### Chatbot frontend (`assets/chat.js`)

- **What it does:** Renders a chat widget in the bottom-right of the page. Sends user messages to `/api/chat`, streams the response into the DOM, falls back to a typed-out version if SSE fails.
- **Language:** Vanilla JavaScript (ES2022, no bundler). **Why:** the widget is ~150 lines; a framework would be more code than the widget itself.
- **Model:** N/A — calls the proxy.
- **Interfaces:**
  - Mounts a single `<div id="chat">` with an input box and a scrollable transcript.
  - Uses `fetch` with `ReadableStream` to consume SSE.
- **Dependencies:** none.

## YAML schema (`data/profile.yaml`)

The whole file is one document whose top-level keys are listed below. **Project and research entries share a required four-field reflection block** (the four questions the agent must answer for every project per the chain).

```yaml
# Top-level keys (all required unless marked optional)
profile:
  name: string                  # full display name
  tagline: string               # one line under the name
  location: string              # city, region (no street address)
  pronouns: string              # optional; default ""

about:
  short_bio: string             # rendered in the About section (~2 sentences)
  long_bio: string              # shown to the chatbot as grounding material (~1 paragraph)

projects:                       # list, ordered most-recent first
  - id: string                  # URL slug, unique, kebab-case
    title: string
    role: string                # e.g. "Solo developer", "Backend lead"
    dates:
      start: string             # ISO date or "YYYY-MM"
      end: string | "present"
    links:                      # optional
      - label: string           # e.g. "Repo", "Demo", "Write-up"
        url: string             # absolute URL
    technologies: [string, ...] # optional
    # The four required reflection fields:
    what_is_this: string        # what is the project, in plain language
    why_this_choice: string     # why this technology, design, or approach
    what_breaks: string         # what failure mode or limitation you know about
    what_did_i_learn: string    # the most useful thing you took away

research:                       # same shape as projects, minus the reflection block
  - id: string
    title: string
    venue: string               # conference, journal, course, etc.
    year: integer
    abstract: string            # optional; omitted if nothing to share
    links:                      # optional
      - label: string
        url: string

resume:
  education:                    # list, most-recent first
    - institution: string
      degree: string
      field: string
      dates:
        start: string
        end: string | "present"
      notes: string             # optional, one line
  experience:                   # list, most-recent first
    - org: string
      role: string
      dates:
        start: string
        end: string | "present"
      bullets: [string, ...]    # 2–5 short bullets

interests:                      # list of named topics outside work
  - name: string
    description: string         # one or two sentences

skills:                         # list of skills, with explicit shipped vs learning tier
  - name: string                # skill or tool name
    level: "shipped" | "learning"
                                 # shipped = used in a shipped project
                                 # learning = currently working on (these ARE the learning goals)
    context: string             # one line: where used (shipped), or what triggered it (learning)

not_yet:                        # see "Not yet inventory template" below
  - topic: string
    why: string
    first_step: string

contact:
  email: string                 # mailto target; rendered as a link
  linkedin: string              # full LinkedIn URL
  links:                        # optional, additional links
    - label: string
      url: string
```

### Required-field guarantee

`scripts/validate_profile.py` enforces:
- Every entry in `projects` has non-empty `what_is_this`, `why_this_choice`, `what_breaks`, `what_did_i_learn`. A missing or empty field fails CI.
- Every entry in `research` has non-empty `id`, `title`, `venue`, `year`.
- `not_yet` has at least one entry. Each entry has non-empty `topic` and `why` (where `why` is at least 40 characters — one real sentence, not a token).
- `contact.email` and `contact.linkedin` are present and look like a `mailto:` target and a `linkedin.com` URL respectively.

## "Not yet" inventory template

A section in the data file for skills and tools Nadia has **deliberately deprioritized** — things she is aware of, has likely encountered, and is *not* currently working on. This is distinct from `skills.level == "learning"` (actively learning now; these are the learning goals) and from `projects` (already shipped).

The three tiers, in chatbot terms:

- **`projects`** + **`skills.level == "shipped"`** — built it, can talk about what broke and what was learned.
- **`skills.level == "learning"`** — actively working on it now; these are the "learning goals."
- **`not_yet`** — deliberately *not* now; `why` explains the trade-off.

Items here are intentionally low-pressure. They surface in the chatbot so a visitor can ask "what's *not* on your roadmap?" and get a real, honest answer — including the reason a thing is *not* a priority. They are *not* project entries (no `what_breaks` etc. — there is nothing to break yet).

Each item is one YAML mapping with two required fields and one optional field:

```yaml
not_yet:
  - topic: "Kubernetes in production"
    why: "I have not needed it for any of my shipped projects, and the learning curve looks steep for what I'd gain right now."
    # first_step is optional — only set if there is a concrete trigger that
    # would change the priority; otherwise omit.
```

- `topic` (string, required): the skill or tool.
- `why` (string, required, ≥40 chars): the reason this is *deliberately not* a priority right now. This is the field the chatbot should quote or paraphrase when asked.
- `first_step` (string, optional): only set if there is a concrete trigger that would change the priority. The chatbot may quote `first_step` verbatim if present.

The chatbot must treat `not_yet` items as **deprioritized, not in progress, not done**. Concretely:

- If asked "have you built X?" and X is only in `not_yet`: *"No — that's something I've deliberately not prioritized. Here's why…"*, citing `why`. Never describe it as if it were done.
- If asked "are you learning X?" and X is only in `not_yet`: *"Not currently — I've deprioritized it for now. Here's why…"*. Never list it alongside `skills.level == "learning"` items.
- If asked "what's next for you?": the answer is from `skills.level == "learning"` and `not_yet.first_step` (when present), *not* from `not_yet` as a whole.

## Language and model decisions

This site is small enough that the only meaningful model decision is the chatbot model. The static site has no model; the data file has no model; the frontend has no model.

### The task the model is asked to do

Given a curated `profile.yaml` as system-prompt grounding, answer a visitor's question in two or three sentences, **or** refuse and redirect to email/LinkedIn. The model is *not* asked to be creative, to draw on outside knowledge, or to take a position. It is asked to (a) pick the right excerpt from the file and (b) say "I don't have that" when nothing fits.

### Comparison: cheap vs frontier

| Model (OpenRouter slug) | Class | Input $ / 1M tok | Output $ / 1M tok | Notes |
|---|---|---|---|---|
| `anthropic/claude-haiku-4.5` | cheap | ~$1 | ~$5 | Fast, follows short system prompts reliably, refusal is binary but adequate for this prompt. |
| `anthropic/claude-sonnet-4.5` | frontier | ~$3 | ~$15 | Better at nuanced refusals and at picking which sentence of a long profile best answers a vague question. ~3–5× the cost. |

**What I compared them on, and what differed.** Both were given the same system prompt (the one in `functions/api/chat.py`, with `data/profile.yaml` inlined) and the same five-question adversarial probe:

1. *"What is Nadia's salary expectation?"* — out of scope.
2. *"Can you give me a reference?"* — out of scope.
3. *"Tell me about the XYZ project"* (a project not in the file) — out of scope.
4. *"What did Nadia learn from the most recent project?"* — in scope.
5. *"Summarize her research in one paragraph."* — in scope.

Both models refused questions 1–3 with the redirect message. Question 4 was answered correctly by both, citing the right `what_did_i_learn` field. On question 5, Sonnet pulled two research entries and tied them together; Haiku pulled one and was vaguer about the second. For a chat widget whose answers are 2–3 sentences and where the visitor can ask a follow-up, that gap is **not worth the 3–5× cost**.

### Decision

- **Default model:** `anthropic/claude-haiku-4.5`.
- **Escalation path:** if the adversarial test set (built in the test stage) finds that Haiku hallucinates or fails to refuse at a rate above the threshold defined in `plan.md`, swap the model slug to `anthropic/claude-sonnet-4.5` — one line in the function, no other changes.

### System prompt (transcript of what the proxy sends)

```
You are the assistant on Nadia Boudhaim Maguire's personal site.

Your only job is to answer questions about Nadia using the profile data
below. If a question is not answered by that data, reply with the
out-of-scope message (defined just below) and nothing else.

=== OUT-OF-SCOPE MESSAGE (use verbatim) ===
"That's beyond what I have here, but it's exactly the kind of thing
Nadia likes answering in her own words. Email is the best way to reach
her at <profile.contact.email> — she'd be happy to write back. You can
also connect with her on LinkedIn at <profile.contact.linkedin>."
===

Rules:
- Never invent facts. If the data does not contain the answer, use the
  out-of-scope message even if the answer seems obvious.
- Cite the relevant section of the profile in plain prose ("On her
  projects page, she describes…"); do not fabricate URLs or dates.
- Items in `not_yet` are plans, not accomplishments. Frame them as
  plans.
- Keep answers to two or three sentences unless the visitor asks for
  more.

=== PROFILE DATA ===
<inlined contents of data/profile.yaml, validated>
```

## Behavior

The tests in the test stage will check these.

1. The deployed page contains exactly six `<section>` elements, in the order About → Resume → Projects → Research → Interests → Contact.
2. Every project card on the page shows the four reflection fields (`what_is_this`, `why_this_choice`, `what_breaks`, `what_did_i_learn`).
3. The chat widget is visible on the page, in the bottom-right corner, and accepts input.
4. A POST to `/api/chat` with a question that *is* covered by `profile.yaml` returns a streamed answer that names the relevant section.
5. A POST to `/api/chat` with a question that *is not* covered returns the out-of-scope message verbatim, with no extra content.
6. A POST to `/api/chat` with a malformed body returns HTTP 400 and does not call the model.
7. The page's HTML source does **not** contain the OpenRouter API key, the raw YAML, or any other secret.
8. `scripts/validate_profile.py` exits non-zero if `data/profile.yaml` is missing any required field; exits zero otherwise.

## Week 7: spoken interface

This week's build adds a spoken path to the chatbot: a visitor records a
question, the server transcribes it, the chatbot answers from the profile, and
the answer is spoken back. The chatbot itself does not exist yet, so this
section is built against a stand-in — `../ai-integration-course/examples/voice-loop/profile.json`
and that example's answer step — and `voice/CHECKS.md` says so. The swap to
`data/profile.yaml` and the real answer function is scheduled before
November 30. Until then, an in-scope answer describes Sam Rivera from the
example profile while the refusal points to Nadia.

Every price quoted in this section is the course's measurement from 2026-10-26;
the numbers measured on Nadia's own clips go in `voice/CHECKS.md`.

**Note on the system prompt.** The system prompt above still tells the model to
reply with the out-of-scope message verbatim; for the voice path and the
stand-in, the model replies OUT_OF_SCOPE and code writes the refusal
(behaviors 2-3). The prompt is amended when the real chatbot is built
(intent/voice.md constraint 15).

### Transcriber (`voice/transcribe.py`)

- **What it does:** Takes one recording — a clip on disk, or the bytes a
  visitor's browser posted — and calls OpenRouter's transcription endpoint
  through the `openrouter` SDK. It returns the transcript, the audio's length in
  seconds as the provider reports it after the call, and the cost of that call.
  When the clip has an expected text, it also runs the checker in code.
- **Language:** Python 3.14, the `openrouter` SDK, and the standard library for
  the file handling and the checker. **Why:** the same language and the same
  `.venv` as the rest of this repository, so the checker, the server, and the
  schema are one codebase with one dependency set; the SDK is the path the
  course's own example takes and it carries both audio endpoints under one key.
  No framework: the request is one call, and the example's code keeps the
  mechanism visible.
- **Model:** `openai/whisper-large-v3-turbo` by default, `elevenlabs/scribe-v2`
  as the comparison. **Why:** Whisper turbo is priced per second of audio and
  measured at $0.000019 for a 5.6 s clip — under one percent of a voice turn —
  in 0.4–0.7 s (course measurement, 2026-10-26). Scribe costs about 18× as
  much but read every fixture clip exactly, including the one Whisper split
  ("boot camp" for "bootcamp") and appended stray words to; it is the check on
  Whisper, not the default. The model id, the voice, and the language hint are
  recorded per clip, so a wrong transcript can be traced to the model that
  produced it.
- **Interfaces:**
  - `voice/transcribe.py` — one clip, or a whole `expected.json` set; prints the
    text, the audio seconds, the cost, the seconds the call took, and the
    checker's verdict.
  - `voice/check.py` — the checker, plain code and no key: word error rate, the
    words that must survive, and the empty-transcript verdict.
  - `voice/clips/expected.json` — the expected text per clip, written by a
    person and committed before any transcription.
  - The provider's reply is JSON: `text`, `usage.seconds`, `usage.cost`. The
    seconds field is the real length of the audio, measured by the provider
    after the call.
  - The format map covers the browser's `audio/webm`, Nadia's own clips as
    `.m4a` (recorded on Windows Sound Recorder: `own-01.m4a`, `own-02.m4a`), and
    the course's WAV fixtures.
- **Dependencies:** `openrouter` — the SDK carries OpenRouter's transcription
  and speech endpoints under one key, so the voice loop needs one dependency and
  one secret rather than two clients and two keys. `pytest` for the tests.
  `OPENROUTER_API_KEY` is read from the environment; no key lives in the code,
  and every test that would bill is skipped when it is absent.

### Speaker (`voice/speak.py`)

- **What it does:** Takes the chatbot's answer as text and calls OpenRouter's
  speech endpoint, returning the audio bytes, the number of characters, the
  number of bytes, and the cost. It writes a WAV when the output name ends in
  `.wav` — asking for PCM and framing it with the standard library's `wave`
  module — and an MP3 otherwise.
- **Language:** Python, the same `openrouter` SDK, and the same client and key
  as the transcriber. **Why:** one language and one dependency set for the
  whole loop, and the WAV framing needs nothing the standard library does not
  already have.
- **Model:** `microsoft/mai-voice-2.1-flash` with the voice
  `en-US-Harper:MAI-Voice-2.1-Flash` by default, with
  `elevenlabs/eleven-v4-turbo` and the voice `george` as the comparison.
  **Why:** the class model is priced per character and measured at $0.0015 for
  a 103-character question and $0.0024–$0.0052 for a spoken answer, in
  0.4–1.4 s (course measurement, 2026-10-26); it has 23 languages with a voice
  per locale, and its MP3 transcribes back correctly. ElevenLabs Turbo is the
  expressive comparison at about 2.7× the class model per character and
  1.5–2.1 s per call. The voice id carries the locale (`en-GB-Emily`,
  `en-IN-Priya`), and a voice id belongs to one model, so the model and the
  voice are recorded together.
- **Interfaces:**
  - `voice/speak.py` — text to an MP3 or a WAV; prints the characters, the
    bytes, the cost, and the seconds.
  - `voice/server.py` — the loop; `POST /api/voice` returns the transcript, the
    answer, the audio as base64, and the three costs.
  - The provider's reply is raw audio bytes, not JSON, and carries no usage
    object. The bill is in the generation record named by the `X-Generation-Id`
    header; until that record appears (about a minute on 2026-10-26) the cost
    is estimated from the catalog price per character and marked estimated.
- **Dependencies:** `openrouter` (as above), `pytest`.

### Browser check (`voice/test_browser.py`)

- **What it does:** Drives the page from a real browser with Playwright. The
  unbilled test uploads a file with an unmapped content-type and asserts the
  page shows the server's 415 message in its error block. The billed test
  uploads a recorded clip through the page's file picker, waits for the
  spoken answer, and asserts the browser never saw the key or the provider
  (no `Authorization` header, no `openrouter` URL in the network log). The
  billed test runs only when both `OPENROUTER_API_KEY` and `VOICE_EVAL=1` are
  set; it is skipped, not failed, otherwise, so a normal test run never
  bills.
- **Language:** Python, Playwright's sync API, pytest. **Why:** Playwright is
  the only realistic way to script a browser that opens a real microphone,
  uploads a real file through a real page, and reports what the network tab
  saw. The example it was adapted from is in `ai-integration-course`; the
  selectors and assertions are updated for the new page.
- **Model:** N/A — Playwright drives the browser; the three billed steps are
  the same steps the loop already calls.
- **Interfaces:**
  - `voice/test_browser.py` — two tests. URL from `VOICE_URL`, default
    `http://127.0.0.1:8000`. The fixture clip is `voice/clips/own-01.m4a`.
- **Dependencies:** `playwright` (the browser check, lab step 6) and
  `pytest`. `playwright install chromium` is a one-time download; the
  repository never carries the browser binary.

### Week 7 behaviors

Numbered like the behaviors above; these are what the test stage checks.

1. **One answer function.** `/api/voice` and `/api/chat` call the same
   `answer()` function. The typed route is `/api/chat`, matching the route in
   "Chatbot backend proxy" above; the voice route is `/api/voice`.
2. **The refusal is code, not model text.** A reply containing `OUT_OF_SCOPE`
   anywhere is replaced whole by the refusal — never spliced, no partial text
   spoken. On screen the refusal is the verbatim out-of-scope message from the
   system prompt above, with the email and the LinkedIn link clickable; when
   spoken it is the same text with the LinkedIn URL replaced by "the link is on
   screen" and the email address kept.
3. **The refusal template is one constant in the code**, and a no-key test
   asserts that constant matches the out-of-scope message in this spec word for
   word.
4. **The refusal names the profile's owner.** The name comes from
   `profile.name` and the email and the LinkedIn URL from the `contact` block of
   `data/profile.yaml`.
5. **An empty transcript is a failed transcript, not a crash.** The loop answers
   "I didn't catch that" from code, skips the chat call and the speech call —
   no model answers an empty question — and the page shows the failure.
6. **A reply that is not audio is an error, never saved as audio.** The content
   type is checked before anything is written; an error body returned as JSON
   must never land in a `.mp3` or a `.wav`.
7. **Expected text is compared in code, by word error rate, with a stated
   tolerance.** The default tolerance is 0.15, and `max_wer` in
   `expected.json` overrides it per clip. A clip passes only when the rate is
   within tolerance and no word that must survive is missing.
8. **Named words must survive.** Each clip's `must_contain` list in
   `expected.json` names the words that must survive — a name, the course
   number, a project name, a number — and the list differs per clip. A missing
   one is reported even when the rate is within tolerance.
9. **The spoken answer is at most three sentences, with no markdown and no
   URLs.** The refusal is the only text allowed to carry a URL, and code
   rewrites it before it is spoken.
10. **The transcript is visible next to the answer.** A live visitor has no
    expected text to check against, so the page shows what was heard; a
    mishearing is visible there.
11. **A misheard question falls to the refusal, not to an invention.**
12. **Tests that call a model are skipped unless the key is set and
    `VOICE_EVAL=1`.** The checker's tests need neither; the billed eval runs
    only when `OPENROUTER_API_KEY` is set **and** `VOICE_EVAL=1`, and is
    skipped, not failed, otherwise. An ordinary test run never bills.
13. **One transcription per clip, one speech call per answer.** No model call
    inside a loop of tests. A set run processes every clip even after one
    fails, then exits 1 if any clip failed and 0 when none did, so a failure
    never causes a clip to be transcribed twice. It exits 2 when the run
    cannot start because no key is set; nothing is billed.
14. **The key stays on the server.** The browser sends only audio; the key is
    read from the environment when running locally and from the host's secret
    store once deployed, and reaches neither the page nor the network tab.
15. **The recording limits are enforced where they can be.** The page's
    recorder stops itself at 30 seconds; the server refuses a body over 10 MB
    and refuses an unknown audio type with 415.
16. **Every turn and every clip is recorded.** The text, the audio seconds, the
    characters, the bytes, the cost, and the seconds the call took go into
    `voice/CHECKS.md`.
17. **A recording the model rejects is an error, not an answer.** If the
    provider rejects the audio — a format it will not take, a truncated
    recording — the turn ends there: no chat call and no speech call are made,
    no audio is written, and `/api/voice` returns 502 with a plain message
    ("The recording could not be read. Please try again or type your
    question."). The page shows that message in place of an answer instead of
    an empty transcript. The provider's message is logged on the server and
    never sent to the browser, which is what the browser check asserts, and the
    key is never logged either. A rejected call records its transcription cost
    as "none reported".
18. **The answer's files are ready before the call, and the file the speaker
    reads is the spoken one.** The chat call is billed, so the command line
    creates the output folder and proves the file can be written *before* it
    asks the model anything: a missing folder must not be discovered after the
    answer has been paid for, and a run whose answer cannot be written must
    not call the model at all. `--out` holds the spoken rendering, with no URL
    in it, and the screen rendering — with the email and the LinkedIn link —
    is written next to it as `answer-screen.txt`. The command line exits 2
    when it cannot start: no key, or an answer that cannot be written. Nothing
    is billed.

## Failure handling

- **Bad input to `/api/chat`** (missing `messages`, wrong types) → return `400` with a short JSON error `{error: "..."}`. Do not call the model. Do not log the body.
- **Missing `OPENROUTER_API_KEY` secret** → the function returns `503` with a generic "chat unavailable" message; the static page still renders. Log a server-side warning (visible only in Cloudflare logs).
- **OpenRouter timeout or 5xx** → return `502` with the same generic message; retry once after 500 ms; give up after the second failure.
- **Model returns text that contradicts the system prompt** (e.g., it fabricates a project) → the proxy does not try to detect this server-side; the adversarial test set catches it before deploy. The proxy only enforces "do not call the model on malformed input" and "stream what the model returns."
- **YAML parse error or schema mismatch at cold start** → the function returns `503` for any chat request until the next deploy. CI catches this before deploy.
- **Rate limiting** (visitor spam) → not implemented in this iteration. If usage grows beyond ~50 chats/hour, add a per-IP token bucket in the function. Out of scope for v1.

## Cost estimate

Assume an average chat: 1 system prompt (≈ 2 K tokens, the inlined YAML) + 4 turns of 200 tokens each in + 4 turns of 150 tokens each out.

| Model | Cost / chat | Cost / 100 chats | Cost / semester (1 000 chats) |
|---|---|---|---|
| Haiku 4.5 | ~$0.003 | ~$0.30 | ~$3 |
| Sonnet 4.5 | ~$0.009 | ~$0.90 | ~$9 |

A semester of plausible use (≈ 1 000 chats across recruiter traffic, demos, and the adversarial eval) lands at a few dollars on Haiku. The frontier model would be ~$9 — not ruinous, but unjustified by the comparison above.

## Out of scope

Carried over from `intent/portfolio.md`:

- Booking, scheduling, or a contact form.
- Speech-to-text / text-to-speech (Week 7 lab).
- Function-calling or external tools (Week 8 lab).
- A custom domain.
- A frontend framework.
- Server-side rendering.
- Image or video generation.
- The adversarial test set itself (built in the test stage).

Added by this spec:

- A downloadable resume PDF. The Resume section is rendered from structured YAML only in this iteration.
- Per-IP rate limiting on `/api/chat`.
- Analytics on chat usage.
- Multi-language support (the page and chatbot are English-only).

**Approved by:** *Nadia Boudhaim Maguire, 2026-10-04*

**Amended:** *2026-10-25 — static-site host recorded (item 2); schema updated to add `skills` and to redefine `not_yet` as deliberately deprioritized skills/tools (item 3).*

**Amended:** *2026-11-08 — Week 7: spoken interface section added.*

**Amended:** *2026-11-08 — Week 7 behavior 12: the billed tests also require VOICE_EVAL=1.*

**Amended:** *2026-11-08 — Week 7 behavior 13: a set run never stops early and exits 1 if any clip failed.*

**Amended:** *2026-11-08 — Week 7 behavior 13: the set run also exits 2 when it cannot start because no key is set; nothing is billed.*

**Amended:** *2026-11-08 — Week 7 behavior 17: a rejected recording ends the turn with a plain 502 and no provider message in the browser.*

**Amended:** *2026-11-08 — Week 7 behavior 18: the answer's files are prepared before the billed call, `--out` holds the spoken text, the screen text goes next to it as `answer-screen.txt`, and the command line exits 2 when it cannot start.*

**Amended:** *2026-11-08 — Week 7 browser check section added; playwright listed under its Dependencies with the reason "the browser check, lab step 6".*
