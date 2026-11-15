"""The registry's tests, from spec.md §"Week 8 behaviors" #1.

The repository list is one constant; the schema's description is built from
that constant so the list is never written twice; the schema is the JSON
Schema the model sees. No key, no network, nothing billed.
"""
import re

import registry


# ---- the constant ----------------------------------------------------------------------------
def test_repository_list_is_one_constant():
    """Behavior #1: the six repositories the model can ask about are one constant."""
    assert tuple(registry.RECENT_COMMITS_REPOS) == (
        "cpsc415-portfolio",
        "cpsc415-week01",
        "cpsc415-week02",
        "cpsc415-week03",
        "cpsc415-week04",
        "cpsc415-week05",
    )


# ---- the schema's description is built from the constant --------------------------------------
def test_description_lists_every_repository_in_the_constant():
    """Behavior #1: the description is built from the constant; the list is never written twice."""
    description = _recent_commits_description()
    for repo in registry.RECENT_COMMITS_REPOS:
        assert repo in description, f"description does not name {repo!r}: {description!r}"


def test_description_does_not_invent_extra_repositories():
    """Behavior #1: a drift fails the suite — the description is built from the constant."""
    description = _recent_commits_description()
    # a token matching cpsc415-* that is not in the constant is an invented repository
    mentioned = set(re.findall(r"\bcpsc415-[\w.-]+\b", description))
    drift = mentioned - set(registry.RECENT_COMMITS_REPOS)
    assert not drift, f"description mentions repositories not in the constant: {drift}"


# ---- the schema is the JSON Schema the model sees ---------------------------------------------
def test_two_tools_are_registered():
    """Behavior #1: two tools are registered, and only two."""
    names = sorted(t["function"]["name"] for t in registry.TOOLS)
    assert names == ["recent_commits", "request_intro"]


def test_recent_commits_schema_is_json_schema():
    """Behavior #1: the schema is the JSON Schema the model sees."""
    schema = _schema("recent_commits")
    assert schema["type"] == "function"
    fn = schema["function"]
    assert fn["name"] == "recent_commits"
    assert isinstance(fn["description"], str) and fn["description"]
    params = fn["parameters"]
    assert params["type"] == "object"
    assert "repo" in params["properties"]
    assert "repo" in params["required"]
    assert params["properties"]["repo"]["type"] == "string"


def test_request_intro_schema_is_json_schema():
    """Behavior #1, #5: request_intro exposes a name, a description, and a JSON Schema."""
    schema = _schema("request_intro")
    assert schema["type"] == "function"
    fn = schema["function"]
    assert fn["name"] == "request_intro"
    assert isinstance(fn["description"], str) and fn["description"]
    params = fn["parameters"]
    assert params["type"] == "object"
    assert set(params["required"]) == {"email", "message"}
    assert params["properties"]["email"]["type"] == "string"
    assert params["properties"]["message"]["type"] == "string"


# ---- helpers ----------------------------------------------------------------------------------
def _schema(name: str) -> dict:
    return next(t for t in registry.TOOLS if t["function"]["name"] == name)


def _recent_commits_description() -> str:
    return _schema("recent_commits")["function"]["description"]
