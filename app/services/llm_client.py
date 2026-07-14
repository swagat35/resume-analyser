"""
Thin wrapper around the Groq API (free tier, Llama 3.3 70B by default).

Why Groq: generous free tier, very fast inference, OpenAI-compatible-ish
Python SDK. Swap `_call_groq` for Gemini/OpenRouter if you prefer —
the rest of the app only depends on `get_llm_feedback`'s return shape.
"""
from __future__ import annotations

import json

from fastapi import HTTPException, status
from groq import APIError, APITimeoutError, Groq

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

_client: Groq | None = None

SYSTEM_PROMPT = """You are an expert recruiter and resume reviewer with deep
experience hiring across many fields — technology, healthcare, finance,
education, legal, sales, marketing, operations, hospitality, skilled trades,
creative/design, and more. Judge the resume using the norms and terminology
of whatever field the job description belongs to; do not assume it is a
technical/software role unless the job description says so.

You will be given resume text and a job description. Respond with ONLY a
valid JSON object (no markdown fences, no commentary) matching exactly this
schema:

{
  "match_score": <number 0-100>,
  "matching_skills": [<string>, ...],
  "missing_skills": [<string>, ...],
  "strengths": [<string>, ...],
  "suggestions": [<string>, ...],
  "summary": "<2-3 sentence plain-text summary>"
}

Be concise, specific, and constructive. Use the vocabulary of the relevant
industry (e.g. "patient charting" for healthcare, "GAAP" for accounting,
"lesson planning" for teaching) rather than generic tech terms. Do not
invent skills, certifications, or experience that are not present in the
resume text."""


def _get_client() -> Groq:
    global _client
    if _client is None:
        if not settings.groq_api_key:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "AI service is not configured. Set GROQ_API_KEY in the environment.",
            )
        _client = Groq(api_key=settings.groq_api_key)
    return _client


def get_llm_feedback(resume_text: str, job_description: str) -> dict:
    """
    Calls the LLM and returns a parsed dict matching SYSTEM_PROMPT's schema.
    Raises HTTPException on any failure — never lets a raw exception or
    malformed response reach the client.
    """
    client = _get_client()
    user_prompt = (
        f"RESUME TEXT:\n{resume_text[:8000]}\n\n"
        f"JOB DESCRIPTION:\n{job_description[:4000]}"
    )

    try:
        completion = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=1200,
            response_format={"type": "json_object"},
            timeout=20,
        )
    except APITimeoutError:
        logger.warning("Groq API timed out")
        raise HTTPException(
            status.HTTP_504_GATEWAY_TIMEOUT, "AI service timed out. Please try again."
        )
    except APIError as e:
        logger.error("Groq API error: %s", e)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "AI service is temporarily unavailable."
        )

    raw_content = completion.choices[0].message.content or "{}"

    try:
        data = json.loads(raw_content)
    except json.JSONDecodeError:
        logger.error("LLM returned non-JSON content")
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "AI service returned an unexpected response."
        )

    return _validate_llm_output(data)


def _validate_llm_output(data: dict) -> dict:
    """Defensive validation so a malformed LLM response can't crash the API."""
    required_keys = {
        "match_score", "matching_skills", "missing_skills",
        "strengths", "suggestions", "summary",
    }
    if not required_keys.issubset(data.keys()):
        logger.error("LLM response missing required keys: %s", data.keys())
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "AI service returned an incomplete response."
        )

    try:
        data["match_score"] = max(0.0, min(100.0, float(data["match_score"])))
    except (TypeError, ValueError):
        data["match_score"] = 0.0

    for key in ("matching_skills", "missing_skills", "strengths", "suggestions"):
        if not isinstance(data[key], list):
            data[key] = []

    if not isinstance(data["summary"], str):
        data["summary"] = ""

    return data
