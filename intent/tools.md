# Intent: One Live Tool for the Profile Chatbot

## Goal
The portfolio chatbot gains one real tool: `recent_commits(repo)`, the last few
commits of one of Nadia's public GitHub repositories, read from GitHub's REST
API. A visitor can ask what has been worked on lately and get an answer the
hand-maintained profile cannot give, because the profile goes stale between
edits and the repository does not.

The model never runs anything. It writes a request; our code validates it,
runs it or refuses it, and hands the result back to the model as the next
message.

## Who it is for
Recruiters and interviewers who ask what someone has been working on lately,
and want an answer that is true today rather than true on the last edit of the
profile. And Nadia, who needs the tool-loop mechanism — the model asks, the
program decides — in her own repository, because that shape is what coding
agents and next week's MCP work are built on.

## Constraints

1. **One tool, one argument.** `recent_commits(repo)` takes `repo` as
   `owner/name` and returns the last five commits: each one's short sha, date,
   and first line of the commit message. The model gets no say in how many.

2. **The repository list is one constant in code.** The six public `nboudhai`
   repositories — `cpsc415-portfolio` and `cpsc415-week01` through
   `cpsc415-week05` — live in a single constant, and the schema's description
   is built from that constant so the list is never written twice. A repository
   outside the list is an error result naming what is on record, and no request
   goes to GitHub for it.

3. **Only `nboudhai`.** The owner check happens in our code before anything
   leaves the server, so a visitor cannot make the chatbot report a stranger's
   commits. A name that is not `owner/name` is a different error from a
   repository that does not exist, and both are results.

4. **Every failure is a result, not an exception.** A malformed name, a
   repository that is not on record, a repository that no longer exists, the
   rate limit, GitHub unreachable: each comes back as a result the model can
   read. The answer states the failure plainly and claims nothing in its
   place. A failed lookup is not the out-of-scope refusal, because the
   question was in scope and the lookup is what failed.

5. **The model never runs anything.** Every request is validated in code
   against the schema before it runs. A bad argument name, a wrong type, a
   call to a tool that does not exist: each returns an error result and the
   loop carries on.

6. **The loop has a cap of four steps.** A model that keeps asking is stopped
   there, and the answer it gets is the program's sentence, not the model's.

7. **The side-effect tool is registered and never runs.**
   `request_intro(email, message)` validates its arguments and is then always
   held as pending. Nothing is written and nothing is sent, so a visitor's
   email address never reaches the public repository. The pending record stays
   in the trace, and the visitor gets the existing out-of-scope refusal with
   the email and LinkedIn link — the portfolio has no contact form, and this
   keeps that true.

8. **No claim the tool did not support.** Plain code checks that every short
   sha and every repository name in the answer came back from a tool result. A
   repository name counts as returned if it appeared anywhere in a tool result,
   including the list inside a not-on-record error. The check cannot see an
   invented commit subject, and `tools/CHECKS.md` says so.

9. **The answers stay impersonal.** A commit answer names the repository and
   its commits and says nothing about whose work they are. The chatbot's
   profile half still answers from the Sam Rivera stand-in until
   `data/profile.yaml` replaces it, so this keeps the tool from adding a third
   persona to a screen that already carries two. The one place a name appears
   is the refusal, which is code and points at Nadia.

10. **Both paths go through one answer function.** The typed path and the
    voice path call the same `answer()` with the loop in it. The spoken answer
    keeps the Week 7 rules — no URLs, no markdown, two or three sentences — so
    a commit answer names the repository and the change in words, and never
    reads out a URL or a list of shas.

11. **No credential in the repository.** The tool sends an `Authorization`
    header when `GITHUB_TOKEN` is in the environment and sends nothing when it
    is not. No test that runs without a key reaches GitHub: `recent_commits`
    is faked in the tests, and the real GitHub call happens only in the billed
    eval.

12. **A tool call costs one extra chat call.** The cost of a question with a
    tool and without one is recorded per question in `tools/CHECKS.md`, and it
    joins the per-turn cost in the hosting decision before November 30.

13. **Two models in the eval.** The class model `minimax/minimax-m3` and the
    comparison `anthropic/claude-haiku-4.5`; both support tool calling.

14. **Week 8 of the course.** The tool's code lives in `tools/`. The stages
    are intent, spec, plan, tests, committed to `main`, tagged
    `week08-submitted`, due Monday November 16, 2026 at 1:30 PM.

## Not in scope
- The profile's own data behind a tool. The profile stays in the prompt.
- Running `request_intro` for real, sending mail, or a contact form.
- Any write to GitHub — creating issues, comments, or branches — even with a
  token.
- Caching commits, or any rate-limit workaround beyond the optional token.
- Commits beyond the last five: no diffs, no file lists, no per-commit
  detail beyond sha, date, and subject line.
- A second tool that the chatbot needs for one question.
- The real chatbot, which is still plan.md steps 3-6. The tool is wired into
  the stand-in's answer function and moves with it.
- Week 9's MCP server and Team Project 2.

## Success looks like
- A visitor asks what has been worked on lately. The answer names a
  repository from the list and only what the commits carry, and the trace
  shows the call and the result.
- A visitor asks about a repository that is not on record. The answer says
  so plainly, names the repositories that are on record, and claims nothing
  about the one asked for.
- A visitor asks for an introduction. The request is held as pending, nothing
  is written, and the visitor gets the email and the LinkedIn link.
- A model that keeps asking is stopped at four steps, and the visitor gets
  the program's sentence.
- An answer naming a sha or a repository the tool never returned is flagged
  by code, in a test that runs with no key.
- The billed eval records five questions on two models: the tools called, the
  number of steps, the verdict, the cost and the seconds, plus the cost of a
  question with a tool and without one.

## Open questions
- The exact wording of the schema description and of each error message. The
  model reads these and recovers or gives up on them, so the wording is part
  of the design, not decoration.
- Whether the tool path gets its own system prompt or rides on the profile's,
  and what the model is told to do when the profile and the tool could both
  answer.
- What the trace carries and where it is shown: the lab wants it returned with
  the answer, and whether the chat page displays it is undecided.
- Whether a tool answer may be longer than the two or three sentences the
  profile answers get, since five commits with their subjects can need the
  room.

**Approved by:** Nadia Boudhaim Maguire, 2026-11-15
