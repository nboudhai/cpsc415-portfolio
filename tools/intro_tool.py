"""The request_intro tool: a side effect, gated behind a person's confirmation.

The handler validates its arguments and always records the call as pending;
nothing is written, nothing is sent. A pending record becomes a real call
only when a person confirms, which is not in scope for Week 8 and lives in
a separate code path added later.
"""


def request_intro(email=None, message=None) -> dict:
    """A side-effect call that is held as pending in the trace.

    Returns `{"pending": {"email": ..., "message": ...}}` when arguments are
    well-formed, or `{"error": "..."}` when they are not. Never raises; never
    writes a file; never sends an email.
    """
    # the import is inside the function so registry.py can import this module
    # without a circular dependency at module load
    from registry import validate

    args = {"email": email, "message": message}
    problem = validate("request_intro", args)
    if problem:
        return {"error": problem}
    return {"pending": args}
