# Intent: Voice Interface for the Profile Chatbot

## Goal
A visitor to Nadia's portfolio asks the chatbot a question out loud. The server
transcribes the recording, the chatbot answers from the profile exactly as it
does for typed questions, and the answer is spoken back.

The transcript is model output and can be confidently wrong — in exactly the
places that matter to a recruiter, names and numbers. So the program checks the
transcript wherever a program can check it, and makes the rest visible.

## Who it is for
Visitors to the portfolio site — employers, recruiters, interviewers — who may
prefer to speak a question than type it. And Nadia, testing the loop.

## Constraints

1. **One answer function, two input paths.** The voice path and the typed path
   both call the same `answer()` function; the Week 7 grading checks that
   `/api/voice` answers through the same function as the typed path. The typed
   route is named `/api/chat`, matching `spec.md` — not `/api/ask`. The
   stand-in's `/api/chat` returns the whole answer at once; `spec.md`'s
   streaming `/api/chat` replaces it when the real chatbot is built, and
   `/api/voice` moves next to it then.

2. **The spoken answer is the chatbot's answer.** The refuse-to-fabricate rule
   applies to what is said aloud exactly as to what is typed. Answers stay in
   two or three sentences, with no markdown and no URLs.

3. **The model never writes the refusal.** When the profile does not answer the
   question, the model replies with exactly `OUT_OF_SCOPE`. Code replaces that
   token with the verbatim out-of-scope message from `spec.md` for the screen —
   email and LinkedIn link clickable — and with the URL-free version for
   speech, where the LinkedIn URL becomes "the link is on screen" and the email
   address stays. Because the model's own text never carries a URL, the "no
   URLs" rule applies to every reply.

   If a reply contains `OUT_OF_SCOPE` anywhere, the whole reply is replaced by
   the refusal; nothing is ever spliced and no partial text is spoken. A
   refusal is better than a failed answer because the visitor still gets a way
   to reach Nadia. Testable without a key.

4. **The refusal names its owner.** The message is assembled in code from
   `data/profile.yaml`: the name from `profile.name`, the email and LinkedIn URL
   from the `contact` block. The stand-in's prompt is name-agnostic ("the person
   in the profile data"), so it works with the example's `profile.json` now and
   with `data/profile.yaml` later.

5. **A stand-in for the chatbot that does not exist yet.** The lab uses
   `../ai-integration-course/examples/voice-loop/profile.json` and that
   example's answer step. `CHECKS.md` says so. The swap is scheduled before
   November 30.

   During the stand-in, in-scope answers describe Sam Rivera from the example
   profile while the refusal points to Nadia; this ends when Nadia's profile
   replaces `profile.json`.

6. **Check the transcript where a program can; show the rest.** Where the
   expected text is known — the fixture clips and Nadia's own clips — the code
   compares the transcript in code: word error rate against the expected text
   with a stated tolerance, and the words that must survive. An empty
   transcript is a failed transcript, not a crash. A live visitor has no
   expected text, so the transcript is shown next to the answer, where a
   mishearing is visible.

   Nadia's two own clips are recorded in `voice/clips/expected.json`: `own-01`
   asks about Sam's receipt reader project and must keep "receipt reader" and
   "415"; `own-02` states Nadia's full name and asks about salary, which the
   profile cannot answer.

7. **A misheard question falls to the refusal, not to an invention.**

8. **One recording, one transcription, one answer, one speech call.** Never a
   model call inside a loop of tests.

9. **Expected text is written by a person before the model hears it.**
   `voice/clips/expected.json` is written and committed before the first
   transcription of those clips.

10. **Recording limits.** The page's recorder stops itself at 30 seconds; the
    server refuses a body over 10 MB and refuses an unknown audio type with
    415. The transcription reply's `seconds` field reports the real length of
    the audio after the call. The 30-second cap is a page-side guardrail — the
    server cannot measure duration without decoding the audio — so it bounds
    latency and abuse for an honest visitor, not a crafted request. The cap is
    not about cost.

11. **Cost.** A voice turn costs about half a cent on the class models (course
    measurement, 2026-10-26): transcription under one percent of it, the chat
    answer about a tenth, the speech the rest. A $5 key limit is about a
    thousand voice questions.

12. **The key stays on the server.** The browser sends only audio; the key is read on the server — from the environment when running locally, from the host's secret store once deployed — and reaches neither the page nor the network tab.

13. **English only for the interface, matching `spec.md`'s out-of-scope list.**

14. **The clips are committed to the public repository.** The Week 7 submission
    requires `clips/` with at least two clips of Nadia's own voice. They are
    short questions to the chatbot, nothing personal beyond her name, and she
    accepts that they stay in the public repo's history.

15. **A spec change is owed.** This changes how the typed chatbot's refusal
    works too: `spec.md`'s system prompt tells the model to reply with the
    out-of-scope message verbatim, and it must change to the `OUT_OF_SCOPE`
    token when the real chatbot is built. Flagged here, not done in Week 7.

## Not in scope
- Editing the transcript and re-asking. A later intent, once the typed chatbot
  exists.
- Multi-language support: the page, the chatbot, and the voice interface are
  English-only.
- Building the real chatbot, or the portfolio page that would host the voice
  button — that is plan.md step 3-6.
- Function calling and external tools (Week 8).
- Streaming the answer in the voice path.

## Success looks like
- A visitor opens the voice page, records a question, and hears the chatbot's
  answer from the profile, with the transcript visible next to it.
- A question the profile cannot answer gets the refusal, not an invention: on
  screen with clickable contact links, and aloud with no URL.
- `/api/voice` and `/api/chat` answer through the same `answer()` function.
- The three fixture clips and Nadia's two own clips are transcribed once per
  model, checked in code, and recorded in `CHECKS.md` with the word error rate,
  the words that went missing, the audio seconds, the cost, and the seconds the
  call took.
- The browser check passes: the page never sees the key or the provider.
- One voice turn's total cost is recorded, because that is what a visitor costs
  per question, and it belongs in `spec.md` before November 30.

## Open questions
- Where the refusal template lives: one constant in the code, plus a no-key
  test that asserts it matches `spec.md` word for word. Left for the spec
  stage.
- Where `/api/voice` runs in production: the hosting decision due November 30
  (`weeks/07/hosting.md`).

**Approved by:** Nadia Boudhaim Maguire, 2026-11-08
