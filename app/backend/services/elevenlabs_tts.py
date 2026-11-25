"""ElevenLabs text-to-speech adapter (TTSProvider). Returns OGG/Opus for Telegram voice notes.

Policy (allowlist, mode, guard, length, rate limit) is decided before this is called, in
harness/tools/audio_generator.py. Only metadata is logged, never the text or the audio.
"""

from __future__ import annotations

import asyncio
import logging
import random
import shutil

from elevenlabs import VoiceSettings
from elevenlabs.client import AsyncElevenLabs
from elevenlabs.core import ApiError

from app.backend.core.errors import ConfigError
from app.backend.core.settings import Settings

log = logging.getLogger(__name__)

TTS_MODEL = "eleven_v4"
OUTPUT_FORMAT = "opus_48000_32"
MAX_TTS_CHARS = 900  # rough budget for ~60 s of speech; measure and tune


class VoiceError(Exception):
    """A provider failure reduced to a short kind: rate_limited, auth, invalid_request, provider_error."""

    def __init__(self, kind: str, status: int | None = None) -> None:
        super().__init__(kind)
        self.kind, self.status = kind, status


def classify(exc: ApiError) -> VoiceError:
    status = exc.status_code
    if status == 429:
        return VoiceError("rate_limited", status)
    if status in (401, 403):
        return VoiceError("auth", status)
    if status in (400, 422):
        return VoiceError("invalid_request", status)
    return VoiceError("provider_error", status)


def is_ogg(data: bytes) -> bool:
    return data[:4] == b"OggS"


async def to_ogg_opus(audio: bytes) -> bytes:
    """Wrap or transcode audio to OGG/Opus with ffmpeg (stdin to stdout, nothing on disk)."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise VoiceError("provider_error")
    proc = await asyncio.create_subprocess_exec(
        ffmpeg, "-loglevel", "error", "-i", "pipe:0",
        "-c:a", "libopus", "-b:a", "32k", "-ar", "48000", "-ac", "1", "-f", "ogg", "pipe:1",
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )  # fmt: skip
    out, _ = await proc.communicate(audio)
    if proc.returncode != 0 or not is_ogg(out):
        raise VoiceError("provider_error")
    return out


class ElevenLabsTTS:
    def __init__(self, api_key: str, voice_id: str) -> None:
        self._voice_id = voice_id
        self._client = AsyncElevenLabs(api_key=api_key, timeout=60)

    async def speak(self, text: str, attempts: int = 3) -> bytes:
        if not text.strip() or len(text) > MAX_TTS_CHARS:
            raise VoiceError("invalid_request")
        for attempt in range(attempts):
            try:
                chunks = self._client.text_to_speech.convert(
                    self._voice_id,
                    text=text,
                    model_id=TTS_MODEL,
                    output_format=OUTPUT_FORMAT,
                    voice_settings=VoiceSettings(stability=0.5, similarity_boost=0.75, speed=1.0),
                )
                audio = b"".join([chunk async for chunk in chunks])
                break
            except ApiError as exc:  # streamed calls are not retried by the SDK
                err = classify(exc)
                retryable = err.kind == "rate_limited" or (err.status or 0) >= 500
                if not retryable or attempt == attempts - 1:
                    raise err from exc
                await asyncio.sleep(2**attempt + random.uniform(0, 0.25))
        log.info("tts ok: %s chars, %s bytes, ogg=%s", len(text), len(audio), is_ogg(audio))
        return audio if is_ogg(audio) else await to_ogg_opus(audio)


def make_tts(settings: Settings) -> ElevenLabsTTS:
    if not settings.tts_api_key or not settings.tts_voice_id:
        raise ConfigError("TTS is not configured: set TTS_API_KEY and TTS_VOICE_ID.")
    return ElevenLabsTTS(settings.tts_api_key, settings.tts_voice_id)
