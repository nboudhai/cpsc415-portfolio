"""The set run's tests, from spec.md's Week 7 behaviors 7, 8, 13, 16 and 17.

The transcription call is faked: the stub records the clip it was handed and
returns the text that clip was supposed to contain. So the assertions are about
this code's behaviour and not about a provider's answer.

No network, nothing billed: every transcription goes through the stub, and the
key the command line asks for is a fake one that conftest.py sets, so these
tests run the same on a machine where no key is set. The one test that wants
no key removes it again.
"""
import json

import pytest
import transcribe as transcribe_module

CLIPS = [
    {"file": "own-01.m4a",
     "text": "What broke in your receipt reader project, and which skills from CPSC 415 have you actually shipped?",
     "must_contain": ["receipt reader", "415"]},
    {"file": "own-02.m4a",
     "text": "My name is Nadia Boudhaim Maguire. What salary would you expect for your first job?",
     "must_contain": ["Nadia", "Boudhaim", "Maguire", "salary"]},
]


class Fake:
    """The transcription call, faked.

    It records the clips it was handed, so a test can prove a clip was
    transcribed once and not twice.
    """

    def __init__(self, texts=None, fail=()):
        self.calls = []
        self.texts = texts or {}
        self.fail = set(fail)

    def __call__(self, audio, fmt, model=None, client=None, language=None):
        name = audio.decode("utf-8")
        self.calls.append(name)
        if name in self.fail:
            raise RuntimeError("the provider refused: unsupported audio")
        return {"text": self.texts.get(name, ""), "model": model, "audio_seconds": 5.6,
                "cost": 0.000019, "seconds": 0.4}


@pytest.fixture
def clips(tmp_path):
    """Two clips on disk and the expected.json that names them.

    A clip's bytes are its own name, so the fake can tell which clip it was
    handed without the test needing a real recording.
    """
    entries = []
    for clip in CLIPS:
        (tmp_path / clip["file"]).write_text(clip["file"], encoding="utf-8")
        entries.append(dict(clip))
    path = tmp_path / "expected.json"
    path.write_text(json.dumps(entries), encoding="utf-8")
    return path


@pytest.fixture
def said():
    """What each clip says when it is transcribed correctly."""
    return {clip["file"]: clip["text"] for clip in CLIPS}


def test_every_clip_in_the_set_is_transcribed_once(clips, monkeypatch, said):
    """Behavior 13: the set is processed, one transcription per clip."""
    fake = Fake(texts=said)
    monkeypatch.setattr(transcribe_module, "transcribe", fake)
    results, code = transcribe_module.run_set(clips)
    assert fake.calls == ["own-01.m4a", "own-02.m4a"]
    assert [record["file"] for record in results] == ["own-01.m4a", "own-02.m4a"]
    assert code == 0


def test_a_rejected_clip_is_a_failed_clip_with_its_cost_recorded_as_none_reported(clips, monkeypatch, said):
    """Behaviors 13 and 17: a clip the provider refuses is a failed clip.

    The provider reports no usage for a call it refused, so its cost is
    "none reported" and not zero.
    """
    fake = Fake(texts=said, fail=["own-01.m4a"])
    monkeypatch.setattr(transcribe_module, "transcribe", fake)
    results, code = transcribe_module.run_set(clips)
    failed = results[0]
    assert failed["file"] == "own-01.m4a"
    assert failed["ok"] is False
    assert failed["cost"] == "none reported"
    assert "unsupported audio" in failed["error"]
    assert code == 1


def test_the_set_carries_on_after_a_failure(clips, monkeypatch, said):
    """Behavior 13: one clip's failure does not stop the rest of the set."""
    fake = Fake(texts=said, fail=["own-01.m4a"])
    monkeypatch.setattr(transcribe_module, "transcribe", fake)
    results, code = transcribe_module.run_set(clips)
    assert fake.calls == ["own-01.m4a", "own-02.m4a"]
    assert results[1]["ok"] is True
    assert code == 1


def test_a_failed_clip_is_never_transcribed_twice(clips, monkeypatch, said):
    """Behavior 13: the run does not retry, so a clip is billed once at most."""
    fake = Fake(texts=said, fail=["own-01.m4a"])
    monkeypatch.setattr(transcribe_module, "transcribe", fake)
    transcribe_module.run_set(clips)
    assert fake.calls.count("own-01.m4a") == 1
    assert len(fake.calls) == 2


