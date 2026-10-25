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

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)


# A deliberately loose email shape — the spec only requires "looks like a
# mailto: target", which means "name@domain.tld". We avoid pulling in the
# ``email-validator`` package for a check this small.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# YYYY-MM. ``DateRange.end`` may also be the literal ``"present"``;
# ``DateRange.start`` is always a date string. Months are restricted to
# 01–12 — ``2026-13`` or ``2026-00`` would otherwise parse as "valid"
# 6-character strings and let nonsense dates through the schema.
_DATE_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class _Strict(BaseModel):
    """Base model with ``extra='forbid'`` so unknown keys fail loudly.

    ``str_strip_whitespace=True`` makes ``min_length=1`` honor the spec's
    "non-empty" guarantee — a value of ``" "`` (just spaces) becomes
    ``""`` and fails the length check. Same for ``NotYetItem.why``'s
    ≥40-char floor: 40 spaces would otherwise pass.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProfileInfo(_Strict):
    name: str = Field(min_length=1)
    tagline: str = Field(min_length=1)
    location: str = Field(min_length=1)
    pronouns: str = ""


class About(_Strict):
    short_bio: str = Field(min_length=1)
    long_bio: str = Field(min_length=1)


class DateRange(_Strict):
    """A date range used for projects, education, and experience.

    Both ``start`` and ``end`` are required. Both must match ``YYYY-MM``
    with month 01–12 (e.g. ``"2026-01"``); the special value ``"present"``
    is also allowed for ``end`` to indicate an open-ended range.
    ``start`` must not be after ``end`` (string comparison works because
    YYYY-MM sorts lexicographically).
    """

    start: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    end: str

    @field_validator("end")
    @classmethod
    def _end_format(cls, v: str) -> str:
        if v != "present" and not _DATE_RE.match(v):
            raise ValueError(
                "end must be 'present' or match YYYY-MM with month 01-12 "
                "(e.g. '2026-01')"
            )
        return v

    @model_validator(mode="after")
    def _start_not_after_end(self) -> "DateRange":
        if self.end == "present":
            return self
        if self.start > self.end:
            raise ValueError(
                f"start ({self.start}) must not be after end ({self.end})"
            )
        return self


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
        # Exact match (not substring) — "linkedin.com" in host also accepts
        # "notlinkedin.com" or "linkedin.com.example.org".
        host = (v.host or "").lower()
        if host != "linkedin.com" and not host.endswith(".linkedin.com"):
            raise ValueError(
                "contact.linkedin must be a linkedin.com URL "
                "(e.g. https://www.linkedin.com/in/your-handle)"
            )
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

    @model_validator(mode="after")
    def _unique_project_ids(self) -> "Profile":
        ids = [p.id for p in self.projects]
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            raise ValueError(f"duplicate project id(s): {duplicates}")
        return self

    @model_validator(mode="after")
    def _unique_research_ids(self) -> "Profile":
        ids = [r.id for r in self.research]
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            raise ValueError(f"duplicate research id(s): {duplicates}")
        return self

    @model_validator(mode="after")
    def _no_overlap_between_skills_and_not_yet(self) -> "Profile":
        # Case-insensitive: "Docker" in skills and "docker" in not_yet
        # would give the chatbot contradictory grounding.
        skill_names = {s.name.lower() for s in self.skills}
        not_yet_topics = {n.topic.lower() for n in self.not_yet}
        overlap = sorted(skill_names & not_yet_topics)
        if overlap:
            raise ValueError(
                f"topic(s) appear in both skills and not_yet "
                f"(case-insensitive): {overlap}"
            )
        return self
