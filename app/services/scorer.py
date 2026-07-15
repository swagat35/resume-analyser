"""
Combines local text similarity (free, TF-IDF via scikit-learn — no PyTorch
required, so it fits comfortably in low-memory free-tier hosting) with the
LLM's qualitative feedback, and handles the DB-backed cache so identical
resume+JD pairs don't re-hit the LLM (protects your free API quota).
"""
from __future__ import annotations

import hashlib

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session

from app.db.models import AnalysisRecord
from app.services import llm_client, nlp_engine


def semantic_similarity(resume_text: str, job_description: str) -> float:
    """
    TF-IDF cosine similarity between resume and JD, scaled 0-100.
    Lightweight alternative to transformer embeddings — no GPU/large model
    downloads, minimal memory footprint, well suited to free-tier hosting.
    """
    vectorizer = TfidfVectorizer(stop_words="english")
    try:
        tfidf_matrix = vectorizer.fit_transform([resume_text, job_description])
    except ValueError:
        # Happens if both texts are empty/only stopwords after cleaning.
        return 0.0
    score = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
    return round(max(0.0, min(1.0, float(score))) * 100, 1)

def request_hash(resume_text: str, job_description: str) -> str:
    payload = (resume_text.strip() + "||" + job_description.strip()).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def analyze(resume_text: str, job_description: str, db: Session | None = None) -> dict:
    """
    Full analysis pipeline:
    1. Local keyword skill extraction (spaCy) — free, instant.
    2. Local embedding similarity — free, instant.
    3. LLM qualitative feedback — free tier API call.
    4. Blend + cache result metadata (no raw text stored) in DB.
    """
    req_hash = request_hash(resume_text, job_description)

    resume_skills = nlp_engine.extract_skills(resume_text)
    jd_skills = nlp_engine.extract_skills(job_description)
    matching_local = sorted(resume_skills & jd_skills)
    missing_local = sorted(jd_skills - resume_skills)

    embedding_score = semantic_similarity(resume_text, job_description)
    llm_result = llm_client.get_llm_feedback(resume_text, job_description)

    # Blend: 40% embedding similarity, 60% LLM's holistic judgment.
    blended_score = round(0.4 * embedding_score + 0.6 * llm_result["match_score"], 1)

    matching_skills = sorted(set(matching_local) | set(llm_result["matching_skills"]))
    missing_skills = sorted(set(missing_local) | set(llm_result["missing_skills"]))

    result = {
        "match_score": blended_score,
        "skill_gap": {
            "matching_skills": matching_skills,
            "missing_skills": missing_skills,
        },
        "strengths": llm_result["strengths"],
        "suggestions": llm_result["suggestions"],
        "summary": llm_result["summary"],
    }

    if db is not None:
        _cache_result(db, req_hash, blended_score)

    return result


def _cache_result(db: Session, req_hash: str, score: float) -> None:
    existing = db.query(AnalysisRecord).filter_by(request_hash=req_hash).first()
    if existing is None:
        db.add(AnalysisRecord(request_hash=req_hash, match_score=score))
        db.commit()
