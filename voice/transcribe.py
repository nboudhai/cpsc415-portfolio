"""Audio in, text out, through OpenRouter's transcription endpoint.

The provider call lives here. The command line around it — one clip, or a whole
expected.json set — comes with the set run.
"""
import base64
import os
import time

from openrouter import OpenRouter

DEFAULT_MODEL = "openai/whisper-large-v3-turbo"     # priced per second of audio
FORMATS = {".mp3": "mp3", ".wav": "wav", ".m4a": "m4a", ".webm": "webm", ".ogg": "ogg",
           ".flac": "flac", ".aac": "aac"}


def _client() -> OpenRouter:
    """The client is built when a call is about to be made, never at import: the no-key
    tests import this module and fake the call."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set; nothing was billed.")
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
