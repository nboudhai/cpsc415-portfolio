# Project conventions

## What this repository is
My CPSC 415 portfolio: a single-page profile site with a chatbot that answers
only from data/profile.yaml and refuses to fabricate. Current design: spec.md.
Done so far: the profile schema and its validator (plan.md step 2).

## Commands
```
# test      pytest -q
# validate  python scripts/validate_profile.py   (add --strict before deploy)
# lint      ruff check .
# build     not yet written (plan.md step 3)
# run       not yet written
```

## Conventions
- Python 3.14 in .venv; Pydantic v2 for all schema work.
- Tests live in tests/ (and voice/tests/ for Week 7), named test_*.py.
- Branches: feat/<short-name>, one feature per branch and pull request.

## Working rules

For an introductory lab, follow its explicitly assigned stages; the full chain below applies to major projects.

- Write or update `intent/` and `spec.md` before code. Get `plan.md` approved before implementing.
- One feature per branch and pull request. Never push to `main` directly.
- Exception: the Week 7 lab commits go to main, as the lab specifies.
- Never commit `.env` or `.claude/settings.local.json`.
- Week 7: the spoken interface lives in voice/. Stages assigned: intent, spec,
  plan, tests. Commit to main.
- Transcription and speech calls are billed. One transcription per clip, one
  speech call per answer, never a model call inside a loop of tests. Fixture
  clips are WAV; expected.json is written by a person before the model hears it.
- The spoken answer is the chatbot's answer: the refuse-to-fabricate rule
  applies to what is said aloud exactly as to what is typed.
- My chatbot is not built yet. For Week 7, use
  ../ai-integration-course/examples/voice-loop/profile.json and that
  example's answer step as a stand-in, and say so in CHECKS.md.
- My OPENROUTER_API_KEY is set in the shell that launched the agent, so every
  command the agent runs can bill. Never start the server, call answer(),
  transcribe(), or speak(), or probe a route by hand. Prove things only through
  pytest with the faked clients. Billed calls are made by me, by hand.
  - Week 8: the chatbot's tools live in tools/. Stages assigned: intent, spec,
  plan, tests. Commit to main.
- The model never runs anything. Every tool request is validated and run (or
  refused) by our code; every problem goes back to the model as a result, not
  an exception. Tools with side effects are never run on the model's request
  alone. The loop has a step cap.
- No model call inside a test that runs without a key; the billed eval is
  separate and skipped when OPENROUTER_API_KEY is unset.
- No test that runs without a key reaches GitHub either: recent_commits is
  faked in tests. The real GitHub call happens only in the billed eval.
- Week 8 still uses the Sam Rivera stand-in profile in voice/answer.py; the
  recent_commits tool reads my real GitHub (nboudhai). Say so in tools/CHECKS.md.

## Common mistakes
- 2026-11-08: Told to show CHECKS.md before saving, the agent saved first and
  summarized afterward. When a prompt says "show me before you save," wait
  for approval before writing the file.
- 2026-11-08: Explaining a mishearing, the agent named a "web scraper" project
  as "another real project in the profile"; Sam Rivera's profile.json has only
  the RAG project and the Receipt reader. Check every claim about the profile
  against the file.
- 2026-11-08: During step 3, a timing probe hit POST /api/chat twice with my key
  inherited from the session: two billed chat calls, after being told never to
  run a billed call. Recorded in voice/CHECKS.md "Cost record".
- 2026-11-08: Step 4 reported 82 passed, but 5 tests failed on a machine with
  no key: they passed only because my key was inherited from the shell. Every
  voice test now gets a fake key from voice/tests/conftest.py. Before claiming
  "no key needed", run the suite with the key removed.
- 2026-11-15: Told "show me the draft before you save," the agent wrote
  intent/tools.md first, then deleted it and admitted it; a second write was
  blocked by Claude Code's auto-mode classifier. The rule above was already in
  this file and in the prompt. Check git status after any "show me first" step.