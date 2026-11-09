"""The browser check for the voice page, adapted from
../ai-integration-course/examples/voice-loop/test_browser.py.

The whole module is skipped when playwright is not installed: nothing is
billed, no browser is launched, and the import does not crash a test run
on a machine that has not run `playwright install chromium` yet.

The billed test runs only when OPENROUTER_API_KEY and VOICE_EVAL=1 are both
set; otherwise it is skipped, not failed. The 415 test costs nothing: the
server refuses an unmapped content-type before any provider call, and the
page is the one that shows the message.

Run it by hand with the server already up:

    pip install playwright pytest
    playwright install chromium
    python server.py &
    $env:VOICE_EVAL=1; pytest voice/test_browser.py -v
"""
import os
from pathlib import Path

import pytest

pytest.importorskip("playwright", reason="playwright is not installed")
from playwright.sync_api import sync_playwright

URL = os.environ.get("VOICE_URL", "http://127.0.0.1:8000")
HERE = Path(__file__).resolve().parent
CLIP = HERE / "clips" / "own-01.m4a"


def _billed_eval_enabled() -> bool:
    """The billed test runs only when the user has the key and has set VOICE_EVAL=1.

    Spec behavior 12: tests that call a model are skipped unless the key is
    set and VOICE_EVAL=1; otherwise skipped, not failed. The same gate is
    enforced here.
    """
    return bool(os.environ.get("OPENROUTER_API_KEY")) and os.environ.get("VOICE_EVAL") == "1"


def test_a_recording_through_the_page_never_exposes_the_key_or_the_provider():
    """A clip uploaded via the page is answered, and the browser never saw the key.

    Adapted from the example's test of the same name. The page is opened at
    the URL above, a clip is uploaded through the file picker, and the page
    is polled until the answer comes back. The last three assertions are
    the point: no Authorization header left the browser, the browser never
    called openrouter directly, and it did call our server. The transcript
    check is the same one as in CHECKS.md: 'receipt reader' and '415' must
    survive.
    """
    if not _billed_eval_enabled():
        pytest.skip("set OPENROUTER_API_KEY and VOICE_EVAL=1 to run the billed browser check")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=not os.environ.get("HEADED"),
            slow_mo=500 if os.environ.get("HEADED") else 0,
        )
        page = browser.new_page()
        requests = []
        page.on("request", lambda r: requests.append((r.url, r.headers.get("authorization"))))

        page.goto(URL)
        assert "sk-or" not in page.content(), "the page leaked the key"
        page.set_input_files("#file-input", str(CLIP))
        page.wait_for_function(
            "document.querySelector('#transcript').textContent.trim().length > 0",
            timeout=120_000,
        )
        transcript = page.inner_text("#transcript")
        answer = page.inner_text("#answer")
        has_audio = page.evaluate("!!document.querySelector('#audio').src")
        browser.close()

    assert "receipt reader" in transcript.lower(), transcript
    assert "415" in transcript, transcript
    assert len(answer.strip()) > 20, answer
    assert has_audio, "the page did not receive an audio reply"
    assert all(auth is None for _, auth in requests), "an Authorization header left the browser"
    assert all("openrouter" not in url for url, _ in requests), "the browser called the provider"
    assert any(url.endswith("/api/voice") for url, _ in requests), "the browser did not call our server"


def test_an_unmapped_audio_type_shows_the_415_message_in_the_page(tmp_path):
    """A file the server does not recognize gets 415, and the page shows it.

    This costs nothing: the server refuses an unmapped content-type before
    any provider call, the page shows the server's message in its error
    block, and the result block stays hidden. A .txt file is the simplest
    way to force an unmapped type without a network call.
    """
    bad_file = tmp_path / "not-audio.txt"
    bad_file.write_text("not audio", encoding="utf-8")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL)
        page.set_input_files("#file-input", str(bad_file))
        page.wait_for_function("!document.querySelector('#error').hidden", timeout=10_000)
        error_text = page.inner_text("#error")
        result_hidden = page.evaluate("document.querySelector('#result').hidden")
        browser.close()

    assert "unsupported audio type" in error_text.lower(), error_text
    assert result_hidden, "the result block should stay hidden when the server returns 415"
