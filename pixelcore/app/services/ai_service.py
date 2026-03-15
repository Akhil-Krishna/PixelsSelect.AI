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

_SYSTEM_PROMPT = """
You are a senior {job_role} interviewer at a real tech company conducting a live technical interview over chat.

Speak naturally like a real human interviewer: friendly, curious, and professional.

Never provide answers to the candidate.

════════ INTERVIEW STYLE ════════
• Keep responses short (1–3 sentences).
• Ask ONE question at a time.
• Give brief natural feedback before the next question.

Good feedback examples:
"Nice, that makes sense."
"Yeah, that's solid."
"Alright, got it."
"Interesting approach."

Weak answer responses:
"Hmm, not quite."
"Close, but think about edge cases."
"That's one way — what about..."

Rules:
• Never repeat the same feedback twice.
• Never say “Great question” or “Great answer”.
• Never teach or explain concepts.
• If an answer is wrong, probe or move on without revealing the solution.

════════ INTERVIEW FLOW ════════

Continue the interview until {duration_minutes} minutes are nearly over unless the candidate stops responding.

Phase 1 — Warm-up (1–2 exchanges)  
Start casually:  
“Hey, thanks for joining. Before we dive in, tell me a bit about yourself.”

Phase 2 — CS fundamentals (~30%)  
Ask practical questions about:
data structures, algorithms, databases, networking, OS, Git.

Phase 3 — Role deep dive (~40%)  
Use the question bank if provided. Focus on {job_role} skills.

Phase 4 — Coding (1 problem)  
Start the message with:

[CODING_QUESTION]

Also include a time limit:

[TIME:Xmin]

Time rules:
5-15 min interview → 1-2 min  
20-30 min interview → 2-4 min  
45-60 min interview → 3-5 min

Give one clear coding problem. After submission, briefly ask about trade-offs or edge cases.

Phase 5 — Practical scenario (~10%)  
Ask one real-world engineering question relevant to the role.

Phase 6 — Wrap-up  
When time is almost over:

Step A  
Ask if the candidate has questions.

Step B (only after they reply)  
Start the message with:

INTERVIEW_COMPLETE

Then write a warm 3–5 sentence closing:
• thank them
• mention the role
• highlight 1–2 positives
• explain next steps
• say goodbye

════════ FORMAT RULES ════════

Coding question → start with:
[CODING_QUESTION]

End of interview → start with:
INTERVIEW_COMPLETE

Everything else → normal conversational text.

════════ CONTEXT ════════
Role: {job_role}  
Interview length: {duration_minutes} minutes

{question_bank_context}

{resume_context}
"""

# Simplified evaluation prompt - LLM only provides essential scores and feedback
# All detailed fields are filled in by code using existing data
_EVAL_PROMPT = """\
You are an expert technical interview evaluator. Evaluate this interview transcript and provide scores and feedback.

Position: {job_role}
Interview Duration: {duration_minutes} minutes
Candidate Name/ID: {candidate_identifier}
Tab Switch Count: {tab_switch_count}
{resume_context}

Transcript:
{transcript}

Scoring guidelines:
- answer_score: Rate the quality of the candidate's answers to non-coding questions (0-100).
- code_score: If the candidate submitted code, evaluate correctness, complexity, edge cases, and style (0-100). If no coding was done, set to null.
- Performance scores: Rate each category 1-10 based on what the transcript actually shows.
- Keep string values concise (under 40 words each).

Respond with ONLY a valid JSON object — no markdown, no backticks, no explanation:

{{
  "answer_score": <integer 0-100>,
  "code_score": <integer 0-100 or null if no coding was done>,
  "performance": {{
    "technical_knowledge": <integer 1-10>,
    "problem_solving": <integer 1-10>,
    "coding_ability": <integer 1-10 or 5 if no coding>,
    "communication_clarity": <integer 1-10>,
    "practical_engineering": <integer 1-10>
  }},
  "strengths": ["strength 1", "strength 2", "strength 3"],
  "weaknesses": ["weakness 1", "weakness 2"],
  "ai_feedback": "2-3 sentences summarizing overall performance",
  "final_hiring_recommendation": "Strong Hire|Hire|Borderline|No Hire",
  "recommendation_justification": "2-3 sentence justification"
}}
"""


