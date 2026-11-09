"""The loop's tests, from spec.md's Week 7 behaviors 1, 5, 6, 15 and 17.

Every billed step is faked: the transcription, the chat call and the speech call
are stubs that record what they were asked, so the assertions are about this
code's behaviour and not about a provider's answer.

No key, no network, nothing billed: the server builds its client when a call is
about to be made, so the fakes never reach one.
"""
import base64
import json
import threading
import urllib.error
import urllib.request
from typing import ClassVar

import answer as answer_module
import pytest
import refusal
import server as server_module
import speak as speak_module

QUESTION = "what broke in your receipt reader project"
REPLY = "The receipt reader choked on a folded receipt, and I shipped it with tests."
PLAIN_MESSAGE = "The recording could not be read. Please try again or type your question."


def reject(*args, **kwargs):
    """A transcription the provider refuses."""
    raise RuntimeError("the provider refused: unsupported audio")


class Loop:
    """The running server, and the calls it made."""

    def __init__(self, url: str, calls: list[tuple]):
        self.url = url
        self.calls = calls

    def post(self, path: str, data: bytes, content_type: str = "audio/webm") -> tuple[int, dict]:
        request = urllib.request.Request(self.url + path, data=data,
                                         headers={"Content-Type": content_type})
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def kinds(self) -> list[str]:
        return [call[0] for call in self.calls]


