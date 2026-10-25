"""Tests for ``scripts/validate_profile.py``.

Coverage:

  * The four pre-existing cases from ``plan.md`` §step 2 (passing fixture,
    missing field, wrong type, empty-not-yet — now inverted).
  * Skills: shipped and learning tiers both pass; invalid level and empty
    context fail.
  * ``not_yet`` tightening: non-empty required; ``why`` must be ≥40 chars.
  * ``TODO_FILL_IN`` markers: warnings by default (exit 0), fatal under
    ``--strict`` (exit 1); YAML comments are scanned; the lowercase word
    "placeholder" in a real field is *not* treated as a marker.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure repo root is on sys.path so the imports below resolve whether
# pytest is invoked from the repo root or from elsewhere.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.validate_profile import main, validate  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


# A complete, valid profile with skills (shipped + learning) and a real
# non-empty ``not_yet`` whose ``why`` is ≥40 chars. Used as the "passes
# everything" baseline; tests below add TODO_FILL_IN markers by
# string-replacing into this.
PASSING = """\
profile:
  name: "Nadia Boudhaim Maguire"
  tagline: "Computer Science student at Trinity College"
  location: "Hartford, CT"
  pronouns: "she/her"

about:
  short_bio: "CS student who likes to make things."
  long_bio: "Longer bio for chatbot grounding."

projects:
  - id: "hello-world"
    title: "Hello World"
    role: "Solo developer"
    dates:
      start: "2025-09"
      end: "present"
    what_is_this: "A small project."
    why_this_choice: "Because."
    what_breaks: "Nothing really."
    what_did_i_learn: "How to ship."

research:
  - id: "course-project"
    title: "A Course Project"
    venue: "CPSC 415"
    year: 2026

resume:
  education:
    - institution: "Trinity College"
      degree: "B.A."
      field: "Computer Science"
      dates:
        start: "2023-09"
        end: "present"
  experience:
    - org: "Trinity College"
      role: "Student"
      dates:
        start: "2023-09"
        end: "present"
      bullets:
        - "Took classes."
        - "Did homework."

interests:
  - name: "Reading"
    description: "Fiction and non-fiction."

skills:
  - name: "Python"
    level: "shipped"
    context: "Used in three shipped projects."
  - name: "Rust"
    level: "learning"
    context: "Reading the book and porting a small CLI."

not_yet:
  - topic: "Kubernetes in production"
    why: "I have not needed it for any of my shipped projects, and the learning curve looks steep for what I'd gain right now."

contact:
  email: "nadia@example.com"
  linkedin: "https://www.linkedin.com/in/nadia"
"""

# Minimal valid baseline — all required fields, no projects/research, an
# empty skills list, and a one-entry not_yet. Used by tests that only
# care about a *specific* failure and want everything else quiet.
MINIMAL_VALID = """\
profile:
  name: "Nadia Boudhaim Maguire"
  tagline: "CS student"
  location: "Hartford, CT"

about:
  short_bio: "Short."
  long_bio: "Long."

projects: []

research: []

resume:
  education: []
  experience: []

interests: []

skills: []

not_yet:
  - topic: "Kubernetes"
    why: "I have not needed it for any of my shipped projects, and the learning curve looks steep."

contact:
  email: "nadia@example.com"
  linkedin: "https://www.linkedin.com/in/nadia"
"""

# A profile whose project is missing the required ``what_did_i_learn``
# reflection field. Should fail with an error mentioning that field.
MISSING_FIELD = """\
profile:
  name: "Nadia Boudhaim Maguire"
  tagline: "CS student"
  location: "Hartford, CT"

about:
  short_bio: "Short."
  long_bio: "Long."

projects:
  - id: "broken"
    title: "Broken Project"
    role: "Solo developer"
    dates:
      start: "2025-09"
      end: "present"
    what_is_this: "Exists."
    why_this_choice: "Reason."
    what_breaks: "Nothing."
    # what_did_i_learn deliberately omitted — should fail.

