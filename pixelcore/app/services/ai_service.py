"""
AI service — LLM-backed interview conversation and evaluation.

Supports three providers via a common OpenAI-compatible HTTP interface:
  groq   — Groq cloud API (fast, low-latency)
  openai — OpenAI API or any local OpenAI-compatible server (OPENAI_BASE_URL)
  ollama — Ollama local server (/api/chat endpoint)
  mock   — Deterministic offline responses for testing

Design:
  LLMProvider  — abstract base class
  GroqProvider, OpenAIProvider, OllamaProvider, MockProvider — concrete impls
  LLMDispatcher — selects provider at runtime from settings
  AIService     — builds prompts and orchestrates conversation/evaluation
"""
import json
import logging
from abc import ABC, abstractmethod
from types import SimpleNamespace
from typing import List, Optional, Tuple

import httpx

from app.core.config import settings
from app.models.interview import Interview, InterviewMessage

logger = logging.getLogger(__name__)

# ── System prompt ─────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = """\
You are a professional {job_role} technical interviewer conducting a structured interview.

STRICT BEHAVIOURAL RULES — follow these without exception

WHAT YOU MUST NEVER DO:
- NEVER ask more than ONE question at a time.
- NEVER teach, correct, or elaborate on the candidate's answer.
- NEVER dump multiple question-bank questions in one response.
- NEVER explain concepts unless the candidate explicitly asked you to clarify.

WHAT YOU MUST ALWAYS DO:
- Start the interview by asking the candidate to introduce.
- Keep a natural interviewer tone: brief acknowledgement (3-10 words), then either one follow-up OR one next question.
- If the answer was strong: give short acknowledgement and move forward.
- If the answer was incomplete: ask ONE specific probing follow-up before moving on.
- Keep every response under 3 short sentences unless evaluating submitted code.
- Use only a curated subset of the question bank (about 6-8 total questions for the whole interview), not every question.
- Track progression; after reasonable coverage for {duration_minutes} min worth of exchanges, wrap up.

FORMAT RULES:
- Coding question: start the ENTIRE message with: CODING_QUESTION:
- End of interview: start the ENTIRE message with: INTERVIEW_COMPLETE
- All other responses: plain natural language, no bullet points, no headers.

INTERVIEW FLOW:
  1. Brief introduction (1-2 exchanges)
  2. Core technical questions — 3 to 4 selected from question bank if relevant
  3. 1 coding problem (or 2 only if time allows) with CODING_QUESTION prefix
  4. 1 practical/system design style question
  5. 1-2 resume/project questions based on candidate background
  6. Wrap-up — TWO steps:

     STEP 6a (pre-close — do NOT use INTERVIEW_COMPLETE yet):
     Ask the candidate one warm closing question, e.g.:
       "That covers everything on my end. Do you have any questions about the role or next steps?"
     Wait for their reply and give a brief acknowledgement (1 sentence max).

     STEP 6b (conclusion — only after their reply to 6a):
     Start EXACTLY with: INTERVIEW_COMPLETE
     Then write a warm, personalised 3-5 sentence conclusion that:
       - Thanks the candidate sincerely by name (if known)
       - Mentions the specific job role
       - Highlights 1-2 positive things observed
       - Explains what happens next
       - Ends with a warm farewell

═══════════════════════════════════════════════════════
CONTEXT
═══════════════════════════════════════════════════════
Job Role         : {job_role}
Question number  : {q_num}
Interview length : {duration_minutes} min

{question_bank_context}

{resume_context}\
"""

_EVAL_PROMPT = """\
You are an expert technical interview evaluator. Score this interview transcript.

Position: {job_role}
{resume_context}
Transcript:
{transcript}

