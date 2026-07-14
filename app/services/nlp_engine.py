"""
Local, free NLP layer using spaCy. Runs entirely on-device (no API calls),
so it costs nothing and never sends resume text to a third party.

Used for: named entity extraction (orgs, dates) and a lightweight
keyword-based skill matcher. The heavier semantic reasoning is delegated
to the LLM in llm_client.py.
"""
from __future__ import annotations

import spacy

_NLP = None

# Skill vocabulary organized by field, so the matcher isn't biased toward
# any one profession. Extend any category freely as the project grows —
# these are seed lists, not exhaustive taxonomies.
SKILLS_BY_CATEGORY: dict[str, set[str]] = {
    "tech": {
        "python", "java", "javascript", "typescript", "sql", "nosql", "react",
        "node.js", "fastapi", "django", "flask", "docker", "kubernetes", "aws",
        "azure", "gcp", "git", "ci/cd", "postgresql", "mysql", "mongodb",
        "redis", "machine learning", "deep learning", "nlp", "pandas", "numpy",
        "tensorflow", "pytorch", "rest api", "graphql", "linux",
        "agile", "scrum", "excel", "tableau", "power bi", "sql server",
    },
    "healthcare": {
        "patient care", "clinical documentation", "emr", "ehr", "epic",
        "cerner", "hipaa", "medication administration", "phlebotomy",
        "vital signs", "triage", "cpr", "bls", "acls", "case management",
        "patient advocacy", "infection control", "clinical trials",
        "icd-10", "cpt coding", "medical billing", "nursing care plans",
    },
    "finance_accounting": {
        "financial modeling", "forecasting", "budgeting", "gaap", "ifrs",
        "accounts payable", "accounts receivable", "reconciliation",
        "quickbooks", "sap", "financial reporting", "auditing",
        "tax preparation", "variance analysis", "cash flow analysis",
        "risk management", "financial statements", "bloomberg terminal",
        "cpa", "cfa",
    },
    "marketing_sales": {
        "seo", "sem", "content marketing", "social media marketing",
        "email marketing", "google analytics", "google ads", "hubspot",
        "salesforce", "crm", "lead generation", "brand strategy",
        "market research", "copywriting", "campaign management",
        "account management", "cold calling", "negotiation",
        "b2b sales", "b2c sales", "customer retention", "adobe creative suite",
    },
    "education": {
        "curriculum development", "lesson planning", "classroom management",
        "differentiated instruction", "student assessment", "iep",
        "special education", "esl", "google classroom", "canvas lms",
        "blackboard", "tutoring", "academic advising", "e-learning",
    },
    "legal": {
        "legal research", "contract drafting", "litigation support",
        "legal writing", "westlaw", "lexisnexis", "compliance",
        "due diligence", "case management", "regulatory filings",
        "paralegal", "intellectual property", "mergers and acquisitions",
    },
    "operations_hr": {
        "project management", "supply chain management", "logistics",
        "inventory management", "vendor management", "process improvement",
        "lean six sigma", "recruiting", "onboarding", "payroll",
        "employee relations", "performance management", "ats", "workday",
        "hris", "benefits administration", "talent acquisition",
    },
    "design_creative": {
        "figma", "sketch", "adobe photoshop", "adobe illustrator",
        "ui/ux design", "wireframing", "prototyping", "typography",
        "graphic design", "video editing", "premiere pro", "after effects",
        "user research", "design systems",
    },
    "hospitality_retail": {
        "customer service", "point of sale", "pos systems", "inventory control",
        "food safety", "servsafe", "guest relations", "event planning",
        "merchandising", "shift scheduling", "cash handling",
    },
}

# Flattened set used for fast membership checks.
COMMON_SKILLS: set[str] = {
    skill for skills in SKILLS_BY_CATEGORY.values() for skill in skills
}


def _get_nlp():
    global _NLP
    if _NLP is None:
        _NLP = spacy.load("en_core_web_sm")
    return _NLP


def extract_entities(text: str) -> dict[str, list[str]]:
    """Extract organizations, dates, and other named entities."""
    nlp = _get_nlp()
    doc = nlp(text[:100_000])  # cap length for performance/safety
    entities: dict[str, list[str]] = {"ORG": [], "DATE": [], "GPE": []}
    for ent in doc.ents:
        if ent.label_ in entities:
            entities[ent.label_].append(ent.text)
    # de-dupe while preserving order
    for key in entities:
        entities[key] = list(dict.fromkeys(entities[key]))
    return entities


def extract_skills(text: str) -> set[str]:
    """Simple, fast keyword-based skill matcher against a known vocabulary."""
    lowered = text.lower()
    return {skill for skill in COMMON_SKILLS if skill in lowered}
