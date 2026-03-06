"""
Interview orchestrator — thin coordination layer.

Decides whether to call AIService directly (fast-path) or dispatch via Celery,
to keep API endpoints free of concurrency strategy details.
"""
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.task_runner import run_task_with_fallback
from app.models.interview import Interview, InterviewMessage
from app.services.ai_service import AIService
from app.tasks.ai_tasks import generate_ai_response_task, generate_final_evaluation_task


def _serialize_interview(iv: Interview) -> dict:
    return {
        "job_role": iv.job_role,
        "question_bank": iv.question_bank,
        "resume_text": iv.resume_text,
        "duration_minutes": iv.duration_minutes,
    }


def _serialize_messages(messages: List[InterviewMessage]) -> List[dict]:
    return [
        {"role": m.role, "content": m.content, "code_snippet": m.code_snippet}
        for m in messages
    ]


class InterviewOrchestrator:
    """Coordinates AI calls with optional Celery offloading."""

    @staticmethod
    async def start_interview(iv: Interview) -> Dict[str, Any]:
        if settings.AI_LOCAL_FASTPATH_ENABLED and not settings.CELERY_REALTIME_ENABLED:
            text, complete = await AIService.get_ai_response(
                interview=iv, messages=[], candidate_message="[START INTERVIEW]"
            )
            return {"text": text, "is_complete": complete}

        async def _fallback():
            text, complete = await AIService.get_ai_response(
                interview=iv, messages=[], candidate_message="[START INTERVIEW]"
            )
            return {"text": text, "is_complete": complete}

        return await run_task_with_fallback(
            generate_ai_response_task,
            payload={**_serialize_interview(iv), "messages": [], "candidate_message": "[START INTERVIEW]", "code_snippet": None},
            fallback_callable=_fallback,
            endpoint_name="/interview-session/start",
            realtime=True,
        )

    @staticmethod
    async def chat_turn(
        iv: Interview,
        messages: List[InterviewMessage],
        candidate_message: str,
        code_snippet: Optional[str],
    ) -> Dict[str, Any]:
        if settings.AI_LOCAL_FASTPATH_ENABLED and not settings.CELERY_REALTIME_ENABLED:
            text, complete = await AIService.get_ai_response(
                interview=iv,
                messages=messages,
                candidate_message=candidate_message,
                code_snippet=code_snippet,
            )
            return {"text": text, "is_complete": complete}

        async def _fallback():
            text, complete = await AIService.get_ai_response(
                interview=iv, messages=messages,
                candidate_message=candidate_message, code_snippet=code_snippet,
            )
            return {"text": text, "is_complete": complete}

        return await run_task_with_fallback(
            generate_ai_response_task,
            payload={
                **_serialize_interview(iv),
                "messages": _serialize_messages(messages),
                "candidate_message": candidate_message,
                "code_snippet": code_snippet,
            },
            fallback_callable=_fallback,
            endpoint_name="/interview-session/chat",
            realtime=True,
        )

    @staticmethod
    async def complete_evaluation(
        iv: Interview,
        messages: List[InterviewMessage],
        emotion_data: Optional[dict],
        cheating_score: Optional[float],
    ) -> Dict[str, Any]:
        if settings.AI_LOCAL_FASTPATH_ENABLED and not settings.CELERY_REALTIME_ENABLED:
            return await AIService.generate_final_evaluation(
                interview=iv, messages=messages,
                emotion_data=emotion_data, cheating_score=cheating_score,
            )

        async def _fallback():
            return await AIService.generate_final_evaluation(
                interview=iv, messages=messages,
                emotion_data=emotion_data, cheating_score=cheating_score,
            )

        return await run_task_with_fallback(
            generate_final_evaluation_task,
            payload={
                "job_role": iv.job_role,
                "resume_text": iv.resume_text,
                "messages": _serialize_messages(messages),
                "emotion_data": emotion_data,
                "cheating_score": cheating_score,
            },
            fallback_callable=_fallback,
            endpoint_name="/interview-session/complete",
            realtime=True,
        )


# Convenience module-level aliases (used by endpoints)
interview_orchestrator = InterviewOrchestrator()
start_interview_ai = InterviewOrchestrator.start_interview
chat_turn = InterviewOrchestrator.chat_turn
complete_interview_evaluation = InterviewOrchestrator.complete_evaluation
