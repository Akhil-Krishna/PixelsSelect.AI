"""
Vision service — emotion analysis and cheating detection.

Backends:
  deepface — DeepFace + OpenCV (CPU, runs in a dedicated thread pool)
  mock     — random plausible values for testing without GPU/model files

Design:
  VisionAnalyser (abstract) → DeepFaceAnalyser, MockAnalyser
  VisionService — public façade; picks backend, adds telemetry, persists logs
"""
import asyncio
import base64
import logging
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Dedicated CPU thread pool for DeepFace (blocking ML) ──────────────────────
_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="vision-worker")

# ── Lazy module-level state ────────────────────────────────────────────────────
_deepface = None
_cv2 = None
_np = None
_haar = None

# ── Emotion → interview score mapping ─────────────────────────────────────────
EMOTION_MAP = {
    "happy":    {"confidence": 88.0, "engagement": 92.0, "stress": 8.0},
    "neutral":  {"confidence": 72.0, "engagement": 67.0, "stress": 18.0},
    "surprise": {"confidence": 58.0, "engagement": 82.0, "stress": 32.0},
    "sad":      {"confidence": 38.0, "engagement": 42.0, "stress": 58.0},
    "angry":    {"confidence": 42.0, "engagement": 52.0, "stress": 68.0},
    "fear":     {"confidence": 28.0, "engagement": 48.0, "stress": 78.0},
    "disgust":  {"confidence": 35.0, "engagement": 40.0, "stress": 72.0},
}


def _load_deps() -> bool:
    global _deepface, _cv2, _np, _haar
    if _np is None:
        try:
            import numpy as np
            _np = np
        except ImportError:
            logger.warning("numpy not installed")
    if _cv2 is None:
        try:
            import cv2
            _cv2 = cv2
        except ImportError:
            logger.warning("opencv not installed")
    if _deepface is None:
        try:
            from deepface import DeepFace
            _deepface = DeepFace
        except ImportError:
            logger.warning("deepface not installed")
    if _haar is None and _cv2 is not None:
        try:
            xml = _cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            c = _cv2.CascadeClassifier(xml)
            if not c.empty():
                _haar = c
        except Exception:
            pass
    return _deepface is not None and _cv2 is not None and _np is not None


def model_ready() -> bool:
    return _deepface is not None and _cv2 is not None and _np is not None


# ── Sync helpers (run inside executor) ────────────────────────────────────────

def _decode_frame(b64: str):
    if not b64 or not b64.strip():
        return None
    try:
        if "," in b64:
            b64 = b64.split(",", 1)[1]
        raw = base64.b64decode(b64)
        arr = _np.frombuffer(raw, _np.uint8)
        img = _cv2.imdecode(arr, _cv2.IMREAD_COLOR)
        return img
    except Exception as exc:
        logger.error("Frame decode: %s", exc)
        return None


def _count_faces(img) -> int:
    if _haar is None or _haar.empty():
        return 1
    try:
        gray = _cv2.cvtColor(img, _cv2.COLOR_BGR2GRAY)
        faces = _haar.detectMultiScale(gray, 1.1, 5, minSize=(50, 50))
        return int(len(faces))
    except Exception:
        return 1


def _gaze_score(img) -> float:
    try:
        h, w = img.shape[:2]
        gray = _cv2.cvtColor(img, _cv2.COLOR_BGR2GRAY)
        eye = gray[int(h * 0.20): int(h * 0.48), int(w * 0.05): int(w * 0.95)]
        mid = eye.shape[1] // 2
        l_m = float(_np.mean(eye[:, :mid]))
        r_m = float(_np.mean(eye[:, mid:]))
        peak = max(l_m, r_m, 1.0)
        return min(100.0, abs(l_m - r_m) / peak * 450.0)
    except Exception:
        return 0.0


