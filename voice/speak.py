"""Text in, audio out, through OpenRouter's speech endpoint.

    python speak.py "Hello from CPSC 415." --out hello.mp3
    python speak.py --in speaks/answer.txt --out speaks/answer.wav

The reply is raw audio, not JSON: an error body comes back as JSON, so the
content type is checked before anything is written — an error body never lands
in a .mp3.

The provider call lives here. The command line around it comes with the set run.

Exit codes: 0 when the audio was written, 2 when the run could not start or
the provider would not speak the text.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request
import wave
from pathlib import Path

from openrouter import OpenRouter
from redact import redact

DEFAULT_MODEL = "microsoft/mai-voice-2.1-flash"        # priced per character
DEFAULT_VOICE = "en-US-Harper:MAI-Voice-2.1-Flash"     # the voice ids carry the locale
CATALOG = "https://openrouter.ai/api/v1/models?output_modalities=speech"
NO_KEY = "OPENROUTER_API_KEY is not set; nothing was billed."
_PRICES: dict[str, float] = {}


def _client() -> OpenRouter:
    """The client is built when a call is about to be made, never at import: the no-key
    tests import this module and fake the call."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError(NO_KEY)
    return OpenRouter(api_key=key)


def speak(text: str, out: Path, model: str = DEFAULT_MODEL, voice: str = DEFAULT_VOICE,
          client=None) -> dict:
    """One TTS call. Writes the file (MP3, or WAV when `out` ends in .wav) and returns what
    the lab records: the characters, the bytes, the seconds, and the cost.

    Why WAV exists here: on 2026-10-26 the MP3s from two per-character models carried a
    wrong length in their header, and Whisper's host trusted it and transcribed only the
    first half of each clip, while Scribe read the whole thing. Raw PCM has no header to
    be wrong; `wave` writes a correct one.
    """
    client = client or _client()
    fmt = "pcm" if out.suffix.lower() == ".wav" else "mp3"
    t0 = time.time()
    reply = client.tts.create_speech(model=model, input=text, voice=voice, response_format=fmt)
    data = reply.read()                          # the SDK hands back a streaming response
    seconds = round(time.time() - t0, 1)
    content_type = reply.headers.get("content-type", "")
    if not content_type.startswith("audio/"):    # an error body is JSON; never save JSON as audio
        raise RuntimeError(f"expected audio, got {content_type}: {data[:300]!r}")
    if fmt == "pcm":                             # "audio/pcm;rate=24000;channels=1" says how to frame it
        rate = int((re.search(r"rate=(\d+)", content_type) or ["", "24000"])[1])
        channels = int((re.search(r"channels=(\d+)", content_type) or ["", "1"])[1])
        with wave.open(str(out), "wb") as w:
            w.setnchannels(channels)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(data)
    else:
        out.write_bytes(data)
    generation_id = reply.headers.get("x-generation-id")
    billed = cost_of(client, generation_id)
    estimated = billed is None
    return {"file": str(out), "model": model, "voice": voice, "chars": len(text),
            "bytes": len(data), "seconds": seconds, "generation_id": generation_id,
            "cost": billed if not estimated else estimate(model, len(text)),
            "cost_is_estimate": estimated}


def cost_of(client, generation_id: str | None) -> float | None:
    """The generation record carries the bill. It takes about a minute to appear, so this
    is one try; the estimate covers the gap."""
    if not generation_id:
        return None
    try:
        return client.generations.get_generation(id=generation_id).data.total_cost
    except Exception:  # noqa: BLE001  # not there yet, or the lookup failed; the audio is saved
        return None


def estimate(model: str, chars: int) -> float | None:
    """The catalog price per character, for the minute before the record appears."""
    if not _PRICES:
        try:
            with urllib.request.urlopen(CATALOG, timeout=20) as response:
                for entry in json.load(response)["data"]:
                    _PRICES[entry["id"]] = float(entry["pricing"].get("prompt") or 0)
        except Exception:  # noqa: BLE001  # the catalog is a nicety; the call itself worked
            return None
    return round(_PRICES[model] * chars, 6) if model in _PRICES else None


def main(argv: list[str] | None = None) -> int:
    """The command line: the text to speak, and where to write the audio."""
    parser = argparse.ArgumentParser(description="Speak some text to an audio file.")
    parser.add_argument("text", nargs="?", help="the text to speak")
    parser.add_argument("--in", dest="source", type=Path,
                        help="read the text from this file")
    parser.add_argument("--out", type=Path, default=Path("speech.mp3"))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--voice", default=DEFAULT_VOICE)
    args = parser.parse_args(argv)
    if not os.environ.get("OPENROUTER_API_KEY"):
        print(NO_KEY, file=sys.stderr)
        return 2
    text = args.text
    if args.source:
        text = args.source.read_text(encoding="utf-8")
    if not text:
        parser.error("give the text to speak, or --in file")
    try:
        info = speak(text, args.out, args.model, args.voice)
    except Exception as error:  # noqa: BLE001  # the provider's message never carries the key
        print(redact(str(error)), file=sys.stderr)
        return 2
    cost = info["cost"]
    shown = f"${cost:.6f}" if isinstance(cost, (int, float)) else "cost not reported"
    mark = " (estimated)" if info["cost_is_estimate"] else ""
    print(f"{info['file']}  {info['bytes']} bytes  {info['chars']} chars  {info['seconds']}s  "
          f"cost {shown}{mark}  [{info['model']} / {info['voice']}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