# ── Provider abstractions ──────────────────────────────────────────────────────

class LLMProvider(ABC):
    """Abstract base for all LLM backends."""

    @abstractmethod
    async def chat(self, system: str, messages: List[dict], max_tokens: int = 400) -> Optional[str]:
        ...


class GroqProvider(LLMProvider):
    """Groq cloud API — OpenAI-compatible."""

    async def chat(self, system: str, messages: List[dict], max_tokens: int = 400) -> Optional[str]:
        if not settings.GROQ_API_KEY:
            return None
        payload = {
            "model": settings.GROQ_MODEL,
            "messages": [{"role": "system", "content": system}] + messages,
            "temperature": 0.7,
            "max_tokens": max_tokens,
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

    async def chat(self, system: str, messages: List[dict], max_tokens: int = 400) -> Optional[str]:
        if not settings.OPENAI_API_KEY and settings.OPENAI_BASE_URL == "https://api.openai.com/v1":
            logger.warning("OPENAI_API_KEY is empty — skipping OpenAI provider")
            return None
        payload = {
            "model": settings.OPENAI_MODEL,
            "messages": [{"role": "system", "content": system}] + messages,
            "temperature": 0.7,
            "max_tokens": max_tokens,
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

    async def chat(self, system: str, messages: List[dict], max_tokens: int = 400) -> Optional[str]:
        try:
            async with httpx.AsyncClient(timeout=settings.OLLAMA_TIMEOUT) as client:
                resp = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/api/chat",
                    json={
                        "model": settings.OLLAMA_MODEL,
                        "stream": False,
                        "messages": [{"role": "system", "content": system}] + messages,
                        "options": {"temperature": 0.7, "num_predict": max_tokens},
                    },
                )
                resp.raise_for_status()
                return resp.json()["message"]["content"].strip()
        except Exception as exc:
            logger.warning("Ollama error: %s", exc)
            return None


class MockProvider(LLMProvider):
    """Deterministic offline provider — useful for unit tests."""

    async def chat(self, system: str, messages: List[dict], max_tokens: int = 400) -> Optional[str]:
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
    async def chat(cls, system: str, messages: List[dict], max_tokens: int = 400) -> Optional[str]:
        provider = cls._providers.get(settings.LLM_PROVIDER.lower().strip())
        if provider is None:
            logger.warning("Unknown LLM_PROVIDER=%s — using mock", settings.LLM_PROVIDER)
            return None
        return await provider.chat(system, messages, max_tokens=max_tokens)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_history(messages: List[InterviewMessage]) -> List[dict]:
    result = []
    for m in messages:
        content = m.content
        if m.code_snippet:
            content += f"\n\n[CODE SUBMITTED]\n```\n{m.code_snippet}\n```"
        if m.role == "interviewer":
            # Human interviewer messages: use system role so the LLM
            # can distinguish them from candidate responses.
            result.append({"role": "system", "content": f"[Human Interviewer]: {content}"})
        elif m.role == "candidate":
            result.append({"role": "user", "content": content})
        else:  # ai
            result.append({"role": "assistant", "content": content})
    return result


def _parse_json_response(text: str) -> Optional[dict]:
    try:
        clean = text.strip()
        if clean.startswith("```"):
            lines = clean.split("\n")
            clean = "\n".join(lines[1:]).rstrip("`").strip()
        return json.loads(clean)
    except json.JSONDecodeError:
        # Attempt to repair truncated JSON
        repaired = _repair_truncated_json(clean)
        if repaired:
            try:
                return json.loads(repaired)
            except Exception:
                pass
        logger.error("JSON parse failed | raw: %.500s", text)
        return None
    except Exception as exc:
        logger.error("JSON parse error: %s | raw: %.300s", exc, text)
        return None


def _repair_truncated_json(text: str) -> Optional[str]:
    """Try to fix common truncation issues in LLM JSON output."""
    if not text or not text.strip().startswith('{'):
        return None
    s = text.rstrip()
    # If it already ends with }, it's probably complete
    if s.endswith('}'):
        return None
    # Close unclosed string
    quote_count = s.count('"') - s.count('\\"')
    if quote_count % 2 != 0:
        s += '"'
    # Close unclosed arrays/objects
    open_brackets = s.count('[') - s.count(']')
    open_braces = s.count('{') - s.count('}')
    s += ']' * max(0, open_brackets)
    s += '}' * max(0, open_braces)
    return s


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
    """Return a mock evaluation with all fields for backward compatibility."""
    return {
        "candidate_overview": {
            "candidate_name": "Unknown",
            "job_role": "Unknown",
            "interview_duration_minutes": 60,
            "overall_result": "Fail"
        },
        "confidence_score": {
            "score": 0,
            "factors": ["quality of answers", "consistency", "coding performance", "technical depth"]
        },
        "performance_breakdown": {
            "technical_knowledge": {"score": 0, "explanation": "Unable to evaluate"},
            "problem_solving": {"score": 0, "explanation": "Unable to evaluate"},
            "coding_ability": {"score": 0, "explanation": "Unable to evaluate"},
            "communication_clarity": {"score": 0, "explanation": "Unable to evaluate"},
            "practical_engineering_thinking": {"score": 0, "explanation": "Unable to evaluate"}
        },
        "interview_integrity": {
            "tab_switch_count": 0,
            "long_inactivity_periods": 0,
            "unusual_timing_patterns": False,
            "integrity_issues_detected": None
        },
        "sample_qa_review": [],
        "coding_evaluation": {
            "problem_summary": None,
            "solution_summary": None,
            "correctness": None,
            "edge_case_handling": None,
            "code_quality_feedback": None
        },
        "strengths": ["—"],
        "areas_for_improvement": ["—"],
        "final_hiring_recommendation": "No Hire",
        "recommendation_justification": "Unable to generate evaluation at this time.",
        "answer_score": 5,
        "code_score": 0,
        "overall_score": 10,
        "passed": False,
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
_MAX_TRANSCRIPT_LENGTH = 6000  # Max characters in final transcript
_SKIP_INITIAL_MESSAGES = 1  # Skip first greeting from each role


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
            mock_q = sum(1 for m in messages if m.role == "ai") + 1
            text = _mock_interview_response(mock_q, interview.job_role)

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
        Returns a dict compatible with EvaluationResult schema with enhanced report.
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

        # Get candidate info
        candidate_name = "Unknown"
        candidate_identifier = "Unknown"
        if hasattr(interview, 'candidate') and interview.candidate:
            candidate_name = getattr(interview.candidate, 'full_name', None) or interview.candidate.email or "Unknown"
            candidate_identifier = interview.candidate.email or interview.candidate.id
        elif hasattr(interview, 'candidate_id') and interview.candidate_id:
            candidate_identifier = interview.candidate_id

        # Get tab switch count from interview
        tab_switch_count = getattr(interview, 'tab_switch_count', 0) or 0

        # Get interview duration
        duration_minutes = getattr(interview, 'duration_minutes', 60) or 60

        system = "You are an expert technical interview evaluator. Output only valid JSON, no markdown."
        prompt = _EVAL_PROMPT.format(
            job_role=interview.job_role,
            transcript=transcript,
            resume_context=resume_context,
            duration_minutes=duration_minutes,
            candidate_identifier=candidate_identifier,
            candidate_name=candidate_name,
            tab_switch_count=tab_switch_count,
        )

        # Call LLM with detailed logging — generous token limit for structured JSON
        try:
            text = await LLMDispatcher.chat(system, [{"role": "user", "content": prompt}], max_tokens=1500)
            
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
                    # Retry once with a stricter prompt
                    logger.warning(
                        "evaluation_json_retry",
                        extra={"event": "evaluation_parse_retry"},
                    )
                    retry_system = (
                        "You are an expert technical interview evaluator. "
                        "Output ONLY a valid JSON object. "
                        "No explanation, no markdown. Keep string values short (under 50 words each)."
                    )
                    text2 = await LLMDispatcher.chat(
                        retry_system,
                        [{"role": "user", "content": prompt}],
                        max_tokens=1500,
                    )
                    if text2:
                        result = _parse_json_response(text2)
                    if result is None:
                        logger.error(
                            "evaluation_json_parse_failed_after_retry",
                            extra={
                                "event": "evaluation_parse_failure",
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

        # Build comprehensive report from LLM response + existing data
        result = _build_comprehensive_report(
            result=result,
            interview=interview,
            messages=messages,
            emotion_data=emotion_data,
            cheating_score=cheating_score,
            duration_minutes=duration_minutes,
            candidate_name=candidate_name,
            tab_switch_count=tab_switch_count,
        )

        return result


def _build_comprehensive_report(
    result: dict,
    interview: Interview,
    messages: List[InterviewMessage],
    emotion_data: Optional[dict],
    cheating_score: Optional[float],
    duration_minutes: int,
    candidate_name: str,
    tab_switch_count: int,
) -> dict:
    """Build comprehensive report by combining LLM response with existing data."""
    
    # Get scores from LLM
    answer_score = float(result.get("answer_score", 0))
    code_score = result.get("code_score")
    if code_score is not None:
        code_score = float(code_score)
    
    # Calculate confidence score based on available data
    confidence_factors = []
    confidence_base = 50.0
    
    if answer_score >= 70:
        confidence_base += 15
        confidence_factors.append("quality of answers")
    elif answer_score >= 50:
        confidence_base += 5
    
    if code_score and code_score >= 70:
        confidence_base += 10
        confidence_factors.append("coding performance")
    
    if emotion_data:
        conf = float(emotion_data.get("avg_confidence", 50.0))
        eng = float(emotion_data.get("avg_engagement", 50.0))
        if conf >= 60 and eng >= 60:
            confidence_base += 10
            confidence_factors.append("consistency")
    
    if cheating_score is not None and cheating_score < 30:
        confidence_base += 5
        confidence_factors.append("interview integrity")
    
    confidence_score = min(100, int(confidence_base))
    
    # Determine overall result
    overall_score = result.get("overall_score", 0)
    if overall_score >= 70:
        overall_result = "Pass"
    elif overall_score >= 50:
        overall_result = "Borderline"
    else:
        overall_result = "Fail"
    
    # Build performance breakdown — use LLM-provided scores if available,
    # fall back to derived values from answer_score/code_score.
    answer_score_10 = max(1, min(10, int(answer_score / 10)))
    code_score_10 = int(code_score / 10) if code_score is not None else 5
    llm_perf = result.get("performance") or {}

    def _perf_score(key: str, fallback: int) -> int:
        """Read LLM score (1-10), clamped, with a derived fallback."""
        val = llm_perf.get(key)
        if val is not None:
            return max(1, min(10, int(val)))
        return max(1, min(10, fallback))

    performance_breakdown = {
        "technical_knowledge": {
            "score": _perf_score("technical_knowledge", answer_score_10),
        },
        "problem_solving": {
            "score": _perf_score("problem_solving", answer_score_10 + (1 if answer_score > 60 else -1)),
        },
        "coding_ability": {
            "score": _perf_score("coding_ability", code_score_10),
        },
        "communication_clarity": {
            "score": _perf_score("communication_clarity", answer_score_10 + (1 if answer_score > 50 else 0)),
        },
        "practical_engineering_thinking": {
            "score": _perf_score("practical_engineering", answer_score_10),
        }
    }
    
    # Interview integrity assessment
    integrity_issues = []
    if tab_switch_count and tab_switch_count > 5:
        integrity_issues.append(f"High tab switch count: {tab_switch_count}")
    
    if cheating_score and cheating_score > 50:
        integrity_issues.append("Elevated cheating indicators detected")
    
    if emotion_data:
        cheating_flags = emotion_data.get("cheating_flags", [])
        if cheating_flags:
            integrity_issues.append(f"Behavioral flags: {', '.join(cheating_flags)}")
    
    interview_integrity = {
        "tab_switch_count": tab_switch_count,
        "long_inactivity_periods": 0,
        "unusual_timing_patterns": False,
        "integrity_issues_detected": "; ".join(integrity_issues) if integrity_issues else None
    }
    
    # Extract sample Q/A from messages
    sample_qa_review = _extract_sample_qa(messages)
    
    # Coding evaluation
    coding_evaluation = _extract_coding_evaluation(messages)
    
    # Get strengths and weaknesses from LLM
    strengths = result.get("strengths", ["—"])
    weaknesses = result.get("weaknesses", ["—"])
    
    # Convert weaknesses to areas_for_improvement
    areas_for_improvement = weaknesses if weaknesses != ["—"] else ["Practice more technical concepts"]
    
    # Build final comprehensive report
    comprehensive = {
        "candidate_overview": {
            "candidate_name": candidate_name,
            "job_role": interview.job_role,
            "interview_duration_minutes": duration_minutes,
            "overall_result": overall_result
        },
        "confidence_score": {
            "score": confidence_score,
            "factors": confidence_factors if confidence_factors else ["quality of answers"]
        },
        "performance_breakdown": performance_breakdown,
        "interview_integrity": interview_integrity,
        "sample_qa_review": sample_qa_review,
        "coding_evaluation": coding_evaluation,
        "strengths": strengths,
        "areas_for_improvement": areas_for_improvement,
        "final_hiring_recommendation": result.get("final_hiring_recommendation", "Borderline"),
        "recommendation_justification": result.get("recommendation_justification", result.get("ai_feedback", "")),
        # Keep original scores for compatibility
        "answer_score": answer_score,
        "code_score": code_score,
        "overall_score": result.get("overall_score"),
        "passed": result.get("passed"),
        "ai_feedback": result.get("ai_feedback", ""),
        "emotion_score": result.get("emotion_score"),
        "integrity_score": result.get("integrity_score"),
        "cheating_score": result.get("cheating_score"),
        "weights_used": result.get("weights_used", {}),
    }
    
    return comprehensive



def _extract_sample_qa(messages: List[InterviewMessage]) -> list:
    """Extract 2-3 representative Q/A pairs from the interview."""
    qa_pairs = []
    
    for i in range(len(messages) - 1):
        if messages[i].role == "ai" and messages[i + 1].role == "candidate":
            question = messages[i].content
            answer = messages[i + 1].content
            
            # Skip system messages
            if question.startswith("[CODING_QUESTION]") or "INTERVIEW_COMPLETE" in question:
                continue
            
            # Truncate long content
            if len(question) > 200:
                question = question[:200] + "..."
            if len(answer) > 300:
                answer = answer[:300] + "..."
            
            qa_pairs.append({
                "question": question,
                "answer": answer,
                "evaluation": None,  # Actual evaluation is done by the LLM
            })
            
            if len(qa_pairs) >= 3:
                break
    
    return qa_pairs[:3] if qa_pairs else []


def _extract_coding_evaluation(messages: List[InterviewMessage]) -> dict:
    """Extract coding evaluation metadata from messages.
    
    Note: Actual code quality is evaluated by the LLM via _EVAL_PROMPT (code_score).
    This function only extracts metadata for the report.
    """
    coding_message = None
    for m in messages:
        if m.role == "candidate" and m.code_snippet:
            coding_message = m
            break
    
    if not coding_message:
        return {
            "problem_summary": None,
            "solution_summary": None,
            "correctness": None,
            "edge_case_handling": None,
            "code_quality_feedback": None
        }
    
    code = coding_message.code_snippet or ""
    
    return {
        "problem_summary": "Coding problem was presented during the interview.",
        "solution_summary": code[:200] + ("..." if len(code) > 200 else ""),
        "correctness": "See code_score for LLM evaluation.",
        "edge_case_handling": None,
        "code_quality_feedback": "Evaluated by AI — see code_score."
    }


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
    candidate = None
    if payload.get("candidate_email") or payload.get("candidate_name"):
        candidate = SimpleNamespace(
            email=payload.get("candidate_email"),
            full_name=payload.get("candidate_name", "Unknown"),
            id=payload.get("candidate_id", "unknown"),
        )
    interview = SimpleNamespace(
        job_role=payload.get("job_role", ""),
        resume_text=payload.get("resume_text"),
        duration_minutes=payload.get("duration_minutes", 60),
        tab_switch_count=payload.get("tab_switch_count", 0),
        candidate=candidate,
        candidate_id=payload.get("candidate_id"),
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
