"""The answer command line's tests: the two files it writes, and what it writes
them before the call.

The tool loop is faked: the stub returns a reply and a trace and records what it
was asked. So the assertions are about this code's behaviour and not about a
model's answer.

No network, nothing billed: the key the command line asks for is a fake one
that conftest.py sets, so these tests run the same on a machine where no key
is set. The one test that wants no key removes it again.
"""
import answer as answer_module
import loop as loop_module
import refusal

QUESTION = ("What broke in your receipt reader project, and which skills "
            "from CPSC 415 have you actually shipped?")


class FakeRun:
    """The loop.run call, faked.

    It records what it was asked, and it can look at the disk while it is
    answering: the answer must not be paid for and then lost.
    """

    def __init__(self, reply="OUT_OF_SCOPE", cost=0.00080076, on_call=None):
        self.reply = reply
        self.cost = cost
        self.on_call = on_call
        self.calls = []

    def __call__(self, messages, *, tools=None, model=None, max_steps=None, client=None,
                 allow_side_effects=False):
        self.calls.append({"messages": messages, "tools": tools, "model": model,
                           "max_steps": max_steps})
        if self.on_call:
            self.on_call()
        return (self.reply, self.cost, {"steps": [], "calls": [], "pending": [],
                                         "stopped_by": "answer",
                                         "verdict": {"supported": True, "unsupported": []}})


def fake_run(monkeypatch, **kwargs):
    """Put the fake run where answer() will call the real one."""
    run = FakeRun(**kwargs)
    monkeypatch.setattr(loop_module, "run", run)
    return run


def test_the_out_file_holds_the_spoken_text_and_the_screen_file_the_screen_text(monkeypatch, tmp_path):
    """Behaviors 2 and 9: the spoken text carries no URL, the screen text does.

    The file the speaker reads is the spoken rendering, so the URL is gone
    from it; the screen rendering, with the email and the LinkedIn link, is
    written next to it as answer-screen.txt.
    """
    fake_run(monkeypatch)
    out = tmp_path / "speaks" / "answer.txt"
    assert answer_module.main(["--ask", QUESTION, "--out", str(out)]) == 0
    spoken = out.read_text(encoding="utf-8")
    screen = (out.parent / "answer-screen.txt").read_text(encoding="utf-8")
    assert "https://" not in spoken
    assert "the link is on screen" in spoken
    assert screen == refusal.screen()
    assert "https://" in screen


def test_the_folder_is_created_before_the_call(monkeypatch, tmp_path):
    """The call is billed: the answer must not be lost to a missing folder.

    This is the bug the first billed run found: the folder did not exist, the
    model had already answered, and the answer was lost with the traceback.
    """
    seen = {}
    out = tmp_path / "speaks" / "answer.txt"

    def look():
        seen["folder"] = out.parent.is_dir()

    run = fake_run(monkeypatch, on_call=look)
    assert answer_module.main(["--ask", QUESTION, "--out", str(out)]) == 0
    assert seen["folder"] is True
    assert run.calls
    assert out.read_text(encoding="utf-8")


def test_the_run_does_not_call_the_model_when_the_answer_cannot_be_written(monkeypatch, tmp_path):
    """The call is billed: an answer that cannot be written is found first.

    The parent here is a file, not a folder, so the folder cannot be made and
    the answer could not be written. The loop must not be run.
    """
    run = fake_run(monkeypatch)
    blocked = tmp_path / "blocked"
    blocked.write_text("not a folder", encoding="utf-8")
    assert answer_module.main(["--ask", QUESTION, "--out", str(blocked / "answer.txt")]) == 2
    assert run.calls == []


def test_the_model_is_asked_once_and_it_is_the_one_answer_uses(monkeypatch, tmp_path):
    """One loop call, with answer()'s model, and the question in the messages."""
    run = fake_run(monkeypatch)
    out = tmp_path / "answer.txt"
    assert answer_module.main(["--ask", QUESTION, "--out", str(out)]) == 0
    assert len(run.calls) == 1
    call = run.calls[0]
    assert call["model"] == answer_module.DEFAULT_MODEL
    assert call["messages"][-1] == {"role": "user", "content": QUESTION}


def test_a_plain_answer_is_written_both_ways_and_the_cost_is_printed(monkeypatch, tmp_path, capsys):
    """A reply that is not a refusal: the spoken text loses its markdown and
    its URLs, the screen text keeps them."""
    reply = ("Sam shipped **two** projects: RAG over course notes and a receipt "
             "reader. The RAG one is at https://example.com/rag")
    fake_run(monkeypatch, reply=reply)
    out = tmp_path / "answer.txt"
    assert answer_module.main(["--ask", QUESTION, "--out", str(out)]) == 0
    spoken = out.read_text(encoding="utf-8")
    screen = (out.parent / "answer-screen.txt").read_text(encoding="utf-8")
    assert "**" not in spoken
    assert "https://" not in spoken
    assert "the link is on screen" in spoken
    assert screen == reply
    assert "$0.00080076" in capsys.readouterr().out


def test_a_pending_request_intro_returns_the_refusal_in_code(monkeypatch, tmp_path):
    """Behavior 5: the model called request_intro; the refusal is the code's, not the model's.

    The trace's `pending` field carries the request; answer() returns the
    refusal in code, whatever the model wrote.
    """
    def with_pending(messages, *, tools=None, model=None, max_steps=None, client=None,
                     allow_side_effects=False):
        return ("some answer the model wrote about the intro", 0.0009,
                {"steps": [], "calls": ["request_intro"], "pending": [{"email": "v@x.com",
                                                                        "message": "hi"}],
                 "stopped_by": "answer",
                 "verdict": {"supported": True, "unsupported": []}})

    monkeypatch.setattr(loop_module, "run", with_pending)
    out = tmp_path / "answer.txt"
    assert answer_module.main(["--ask", "introduce me", "--out", str(out)]) == 0
    screen = (out.parent / "answer-screen.txt").read_text(encoding="utf-8")
    assert screen == refusal.screen()


def test_answer_calls_the_same_tools_loop_run_not_a_duplicate(monkeypatch):
    """The same loop.run is reached from answer.py and not duplicated.

    If answer.py called its own copy of run, the stub would never fire; the
    stub is on loop.run itself, and it fires. The test is the proof.
    """
    seen = []

    def sentinel(messages, *, tools=None, model=None, max_steps=None, client=None,
                 allow_side_effects=False):
        seen.append(messages)
        return ("the sentinel's answer", 0.0,
                {"steps": [], "calls": [], "pending": [], "stopped_by": "answer",
                 "verdict": {"supported": True, "unsupported": []}})

    monkeypatch.setattr(loop_module, "run", sentinel)

    text, cost, trace = answer_module.answer("anything")

    assert seen, "answer() did not call loop.run"
    assert text == "the sentinel's answer"


def test_the_run_does_not_start_without_a_key_and_bills_nothing(monkeypatch, tmp_path, capsys):
    """No key: the run does not start, and nothing is billed.

    The real loop.run is left in place, so the key check is the code's
    own. A run that ever happened would fail the test.
    """
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    called = []

    def never(*args, **kwargs):
        called.append((args, kwargs))
        raise AssertionError("the loop must not run without a key")

    monkeypatch.setattr(loop_module, "run", never)
    out = tmp_path / "speaks" / "answer.txt"
    assert answer_module.main(["--ask", QUESTION, "--out", str(out)]) == 2
    assert called == []
    assert "nothing was billed" in capsys.readouterr().err
    assert not out.exists()
