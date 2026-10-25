"""Pydantic v2 schema for ``data/profile.yaml``.

This module is the single source of truth for the YAML structure used by:

* ``scripts/validate_profile.py`` (CI gate)
* ``scripts/build_site.py`` (page generator — step 3)
* ``functions/api/chat.py`` (chatbot system-prompt grounding — step 5)

The model mirrors the schema documented in ``spec.md`` §"YAML schema" and
enforces the "required-field guarantee" listed just below it. Adding a new
top-level key here is a spec change; update ``spec.md`` first.

The schema is deliberately strict (``extra="forbid"`` on every model) so
typos in field names fail at parse time instead of silently rendering as
empty values on the page.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


# A deliberately loose email shape — the spec only requires "looks like a
# mailto: target", which means "name@domain.tld". We avoid pulling in the
# ``email-validator`` package for a check this small.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class _Strict(BaseModel):
    """Base model with ``extra='forbid'`` so unknown keys fail loudly."""

    model_config = ConfigDict(extra="forbid")


class ProfileInfo(_Strict):
    name: str = Field(min_length=1)
    tagline: str = Field(min_length=1)
    location: str = Field(min_length=1)
    pronouns: str = ""


class About(_Strict):
    short_bio: str = Field(min_length=1)
    long_bio: str = Field(min_length=1)


class DateRange(_Strict):
    """``start`` and ``end`` are required. ``end`` may be the literal
    string ``"present"`` or any non-empty date string (``YYYY-MM`` or
    full ISO)."""

    start: str = Field(min_length=1)
    end: str = Field(min_length=1)

    @field_validator("end")
    @classmethod
    def _end_must_be_present_or_non_empty(cls, v: str) -> str:
        if v != "present" and not v.strip():
            raise ValueError("end must be 'present' or a non-empty date string")
        return v


class Link(_Strict):
    label: str = Field(min_length=1)
    url: HttpUrl


class Project(_Strict):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    role: str = Field(min_length=1)
    dates: DateRange
    links: list[Link] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    # The four required reflection fields — missing or empty values fail CI.
    what_is_this: str = Field(min_length=1)
    why_this_choice: str = Field(min_length=1)
    what_breaks: str = Field(min_length=1)
    what_did_i_learn: str = Field(min_length=1)


class ResearchEntry(_Strict):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    venue: str = Field(min_length=1)
    year: int = Field(ge=1900, le=2100)
    abstract: str = ""
    links: list[Link] = Field(default_factory=list)


class Education(_Strict):
    institution: str = Field(min_length=1)
    degree: str = Field(min_length=1)
    field: str = Field(min_length=1)
    dates: DateRange
    notes: str = ""


class Experience(_Strict):
    org: str = Field(min_length=1)
    role: str = Field(min_length=1)
    dates: DateRange
    bullets: list[str] = Field(min_length=2, max_length=5)


class Resume(_Strict):
    education: list[Education]
    experience: list[Experience]


class Interest(_Strict):
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)


class Skill(_Strict):
    """A skill or tool with an explicit shipped-vs-learning tier.

    The chatbot grounding prompt filters by ``level``:
        - ``"shipped"`` → "what do you know?"
        - ``"learning"`` → "what are you learning?" (these ARE the learning goals)
    """

    name: str = Field(min_length=1)
    level: Literal["shipped", "learning"]
    context: str = Field(min_length=1, max_length=200)


class NotYetItem(_Strict):
    """A skill or tool deliberately *not* prioritized right now.

    Distinct from ``Skill(level="learning")`` (which is *actively being learned*)
    and from ``Project`` (which is *shipped*). See spec §"Not yet inventory
    template" and §"Required-field guarantee".
    """

    topic: str = Field(min_length=1)
    # ≥40 chars: one real sentence, not a token. Validator enforces this.
    why: str = Field(min_length=40)
    # Optional. Only set if there is a concrete trigger that would change
    # the priority; otherwise omit (defaults to "").
    first_step: str = ""


class Contact(_Strict):
    email: str
    linkedin: HttpUrl
    links: list[Link] = Field(default_factory=list)

    @field_validator("email")
    @classmethod
    def _email_looks_like_mailto_target(cls, v: str) -> str:
        if not _EMAIL_RE.match(v):
            raise ValueError(
                "contact.email must look like an email address "
                "(e.g. name@example.com)"
            )
        return v

    @field_validator("linkedin")
    @classmethod
    def _linkedin_must_be_linkedin_com(cls, v: HttpUrl) -> HttpUrl:
        host = (v.host or "").lower()
        if "linkedin.com" not in host:
            raise ValueError("contact.linkedin must be a linkedin.com URL")
        return v


class Profile(_Strict):
    profile: ProfileInfo
    about: About
    projects: list[Project]
    research: list[ResearchEntry]
    resume: Resume
    interests: list[Interest]
    skills: list[Skill]
    # Must have at least one entry. See spec §"Not yet inventory template"
    # and §"Required-field guarantee".
    not_yet: list[NotYetItem] = Field(min_length=1)
    contact: Contact
