from app.services import nlp_engine


def test_extract_skills_finds_known_keywords():
    text = "Experienced with Python, FastAPI, Docker, and PostgreSQL."
    skills = nlp_engine.extract_skills(text)
    assert "python" in skills
    assert "fastapi" in skills
    assert "docker" in skills
    assert "postgresql" in skills


def test_extract_skills_ignores_unrelated_words():
    text = "I enjoy hiking and photography on weekends."
    skills = nlp_engine.extract_skills(text)
    assert skills == set()


def test_extract_skills_detects_healthcare_terms():
    text = "5 years of patient care experience, proficient in Epic EHR and CPR certified."
    skills = nlp_engine.extract_skills(text)
    assert "patient care" in skills
    assert "epic" in skills
    assert "cpr" in skills


def test_extract_skills_detects_marketing_terms():
    text = "Ran SEO and email marketing campaigns using HubSpot and Google Analytics."
    skills = nlp_engine.extract_skills(text)
    assert "seo" in skills
    assert "email marketing" in skills
    assert "hubspot" in skills


def test_extract_skills_detects_education_terms():
    text = (
        "Experienced in curriculum development and lesson planning for "
        "special education students using Canvas LMS."
    )
    skills = nlp_engine.extract_skills(text)
    assert "curriculum development" in skills
    assert "lesson planning" in skills
    assert "special education" in skills
    assert "canvas lms" in skills


def test_request_hash_is_deterministic():
    from app.services.scorer import request_hash

    h1 = request_hash("resume text", "job description")
    h2 = request_hash("resume text", "job description")
    h3 = request_hash("different", "job description")
    assert h1 == h2
    assert h1 != h3
