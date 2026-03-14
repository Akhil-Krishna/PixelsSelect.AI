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
You are a senior {job_role} interviewer at a real tech company. You are conducting \
a live technical interview over chat. Your persona is friendly, curious, and professional — \
like a real human who genuinely wants to understand the candidate's abilities.
-Never provide answers back to candidate
═══════════════════════════════════════════════════════
PERSONALITY & TONE
═══════════════════════════════════════════════════════
- Talk like a REAL person. Use natural language, not corporate-speak.
- Give QUICK, GENUINE feedback after each answer — 1 sentence max. Examples:
  Good answers: "Nice, that makes sense." / "Ya, that's solid." / "Cool, I like that approach."
  / "Right, got it." / "Alright, sounds good." / "Interesting take." / "Okay, fair point."
  / "Gotcha." / "Sure, that works." / "Nice one."
  Weak/wrong answers: "Hmm, not quite." / "That's one way, but what about..." / 
  "Not exactly — think about the edge case where..." / "Close, but consider..." /
  "That's not quite right. What if we..." / "Not that one, try thinking about..."
- NEVER repeat the same feedback twice in a row.
- NEVER say "Great question!" or "That's a great answer!" — those sound robotic.
- If candidate gives a good answer, briefly acknowledge AND ask a follow-up question to dig deeper.
- If candidate gives a weak/wrong answer, DON'T correct them — just probe gently or move on.
- Keep responses SHORT — 1 to 3 sentences max. Think of how a real interviewer chats.

═══════════════════════════════════════════════════════
ABSOLUTE RULES
═══════════════════════════════════════════════════════
1. Ask ONE question at a time. Never batch multiple questions.
2. NEVER teach, lecture, or explain concepts. You are evaluating, not tutoring.
3. NEVER give away the answer to a question — not even hints that reveal the solution.
4. NEVER list bullet points or use markdown headers. Talk in natural sentences.
5. NEVER reveal that you're an AI. Behave as if you're a human interviewer.
6. If the candidate asks you to explain something, briefly clarify the question itself, \
but do NOT give away the answer or teach the concept.

═══════════════════════════════════════════════════════
INTERVIEW FLOW
═══════════════════════════════════════════════════════
- KEEP THE INTERVIEW GOING until the prescribed {duration_minutes} minutes are nearly up, \
as long as the candidate is responding and answering questions.
- Only wrap up early if: (a) time is almost over, OR (b) candidate is not responding at all.
- When candidate does well, ask follow-up questions to test depth of knowledge.

═══════════════════════════════════════════════════════
INTERVIEW STRUCTURE (adapt timing to {duration_minutes} minutes)
═══════════════════════════════════════════════════════
Phase 1 — WARM-UP (1-2 exchanges)
  Start casually: "Hey, thanks for joining. Before we get into the technical stuff, \
could you tell me a bit about yourself?" Follow up on something they mentioned.

Phase 2 — CS FUNDAMENTALS (30%)
  Ask about core computer science and practical engineering topics, naturally woven in:
  - Data structures: "If you had to pick between a hash map and a BST for this use case, \
which would you go with and why?"
  - Algorithms / complexity: "Walk me through how you'd approach sorting X — and what's \
the time complexity you'd aim for?"
  - OS / Networking / Databases: "Can you explain what happens behind the scenes when \
you type a URL in a browser?" or "Tell me about database indexing — when would you NOT \
add an index?"
  - Version control: "How do you handle merge conflicts on a team? What's your Git workflow \
like?" or "What's the difference between rebase and merge, and when do you prefer each?"

Phase 3 — ROLE-SPECIFIC DEEP DIVE (20% ,from question bank if provided, extra 40% questions based on role)
  Pick the most relevant questions from the question bank. Adapt difficulty to the \
candidate's level based on their earlier answers.
  Transition naturally: "Alright, let's dive a bit deeper into {job_role} territory."

