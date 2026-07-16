# core/transcription.py — Deepgram speech-to-text for POST /api/summaries/transcribe.
#
# Same shape as core/ai.py and core/email.py: one function in, one result out,
# raise on failure and let the router translate that into a 502.
#
# Why this exists: the frontend's first choice is the browser's built-in Web
# Speech API (free, instant). But iOS Safari's implementation is unreliable and
# iOS Chrome/Firefox don't have it at all, so those devices record audio and
# send it here to be transcribed instead.

import httpx

from config import settings

# Deepgram's "prerecorded" endpoint: one POST with the raw audio bytes, one
# JSON response — no upload-then-poll. nova-2 is their general model;
# smart_format adds punctuation and capitalization so the transcript is
# readable enough to drop straight into the summary draft.
DEEPGRAM_URL = "https://api.deepgram.com/v1/listen"
DEEPGRAM_PARAMS = {"model": "nova-2", "smart_format": "true", "language": "en"}


class TranscriptionError(Exception):
    """The transcription provider failed (no key, API error, network, or empty
    result). The transcribe route catches exactly this and returns a 502."""


async def transcribe_audio(audio_bytes: bytes, content_type: str) -> str:
    """Turn a recorded audio clip into text. Raises TranscriptionError on any
    failure — the route catches it and 502s, and the frontend falls back to
    letting the user type.

    content_type is the recording's MIME (e.g. 'audio/mp4' from iOS Safari,
    'audio/webm' from Chrome). Deepgram detects the format from it.
    """
    if not settings.deepgram_api_key:
        raise TranscriptionError("Transcription is not configured (no API key).")
    if not audio_bytes:
        raise TranscriptionError("No audio was received.")

    headers = {
        "Authorization": f"Token {settings.deepgram_api_key}",
        # Deepgram reads the audio format from this; fall back to a generic
        # type so it sniffs the bytes if the browser didn't say.
        "Content-Type": content_type or "application/octet-stream",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                DEEPGRAM_URL,
                params=DEEPGRAM_PARAMS,
                headers=headers,
                content=audio_bytes,
            )
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        # HTTPError covers network failures AND non-2xx (raise_for_status);
        # ValueError covers a non-JSON body. str(exc) may mention internals,
        # so the route logs it and sends a generic message.
        raise TranscriptionError(str(exc)) from exc

    # results.channels[0].alternatives[0].transcript — Deepgram's shape.
    # Guard every hop: a malformed/silent response must not KeyError into a 500.
    try:
        transcript = data["results"]["channels"][0]["alternatives"][0]["transcript"]
    except (KeyError, IndexError, TypeError) as exc:
        raise TranscriptionError("Transcription returned an unexpected result.") from exc

    return transcript.strip()
