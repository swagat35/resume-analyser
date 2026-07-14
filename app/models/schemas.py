"""
Pydantic schemas for API request/response validation.
Using strict schemas is itself a security control — it rejects malformed
or unexpected payloads before they reach business logic.
"""
from pydantic import BaseModel, Field, field_validator


class AnalyzeRequest(BaseModel):
    job_description: str = Field(..., min_length=20, max_length=10_000)

    @field_validator("job_description")
    @classmethod
    def strip_and_check(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("job_description cannot be blank")
        return v


class SkillGap(BaseModel):
    missing_skills: list[str] = Field(default_factory=list)
    matching_skills: list[str] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    match_score: float = Field(..., ge=0, le=100)
    skill_gap: SkillGap
    strengths: list[str]
    suggestions: list[str]
    summary: str


class HealthResponse(BaseModel):
    status: str
    environment: str
