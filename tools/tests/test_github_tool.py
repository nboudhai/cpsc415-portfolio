"""The recent_commits handler's tests, from spec.md §"Week 8 behaviors" #8, #11.

The owner check is the first thing the handler does; urllib is faked so no
test reaches GitHub; the Authorization header is sent only when GITHUB_TOKEN
is in the environment. No key, no network, nothing billed.
"""
import io
import json
import urllib.error

from conftest import FakeResponse, FakeURLOpener
import github_tool


# ---- helpers ----------------------------------------------------------------------------------
def _commit(sha="abcdef0", date="2026-01-01T00:00:00Z", subject="a commit"):
    """One entry in a GitHub commits response."""
    padded = (sha + "0" * 40)[:40]
    return {"sha": padded,
            "commit": {"author": {"date": date},
                       "message": subject + "\n\nbody lines after the first"}}


def _http_error(code: int) -> urllib.error.HTTPError:
    """A real urllib HTTPError, with a readable body, for the faked urlopen to raise."""
    return urllib.error.HTTPError(
        url="https://api.github.com/repos/nboudhai/x/commits",
        code=code, msg="error", hdrs={}, fp=io.BytesIO(b""))


# ---- the owner check happens first, before any HTTP call --------------------------------------
def test_a_name_without_a_slash_is_an_error_without_calling_github(monkeypatch):
    """Behavior #8: a malformed name never opens a connection."""

    def explode(*args, **kwargs):
        raise AssertionError("urlopen must not be called for a malformed name")

    monkeypatch.setattr("urllib.request.urlopen", explode)
    result = github_tool.recent_commits("just-a-word")
    assert "owner/name" in result["error"]


def test_an_owner_that_is_not_nboudhai_is_an_error_without_calling_github(monkeypatch):
    """Behavior #8: only nboudhai is allowed; a stranger's commits cannot be retrieved."""

    def explode(*args, **kwargs):
        raise AssertionError("urlopen must not be called for a stranger's owner")

    monkeypatch.setattr("urllib.request.urlopen", explode)
    result = github_tool.recent_commits("kousen/cpsc415-portfolio")
    assert "nboudhai" in result["error"]


def test_a_repository_not_on_record_is_an_error_without_calling_github(monkeypatch):
    """Behavior #8: only the six repositories on record are reachable."""

    def explode(*args, **kwargs):
        raise AssertionError("urlopen must not be called for a repo not on record")

    monkeypatch.setattr("urllib.request.urlopen", explode)
    result = github_tool.recent_commits("nboudhai/some-other-repo")
    assert "not on record" in result["error"]
    assert "cpsc415-portfolio" in result["repos_on_record"]


# ---- every GitHub failure is a result, never an exception --------------------------------------
def test_github_403_is_a_result(monkeypatch):
    """Behavior #11: the rate limit is a result the model can read."""
    opener = FakeURLOpener()
    opener.error = _http_error(403)
    monkeypatch.setattr("urllib.request.urlopen", opener)
    result = github_tool.recent_commits("nboudhai/cpsc415-portfolio")
    assert "rate limit" in result["error"].lower()


def test_github_404_is_a_result(monkeypatch):
    """Behavior #8: a repository GitHub does not have is a result, not an exception."""
    opener = FakeURLOpener()
    opener.error = _http_error(404)
    monkeypatch.setattr("urllib.request.urlopen", opener)
    result = github_tool.recent_commits("nboudhai/cpsc415-portfolio")
    assert "no public repository" in result["error"].lower()


def test_github_unreachable_is_a_result(monkeypatch):
    """Behavior #11: a network failure is a result, not an exception."""
    opener = FakeURLOpener()
    opener.error = urllib.error.URLError("dns failed")
    monkeypatch.setattr("urllib.request.urlopen", opener)
    result = github_tool.recent_commits("nboudhai/cpsc415-portfolio")
    assert "could not reach" in result["error"].lower()


# ---- the success path returns five {sha, date, subject} entries --------------------------------
def test_a_successful_call_returns_five_normalized_commits(monkeypatch):
    """Behavior #8: the model sees five {sha, date, subject} entries from a GitHub response."""
    payload = [_commit(sha=f"abcdef{i}", subject=f"commit {i}") for i in range(7)]
    opener = FakeURLOpener()
    opener.response = FakeResponse(json.dumps(payload).encode())
    monkeypatch.setattr("urllib.request.urlopen", opener)

    result = github_tool.recent_commits("nboudhai/cpsc415-portfolio")

    assert result["repo"] == "nboudhai/cpsc415-portfolio"
    assert len(result["commits"]) == 5
    for entry in result["commits"]:
        assert set(entry.keys()) == {"sha", "date", "subject"}
        assert len(entry["sha"]) == 7
        assert len(entry["date"]) == 10
        # only the first line of the commit message survives
        assert "\n" not in entry["subject"]


# ---- the credential is sent only when GITHUB_TOKEN is set --------------------------------------
def test_authorization_header_is_sent_only_when_github_token_is_set(monkeypatch):
    """Behavior #11: the credential never leaves the server unless GITHUB_TOKEN is set."""
    opener = FakeURLOpener()
    opener.response = FakeResponse(b"[]")
    monkeypatch.setattr("urllib.request.urlopen", opener)

    # without GITHUB_TOKEN: no Authorization header is sent
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    github_tool.recent_commits("nboudhai/cpsc415-portfolio")
    headers = opener.calls[-1]["headers"]
    assert not any(k.lower() == "authorization" for k in headers)

    # with GITHUB_TOKEN: an Authorization: Bearer ... header is sent
    monkeypatch.setenv("GITHUB_TOKEN", "test-token-not-real")
    github_tool.recent_commits("nboudhai/cpsc415-portfolio")
    headers = opener.calls[-1]["headers"]
    auth = [v for k, v in headers.items() if k.lower() == "authorization"]
    assert auth and auth[0].startswith("Bearer ")
