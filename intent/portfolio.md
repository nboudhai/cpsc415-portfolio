# Intent: AI-Enabled Profile Site

## Goal
A single-page personal site that introduces Nadia to prospective employers and recruiters, with a chatbot that lets visitors ask grounded questions about her background, projects, research, skills, and holistic interests — and that refuses to invent answers it cannot support from a curated data file.

## Who it is for
Employers, recruiters, interviewers, and other professional contacts who want a quick, current view of who Nadia is and what she could contribute. Today they rely on LinkedIn, a one-off resume PDF, or word-of-mouth; nothing lets them ask follow-up questions tailored to a specific role.

## Constraints
- **Audience-facing surface:** plain HTML/CSS/JS, no frontend framework, deployed as a static site on GitHub Pages.
- **Chatbot backend:** a thin serverless proxy (Cloudflare Workers or Pages Functions) so the OpenRouter API key stays in the host secret store and never reaches the browser.
- **Model + endpoint:** OpenAI-compatible chat-completions endpoint via OpenRouter, configured by environment variables, following the same pattern as the week-2 chat client.
- **Source of truth:** a single curated data file (hand-maintained, roughly two pages) that drives every chatbot answer and the static section content. The chatbot answers only from this file.
- **Honesty rule (non-negotiable):** the chatbot must refuse to fabricate. When a question goes outside the data file, it returns an honest "I don't have that information" and redirects the visitor to email or LinkedIn to reach Nadia directly. The course syllabus enforces this and the adversarial test set will check for it.
- **Contact mechanism:** email (mailto link) and LinkedIn URL. No contact form, no booking or scheduling.
- **Sections (single page):** About, Projects, Research, Resume, Interests, Contact.
- **Deadline:** intent file due Monday, October 5, 2026 (course Week 4).

## Not in scope
- Booking, scheduling, or a contact form (intentionally omitted — Nadia is a student and these do not fit the current site).
- Speech-to-text / text-to-speech interface — added later in the course (Week 7 lab).
- Function-calling or external tools — added later (Week 8 lab).
- A custom domain.
- A frontend framework such as Next.js, SvelteKit, or Astro.
- Server-side rendering.
- Image or video generation features.
- The adversarial test set itself (it belongs to the spec and test stages, not this intent).

## Success looks like
- A visitor to the deployed GitHub Pages URL sees all six sections on one page, each present even if short.
- A visitor can type a question to the chatbot and get a response whose substance is grounded in the data file, with no claims that go beyond it.
- A visitor asking an out-of-scope question (about salary, references, or anything the data file does not cover) gets a clear redirect to email or LinkedIn rather than a guess.

## Open questions
- Cloudflare Workers vs Pages Functions — defer to the spec; either is acceptable.
- Data file format (JSON, YAML, or markdown with frontmatter) — pick whatever is easiest to hand-edit; defer to the spec.
- Section ordering on the page — to be confirmed.
- Resume: an embedded section or a downloadable PDF — to be confirmed.
- Exact wording of the "out-of-scope" redirect message — to be confirmed.

**Approved by:** *Nadia Boudhaim Maguire, October 4th 2026*
