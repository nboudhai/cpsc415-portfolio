"""The speaker's tests, from spec.md's Week 7 behaviors 6 and 16.

The speech call is faked: the client is a stub that hands back raw bytes and
the headers the SDK returns, so the assertions are about this code's behaviour
and not about a provider's audio.

No network, nothing billed: the key the command line asks for is a fake one
that conftest.py sets, so these tests run the same on a machine where no key
is set. The one test that wants no key removes it again.
"""
import wave
from types import SimpleNamespace

import pytest
import speak as speak_module

TEXT = "Hello from CPSC 415."


class FakeResponse:
    """The speech reply: raw bytes, and the headers the SDK hands back."""

    def __init__(self, data, content_type="audio/mpeg", generation_id="gen-1"):
        self.data = data
        self.headers = {"content-type": content_type, "x-generation-id": generation_id}

    def read(self):
        return self.data


class FakeTTS:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def create_speech(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class FakeGenerations:
    """The generation record: the bill, once it has appeared."""

    def __init__(self, total_cost=None, missing=False):
        self.total_cost = total_cost
        self.missing = missing
        self.ids = []

    def get_generation(self, id):
        self.ids.append(id)
        if self.missing:
            raise RuntimeError("not there yet")
        return SimpleNamespace(data=SimpleNamespace(total_cost=self.total_cost))


class FakeClient:
    def __init__(self, response, total_cost=0.0024, missing=False):
        self.tts = FakeTTS(response)
        self.generations = FakeGenerations(total_cost, missing)


@pytest.fixture
def client():
    return FakeClient(FakeResponse(b"fake audio"))


def test_the_speaker_writes_the_file_and_records_what_the_lab_keeps(tmp_path, client):
    """Behavior 16: the characters, the bytes, the cost and the seconds are recorded."""
    out = tmp_path / "hello.mp3"
    info = speak_module.speak(TEXT, out, client=client)
    assert out.read_bytes() == b"fake audio"
    assert info["chars"] == len(TEXT)
    assert info["bytes"] == len(b"fake audio")
    assert info["cost"] == 0.0024
    assert info["seconds"] >= 0
    assert info["model"] == speak_module.DEFAULT_MODEL
    assert info["voice"] == speak_module.DEFAULT_VOICE


def test_the_speech_call_asks_for_the_default_model_and_voice(tmp_path, client):
    """The model and the voice travel together: a voice id belongs to one model."""
    speak_module.speak(TEXT, tmp_path / "hello.mp3", client=client)
    assert client.tts.calls[0]["model"] == speak_module.DEFAULT_MODEL
    assert client.tts.calls[0]["voice"] == speak_module.DEFAULT_VOICE
    assert client.tts.calls[0]["input"] == TEXT
    assert client.tts.calls[0]["response_format"] == "mp3"


def test_a_wav_output_asks_for_pcm_and_is_framed_by_the_wave_module(tmp_path):
    """Behavior 6's other half: the WAV carries a header the wave module wrote."""
    client = FakeClient(FakeResponse(b"\x00\x01" * 1000, content_type="audio/pcm;rate=24000;channels=1"))
    out = tmp_path / "hello.wav"
    info = speak_module.speak(TEXT, out, client=client)
    assert client.tts.calls[0]["response_format"] == "pcm"
    with wave.open(str(out), "rb") as wav:
        assert wav.getframerate() == 24000
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getnframes() == 1000
    assert info["bytes"] == 2000


def test_the_cost_is_estimated_and_marked_when_the_generation_record_is_not_there_yet(tmp_path, monkeypatch):
    """The bill is in the generation record, which takes about a minute to appear.

    Until then the cost comes from the catalog price per character, and it is
    marked as an estimate so the record never claims a bill it does not have.
    """
    monkeypatch.setattr(speak_module, "estimate", lambda model, chars: 0.0015)
    client = FakeClient(FakeResponse(b"fake audio"), missing=True)
    info = speak_module.speak(TEXT, tmp_path / "hello.mp3", client=client)
    assert info["cost"] == 0.0015
    assert info["cost_is_estimate"] is True


def test_the_billed_cost_wins_when_the_generation_record_is_there(tmp_path, client):
    """The record is the bill, so the estimate is not used."""
    info = speak_module.speak(TEXT, tmp_path / "hello.mp3", client=client)
    assert info["cost"] == 0.0024
    assert info["cost_is_estimate"] is False
    assert client.generations.ids == ["gen-1"]


def test_the_command_line_prints_the_characters_the_bytes_the_cost_and_the_seconds(
        tmp_path, monkeypatch, capsys):
    """Behavior 16: the run prints what the lab records."""
    calls = []

    def fake_speak(text, out, model=None, voice=None, client=None):
        calls.append((text, out))
        out.write_bytes(b"fake audio")
        return {"file": str(out), "model": model, "voice": voice, "chars": len(text),
                "bytes": 9, "seconds": 0.8, "generation_id": "gen-1",
                "cost": 0.0024, "cost_is_estimate": False}

    monkeypatch.setattr(speak_module, "speak", fake_speak)
    out = tmp_path / "hello.mp3"
    code = speak_module.main([TEXT, "--out", str(out)])
    printed = capsys.readouterr().out
    assert code == 0
    assert calls == [(TEXT, out)]
    assert f"{len(TEXT)} chars" in printed
    assert "9 bytes" in printed
    assert "$0.0024" in printed
    assert "0.8s" in printed


def test_the_command_line_marks_an_estimated_cost(tmp_path, monkeypatch, capsys):
    """An estimated cost is marked as one, on the screen and in the file."""
    def fake_speak(text, out, model=None, voice=None, client=None):
        out.write_bytes(b"fake audio")
        return {"file": str(out), "model": model, "voice": voice, "chars": len(text),
                "bytes": 9, "seconds": 0.8, "generation_id": None,
                "cost": 0.0015, "cost_is_estimate": True}

    monkeypatch.setattr(speak_module, "speak", fake_speak)
    speak_module.main([TEXT, "--out", str(tmp_path / "hello.mp3")])
    assert "estimated" in capsys.readouterr().out


def test_the_command_line_reads_the_text_from_a_file(tmp_path, monkeypatch):
    """The text can come from a file, so the answer is spoken as it was written."""
    calls = []

    def fake_speak(text, out, model=None, voice=None, client=None):
        calls.append((text, out))
        out.write_bytes(b"fake audio")
        return {"file": str(out), "model": model, "voice": voice, "chars": len(text),
                "bytes": 9, "seconds": 0.8, "generation_id": "gen-1",
                "cost": 0.0024, "cost_is_estimate": False}

    monkeypatch.setattr(speak_module, "speak", fake_speak)
    source = tmp_path / "answer.txt"
    source.write_text(TEXT, encoding="utf-8")
    out = tmp_path / "hello.mp3"
    speak_module.main(["--in", str(source), "--out", str(out)])
    assert calls == [(TEXT, out)]


def test_the_command_line_refuses_without_a_key_and_bills_nothing(tmp_path, monkeypatch, capsys):
    """Behavior 12: without a key the run does not start, and nothing is billed."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    calls = []
    monkeypatch.setattr(speak_module, "speak", lambda *args, **kwargs: calls.append(args))
    code = speak_module.main([TEXT, "--out", str(tmp_path / "hello.mp3")])
    assert code == 2
    assert calls == []
    assert "nothing was billed" in capsys.readouterr().err


def test_the_command_line_never_prints_the_key(tmp_path, monkeypatch, capsys):
    """Behavior 17: the key is never printed, not even if the provider sends it back."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-FAKEKEY-0123456789")

    def fake_speak(*args, **kwargs):
        raise RuntimeError("the provider echoed sk-or-v1-FAKEKEY-0123456789 back")

    monkeypatch.setattr(speak_module, "speak", fake_speak)
    code = speak_module.main([TEXT, "--out", str(tmp_path / "hello.mp3")])
    printed = capsys.readouterr()
    assert code == 2
    assert "sk-or-v1-FAKEKEY-0123456789" not in printed.err
    assert "[redacted]" in printed.err
