"""The refusal's tests, from spec.md's Week 7 behaviors 2, 3 and 4.

The refusal is one constant in the code and one message in spec.md. The first test
reads both and compares them, so the two copies cannot drift apart.

No key, no network, nothing billed: the refusal imports no SDK.
"""
import pathlib

import refusal
import yaml
from answer import apply_refusal

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = ROOT / "spec.md"
PROFILE = ROOT / "data" / "profile.yaml"


def profile() -> dict:
    """data/profile.yaml, the file the refusal reads."""
    return yaml.safe_load(PROFILE.read_text(encoding="utf-8"))


def spec_message() -> str:
    """The out-of-scope message as spec.md writes it, with the profile's values in."""
    text = SPEC.read_text(encoding="utf-8")
    block = text.split("=== OUT-OF-SCOPE MESSAGE (use verbatim) ===", 1)[1]
    block = block.split("\n===", 1)[0]
    message = block.strip().strip('"')          # the spec quotes the message
    contact = profile()["contact"]
    message = message.replace("<profile.contact.email>", contact["email"])
    message = message.replace("<profile.contact.linkedin>", contact["linkedin"])
    return " ".join(message.split())            # the spec wraps the message over lines


def test_the_refusal_constant_matches_spec_word_for_word():
    """Behavior 3: one constant in the code, one message in the spec, and they agree."""
    assert refusal.screen() == spec_message()


def test_the_refusal_names_the_profile_owner(tmp_path, monkeypatch):
    """Behavior 4: the name comes from profile.name, not from the code.

    The refusal points at Nadia while the stand-in profile is Sam Rivera's, so the
    name is read from the profile rather than written into the message: point the
    refusal at another profile and it names that person.
    """
    data = profile()
    data["profile"]["name"] = "Sam Rivera"
    other = tmp_path / "profile.yaml"
    other.write_text(yaml.safe_dump(data), encoding="utf-8")
    monkeypatch.setattr(refusal, "PROFILE", other)
    assert "Sam likes answering" in refusal.screen()
    assert "Nadia" not in refusal.screen()


def test_a_reply_containing_out_of_scope_is_replaced_whole():
    """Behavior 2: the refusal never arrives spliced into a sentence."""
    assert apply_refusal("OUT_OF_SCOPE") == refusal.screen()
    reply = "I think OUT_OF_SCOPE covers this, but here is a guess anyway."
    assert apply_refusal(reply) == refusal.screen()


def test_a_reply_without_out_of_scope_is_left_alone():
    """An answer that is in scope is the model's own text, untouched."""
    reply = "The receipt reader choked on a folded receipt."
    assert apply_refusal(reply) == reply


def test_the_screen_refusal_carries_the_email_and_the_linkedin_link():
    """Behavior 2: the visitor can act on it."""
    contact = profile()["contact"]
    screen = refusal.screen()
    assert contact["email"] in screen
    assert contact["linkedin"] in screen


def test_the_spoken_refusal_carries_no_url():
    """Behavior 9: nothing that cannot be heard is said."""
    contact = profile()["contact"]
    spoken = refusal.spoken()
    assert "http" not in spoken
    assert contact["linkedin"] not in spoken
    assert "the link is on screen" in spoken
    # the email stays: an address can be heard, and reaching her is the point
    assert contact["email"] in spoken


def test_the_two_renderings_are_the_same_message():
    """Both renderings say the spec's message; they differ only in the LinkedIn phrase."""
    shared = spec_message().split(" also connect with her on LinkedIn")[0]
    assert refusal.screen().startswith(shared)
    assert refusal.spoken().startswith(shared)
