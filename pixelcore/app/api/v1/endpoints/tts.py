"""
Text-to-Speech endpoint.
"""
from fastapi import APIRouter, Depends, Response

from app.core.config import settings
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas import TTSRequest
from app.services.tts_service import synthesize_tts

router = APIRouter(prefix="/tts", tags=["tts"])


@router.post("/synthesize")
async def synthesize(payload: TTSRequest, _: User = Depends(get_current_user)):
    result = await synthesize_tts(payload.text)
    if result.get("mode") == "audio" and result.get("available") and result.get("audio_bytes"):
        return Response(
            content=result["audio_bytes"],
            media_type=result.get("content_type") or "audio/wav",
            headers={
                "X-TTS-Provider": str(result.get("provider", settings.TTS_PROVIDER)),
                "X-TTS-Processing-Ms": str(result.get("processing_ms", 0.0)),
            },
        )

    return {
        "available": bool(result.get("available", False)),
        "provider": result.get("provider", settings.TTS_PROVIDER),
        "mode": result.get("mode", "webspeech"),
        "degraded": bool(result.get("degraded", False)),
        "fallback_reason": result.get("fallback_reason"),
    }