research: []

resume:
  education: []
  experience: []

interests: []

skills: []

not_yet:
  - topic: "Kubernetes"
    why: "I have not needed it for any of my shipped projects, and the learning curve looks steep."

contact:
  email: "nadia@example.com"
  linkedin: "https://www.linkedin.com/in/nadia"
"""

# A profile whose research entry has ``year: "not-a-number"``. Should fail
# with an error mentioning ``year``.
WRONG_TYPE = """\
profile:
  name: "Nadia Boudhaim Maguire"
  tagline: "CS student"
  location: "Hartford, CT"

about:
  short_bio: "Short."
  long_bio: "Long."

projects: []

research:
  - id: "bad-year"
    title: "Bad Year"
    venue: "Somewhere"
    year: "not-a-number"

resume:
  education: []
  experience: []

interests: []

skills: []

not_yet:
  - topic: "Kubernetes"
    why: "I have not needed it for any of my shipped projects, and the learning curve looks steep."

contact:
  email: "nadia@example.com"
  linkedin: "https://www.linkedin.com/in/nadia"
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(tmp_path: Path, body: str, name: str = "profile.yaml") -> Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# The original four cases (one inverted to reflect the new rule)
# ---------------------------------------------------------------------------


def test_passing_fixture(tmp_path: Path) -> None:
    errors = validate(_write(tmp_path, PASSING))
    assert errors == [], f"expected no errors, got {errors}"


def test_missing_field(tmp_path: Path) -> None:
    errors = validate(_write(tmp_path, MISSING_FIELD))
    assert errors, "expected validation errors for missing what_did_i_learn"
    assert any("what_did_i_learn" in e for e in errors), (
        f"errors should mention what_did_i_learn, got: {errors}"
    )


def test_wrong_type(tmp_path: Path) -> None:
    errors = validate(_write(tmp_path, WRONG_TYPE))
    assert errors, "expected validation errors for year: 'not-a-number'"
    assert any("year" in e for e in errors), (
        f"errors should mention year, got: {errors}"
    )


def test_empty_not_yet_fails(tmp_path: Path) -> None:
    """Empty ``not_yet`` is now an error (was a pass in the previous spec)."""
    body = MINIMAL_VALID.replace(
        "not_yet:\n  - topic:",
        "not_yet: []\n# was:\n# not_yet:\n#   - topic:",
    )
    errors = validate(_write(tmp_path, body))
    assert errors, "empty not_yet must fail per updated spec"
    assert any("not_yet" in e for e in errors), (
        f"errors should mention not_yet, got: {errors}"
    )


def test_bad_email_is_rejected(tmp_path: Path) -> None:
    body = MINIMAL_VALID.replace(
        'email: "nadia@example.com"',
        'email: "not-an-email"',
    )
    errors = validate(_write(tmp_path, body))
    assert errors, "expected validation errors for malformed email"
    assert any("email" in e for e in errors), (
        f"errors should mention email, got: {errors}"
    )


def test_non_linkedin_url_is_rejected(tmp_path: Path) -> None:
    body = MINIMAL_VALID.replace(
        'linkedin: "https://www.linkedin.com/in/nadia"',
        'linkedin: "https://example.com/in/nadia"',
    )
    errors = validate(_write(tmp_path, body))
    assert errors, "expected validation errors for non-linkedin URL"
    assert any("linkedin" in e for e in errors), (
        f"errors should mention linkedin, got: {errors}"
    )


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------


def test_skills_shipped_passes(tmp_path: Path) -> None:
    errors = validate(_write(tmp_path, MINIMAL_VALID))
    assert errors == [], f"shipped skill should pass, got {errors}"


def test_skills_learning_passes(tmp_path: Path) -> None:
    body = MINIMAL_VALID.replace(
        "skills: []",
        'skills:\n  - name: "Go"\n    level: "learning"\n    context: "Working through the tour."',
    )
    errors = validate(_write(tmp_path, body))
    assert errors == [], f"learning skill should pass, got {errors}"