def test_the_run_exits_0_when_every_clip_passed_and_1_when_one_failed(clips, monkeypatch, said, tmp_path):
    """Behavior 13: the exit code says whether any clip failed."""
    fake = Fake(texts=said)
    monkeypatch.setattr(transcribe_module, "transcribe", fake)
    out = tmp_path / "transcripts.json"
    assert transcribe_module.main(["--set", str(clips), "--out", str(out)]) == 0
    fake.fail.add("own-02.m4a")
    assert transcribe_module.main(["--set", str(clips), "--out", str(out)]) == 1


def test_the_run_prints_one_line_per_clip_with_the_text_the_seconds_the_cost_and_the_verdict(
        clips, monkeypatch, said, capsys):
    """Behavior 16: every clip is recorded, and the record is on the screen."""
    fake = Fake(texts=said)
    monkeypatch.setattr(transcribe_module, "transcribe", fake)
    transcribe_module.run_set(clips)
    printed = capsys.readouterr().out
    assert "own-01.m4a: ok" in printed
    assert "wer=0.000" in printed
    assert "5.6s audio" in printed
    assert "$0.000019" in printed
    assert "0.4s" in printed
    assert "receipt reader project" in printed


def test_the_run_writes_one_record_per_clip_to_the_out_file(clips, monkeypatch, said, tmp_path):
    """Behavior 16: the transcripts are written out, one record per clip."""
    fake = Fake(texts=said)
    monkeypatch.setattr(transcribe_module, "transcribe", fake)
    out = tmp_path / "transcripts.json"
    transcribe_module.main(["--set", str(clips), "--out", str(out)])
    written = json.loads(out.read_text(encoding="utf-8"))
    assert [record["file"] for record in written] == ["own-01.m4a", "own-02.m4a"]
    assert written[0]["text"] == CLIPS[0]["text"]
    assert written[0]["cost"] == 0.000019
    assert written[0]["check"]["ok"] is True


def test_a_clip_with_its_own_max_wer_uses_its_own_tolerance(clips, monkeypatch, tmp_path):
    """Behavior 7: the default tolerance is 0.15, and max_wer overrides it.

    The clip's own text is four words and the transcript changes one of them,
    so the rate is 0.25: outside the default, inside the clip's own 0.3.
    """
    (tmp_path / "loose.m4a").write_text("loose.m4a", encoding="utf-8")
    (tmp_path / "strict.m4a").write_text("strict.m4a", encoding="utf-8")
    entries = [{"file": "loose.m4a", "text": "one two three four", "max_wer": 0.3},
               {"file": "strict.m4a", "text": "one two three four"}]
    path = tmp_path / "expected.json"
    path.write_text(json.dumps(entries), encoding="utf-8")
    fake = Fake(texts={"loose.m4a": "one two three five", "strict.m4a": "one two three five"})
    monkeypatch.setattr(transcribe_module, "transcribe", fake)
    results, code = transcribe_module.run_set(path)
    assert results[0]["check"]["wer"] == pytest.approx(0.25)
    assert results[0]["ok"] is True          # the clip's own tolerance
    assert results[1]["ok"] is False         # the default tolerance
    assert code == 1


def test_a_missing_word_that_must_survive_is_reported_and_the_clip_fails(clips, monkeypatch, said):
    """Behavior 8: the words that had to survive are reported when they do not."""
    fake = Fake(texts={**said, "own-02.m4a": "My name is Nadia. What salary would you expect for your first job?"})
    monkeypatch.setattr(transcribe_module, "transcribe", fake)
    results, code = transcribe_module.run_set(clips)
    assert results[1]["check"]["missing"] == ["Boudhaim", "Maguire"]
    assert results[1]["ok"] is False
    assert code == 1


def test_the_provider_error_never_carries_the_key_into_the_record(clips, monkeypatch):
    """Behavior 17: the key is never logged, not even if the provider sends it back.

    The record is written to a file that gets committed, so the key must not
    reach it.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-FAKEKEY-0123456789")

    def refuse(*args, **kwargs):
        raise RuntimeError("the provider echoed sk-or-v1-FAKEKEY-0123456789 back")

    monkeypatch.setattr(transcribe_module, "transcribe", refuse)
    results, _code = transcribe_module.run_set(clips)
    assert "sk-or-v1-FAKEKEY-0123456789" not in json.dumps(results)
    assert "[redacted]" in results[0]["error"]


def test_the_run_refuses_without_a_key_and_bills_nothing(clips, monkeypatch, said, tmp_path, capsys):
    """Behavior 12: without a key the run does not start, and nothing is billed."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    fake = Fake(texts=said)
    monkeypatch.setattr(transcribe_module, "transcribe", fake)
    code = transcribe_module.main(["--set", str(clips), "--out", str(tmp_path / "out.json")])
    assert code == 2
    assert fake.calls == []
    assert "nothing was billed" in capsys.readouterr().err
