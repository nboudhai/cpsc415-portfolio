# Four-question annotation

<!-- Required for every project in the portfolio and every team project.
     Written by you, not the agent. This is what the Comprehension Defense asks about. -->

## What is this?
A plain statement of what it does and does not do.

## Why this choice?
What alternatives existed, including language and model, and what trade-offs were weighed.

## What breaks?
Fragile points, assumptions, blast radius.

## What did I learn?
Concretely. Include places where the agent was confidently wrong and you caught it.
What did you learn about reading code or using concepts that were unfamiliar to you?



## Raw notes (2026-11-08) — fold into the four answers before portfolio-final

### What breaks?
- Week 5 guard does a substring match on spec.md: `pip install openrouter` was
  allowed because spec.md mentions "OpenRouter" the service (voice/CHECKS.md).
- guard.py reads spec.md without encoding="utf-8"; on Windows a character like
  "←" could crash it, and a crashed guard fails open (suspected, untested).
- data/profile.yaml line 2 is a comment containing TODO_FILL_IN, so
  `validate_profile.py --strict` fails even after every field is filled in.
- The 30-second recording cap is page-side only; a crafted request skips it.
- Live voice path: a misheard in-scope question gets a true answer about the
  wrong thing; nothing compares the transcript with the profile.
- Behavior 11 (misheard question falls to the refusal) has no no-key test.

### What did I learn? (agent confidently wrong, caught)
- Told to show CHECKS.md before saving; it saved first.
- Invented a "web scraper" project in Sam Rivera's profile (there are two
  projects: RAG and Receipt reader).
- First Week 7 plan: gitignored the spoken answers the submission requires;
  bash commands on Windows; a wrong relative path; a duplicate billed
  transcription; claimed a CI grep that does not exist; treated "boot camp" as
  equal to "bootcamp".
- First Week 7 plan's key check would never be empty: the repo legitimately
  contains "sk-or" in placeholders. Search for the key's shape instead.
- Good habit seen: the agent ran the key searches before writing claims about
  them. Checking, not asserting.
- Windows PowerShell 5.1: `>>` writes UTF-16 (broke requirements.txt);
  Get-Content shows UTF-8 as "â€”" unless given -Encoding UTF8.

### Why this choice? (Week 7 decisions)
- One-shot voice turn with the transcript shown (editing = later intent).
- The model replies OUT_OF_SCOPE; code writes the refusal, so no model reply
  ever carries a URL and the refusal cannot drift.
- Own-voice clips committed: required by the submission; risk accepted.
- Billed tests need the key AND VOICE_EVAL=1, because my key is always set.