@pytest.fixture
def loop(monkeypatch, tmp_path):
    """The real server on a free port, with the three billed steps faked."""
    calls: list[tuple] = []

    def fake_transcribe(audio, fmt, model=None, client=None):
        calls.append(("stt", fmt))
        return {"text": QUESTION, "cost": 0.001, "seconds": 0.4}

    def fake_chat(messages, model=None, client=None):
        calls.append(("chat", messages[-1]["content"]))
        return REPLY, 0.002

    def fake_speak(text, out, model=None, voice=None, client=None):
        calls.append(("tts", text))
        out.write_bytes(b"fake audio")
        return {"bytes": 9, "cost": 0.003, "seconds": 0.2}

    monkeypatch.setattr(server_module, "transcribe", fake_transcribe)
    monkeypatch.setattr(answer_module, "chat", fake_chat)
    monkeypatch.setattr(server_module, "speak", fake_speak)
    monkeypatch.setattr(server_module, "LAST_AUDIO", tmp_path / "answer.mp3")
    # the stand-in's profile lives in the course repository; the prompt is not what
    # these tests are about, and the suite must not depend on that folder
    monkeypatch.setattr(answer_module, "system_prompt", lambda: "the stand-in's system prompt")

    httpd = server_module.make_server(0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        # 127.0.0.1 and not localhost: the Windows resolver takes two seconds for
        # "localhost" here, and every request in this suite would wait for it
        yield Loop(f"http://127.0.0.1:{httpd.server_address[1]}", calls)
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_the_voice_route_hears_answers_and_speaks(loop):
    """The whole loop: a recording comes in, an answer and an audio come out."""
    status, body = loop.post("/api/voice", b"fake audio")
    assert status == 200
    assert body["transcript"] == QUESTION
    assert body["answer"] == REPLY
    assert base64.b64decode(body["audio_b64"]) == b"fake audio"
    assert loop.kinds() == ["stt", "chat", "tts"]
    assert body["cost"] == {"stt": 0.001, "chat": 0.002, "tts": 0.003}


def test_the_typed_route_and_the_voice_route_use_the_same_answer_function(loop):
    """Behavior 1: both routes go through the same answer()."""
    status, typed = loop.post("/api/chat", QUESTION.encode(), content_type="text/plain")
    assert status == 200
    status, spoken = loop.post("/api/voice", b"fake audio")
    assert typed["answer"] == spoken["answer"] == REPLY
    # the same question reached the chat call both times, and only the voice route heard
    assert [call[1] for call in loop.calls if call[0] == "chat"] == [QUESTION, QUESTION]
    assert loop.kinds().count("stt") == 1


def test_an_empty_transcript_skips_the_chat_and_the_speech_call(loop, monkeypatch):
    """Behavior 5: no model is asked to answer an empty question."""
    calls = loop.calls

    def empty_transcribe(audio, fmt, model=None, client=None):
        calls.append(("stt", fmt))
        return {"text": "   ", "cost": 0.001, "seconds": 0.3}

    monkeypatch.setattr(server_module, "transcribe", empty_transcribe)
    status, body = loop.post("/api/voice", b"fake audio")
    assert status == 200
    assert body["answer"] == "I didn't catch that."
    assert body["audio_b64"] is None
    assert loop.kinds() == ["stt"]


def test_a_body_over_10_mb_is_refused(loop):
    """Behavior 15: the server's cap, and nothing was billed for it."""
    status, _body = loop.post("/api/voice", b"x" * (10_000_000 + 1))
    assert status == 413
    assert loop.calls == []


def test_an_unknown_audio_type_gets_415(loop):
    """Behavior 15: the format map decides, before anything is billed."""
    status, _body = loop.post("/api/voice", b"fake audio", content_type="application/x-nonsense")
    assert status == 415
    assert loop.calls == []


def test_a_rejected_recording_returns_502_with_the_plain_message(loop, monkeypatch):
    """Behavior 17: the visitor is told the recording could not be read, in our words."""
    monkeypatch.setattr(server_module, "transcribe", reject)
    status, body = loop.post("/api/voice", b"fake audio")
    assert status == 502
    assert body["error"] == PLAIN_MESSAGE


def test_a_rejected_recording_ends_the_turn(loop, monkeypatch, tmp_path):
    """Behavior 17: no chat call, no speech call, and no audio written."""
    monkeypatch.setattr(server_module, "transcribe", reject)
    out = tmp_path / "answer.mp3"
    monkeypatch.setattr(server_module, "LAST_AUDIO", out)
    loop.post("/api/voice", b"fake audio")
    assert loop.calls == []
    assert not out.exists()


def test_the_providers_message_is_in_the_server_log_and_not_in_the_reply(loop, monkeypatch, capsys):
    """Behavior 17: the browser never sees the provider, and the server log does."""
    monkeypatch.setattr(server_module, "transcribe", reject)
    status, body = loop.post("/api/voice", b"fake audio")
    assert status == 502
    logged = capsys.readouterr()
    assert "unsupported audio" in logged.err
    assert "unsupported audio" not in json.dumps(body)


def test_the_key_is_never_logged(loop, monkeypatch, capsys):
    """Behavior 17: the key is not logged either, even if the provider echoes it back."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-FAKEKEY-0123456789")

    def echo_the_key(*args, **kwargs):
        raise RuntimeError("the provider echoed sk-or-v1-FAKEKEY-0123456789 back")

    monkeypatch.setattr(server_module, "transcribe", echo_the_key)
    loop.post("/api/voice", b"fake audio")
    logged = capsys.readouterr()
    assert "sk-or-v1-FAKEKEY-0123456789" not in logged.err
    assert "[redacted]" in logged.err


def test_a_refusal_is_spoken_without_its_link(loop, monkeypatch):
    """Behaviors 2 and 9: the page shows the link, the speech call does not say it."""
    monkeypatch.setattr(answer_module, "chat",
                        lambda messages, model=None, client=None: ("OUT_OF_SCOPE", 0.002))
    status, body = loop.post("/api/voice", b"fake audio")
    assert status == 200
    assert body["answer"] == refusal.screen()
    spoken = next(call[1] for call in loop.calls if call[0] == "tts")
    assert "http" not in spoken
    assert "the link is on screen" in spoken


def test_a_non_audio_speech_reply_raises_and_writes_no_file(tmp_path):
    """Behavior 6: an error body returned as JSON never lands in a .mp3."""

    class FakeResponse:
        headers: ClassVar[dict] = {"content-type": "application/json"}

        def read(self):
            return b'{"error": "no"}'

    class FakeTTS:
        @staticmethod
        def create_speech(**kwargs):
            return FakeResponse()

    class FakeClient:
        tts = FakeTTS()

    out = tmp_path / "answer.mp3"
    with pytest.raises(RuntimeError):
        speak_module.speak("hello", out, client=FakeClient())
    assert not out.exists()


def test_the_server_serves_the_page_when_it_is_there(loop, monkeypatch, tmp_path):
    """GET / serves voice/index.html."""
    page = tmp_path / "index.html"
    page.write_text("<html>the page</html>", encoding="utf-8")
    monkeypatch.setattr(server_module, "PAGE", page)
    with urllib.request.urlopen(loop.url + "/") as response:
        assert response.status == 200
        assert b"the page" in response.read()


def test_the_recording_limit_is_the_servers_own():
    """Behavior 15: the cap is ten megabytes, in the server's own constant."""
    assert server_module.MAX_BODY == 10_000_000


def test_make_server_binds_127_0_0_1():
    """The server binds to 127.0.0.1, not 'localhost'.

    The Windows resolver waits two seconds for the name 'localhost' (CHECKS.md
    "localhost vs 127.0.0.1", step 3), so every request would wait for it.
    The bind is the kernel's view, not the print at startup, and this test
    reads it directly. The socket is closed before the test returns so a
    stray port can never outlive the suite.
    """
    httpd = server_module.make_server(0)
    try:
        host = httpd.server_address[0]
        assert host == "127.0.0.1", f"make_server bound {host!r}, expected '127.0.0.1'"
    finally:
        httpd.server_close()
