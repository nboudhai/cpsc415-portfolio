"""The tool registry: name, description, JSON Schema arguments, and the handler, per tool.

The repository list is one constant in code, and the schema's description is built
from that constant so the list is never written twice. Argument validation is the
plain-code `validate()` pattern from the course's `tools.py`.

The handlers themselves live in `github_tool.py` and `intro_tool.py`; this module
exposes the schemas, validation, and the `run_tool()` decision that the loop
calls for every request.
"""
import json

from github_tool import recent_commits
from intro_tool import request_intro


# ---- the constants ----------------------------------------------------------------------------
RECENT_COMMITS_REPOS = (
    "cpsc415-portfolio",
    "cpsc415-week01",
    "cpsc415-week02",
    "cpsc415-week03",
    "cpsc415-week04",
    "cpsc415-week05",
)


# ---- the schemas: this list goes in the request as `tools` -------------------------------------
RECENT_COMMITS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "recent_commits",
        "description": (
            "The most recent commits in one of Nadia's public GitHub repositories. "
            f"The repositories on record are: {', '.join(RECENT_COMMITS_REPOS)}. "
            "Use this before saying anything about what she has worked on lately."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": (
                        "The repository, one of the repositories on record, "
                        "for example cpsc415-portfolio."
                    ),
                },
            },
            "required": ["repo"],
        },
    },
}

REQUEST_INTRO_SCHEMA = {
    "type": "function",
    "function": {
        "name": "request_intro",
        "description": (
            "Record an introduction request from a visitor. Only when the visitor "
            "explicitly asks to be introduced and gives an email address. The call "
            "is recorded as pending; nothing is written and nothing is sent until a "
            "person confirms."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "email": {"type": "string", "description": "The visitor's email address."},
                "message": {"type": "string", "description": "What the visitor wants."},
            },
            "required": ["email", "message"],
        },
    },
}

TOOLS = [RECENT_COMMITS_SCHEMA, REQUEST_INTRO_SCHEMA]


# ---- the handlers: name -> function -----------------------------------------------------------
HANDLERS = {
    "recent_commits": recent_commits,
    "request_intro": request_intro,
}


# ---- the decision -----------------------------------------------------------------------------
def validate(name: str, arguments) -> str | None:
    """Return an error message, or None if the call is well formed. Plain code, no model."""
    schema = next((t["function"]["parameters"] for t in TOOLS if t["function"]["name"] == name), None)
    if schema is None:
        return f"unknown tool {name!r}; the tools are {sorted(HANDLERS)}"
    if not isinstance(arguments, dict):
        return "arguments must be a JSON object"
    for req in schema.get("required", []):
        if req not in arguments:
            return f"missing required argument {req!r}"
    for key, value in arguments.items():
        spec = schema["properties"].get(key)
        if spec is None:
            return f"unexpected argument {key!r}"
        if spec["type"] == "string" and not isinstance(value, str):
            return f"argument {key!r} must be a string, got {type(value).__name__}"
    return None


def run_tool(name: str, arguments, *, allow_side_effects: bool = False) -> dict:
    """What the loop calls for every tool request. Never raises on a bad request: the error
    goes back to the model as the tool's result, so the model can correct itself or give up.
    """
    if isinstance(arguments, str):
        try:
            args = json.loads(arguments or "{}")
        except json.JSONDecodeError as error:
            return {"error": f"arguments were not valid JSON: {error.msg}"}
    else:
        args = arguments
    problem = validate(name, args)
    if problem:
        return {"error": problem}
    return HANDLERS[name](**args)
