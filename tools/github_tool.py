"""The recent_commits tool: the last five commits of one of Nadia's public GitHub
repositories, read from GitHub's REST API.

The owner check is the first thing the handler does — a visitor cannot make
the chatbot report a stranger's commits. A name that is not `owner/name`, an
owner that is not `nboudhai`, or a repository that is not on the list is an
error result that names what is on record; the rate limit and GitHub
unreachable are results too, not exceptions. The `Authorization` header is
sent only when `GITHUB_TOKEN` is in the environment, so the no-key suite
never reaches GitHub and the real call happens only in the billed eval.

    python github_tool.py nboudhai/cpsc415-portfolio
"""
import json
import os
import sys
import urllib.error
import urllib.request

GITHUB_API = "https://api.github.com"


def recent_commits(repo: str) -> dict:
    """The handler. Returns either `{repo, commits}` or `{error, ...}`; never raises.

    `repo` is `owner/name`; the owner must be `nboudhai` and the repository must
    be on the list of six in `RECENT_COMMITS_REPOS`. The response is normalised
    to five entries of `{sha, date, subject}` and the model gets no say in how
    many commits are returned.
    """
    # the import is inside the function so registry.py can import this module
    # without a circular dependency at module load
    from registry import RECENT_COMMITS_REPOS

    if "/" not in repo:
        return {"error": (
            f"repo must be the full owner/name, such as nboudhai/{RECENT_COMMITS_REPOS[0]}; "
            f"got {repo!r}"
        )}
    owner, _, name = repo.partition("/")
    if owner != "nboudhai":
        return {"error": f"only nboudhai is allowed; the owner here is {owner!r}",
                "owner_allowed": "nboudhai"}
    if name not in RECENT_COMMITS_REPOS:
        return {"error": f"{repo!r} is not on record",
                "repos_on_record": list(RECENT_COMMITS_REPOS)}

    request = urllib.request.Request(
        f"{GITHUB_API}/repos/{repo}/commits?per_page=5",
        headers={"Accept": "application/vnd.github+json",
                 "User-Agent": "cpsc415-tool-loop"})
    if os.environ.get("GITHUB_TOKEN"):
        request.add_header("Authorization", f"Bearer {os.environ['GITHUB_TOKEN']}")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return {"error": f"no public repository named {repo!r}", "repo": repo}
        if error.code == 403:
            return {"error": "GitHub rate limit reached; try again in an hour or set GITHUB_TOKEN"}
        return {"error": f"GitHub answered {error.code}"}
    except (urllib.error.URLError, TimeoutError) as error:
        return {"error": f"could not reach GitHub: {error}"}

    return {"repo": repo,
            "commits": [{"sha": c["sha"][:7],
                         "date": c["commit"]["author"]["date"][:10],
                         "subject": c["commit"]["message"].splitlines()[0][:100]}
                        for c in data[:5]]}


if __name__ == "__main__":
    print(json.dumps(recent_commits(sys.argv[1] if len(sys.argv) > 1
                                    else "nboudhai/cpsc415-portfolio"), indent=1))
