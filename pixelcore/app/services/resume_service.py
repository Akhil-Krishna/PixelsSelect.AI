"""
Resume text extraction service.
Supports: PDF (via pypdf), plain text. Returns empty string for unsupported types.
"""
import io
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ResumeService:
    """Extract readable text from resume file bytes."""

    @staticmethod
    def extract_text(content: bytes, filename: str = "resume.pdf") -> str:
        ext = Path(filename).suffix.lower()
        if ext == ".txt":
            return content.decode("utf-8", errors="replace")
        if ext not in (".pdf",):
            logger.warning("Unsupported resume ext: %s", ext)
            return ""

        try:
            from pypdf import PdfReader
        except ImportError:
            return "[PDF extraction requires: pip install pypdf]"

        try:
            reader = PdfReader(io.BytesIO(content))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            logger.error("PDF extraction failed: %s", exc)
            return "[Could not extract PDF text]"


resume_service = ResumeService()
extract_resume_text = resume_service.extract_text
