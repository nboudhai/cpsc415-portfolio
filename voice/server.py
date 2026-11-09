"""The voice loop: the browser records, the server transcribes, answers, and speaks.

GET  /            the page: a record button, the file picker, the transcript and the answer.
POST /api/voice   body = audio bytes; the Content-Type header says which format. Three
                  billed calls on the server: transcription, chat, speech. Returns JSON with
                  the transcript, the answer, the audio as base64, and the three costs.
POST /api/chat    body = the question as text; the same answer() function, no audio.

The key is read from the environment when a call is about to be made, so it reaches
neither the page nor the network tab, and the no-key tests can import this module and
fake the three steps.
"""
import base64
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from answer import DEFAULT_MODEL as CHAT_MODEL
from answer import answer, for_speaking
from redact import redact
from speak import DEFAULT_MODEL as TTS_MODEL
from speak import DEFAULT_VOICE as TTS_VOICE
from speak import speak
from transcribe import DEFAULT_MODEL as STT_MODEL
from transcribe import transcribe

HERE = Path(__file__).resolve().parent
PAGE = HERE / "index.html"
LAST_AUDIO = HERE / "last-answer.mp3"           # the transient output of the last turn
MAX_BODY = 10_000_000                           # the cap on what a visitor can send
FORMATS = {"audio/webm": "webm", "audio/mpeg": "mp3", "audio/mp3": "mp3", "audio/wav": "wav",
           "audio/ogg": "ogg", "audio/x-wav": "wav", "audio/mp4": "m4a", "audio/x-m4a": "m4a",
           "audio/flac": "flac"}
RECORDING_REJECTED = "The recording could not be read. Please try again or type your question."
TURN_FAILED = "Something went wrong. Please try again or type your question."
EMPTY_ANSWER = "I didn't catch that."


class RecordingRejected(Exception):
    """The provider would not take the recording. The turn ends here."""


def log_provider_message(error: Exception) -> None:
    """The provider's message goes to the server's terminal and nowhere else.

    It is never sent to the browser, and the server logs to the terminal only,
    never to a file, so the text in the log can never be committed.
    """
    print(f"provider error: {redact(str(error))}", file=sys.stderr, flush=True)


def models() -> dict:
    """Which models this turn used, recorded per clip and per turn."""
    return {"stt": STT_MODEL, "chat": CHAT_MODEL, "tts": f"{TTS_MODEL} / {TTS_VOICE}"}


def voice_turn(audio: bytes, fmt: str) -> dict:
    """The loop, once: hear, think, speak.

    Each step's cost and seconds are recorded for CHECKS.md. A recording the
    provider will not take ends the turn here: no chat call, no speech call, and
    no audio written. A speech call that fails does not end the turn: the visitor
    can still read the answer, and the error is in the reply beside it.
    """
    t0 = time.time()
    try:
        heard = transcribe(audio, fmt, STT_MODEL)
    except Exception as error:
        raise RecordingRejected(str(error)) from error
    question = (heard.get("text") or "").strip()
    if not question:
        return {"transcript": "", "answer": EMPTY_ANSWER, "audio_b64": None,
                "cost": {"stt": heard.get("cost"), "chat": 0, "tts": 0},
                "seconds": {"stt": round(time.time() - t0, 1)}, "models": models()}
    t1 = time.time()
    reply, chat_cost = answer(question)
    t2 = time.time()
    audio_b64, tts_cost, tts_error = None, 0, None
    try:
        spoken = speak(for_speaking(reply), LAST_AUDIO, TTS_MODEL, TTS_VOICE)
        audio_b64 = base64.b64encode(LAST_AUDIO.read_bytes()).decode()
        tts_cost = spoken.get("cost")
    except Exception as error:  # noqa: BLE001  # the visitor can still read the answer
        tts_error = str(error)[:300]
    seconds = {"stt": round(t1 - t0, 1), "chat": round(t2 - t1, 1), "tts": round(time.time() - t2, 1)}
    return {"transcript": question, "answer": reply, "audio_b64": audio_b64, "tts_error": tts_error,
            "cost": {"stt": heard.get("cost"), "chat": chat_cost, "tts": tts_cost},
            "seconds": seconds, "models": models()}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/api/"):
            return self.reply(405, {"error": "POST only"})
        if not PAGE.exists():
            return self.reply(404, {"error": "the page is not written yet"})
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(PAGE.read_bytes())

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(min(length, MAX_BODY + 1))
        try:
            if self.path == "/api/voice":
                if len(body) > MAX_BODY:
                    return self.reply(413, {"error": "The recording is too large. Please try again "
                                                     "or type your question."})
                content_type = self.headers.get("Content-Type", "").split(";")[0]
                fmt = FORMATS.get(content_type)
                if not fmt:
                    return self.reply(415, {"error": f"unsupported audio type {content_type!r}; "
                                                     f"send one of {sorted(FORMATS)}"})
                return self.reply(200, voice_turn(body, fmt))
            if self.path == "/api/chat":
                question = body.decode("utf-8", "replace").strip()[:2000]
                if not question:
                    return self.reply(400, {"error": "ask something first"})
                reply, cost = answer(question)
                return self.reply(200, {"transcript": question, "answer": reply, "audio_b64": None,
                                        "cost": {"stt": 0, "chat": cost, "tts": 0},
                                        "seconds": {"chat": 0}, "models": models()})
            self.reply(404, {"error": "not found"})
        except RecordingRejected as error:
            log_provider_message(error)
            self.reply(502, {"error": RECORDING_REJECTED})
        except Exception as error:  # noqa: BLE001  # the provider's message goes to the log, not the browser
            log_provider_message(error)
            self.reply(502, {"error": TURN_FAILED})

    def reply(self, status: int, data: dict):
        payload = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def make_server(port: int = 8000) -> ThreadingHTTPServer:
    """The server on the port given: a slow turn must not block the next visitor.

    The bind address is 127.0.0.1, not 'localhost': on this machine the
    resolver waits two seconds for that name, which would make every
    request in a session wait for it.
    """
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
    print(f"http://127.0.0.1:8000  (stt {STT_MODEL}, chat {CHAT_MODEL}, tts {TTS_MODEL}/{TTS_VOICE})")
    try:
        make_server(8000).serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