Phase 4 — CODING (1 problem, 2 only if time allows)
  Start the ENTIRE message with: [CODING_QUESTION]
  Give a clear, self-contained problem. Keep it practical and role-relevant when possible.
  After they submit code, briefly acknowledge it and ask about trade-offs or edge cases.

Phase 5 — PRACTICAL SCENARIO (10%)
  Ask a system design or real-world problem-solving question relevant to the role.
  "Say you're designing a notification system that needs to handle 10K messages per second — \
how would you architect that?"

Phase 6 — WRAP-UP (2 steps)
  Only wrap up if time duration is almost over or candidate is not at all answering properly
  STEP A (do NOT use INTERVIEW_COMPLETE):
    Wind down naturally: "Alright, that wraps up the technical portion on my end. \
Is there anything you'd like to ask me — about the role, the team, or anything else?"
    Wait for their reply and give a brief, warm acknowledgement.

  STEP B (ONLY after they reply to step A):
    Start the ENTIRE message with: INTERVIEW_COMPLETE
    Then write a warm, personalised 3-5 sentence conclusion:
    - Thank them sincerely
    - Mention the specific role
    - Highlight 1-2 positive things you noticed
    - Explain next steps
    - End with a genuine farewell

═══════════════════════════════════════════════════════
FORMAT RULES
═══════════════════════════════════════════════════════
- Coding question → start message with: [CODING_QUESTION]
- End of interview → start message with: INTERVIEW_COMPLETE
- Everything else → plain conversational text, no formatting

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
        "[CODING_QUESTION] Write a function that finds two numbers in an array that add up to a target sum. Aim for O(n) complexity.",
        "Explain the difference between synchronous and asynchronous execution with a real-world example.",
        "How do you debug a hard-to-reproduce production issue?",
        "[CODING_QUESTION] Design and implement a simple LRU Cache with get() and put() methods.",
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


# ── Transcript truncation helpers ─────────────────────────────────────────────

# Common AI acknowledgment phrases to strip from the START of AI messages
_AI_ACK_PATTERNS = [
    "nice, that makes sense.",
    "ya, that's solid.",
    "cool, i like that approach.",
    "right, got it.",
    "alright, sounds good.",
    "interesting take.",
    "okay, fair point.",
    "gotcha.",
    "sure, that works.",
    "nice one.",
    "good point.",
    "makes sense.",
    "got it.",
    "alright.",
    "sure.",
    "okay.",
    "thanks for sharing.",
    "appreciate that.",
    "interesting.",
    "i see.",
    "right.",
]

# Maximum settings for transcript
_MAX_MESSAGES_TO_KEEP = 12  # Keep last 12 message pairs (24 messages total)
_MAX_TRANSCRIPT_LENGTH = 4000  # Max characters in final transcript
_SKIP_INITIAL_MESSAGES = 2  # Skip first 2 messages from each role


def _strip_ai_acknowledgment(text: str) -> str:
    """Strip initial acknowledgment phrases from AI response to keep only substantive content."""
    text_lower = text.lower().strip()
    
    for pattern in _AI_ACK_PATTERNS:
        if text_lower.startswith(pattern):
            # Find where the actual content starts (after the acknowledgment + possible follow-up)
            # Look for the next sentence or question
            remaining = text[len(pattern):].strip()
            # Skip common transition phrases
            transition_prefixes = [" ", " — ", ", ", " so ", " then ", " but ", " now "]
            for prefix in transition_prefixes:
                if remaining.lower().startswith(prefix.strip()):
                    remaining = remaining[len(prefix):].strip()
                    break
            if remaining:
                return remaining
            break
    
    return text


def _truncate_candidate_response(text: str, max_length: int = 500) -> str:
    """Truncate candidate response to essential content."""
    if len(text) <= max_length:
        return text
    # Find a sentence boundary near the max length
    truncated = text[:max_length]
    last_period = truncated.rfind('. ')
    last_newline = truncated.rfind('\n')
    cut = max(last_period, last_newline)
    if cut > max_length * 0.5:  # Only cut at sentence if we're past 50% of max
        return text[:cut + 1].strip()
    return truncated.strip() + "..."


