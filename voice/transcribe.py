"""Audio in, text out, through OpenRouter's transcription endpoint.

    python transcribe.py clips/own-01.m4a --expect "what I actually said"
    python transcribe.py --set clips/expected.json --out clips/transcripts-whisper-own.json

The provider call lives here. The command line around it comes with the set run.

Exit codes: 0 when every clip passed, 1 when any clip failed, 2 when the run
could not start because there is no key.
"""
import argparse
import base64
import json
import os
import pathlib
import sys
import time
from dataclasses import asdict

from check import DEFAULT_MAX_WER, compare
from openrouter import OpenRouter
from redact import redact

DEFAULT_MODEL = "openai/whisper-large-v3-turbo"     # priced per second of audio
FORMATS = {".mp3": "mp3", ".wav": "wav", ".m4a": "m4a", ".webm": "webm", ".ogg": "ogg",
           ".flac": "flac", ".aac": "aac"}
NO_COST = "none reported"          # a call the provider refused reports no usage
NO_KEY = "OPENROUTER_API_KEY is not set; nothing was billed."


def _client() -> OpenRouter:
    """The client is built when a call is about to be made, never at import: the no-key
    tests import this module and fake the call."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError(NO_KEY)
    return OpenRouter(api_key=key)


def transcribe(audio: bytes, fmt: str, model: str = DEFAULT_MODEL, client=None,
               language: str | None = None) -> dict:
    """One STT call: the text, the audio's seconds, the cost, and the seconds it took."""
    t0 = time.time()
    kwargs = {"language": language} if language else {}
    reply = (client or _client()).stt.create_transcription(
        model=model, input_audio={"data": base64.b64encode(audio).decode(), "format": fmt},
        **kwargs)
    usage = reply.usage
    return {"text": reply.text, "model": model,
            "audio_seconds": usage.seconds if usage else None,
            "cost": usage.cost if usage else None,
            "seconds": round(time.time() - t0, 1)}


def transcribe_file(path: pathlib.Path, model: str = DEFAULT_MODEL, language: str | None = None,
                    client=None) -> dict:
    """One clip from disk: the format comes from the name, the bytes go to the provider."""
    fmt = FORMATS.get(path.suffix.lower())
    if not fmt:
        raise ValueError(f"{path}: unknown audio format; one of {sorted(FORMATS)}")
    return transcribe(path.read_bytes(), fmt, model=model, client=client, language=language)


def run_set(expected_path: pathlib.Path, model: str = DEFAULT_MODEL, language: str | None = None,
            client=None) -> tuple[list[dict], int]:
    """Every clip in expected.json, transcribed once each and checked in code.

    A clip whose transcription raises — a provider rejection does — is recorded
    as a failed clip, with the error and the cost "none reported", and the set
    carries on. The run never retries, so a clip is billed at most once.

    The exit code is 1 if any clip failed and 0 if none did.
    """
    expected_path = pathlib.Path(expected_path)
    entries = json.loads(expected_path.read_text(encoding="utf-8"))
    records = []
    for entry in entries:
        clip = expected_path.parent / entry["file"]
        try:
            heard = transcribe_file(clip, model=model, language=entry.get("language", language),
                                     client=client)
        except Exception as error:  # noqa: BLE001  # one clip's failure does not stop the set
            record = {"file": entry["file"], "model": model, "text": None, "audio_seconds": None,
                      "cost": NO_COST, "seconds": None, "ok": False, "check": None,
                      "error": redact(str(error))[:300]}
            records.append(record)
            print(f"{entry['file']}: FAIL  {record['error']}  cost {NO_COST}")
            continue
        verdict = compare(entry["text"], heard["text"], entry.get("must_contain"),
                          entry.get("max_wer", DEFAULT_MAX_WER))
        record = {"file": entry["file"], "model": model, "text": heard["text"],
                  "audio_seconds": heard.get("audio_seconds"), "cost": heard.get("cost"),
                  "seconds": heard.get("seconds"), "ok": verdict.ok, "check": asdict(verdict),
                  "error": None}
        records.append(record)
        print(f"{entry['file']}: {'ok' if verdict.ok else 'FAIL'}  wer={verdict.wer:.3f}  "
              f"missing={verdict.missing}  {record['audio_seconds']}s audio  "
              f"${record['cost']:.6f}  {record['seconds']}s\n    got: {record['text']!r}")
    failed = [record for record in records if not record["ok"]]
    return records, (1 if failed else 0)


def main(argv: list[str] | None = None) -> int:
    """The command line: one clip, or a whole set. Exit 0, 1 or 2."""
    parser = argparse.ArgumentParser(description="Transcribe a clip, or a whole expected.json set.")
    parser.add_argument("audio", nargs="?", type=pathlib.Path, help="one clip")
    parser.add_argument("--set", dest="expected", type=pathlib.Path,
                        help="expected.json: file, text, must_contain per clip")
    parser.add_argument("--expect", help="what was said, for the checker")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--language", help="ISO-639-1 hint, e.g. en; omitted means auto-detect")
    parser.add_argument("--out", type=pathlib.Path, default=pathlib.Path("transcripts.json"))
    args = parser.parse_args(argv)
    if not os.environ.get("OPENROUTER_API_KEY"):
        print(NO_KEY, file=sys.stderr)
        return 2
    if args.expected:
        records, code = run_set(args.expected, model=args.model, language=args.language)
        args.out.write_text(json.dumps(records, indent=2), encoding="utf-8")
        total = sum(record["cost"] for record in records if isinstance(record["cost"], (int, float)))
        failed = sum(1 for record in records if not record["ok"])
        print(f"{len(records)} clips, {failed} failed, ${total:.6f} total, written to {args.out}")
        return code
    if args.audio:
        record = transcribe_file(args.audio, model=args.model, language=args.language)
        print(f"{record['text']}\n[{record['model']}  {record['audio_seconds']}s audio  "
              f"${record['cost']:.6f}  {record['seconds']}s]")
        if args.expect:
            verdict = compare(args.expect, record["text"])
            print(f"check: ok={verdict.ok} wer={verdict.wer:.3f} missing={verdict.missing}")
        return 0
    parser.error("give an audio file or --set expected.json")


if __name__ == "__main__":
    sys.exit(main())