def _run_vision_sync(b64: str) -> dict:
    """Full DeepFace + OpenCV pipeline. Runs in _executor."""
    result = {
        "success": False,
        "emotions": {},
        "dominant_emotion": "neutral",
        "confidence_score": 65.0,
        "engagement_score": 65.0,
        "stress_score": 20.0,
        "face_count": 1,
        "gaze_deviation": 0.0,
        "cheating_flags": [],
        "cheating_score": 0.0,
        "error": None,
    }
    if not _load_deps():
        result["error"] = "Vision libs unavailable"
        return result

    img = _decode_frame(b64)
    if img is None:
        result["error"] = "Could not decode frame"
        return result

    flags, score = [], 0.0
    faces = _count_faces(img)
    result["face_count"] = faces
    if faces == 0:
        flags.append("no_face_detected")
        score += 35.0
    elif faces > 1:
        flags.append(f"multiple_faces_{faces}")
        score += 45.0

    try:
        t0 = time.perf_counter()
        analysis = _deepface.analyze(
            img_path=img,
            actions=["emotion"],
            enforce_detection=False,
            silent=True,
            detector_backend="opencv",
        )
        logger.debug("DeepFace.analyze %.3fs", time.perf_counter() - t0)
        face_data = analysis[0] if isinstance(analysis, list) else analysis
        raw = face_data.get("emotion", {})
        dominant = str(face_data.get("dominant_emotion", "neutral")).lower()
        total = max(float(sum(raw.values())), 1.0)
        pct = {k: round(float(v) / total * 100.0, 2) for k, v in raw.items()}
        result["emotions"] = pct
        result["dominant_emotion"] = dominant
        mapping = EMOTION_MAP.get(dominant, EMOTION_MAP["neutral"])
        h_pct = pct.get("happy", 0.0) / 100.0
        f_pct = pct.get("fear", 0.0) / 100.0
        result["confidence_score"] = round(min(100.0, mapping["confidence"] * (1 + h_pct * 0.10 - f_pct * 0.15)), 1)
        result["engagement_score"] = round(min(100.0, mapping["engagement"] * (1 + h_pct * 0.08)), 1)
        result["stress_score"] = round(float(mapping["stress"]), 1)
        if dominant in ("fear", "angry", "disgust") and pct.get(dominant, 0.0) > 45.0:
            score += 12.0
        result["success"] = True
    except Exception as exc:
        logger.warning("DeepFace emotion error: %s", exc)
        result["error"] = str(exc)

    gaze = _gaze_score(img)
    result["gaze_deviation"] = round(gaze, 1)
    if gaze > 45.0:
        flags.append("gaze_away")
        score += min(20.0, gaze * 0.38)

    result["cheating_flags"] = flags
    result["cheating_score"] = round(min(100.0, score), 1)
    return result


# ── Abstract provider ──────────────────────────────────────────────────────────

class VisionAnalyser(ABC):
    @abstractmethod
    async def analyze(self, b64_image: str) -> dict:
        ...


class DeepFaceAnalyser(VisionAnalyser):
    async def analyze(self, b64_image: str) -> dict:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_executor, _run_vision_sync, b64_image)


class MockAnalyser(VisionAnalyser):
    async def analyze(self, b64_image: str) -> dict:
        import random
        dominant = random.choice(["happy", "neutral", "neutral", "neutral", "surprise"])
        mapping = EMOTION_MAP.get(dominant, EMOTION_MAP["neutral"])
        return {
            "success": True,
            "emotions": {
                "happy": round(random.uniform(20, 60), 2),
                "neutral": round(random.uniform(20, 50), 2),
                "surprise": round(random.uniform(0, 15), 2),
                "sad": round(random.uniform(0, 10), 2),
                "angry": round(random.uniform(0, 8), 2),
                "fear": round(random.uniform(0, 8), 2),
                "disgust": round(random.uniform(0, 5), 2),
            },
            "dominant_emotion": dominant,
            "confidence_score": round(mapping["confidence"] + random.uniform(-5, 5), 1),
            "engagement_score": round(mapping["engagement"] + random.uniform(-5, 5), 1),
            "stress_score": round(mapping["stress"] + random.uniform(-3, 3), 1),
            "face_count": 1,
            "gaze_deviation": round(random.uniform(0, 20), 1),
            "cheating_flags": [],
            "cheating_score": 0.0,
            "error": None,
        }


# ── Public vision service ──────────────────────────────────────────────────────

