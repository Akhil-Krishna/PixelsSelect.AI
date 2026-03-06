"""
Speech-to-Text service.

Backends:
  groq  — Groq Whisper API (~150 ms, cloud)
  local — faster-whisper on CPU/GPU (runs in a dedicated thread pool)

Design:
  STTProvider (abstract) → GroqSTTProvider, LocalSTTProvider
  STTService — public façade; picks backend, adds logging, handles fallback
"""
import asyncio
import io
import logging
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Dedicated thread pool for local faster-whisper  ────────────────────────────
_stt_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="stt-worker")

# ── Local model singleton ──────────────────────────────────────────────────────
_model: Optional[object] = None
_model_lock = asyncio.Lock()


# ── Sync helpers (run inside _stt_executor) ────────────────────────────────────

def _load_model_sync(size: str, device: str, compute: str):
    from faster_whisper import WhisperModel
    logger.info("Loading faster-whisper %s on %s/%s", size, device, compute)
    m = WhisperModel(size, device=device, compute_type=compute)
    logger.info("✅ Whisper model ready (%s)", size)
    return m


def _transcribe_sync(model, audio_bytes: bytes, language: str):
    started = time.perf_counter()
    audio_io = io.BytesIO(audio_bytes)
    segments, info = model.transcribe(
        audio_io,
        language=language if language not in ("auto", "") else None,
        beam_size=max(1, settings.STT_BEAM_SIZE),
        vad_filter=settings.STT_VAD_FILTER,
        vad_parameters={"min_silence_duration_ms": max(50, settings.STT_VAD_MIN_SILENCE_MS)},
        word_timestamps=False,
    )
    text = " ".join(seg.text.strip() for seg in segments).strip()
    infer_ms = (time.perf_counter() - started) * 1000.0
    return text, info.language, info.duration, round(infer_ms, 1)


# ── Provider abstractions ──────────────────────────────────────────────────────

class STTProvider(ABC):
    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, language: str = "en") -> dict:
        ...


class GroqSTTProvider(STTProvider):
    """Groq Whisper cloud API — fast, no local GPU needed."""

    async def transcribe(self, audio_bytes: bytes, language: str = "en") -> dict:
        started = time.perf_counter()
        model_name = settings.GROQ_STT_MODEL

        if not settings.GROQ_API_KEY:
            logger.warning("GROQ_API_KEY empty — falling back to local Whisper")
            return await LocalSTTProvider().transcribe(audio_bytes, language)

        form_data: dict = {"model": model_name, "response_format": "verbose_json"}
        if language and language.lower() not in ("auto", ""):
            form_data["language"] = language

        try:
            async with httpx.AsyncClient(timeout=settings.GROQ_STT_TIMEOUT) as client:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
                    files={"file": ("audio.webm", audio_bytes, "audio/webm")},
                    data=form_data,
                )
                resp.raise_for_status()
                data = resp.json()

            text = (data.get("text") or "").strip()
            detected_lang = data.get("language") or language
            duration = float(data.get("duration") or 0.0)
            total_ms = round((time.perf_counter() - started) * 1000.0, 1)
            logger.info(
                "Groq STT bytes=%d lang=%s model=%s duration=%.2fs ms=%.1f",
                len(audio_bytes), detected_lang, model_name, duration, total_ms,
            )
            return {
                "text": text, "language": detected_lang, "duration": round(duration, 2),
                "available": True, "processing_ms": total_ms,
                "model": model_name, "provider": "groq",
            }

        except httpx.HTTPStatusError as exc:
            logger.warning("Groq STT HTTP %d — falling back to local", exc.response.status_code)
            return await LocalSTTProvider().transcribe(audio_bytes, language)
        except Exception as exc:
            logger.error("Groq STT error %s — falling back to local", exc)
            return await LocalSTTProvider().transcribe(audio_bytes, language)


class LocalSTTProvider(STTProvider):
    """faster-whisper on CPU (or GPU). Falls back gracefully if not installed."""

    async def _ensure_model(self):
        global _model
        if _model is not None:
            return _model
        async with _model_lock:
            if _model is not None:
                return _model
            try:
                loop = asyncio.get_running_loop()
                _model = await loop.run_in_executor(
                    _stt_executor,
                    _load_model_sync,
                    settings.STT_MODEL,
                    settings.STT_DEVICE,
                    settings.STT_COMPUTE,
                )
            except ImportError:
                logger.warning("faster-whisper not installed — local STT disabled")
                _model = "unavailable"
            except Exception as exc:
                logger.error("Whisper load failed: %s", exc)
                _model = "unavailable"
        return _model

    async def transcribe(self, audio_bytes: bytes, language: str = "en") -> dict:
        started = time.perf_counter()
        model_name = settings.STT_MODEL

        if not audio_bytes:
            return {
                "text": "", "language": language, "duration": 0.0,
                "available": False, "processing_ms": 0.0,
                "model": model_name, "provider": "local",
            }

        model = await self._ensure_model()
        if model in ("unavailable", None):
            return {
                "text": "", "language": language, "duration": 0.0,
                "available": False, "processing_ms": round((time.perf_counter() - started) * 1000.0, 1),
                "model": model_name, "provider": "local",
            }

        try:
            loop = asyncio.get_running_loop()
            text, detected_lang, duration, infer_ms = await loop.run_in_executor(
                _stt_executor, _transcribe_sync, model, audio_bytes, language
            )
            total_ms = round((time.perf_counter() - started) * 1000.0, 1)
            logger.info(
                "Local STT bytes=%d lang=%s model=%s infer_ms=%.1f total_ms=%.1f",
                len(audio_bytes), language, model_name, infer_ms, total_ms,
            )
            return {
                "text": text, "language": detected_lang, "duration": round(duration, 2),
                "available": True, "processing_ms": total_ms,
                "model": model_name, "provider": "local",
            }
        except Exception as exc:
            logger.error("Local Whisper error: %s", exc)
            return {
                "text": "", "language": language, "duration": 0.0,
                "available": False, "error": str(exc),
                "processing_ms": round((time.perf_counter() - started) * 1000.0, 1),
                "model": model_name, "provider": "local",
            }


# ── Public service ─────────────────────────────────────────────────────────────

class STTService:
    """Selects provider based on settings.STT_PROVIDER."""

    _groq = GroqSTTProvider()
    _local = LocalSTTProvider()

    @classmethod
    async def transcribe_audio(
        cls, audio_bytes: bytes, language: str = "en"
    ) -> dict:
        provider = settings.STT_PROVIDER.lower().strip()
        if provider == "groq":
            return await cls._groq.transcribe(audio_bytes, language)
        return await cls._local.transcribe(audio_bytes, language)

    @staticmethod
    def model_ready() -> bool:
        if settings.STT_PROVIDER.lower().strip() == "groq":
            return bool(settings.GROQ_API_KEY)
        return _model not in (None, "unavailable")


# Warmup
async def warmup_model() -> None:
    if settings.STT_PROVIDER.lower().strip() == "groq":
        logger.info("STT_PROVIDER=groq — skipping local Whisper warmup")
        return
    await LocalSTTProvider()._ensure_model()


# Module-level aliases
stt_service = STTService()
transcribe_audio = STTService.transcribe_audio
model_ready = STTService.model_ready
