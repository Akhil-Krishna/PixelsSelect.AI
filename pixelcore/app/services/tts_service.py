"""
Text-to-Speech service.

Backends:
  webspeech — frontend browser speech synthesis (no backend audio generation)
  kokoro    — local Kokoro TTS synthesis on CPU/MPS in a dedicated thread pool

Design:
  TTSProvider (abstract) → WebSpeechProvider, KokoroProvider
  TTSService — public façade; picks backend and falls back safely to webspeech
"""
import asyncio
import io
import logging
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Dedicated thread pool for local Kokoro inference ──────────────────────────
_tts_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="tts-worker")

# ── Local model singleton ──────────────────────────────────────────────────────
_pipeline: Optional[object] = None
_pipeline_lock = asyncio.Lock()


# ── Sync helpers (run inside _tts_executor) ───────────────────────────────────
def _load_kokoro_sync():
    from kokoro import KPipeline

    logger.info("Loading Kokoro TTS pipeline")
    p = KPipeline(lang_code="a")  # American English
    logger.info("Kokoro TTS pipeline ready")
    return p


def _synthesize_kokoro_sync(pipeline, text: str, voice: str, speed: float) -> bytes:
    import numpy as np
    import soundfile as sf

    chunks = [audio for _, _, audio in pipeline(text, voice=voice, speed=speed)]
    if not chunks:
        return b""

    audio = np.concatenate(chunks)
    buf = io.BytesIO()
    sf.write(buf, audio, 24000, format="WAV")
    return buf.getvalue()


# ── Provider abstractions ──────────────────────────────────────────────────────
class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, text: str) -> dict:
        ...


class WebSpeechProvider(TTSProvider):
    """
    Frontend/browser TTS mode.
    Backend returns metadata only and frontend continues with speechSynthesis.
    """

    async def synthesize(self, text: str) -> dict:
        return {
            "available": True,
            "provider": "webspeech",
            "mode": "webspeech",
            "audio_bytes": None,
            "content_type": None,
            "processing_ms": 0.0,
        }


class KokoroProvider(TTSProvider):
    async def _ensure_pipeline(self):
        global _pipeline
        if _pipeline is not None:
            return _pipeline
        async with _pipeline_lock:
            if _pipeline is not None:
                return _pipeline
            try:
                loop = asyncio.get_running_loop()
                _pipeline = await loop.run_in_executor(_tts_executor, _load_kokoro_sync)
            except ImportError:
                logger.warning("kokoro/soundfile/numpy not installed — Kokoro TTS unavailable")
                _pipeline = "unavailable"
            except Exception as exc:
                logger.error("Kokoro pipeline load failed: %s", exc)
                _pipeline = "unavailable"
        return _pipeline

    async def synthesize(self, text: str) -> dict:
        started = time.perf_counter()
        clean = (text or "").strip()
        if not clean:
            return {
                "available": False,
                "provider": "kokoro",
                "mode": "audio",
                "audio_bytes": b"",
                "content_type": "audio/wav",
                "processing_ms": 0.0,
            }

        pipeline = await self._ensure_pipeline()
        if pipeline in (None, "unavailable"):
            return {
                "available": False,
                "provider": "kokoro",
                "mode": "audio",
                "audio_bytes": b"",
                "content_type": "audio/wav",
                "processing_ms": round((time.perf_counter() - started) * 1000.0, 1),
            }

        try:
            loop = asyncio.get_running_loop()
            audio_bytes = await loop.run_in_executor(
                _tts_executor,
                _synthesize_kokoro_sync,
                pipeline,
                clean,
                settings.KOKORO_VOICE,
                settings.KOKORO_SPEED,
            )
            total_ms = round((time.perf_counter() - started) * 1000.0, 1)
            return {
                "available": bool(audio_bytes),
                "provider": "kokoro",
                "mode": "audio",
                "audio_bytes": audio_bytes,
                "content_type": "audio/wav",
                "processing_ms": total_ms,
            }
        except Exception as exc:
            logger.error("Kokoro synthesis error: %s", exc)
            return {
                "available": False,
                "provider": "kokoro",
                "mode": "audio",
                "audio_bytes": b"",
                "content_type": "audio/wav",
                "error": str(exc),
                "processing_ms": round((time.perf_counter() - started) * 1000.0, 1),
            }


# ── Public service ─────────────────────────────────────────────────────────────
class TTSService:
    _webspeech = WebSpeechProvider()
    _kokoro = KokoroProvider()

    @classmethod
    async def synthesize(cls, text: str) -> dict:
        provider = settings.TTS_PROVIDER.lower().strip()
        if provider == "kokoro":
            result = await cls._kokoro.synthesize(text)
            if result.get("available"):
                return result
            fallback = await cls._webspeech.synthesize(text)
            fallback["degraded"] = True
            fallback["fallback_reason"] = result.get("error") or "kokoro_unavailable"
            return fallback
        return await cls._webspeech.synthesize(text)

    @staticmethod
    def model_ready() -> bool:
        provider = settings.TTS_PROVIDER.lower().strip()
        if provider == "webspeech":
            return True
        return _pipeline not in (None, "unavailable")


async def warmup_tts() -> None:
    if settings.TTS_PROVIDER.lower().strip() != "kokoro":
        logger.info("TTS_PROVIDER=%s — skipping Kokoro warmup", settings.TTS_PROVIDER)
        return
    await KokoroProvider()._ensure_pipeline()


# Module-level aliases
tts_service = TTSService()
synthesize_tts = TTSService.synthesize
model_ready = TTSService.model_ready