class VisionService:
    """
    Façade: selects backend, adds telemetry, and falls back to mock
    if DeepFace is unavailable.
    
    Includes retry logic with exponential backoff for transient failures.
    """

    _deepface_analyser = DeepFaceAnalyser()
    _mock_analyser = MockAnalyser()
    
    # Retry configuration
    _max_retries = 3
    _base_delay = 0.5  # seconds
    _max_delay = 4.0   # seconds

    @classmethod
    async def analyze_frame(cls, b64_image: str) -> dict:
        """
        Analyze a frame with retry logic and exponential backoff.
        
        Retries on transient failures (network issues, DeepFace errors)
        before falling back to mock analyser.
        """
        started = time.perf_counter()
        provider = settings.VISION_PROVIDER.lower().strip()
        degraded = False
        retry_count = 0
        last_error = None

        if provider == "mock":
            result = await cls._mock_analyser.analyze(b64_image)
            provider_used = "mock"
        else:
            # Try with retry logic for deepface
            while retry_count < cls._max_retries:
                try:
                    result = await cls._deepface_analyser.analyze(b64_image)
                    
                    # Check if result indicates a transient failure
                    if result.get("success"):
                        break
                    
                    error = result.get("error", "")
                    # Retry on certain error types
                    if error and any(err in str(error).lower() for err in ["timeout", "connection", "memory"]):
                        last_error = error
                        retry_count += 1
                        if retry_count < cls._max_retries:
                            delay = min(cls._base_delay * (2 ** retry_count), cls._max_delay)
                            logger.warning(
                                "Vision analysis retry %d/%d after %.1fs - error: %s",
                                retry_count, cls._max_retries, delay, error
                            )
                            await asyncio.sleep(delay)
                            continue
                    
                    # Non-retryable error or max retries reached
                    break
                    
                except Exception as exc:
                    last_error = str(exc)
                    retry_count += 1
                    if retry_count < cls._max_retries:
                        delay = min(cls._base_delay * (2 ** retry_count), cls._max_delay)
                        logger.warning(
                            "Vision analysis exception retry %d/%d after %.1fs - %s",
                            retry_count, cls._max_retries, delay, exc
                        )
                        await asyncio.sleep(delay)
                        continue
                    break
            
            provider_used = "deepface"
            
            # If all retries failed, fall back to mock
            if retry_count >= cls._max_retries or not result.get("success"):
                if str(last_error or "").startswith("Vision libs") or not result.get("success"):
                    result = await cls._mock_analyser.analyze(b64_image)
                    provider_used = "mock"
                    degraded = True
                    logger.info("Vision analysis degraded to mock after %d retries", retry_count)

        result["provider"] = provider_used
        result["degraded"] = degraded
        result["retry_count"] = retry_count
        result["processing_ms"] = round((time.perf_counter() - started) * 1000.0, 1)
        return result

    @staticmethod
    def aggregate_vision_logs(logs: list) -> dict:
        if not logs:
            return {}

        confs = [float(l.confidence_score) for l in logs if l.confidence_score is not None]
        engs = [float(l.engagement_score) for l in logs if l.engagement_score is not None]
        strs = [float(l.stress_score) for l in logs if l.stress_score is not None]
        cheat_scores = [float(l.cheating_score) for l in logs]

        all_flags: list = []
        for l in logs:
            if l.cheating_flags:
                flags = l.cheating_flags if isinstance(l.cheating_flags, list) else l.cheating_flags.get("flags", [])
                all_flags.extend(flags)

        dominant_counts: dict = {}
        for l in logs:
            if l.dominant_emotion:
                dominant_counts[l.dominant_emotion] = dominant_counts.get(l.dominant_emotion, 0) + 1
        dominant_sorted = sorted(dominant_counts, key=dominant_counts.get, reverse=True)  # type: ignore[arg-type]

        def _avg(lst, default=65.0) -> float:
            return round(sum(lst) / len(lst), 1) if lst else default

        return {
            "avg_confidence": _avg(confs),
            "avg_engagement": _avg(engs),
            "avg_stress": _avg(strs, default=20.0),
            "dominant_emotions": dominant_sorted,
            "cheating_flags": list(set(all_flags)),
            "frames_analyzed": len(logs),
            "max_cheating_score": round(max(cheat_scores), 1) if cheat_scores else 0.0,
            "avg_cheating_score": _avg(cheat_scores, default=0.0),
        }


# Warmup
async def warmup_vision() -> None:
    loop = asyncio.get_running_loop()
    ready = await loop.run_in_executor(_executor, _load_deps)
    if ready:
        logger.info("✅ Vision warmup complete")
    else:
        logger.warning("⚠  Vision warmup partial — some deps missing")


# Module-level aliases for backward compat
vision_service = VisionService()
analyze_frame = VisionService.analyze_frame
aggregate_vision_logs = VisionService.aggregate_vision_logs
