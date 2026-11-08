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

## Common mistakes
None recorded yet. Add one each time the agent gets something wrong.