Respond with ONLY a valid JSON object — no markdown, no backticks, no explanation:
{{
  "answer_score": <integer 0-100>,
  "code_score": <integer 0-100, or null if no coding was done>,
  "overall_score": <integer 0-100>,
  "passed": <true if overall_score >= 60 else false>,
  "strengths": ["strength 1", "strength 2", "strength 3"],
  "weaknesses": ["weakness 1", "weakness 2"],
  "ai_feedback": "2-3 sentences summarizing overall performance."
}}\
"""


# ── Provider abstractions ──────────────────────────────────────────────────────

class LLMProvider(ABC):
    """Abstract base for all LLM backends."""

    @abstractmethod
    async def chat(self, system: str, messages: List[dict]) -> Optional[str]:
        ...


class GroqProvider(LLMProvider):
    """Groq cloud API — OpenAI-compatible."""

    async def chat(self, system: str, messages: List[dict]) -> Optional[str]:
        if not settings.GROQ_API_KEY:
            return None
        payload = {
            "model": settings.GROQ_MODEL,
            "messages": [{"role": "system", "content": system}] + messages,
            "temperature": 0.7,
            "max_tokens": 400,
            "stream": False,
        }
        try:
            async with httpx.AsyncClient(timeout=settings.GROQ_TIMEOUT) as client:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            logger.error("Groq LLM error: %s", exc)
            return None


class OpenAIProvider(LLMProvider):
    """
    OpenAI-compatible provider.
    Set OPENAI_BASE_URL to point to a local model server (llama.cpp, vLLM, LM Studio, etc.)
    """

    async def chat(self, system: str, messages: List[dict]) -> Optional[str]:
        if not settings.OPENAI_API_KEY and settings.OPENAI_BASE_URL == "https://api.openai.com/v1":
            logger.warning("OPENAI_API_KEY is empty — skipping OpenAI provider")
            return None
        payload = {
            "model": settings.OPENAI_MODEL,
            "messages": [{"role": "system", "content": system}] + messages,
            "temperature": 0.7,
            "max_tokens": 400,
        }
        headers: dict = {}
        if settings.OPENAI_API_KEY:
            headers["Authorization"] = f"Bearer {settings.OPENAI_API_KEY}"
        try:
            async with httpx.AsyncClient(timeout=settings.OPENAI_TIMEOUT) as client:
                resp = await client.post(
                    f"{settings.OPENAI_BASE_URL.rstrip('/')}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            logger.error("OpenAI provider error: %s", exc)
            return None


class OllamaProvider(LLMProvider):
    """Ollama local server (/api/chat)."""

    async def chat(self, system: str, messages: List[dict]) -> Optional[str]:
        try:
            async with httpx.AsyncClient(timeout=settings.OLLAMA_TIMEOUT) as client:
                resp = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/api/chat",
                    json={
                        "model": settings.OLLAMA_MODEL,
                        "stream": False,
                        "messages": [{"role": "system", "content": system}] + messages,
                        "options": {"temperature": 0.7, "num_predict": 400},
                    },
                )
                resp.raise_for_status()
                return resp.json()["message"]["content"].strip()
        except Exception as exc:
            logger.warning("Ollama error: %s", exc)
            return None


class MockProvider(LLMProvider):
    """Deterministic offline provider — useful for unit tests."""

    async def chat(self, system: str, messages: List[dict]) -> Optional[str]:
        return None  # let caller fall through to mock_response


# ── Dispatcher ────────────────────────────────────────────────────────────────

class LLMDispatcher:
    """Selects the correct provider based on settings.LLM_PROVIDER."""

    _providers: dict[str, LLMProvider] = {
        "groq": GroqProvider(),
        "openai": OpenAIProvider(),
        "ollama": OllamaProvider(),
        "mock": MockProvider(),
    }

    @classmethod
    async def chat(cls, system: str, messages: List[dict]) -> Optional[str]:
        provider = cls._providers.get(settings.LLM_PROVIDER.lower().strip())
        if provider is None:
            logger.warning("Unknown LLM_PROVIDER=%s — using mock", settings.LLM_PROVIDER)
            return None
        return await provider.chat(system, messages)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_history(messages: List[InterviewMessage]) -> List[dict]:
    result = []
    for m in messages:
        content = m.content
        if m.code_snippet:
            content += f"\n\n[CODE SUBMITTED]\n```\n{m.code_snippet}\n```"
        result.append({
            "role": "user" if m.role in ("candidate", "interviewer") else "assistant",
            "content": content,
        })
    return result


def _parse_json_response(text: str) -> Optional[dict]:
    try:
        clean = text.strip()
        if clean.startswith("```"):
            lines = clean.split("\n")
            clean = "\n".join(lines[1:]).rstrip("`").strip()
        return json.loads(clean)
    except Exception as exc:
        logger.error("JSON parse failed: %s | raw: %.300s", exc, text)
        return None


def _mock_interview_response(q_num: int, job_role: str) -> str:
    questions = [
        f"[MOCK] Welcome! I'll be interviewing you for the {job_role} role. Could you briefly introduce yourself?",
        "Walk me through a technically challenging problem you solved recently.",
        "CODING_QUESTION: Write a function that finds two numbers in an array that add up to a target sum. Aim for O(n) complexity.",
        "Explain the difference between synchronous and asynchronous execution with a real-world example.",
        "How do you debug a hard-to-reproduce production issue?",
        "CODING_QUESTION: Design and implement a simple LRU Cache with get() and put() methods.",
        "Describe the components you'd include when designing a URL shortener at scale.",
        f"That covers everything for today's {job_role} interview. Do you have any questions about the role or next steps?",
        f"INTERVIEW_COMPLETE\nThank you so much for your time today.\nYou demonstrated strong problem-solving skills throughout our conversation for the {job_role} role.\nOur team will review your performance and be in touch soon. Take care!",
    ]
    return questions[min(max(q_num - 1, 0), len(questions) - 1)]


def _mock_evaluation() -> dict:
    return {
        "answer_score": 5,
        "code_score": 0,
        "overall_score": 10,
        "passed": False,
        "strengths": ["—"],
        "weaknesses": ["—"],
        "ai_feedback": "Unable to generate evaluation at this time.",
    }


# ── Public AI service class ────────────────────────────────────────────────────

class AIService:
    """
    Orchestrates AI interview conversation and post-interview evaluation.
    Stateless — all context is passed in as arguments.
    """

    @staticmethod
    async def get_ai_response(
        interview: Interview,
        messages: List[InterviewMessage],
        candidate_message: str,
        code_snippet: Optional[str] = None,
    ) -> Tuple[str, bool]:
        """
        Generate the next AI interviewer message.

        Returns:
            (text, is_complete) — is_complete is True when INTERVIEW_COMPLETE prefix found.
        """
        q_num = sum(1 for m in messages if m.role == "ai") + 1

        # Build question bank context
        qb_context = ""
        if interview.question_bank:
            qs = interview.question_bank
            if isinstance(qs, list) and qs:
                lines = []
                for i, q in enumerate(qs[:15], 1):
                    if isinstance(q, dict):
                        lines.append(
                            f"  {i}. [{q.get('difficulty','med').upper()}] {q.get('question','')}"
                        )
                    else:
                        lines.append(f"  {i}. {q}")
                qb_context = (
                    "QUESTION BANK (select the most relevant subset; do NOT ask all questions):\n"
                    + "\n".join(lines)
                )

        resume_context = ""
        if interview.resume_text:
            resume_context = f"CANDIDATE RESUME:\n{interview.resume_text[:3000]}"

        system = _SYSTEM_PROMPT.format(
            job_role=interview.job_role,
            q_num=q_num,
            duration_minutes=interview.duration_minutes,
            question_bank_context=qb_context,
            resume_context=resume_context,
        )

        history = _build_history(messages)
        user_content = candidate_message
        if code_snippet:
            user_content += f"\n\n[CODE SUBMITTED]\n```\n{code_snippet}\n```"
        history.append({"role": "user", "content": user_content})

        text = await LLMDispatcher.chat(system, history)
        if text is None:
            logger.warning("LLM provider unavailable — using mock response")
            text = _mock_interview_response(q_num, interview.job_role)

        return text, "INTERVIEW_COMPLETE" in text

    @staticmethod
    async def generate_final_evaluation(
        interview: Interview,
        messages: List[InterviewMessage],
        emotion_data: Optional[dict] = None,
        cheating_score: Optional[float] = None,
    ) -> dict:
        """
        Generate weighted evaluation scores after interview completion.
        Returns a dict compatible with EvaluationResult schema.
        """
        transcript = "\n".join(
            f"{'Interviewer' if m.role == 'ai' else ('Human Interviewer' if m.role == 'interviewer' else 'Candidate')}: {m.content}"
            + (f"\n[Code: {m.code_snippet[:300]}...]" if m.code_snippet else "")
            for m in messages
        )

        resume_context = ""
        if interview.resume_text:
            resume_context = f"Candidate Resume Summary:\n{interview.resume_text[:1500]}\n"

        system = "You are an expert technical interview evaluator. Output only valid JSON, no markdown."
        prompt = _EVAL_PROMPT.format(
            job_role=interview.job_role,
            transcript=transcript,
            resume_context=resume_context,
        )

        text = await LLMDispatcher.chat(system, [{"role": "user", "content": prompt}])
        result = _parse_json_response(text) if text else None
        if result is None:
            result = _mock_evaluation()

        # Enrich with emotion & integrity scores
        emotion_score: Optional[float] = None
        if emotion_data:
            conf = float(emotion_data.get("avg_confidence", 50.0))
            eng = float(emotion_data.get("avg_engagement", 50.0))
            emotion_score = round((conf + eng) / 2.0, 1)
        result["emotion_score"] = emotion_score

        integrity_score: Optional[float] = None
        if cheating_score is not None:
            integrity_score = round(max(0.0, 100.0 - float(cheating_score)), 1)
        result["integrity_score"] = integrity_score
        result["cheating_score"] = float(cheating_score) if cheating_score is not None else None

        # Weighted overall score
        answer = float(result.get("answer_score", 0))
        code = result.get("code_score")
        weights: dict

        if code is not None and emotion_score is not None and integrity_score is not None:
            overall = answer * 0.50 + float(code) * 0.25 + emotion_score * 0.15 + integrity_score * 0.10
            weights = {"answer": 0.50, "code": 0.25, "emotion": 0.15, "integrity": 0.10}
        elif code is not None and emotion_score is not None:
            overall = answer * 0.55 + float(code) * 0.30 + emotion_score * 0.15
            weights = {"answer": 0.55, "code": 0.30, "emotion": 0.15}
        elif code is not None:
            overall = answer * 0.60 + float(code) * 0.40
            weights = {"answer": 0.60, "code": 0.40}
        elif emotion_score is not None:
            overall = answer * 0.75 + emotion_score * 0.25
            weights = {"answer": 0.75, "emotion": 0.25}
        else:
            overall = answer
            weights = {"answer": 1.0}

        result["overall_score"] = round(float(overall), 1)
        result["passed"] = result["overall_score"] >= 60.0
        result["weights_used"] = weights

        for key in ("answer_score", "code_score", "overall_score", "emotion_score", "integrity_score", "cheating_score"):
            if result.get(key) is not None:
                result[key] = float(result[key])

        return result


# ── Module-level convenience functions (for payload-based task workers) ────────

async def get_ai_response_from_payload(payload: dict) -> dict:
    interview = SimpleNamespace(
        job_role=payload.get("job_role", ""),
        question_bank=payload.get("question_bank"),
        resume_text=payload.get("resume_text"),
        duration_minutes=payload.get("duration_minutes", 60),
    )
    messages = [
        SimpleNamespace(
            role=msg.get("role", ""),
            content=msg.get("content", ""),
            code_snippet=msg.get("code_snippet"),
        )
        for msg in payload.get("messages", [])
    ]
    text, is_complete = await AIService.get_ai_response(
        interview=interview,  # type: ignore[arg-type]
        messages=messages,  # type: ignore[arg-type]
        candidate_message=payload.get("candidate_message", ""),
        code_snippet=payload.get("code_snippet"),
    )
    return {"text": text, "is_complete": is_complete}


async def generate_final_evaluation_from_payload(payload: dict) -> dict:
    interview = SimpleNamespace(
        job_role=payload.get("job_role", ""),
        resume_text=payload.get("resume_text"),
    )
    messages = [
        SimpleNamespace(
            role=msg.get("role", ""),
            content=msg.get("content", ""),
            code_snippet=msg.get("code_snippet"),
        )
        for msg in payload.get("messages", [])
    ]
    return await AIService.generate_final_evaluation(
        interview=interview,  # type: ignore[arg-type]
        messages=messages,  # type: ignore[arg-type]
        emotion_data=payload.get("emotion_data"),
        cheating_score=payload.get("cheating_score"),
    )


# Backwards-compatible module-level aliases
ai_service = AIService()
get_ai_response = AIService.get_ai_response
generate_final_evaluation = AIService.generate_final_evaluation
