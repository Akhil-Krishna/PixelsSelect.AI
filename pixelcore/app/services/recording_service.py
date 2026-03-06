"""
Recording metadata service — thin post-upload hook.
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class RecordingService:
    @staticmethod
    def process_metadata(recording_path: str, size_bytes: int) -> dict:
        path = Path(recording_path)
        logger.info(
            "Recording metadata processed path=%s size_mb=%.1f",
            recording_path,
            size_bytes / 1024 / 1024,
        )
        return {
            "path": str(path),
            "size_bytes": size_bytes,
            "exists": path.exists(),
            "suffix": path.suffix.lower(),
        }


recording_service = RecordingService()
process_recording_metadata = recording_service.process_metadata
