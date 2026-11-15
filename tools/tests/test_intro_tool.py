"""The request_intro handler's tests, from spec.md §"Week 8 behaviors" #5.

A tool with a side effect is pending, not run. The handler validates its
arguments and always records the call as pending; nothing is written,
nothing is sent. No key, no network, nothing billed.
"""
import intro_tool


# ---- arguments are validated, the call is held as pending --------------------------------------
def test_valid_arguments_are_recorded_as_pending():
    """Behavior #5: a well-formed call is recorded as pending, with its arguments intact."""
    result = intro_tool.request_intro(email="v@x.com", message="hi")
    assert result == {"pending": {"email": "v@x.com", "message": "hi"}}


def test_wrong_type_email_is_an_error_not_pending():
    """Behavior #5: bad arguments are an error result, not a pending record."""
    result = intro_tool.request_intro(email=42, message="hi")
    assert "error" in result
    assert "pending" not in result


def test_wrong_type_message_is_an_error_not_pending():
    """Behavior #5: bad arguments are an error result, not a pending record."""
    result = intro_tool.request_intro(email="v@x.com", message=42)
    assert "error" in result
    assert "pending" not in result


def test_missing_email_is_an_error_not_pending():
    """Behavior #5: a missing required field is an error result, not a pending record."""
    result = intro_tool.request_intro(message="hi")
    assert "error" in result
    assert "pending" not in result


# ---- the side effect is held: nothing leaves the process ---------------------------------------
def test_nothing_is_written_to_disk(tmp_path, monkeypatch):
    """Behavior #5: no outbox, no log, no file — the call lives only in the trace."""
    monkeypatch.chdir(tmp_path)
    intro_tool.request_intro(email="v@x.com", message="hi")
    assert list(tmp_path.iterdir()) == []


def test_no_email_or_network_module_is_imported():
    """Behavior #5: the handler doesn't have smtplib in scope; nothing is sent."""
    # The handler must not import any module that could send an email or make a request.
    for name in ("smtplib", "requests", "httpx", "urllib", "urllib.request"):
        assert not hasattr(intro_tool, name), (
            f"intro_tool must not import {name}; request_intro is pending, not run")
