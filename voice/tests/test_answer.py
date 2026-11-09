"""The answer command line's tests: the two files it writes, and what it writes
them before the call.

The chat call is faked: the stub answers with a text and records what it was
asked. So the assertions are about this code's behaviour and not about a
model's answer.

No network, nothing billed: the key the command line asks for is a fake one
that conftest.py sets, so these tests run the same on a machine where no key
is set. The one test that wants no key removes it again.
"""
from types import SimpleNamespace

import answer as answer_module
import refusal

QUESTION = ("What broke in your receipt reader project, and which skills "
            "from CPSC 415 have you actually shipped?")


class FakeClient:
    """The chat call, faked.

    It records what it was asked, and it can look at the disk while it is
    answering: the answer must not be paid for and then lost.
    """

    def __init__(self, reply="OUT_OF_SCOPE", cost=0.00080076, on_call=None):
        self.reply = reply
        self.cost = cost
        self.on_call = on_call
        self.calls = []
        self.chat = SimpleNamespace(send=self._send)

    def _send(self, **kwargs):
        self.calls.append(kwargs)
        if self.on_call:
            self.on_call()
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.reply))],
            usage=SimpleNamespace(cost=self.cost))


def fake_client(monkeypatch, **kwargs):
    """Put the fake client where the command line will build the real one."""
    client = FakeClient(**kwargs)
    monkeypatch.setattr(answer_module, "_client", lambda: client)
    return client


def test_the_out_file_holds_the_spoken_text_and_the_screen_file_the_screen_text(monkeypatch, tmp_path):
    """Behaviors 2 and 9: the spoken text carries no URL, the screen text does.

    The file the speaker reads is the spoken rendering, so the URL is gone
    from it; the screen rendering, with the email and the LinkedIn link, is
    written next to it as answer-screen.txt.
    """
    fake_client(monkeypatch)
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

    client = fake_client(monkeypatch, on_call=look)
    assert answer_module.main(["--ask", QUESTION, "--out", str(out)]) == 0
    assert seen["folder"] is True
    assert client.calls
    assert out.read_text(encoding="utf-8")


def test_the_run_does_not_call_the_model_when_the_answer_cannot_be_written(monkeypatch, tmp_path):
    """The call is billed: an answer that cannot be written is found first.

    The parent here is a file, not a folder, so the folder cannot be made and
    the answer could not be written. The model must not be asked.
    """
    client = fake_client(monkeypatch)
    blocked = tmp_path / "blocked"
    blocked.write_text("not a folder", encoding="utf-8")
    assert answer_module.main(["--ask", QUESTION, "--out", str(blocked / "answer.txt")]) == 2
    assert client.calls == []


def test_the_model_is_asked_once_and_it_is_the_one_answer_uses(monkeypatch, tmp_path):
    """One call, with answer()'s model, and the question in the messages."""
    client = fake_client(monkeypatch)
    out = tmp_path / "answer.txt"
    assert answer_module.main(["--ask", QUESTION, "--out", str(out)]) == 0
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["model"] == answer_module.DEFAULT_MODEL
    assert call["messages"][-1] == {"role": "user", "content": QUESTION}


def test_a_plain_answer_is_written_both_ways_and_the_cost_is_printed(monkeypatch, tmp_path, capsys):
    """A reply that is not a refusal: the spoken text loses its markdown and
    its URLs, the screen text keeps them."""
    reply = ("Sam shipped **two** projects: RAG over course notes and a receipt "
             "reader. The RAG one is at https://example.com/rag")
    fake_client(monkeypatch, reply=reply)
    out = tmp_path / "answer.txt"
    assert answer_module.main(["--ask", QUESTION, "--out", str(out)]) == 0
    spoken = out.read_text(encoding="utf-8")
    screen = (out.parent / "answer-screen.txt").read_text(encoding="utf-8")
    assert "**" not in spoken
    assert "https://" not in spoken
    assert "the link is on screen" in spoken
    assert screen == reply
    assert "$0.00080076" in capsys.readouterr().out


def test_the_run_does_not_start_without_a_key_and_bills_nothing(monkeypatch, tmp_path, capsys):
    """No key: the run does not start, and nothing is billed.

    The real _client is left in place, so the key check is the code's own.
    A client that was ever built would fail the test.
    """
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    built = []

    def never(*args, **kwargs):
        built.append(args)
        raise AssertionError("no client may be built without a key")

    monkeypatch.setattr(answer_module, "OpenRouter", never)
    out = tmp_path / "speaks" / "answer.txt"
    assert answer_module.main(["--ask", QUESTION, "--out", str(out)]) == 2
    assert built == []
    assert "nothing was billed" in capsys.readouterr().err
    assert not out.exists()
