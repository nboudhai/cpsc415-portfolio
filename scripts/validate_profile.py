#!/usr/bin/env python3
"""Validate ``data/profile.yaml`` against ``profile_schema.Profile``.

Two layers of check:

1. **Schema.** Required fields, types, the email/linkedin shape rules, and
   the structural rules (e.g. ``not_yet`` must be non-empty,
   ``NotYetItem.why`` must be ≥40 chars). Failures here are always fatal.

2. **TODO markers.** A scan for ``TODO_FILL_IN`` in the raw text (catches
   markers in YAML comments too). By default these are *warnings*: they
   are printed and the validator still exits 0, so PR CI stays green
   while a placeholder profile is being filled in. Pass ``--strict``
   (or call ``validate(path, strict=True)``) to make them fatal — the
   deploy workflow runs in strict mode.

Exit codes:
    0  profile parses and matches the schema; any TODO markers are warnings only
    1  schema validation failed, *or* ``--strict`` and at least one TODO marker
    2  profile file does not exist

CLI usage:
    python scripts/validate_profile.py                    # default path, non-strict
    python scripts/validate_profile.py --strict           # TODO markers are fatal
    python scripts/validate_profile.py path/to/yaml       # custom path
    python scripts/validate_profile.py --strict path/to/yaml

Importable:
    from scripts.validate_profile import validate, main
    errors = validate(Path("data/profile.yaml"))            # strict=False
    errors = validate(Path("data/profile.yaml"), strict=True)
    rc = main(["--strict"])                                  # returns int exit code
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

# Ensure the repo root is on sys.path so ``from profile_schema import Profile``
# works whether this file is run as a script or imported by tests.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import yaml  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from profile_schema import Profile  # noqa: E402


# Case-sensitive on purpose: the word "placeholder" is used elsewhere in
# the codebase (e.g. the chat widget's pulsing-dots loading pattern), and
# real profile fields may legitimately describe things as "a placeholder
# for later work" without being a TODO marker.
_TODO_FILL_IN_TOKEN = "TODO_FILL_IN"


def _format_schema_error(loc: Iterable[object], msg: str) -> str:
    """Render a Pydantic error as ``<loc>: <msg>`` for humans."""
    loc_str = ".".join(str(part) for part in loc) or "<root>"
    return f"{loc_str}: {msg}"


def _scan_todo_markers(text: str) -> list[str]:
    """Return one warning per line containing ``TODO_FILL_IN``.

    Operates on raw text (not the parsed YAML) so markers inside YAML
    comments are caught too. The token is case-sensitive; see the module
    docstring for why.
    """
    return [
        f"line {i}: TODO_FILL_IN marker remains — replace before deploy"
        for i, line in enumerate(text.splitlines(), start=1)
        if _TODO_FILL_IN_TOKEN in line
    ]


def validate(path: Path, *, strict: bool = False) -> list[str]:
    """Return a list of validation messages.

    The list always contains every TODO-marker warning and every schema
    error. The ``strict`` flag is *not* applied here — it only affects
    whether the CLI treats TODO warnings as fatal. Callers that want to
    treat warnings as fatal can filter the returned list (e.g. any
    message starting with ``"line "``).
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return [f"file not found: {path}"]
    except OSError as e:
        return [f"could not read {path}: {e}"]

    todo_warnings = _scan_todo_markers(text)

    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as e:
        return todo_warnings + [f"YAML parse error in {path}: {e}"]

    if not isinstance(raw, dict):
        return todo_warnings + [
            f"{path}: top-level must be a YAML mapping, "
            f"got {type(raw).__name__}"
        ]

    try:
        Profile.model_validate(raw)
    except ValidationError as e:
        schema_errors = [
            _format_schema_error(err["loc"], err["msg"]) for err in e.errors()
        ]
        return todo_warnings + schema_errors

    return todo_warnings


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate data/profile.yaml. TODO_FILL_IN markers are warnings "
            "by default; pass --strict to make them fatal."
        )
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Path to profile YAML (default: data/profile.yaml).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail (exit 1) on any TODO_FILL_IN marker. Deploy runs in strict mode.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    path = Path(args.path) if args.path else _REPO_ROOT / "data" / "profile.yaml"

    if not path.exists():
        print(f"profile file not found: {path}", file=sys.stderr)
        return 2

    messages = validate(path, strict=args.strict)
    todo_warnings = [m for m in messages if m.startswith("line ")]
    schema_errors = [m for m in messages if not m.startswith("line ")]

    if todo_warnings:
        verb = "FAILED" if args.strict else "WARN"
        print(
            f"{verb}: {len(todo_warnings)} TODO_FILL_IN marker(s) remain "
            f"in {path}:",
            file=sys.stderr,
        )
        for m in todo_warnings:
            print(f"  - {m}", file=sys.stderr)

    if schema_errors:
        print(
            f"profile validation FAILED ({len(schema_errors)} error(s)) "
            f"in {path}:",
            file=sys.stderr,
        )
        for m in schema_errors:
            print(f"  - {m}", file=sys.stderr)
        return 1

    if args.strict and todo_warnings:
        return 1

    if todo_warnings:
        # Non-strict with warnings only — still pass.
        print(f"profile validation OK (with warnings): {path}")
    else:
        print(f"profile validation OK: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
