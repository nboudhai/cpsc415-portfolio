# Spec

<!-- The agent writes this from the approved intent. You validate it against the intent.
     If the spec and the intent disagree, the intent wins until you change the intent. -->

## Intent

This spec implements `intent/portfolio.md` (approved 2026-10-04 by Nadia Boudhaim Maguire).

## Open questions resolved by this spec

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
- `not_yet` is present (may be empty).
- `contact.email` and `contact.linkedin` are present and look like a `mailto:` target and a `linkedin.com` URL respectively.

## "Not yet" inventory template

A section in the data file for things Nadia plans to do or learn but has not yet. Items here are short, forward-looking, and intentionally low-pressure: they are *not* project entries (no `what_breaks` etc. — there is nothing to break yet). They surface in the chatbot so a recruiter can ask "what's next for you?" and get a real answer.

Each item is one YAML mapping with three required fields:

```yaml
not_yet:
  - topic: "Distributed systems on bare metal"     # what it is, in one line
    why: "Most of my coursework is web-shaped; I want to know what the OS layer actually buys me."
    first_step: "Read the first three chapters of 'Designing Data-Intensive Applications' and reproduce one example on a Raspberry Pi."
```

- `topic` (string, required): short label, like a TODO subject.
- `why` (string, required): one or two sentences on why this is on the list.
- `first_step` (string, required): one concrete, small action that would move the item forward. The chatbot may quote `first_step` verbatim when asked.

The chatbot must treat `not_yet` items as *plans*, not *achievements*. If asked "have you built X?" and X is only in `not_yet`, the answer is "not yet — here is what I plan to do" and the `first_step`, not a description as if it were done.

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