def _build_optimized_transcript(messages: List[InterviewMessage]) -> str:
    """
    Build an optimized transcript for evaluation:
    - Skip first 2 messages from each role (initial greetings)
    - Strip initial acknowledgments from AI messages
    - Truncate long candidate responses
    - Keep last N message pairs
    - Limit total length
    """
    # Filter and process messages
    processed = []
    
    # Count messages by role to track initial messages
    ai_count = 0
    candidate_count = 0
    
    for m in messages:
        content = m.content
        if not content:
            continue
            
        if m.role == "ai":
            ai_count += 1
            # Skip first 2 AI messages (initial greetings)
            if ai_count <= _SKIP_INITIAL_MESSAGES:
                continue
            # Strip initial acknowledgments to keep substantive content
            content = _strip_ai_acknowledgment(content)
            
        elif m.role == "candidate":
            candidate_count += 1
            # Skip first 2 candidate messages (initial introductions)
            if candidate_count <= _SKIP_INITIAL_MESSAGES:
                continue
            # Truncate long responses
            content = _truncate_candidate_response(content)
            
        elif m.role == "interviewer":
            # Human interviewer messages - keep as is but truncate if too long
            content = _truncate_candidate_response(content, max_length=300)
        
        if content:
            processed.append((m.role, content, m.code_snippet))
    
    # Keep only the last N message pairs
    if len(processed) > _MAX_MESSAGES_TO_KEEP * 2:
        processed = processed[-( _MAX_MESSAGES_TO_KEEP * 2):]
    
    # Build transcript
    lines = []
    for role, content, code_snippet in processed:
        role_label = "Interviewer" if role == "ai" else ("Human Interviewer" if role == "interviewer" else "Candidate")
        lines.append(f"{role_label}: {content}")
        if code_snippet:
            # Truncate code snippet for transcript
            code_preview = code_snippet[:200] + "..." if len(code_snippet) > 200 else code_snippet
            lines.append(f"[Code: {code_preview}]")
    
    transcript = "\n".join(lines)
    
    # Final length check - truncate if still too long
    if len(transcript) > _MAX_TRANSCRIPT_LENGTH:
        transcript = transcript[:_MAX_TRANSCRIPT_LENGTH].rsplit("\n", 1)[0] + "\n[... transcript truncated ...]"
    
    logger.info(
        "transcript_optimized",
        extra={
            "event": "transcript_optimization",
            "original_messages": len(messages),
            "processed_messages": len(processed),
            "final_length": len(transcript),
        },
    )
    
    return transcript


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
        # Use optimized transcript builder to reduce length
        transcript = _build_optimized_transcript(messages)
        
        logger.info(
            "evaluation_started",
            extra={
                "event": "evaluation_start",
                "job_role": interview.job_role,
                "message_count": len(messages),
                "transcript_length": len(transcript),
                "has_resume": bool(interview.resume_text),
            },
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

        # Call LLM with detailed logging
        try:
            text = await LLMDispatcher.chat(system, [{"role": "user", "content": prompt}])
            
            if text is None:
                logger.error(
                    "evaluation_llm_returned_none",
                    extra={
                        "event": "evaluation_llm_failure",
                        "job_role": interview.job_role,
                        "reason": "LLM provider returned None",
                    },
                )
                result = _mock_evaluation()
            else:
                logger.info(
                    "evaluation_llm_response_received",
                    extra={
                        "event": "evaluation_llm_response",
                        "response_length": len(text),
                        "response_preview": text[:200],
                    },
                )
                result = _parse_json_response(text)
                if result is None:
                    logger.error(
                        "evaluation_json_parse_failed",
                        extra={
                            "event": "evaluation_parse_failure",
                            "raw_response": text[:500],
                        },
                    )
                    result = _mock_evaluation()
        except Exception as exc:
            logger.error(
                "evaluation_exception",
                extra={
                    "event": "evaluation_exception",
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
            )
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
