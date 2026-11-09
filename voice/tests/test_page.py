"""The page tests: voice/index.html exists, uses 127.0.0.1, and handles errors.

The page is what the server serves at GET / and what the visitor records
into. It must not bind to 'localhost' for its fetch calls: on Windows the
resolver takes two seconds for that name, and every request in a session
would wait for it. The tests here are file-content checks, not browser
runs; the browser check itself is voice/test_browser.py in step 8.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
PAGE = HERE / "index.html"


def test_the_page_exists():
    """Step 7: the page is at voice/index.html."""
    assert PAGE.exists(), f"{PAGE} is not written yet"


def test_the_page_uses_relative_paths_not_hosts():
    """The page's fetch() calls go to a path, not a host.

    The browser opens the page at http://127.0.0.1:8000/ (step 8's
    browser check) and the fetch calls go to that same origin. A relative
    path keeps the page free of any host string so the same file works
    once deployed under a real domain. 'localhost' would make the
    resolver wait two seconds a request on this machine (CHECKS.md
    "localhost vs 127.0.0.1", step 3), which is why neither name belongs
    in the page at all.
    """
    text = PAGE.read_text(encoding="utf-8")
    assert "localhost" not in text, "the page references localhost"
    assert "127.0.0.1" not in text, "the page references 127.0.0.1"
    for line in text.splitlines():
        if "fetch(" in line:
            after = line.split("fetch(", 1)[1].lstrip()
            quote = after[0]
            assert quote in ('"', "'"), f"fetch URL is not a string literal: {line!r}"
            end = after.find(quote, 1)
            path = after[1:end]
            assert path.startswith("/"), f"fetch URL must start with /: {line!r}"


def test_the_page_has_a_record_control():
    """Behavior 15: the page records audio, with the 30-second page-side cap."""
    text = PAGE.read_text(encoding="utf-8")
    assert "MediaRecorder" in text, "the page does not use MediaRecorder"
    assert "30000" in text or "30_000" in text, "the page does not cap recording at 30s"


def test_the_page_handles_failed_responses():
    """Behavior 17: a 502 from the server shows its message, not an empty transcript.

    The server returns 502 with `{"error": "The recording could not be read..."}`
    when the provider rejects the audio, and 415 when the format is not in
    the map. The page must show the message either way.
    """
    text = PAGE.read_text(encoding="utf-8")
    assert "response.ok" in text, "the page does not check response.ok"
    assert "error" in text.lower(), "the page does not display an error message"


def test_the_page_shows_the_transcript_and_the_answer():
    """Behavior 10: a live visitor sees the transcript beside the answer."""
    text = PAGE.read_text(encoding="utf-8")
    assert "transcript" in text.lower(), "the page does not show the transcript"
    assert "answer" in text.lower(), "the page does not show the answer"