def test_skill_invalid_level_fails(tmp_path: Path) -> None:
    body = MINIMAL_VALID.replace(
        "skills: []",
        'skills:\n  - name: "Go"\n    level: "expert"\n    context: "I am very good."',
    )
    errors = validate(_write(tmp_path, body))
    assert errors, "level: expert should fail"
    assert any("level" in e for e in errors), (
        f"errors should mention level, got: {errors}"
    )


def test_skill_empty_context_fails(tmp_path: Path) -> None:
    body = MINIMAL_VALID.replace(
        "skills: []",
        'skills:\n  - name: "Go"\n    level: "shipped"\n    context: ""',
    )
    errors = validate(_write(tmp_path, body))
    assert errors, "empty context should fail"
    assert any("context" in e for e in errors), (
        f"errors should mention context, got: {errors}"
    )


# ---------------------------------------------------------------------------
# not_yet tightening (why ≥40 chars)
# ---------------------------------------------------------------------------


def test_not_yet_why_too_short_fails(tmp_path: Path) -> None:
    body = MINIMAL_VALID.replace(
        "I have not needed it for any of my shipped projects, and the learning curve looks steep.",
        "yes",
    )
    errors = validate(_write(tmp_path, body))
    assert errors, "a one-word why should fail"
    assert any("why" in e for e in errors), (
        f"errors should mention why, got: {errors}"
    )


def test_not_yet_why_one_sentence_passes(tmp_path: Path) -> None:
    """A ~60-char single-sentence why is the floor — must pass."""
    errors = validate(_write(tmp_path, MINIMAL_VALID))
    assert errors == [], f"baseline MINIMAL_VALID must pass, got {errors}"


# ---------------------------------------------------------------------------
# TODO_FILL_IN markers — warn vs strict
# ---------------------------------------------------------------------------


def _with_todo_marker() -> str:
    """Return PASSING with one TODO_FILL_IN marker inserted in a real field."""
    return PASSING.replace(
        'name: "Nadia Boudhaim Maguire"',
        'name: "TODO_FILL_IN your full name"',
        1,
    )


def test_non_strict_warns_and_passes(tmp_path: Path) -> None:
    """Default mode: TODO_FILL_IN is a warning, exit code 0."""
    p = _write(tmp_path, _with_todo_marker())
    rc = main([str(p)])
    assert rc == 0, f"non-strict should pass (with warning), got rc={rc}"


def test_strict_fails_on_todo(tmp_path: Path) -> None:
    """--strict: TODO_FILL_IN is fatal, exit code 1."""
    p = _write(tmp_path, _with_todo_marker())
    rc = main([str(p), "--strict"])
    assert rc == 1, f"strict should fail on TODO_FILL_IN, got rc={rc}"


def test_todo_in_comment_fails_under_strict(tmp_path: Path) -> None:
    """Markers inside YAML comments are caught by the raw-text scan."""
    body = PASSING + "\n# TODO_FILL_IN this comment must be caught under strict\n"
    p = _write(tmp_path, body)
    rc = main([str(p), "--strict"])
    assert rc == 1, (
        f"strict should fail on TODO_FILL_IN in a YAML comment, got rc={rc}"
    )


def test_word_placeholder_passes(tmp_path: Path) -> None:
    """The lowercase word 'placeholder' in a real field is NOT a marker."""
    body = MINIMAL_VALID.replace(
        'short_bio: "Short."',
        'short_bio: "This bio contains the word placeholder in a normal sentence."',
    )
    p = _write(tmp_path, body)
    rc_default = main([str(p)])
    rc_strict = main([str(p), "--strict"])
    assert rc_default == 0, (
        f"non-strict should pass when 'placeholder' is in real text, got {rc_default}"
    )
    assert rc_strict == 0, (
        f"strict should also pass when 'placeholder' is in real text, got {rc_strict}"
    )
