"""The refusal: one constant, two renderings, no SDK.

The message is the out-of-scope message in spec.md, word for word. The name, the
email and the LinkedIn URL come from data/profile.yaml, so the refusal points at
Nadia while the answers still describe the stand-in profile.

The screen rendering is what the visitor reads. The spoken rendering is what the
speech call says, and it carries no URL, because a URL cannot be heard — the
link is on the page instead.
"""
import pathlib

import yaml

HERE = pathlib.Path(__file__).resolve().parent
PROFILE = HERE.parent / "data" / "profile.yaml"

# The one constant: the out-of-scope message from spec.md, with the three values
# the profile fills in. {linkedin} carries its own preposition, so the spoken
# rendering can replace the whole phrase and still read as a sentence.
REFUSAL = (
    "That's beyond what I have here, but it's exactly the kind of thing {name} "
    "likes answering in her own words. Email is the best way to reach her at "
    "{email} — she'd be happy to write back. You can also connect with her on "
    "LinkedIn {linkedin}."
)


def values() -> dict[str, str]:
    """The three values the message needs, read from the profile.

    The message says "Nadia", so it uses the first name out of profile.name.
    """
    data = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    return {"name": data["profile"]["name"].split()[0],
            "email": data["contact"]["email"],
            "linkedin": data["contact"]["linkedin"]}


def screen() -> str:
    """The refusal as the visitor reads it: the email and the LinkedIn link."""
    v = values()
    return REFUSAL.format(name=v["name"], email=v["email"], linkedin=f"at {v['linkedin']}")


def spoken() -> str:
    """The refusal as it is heard: the LinkedIn URL is gone, the email stays."""
    v = values()
    return REFUSAL.format(name=v["name"], email=v["email"], linkedin="— the link is on screen")
