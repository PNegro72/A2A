from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class RiskFlag(BaseModel):
    type: Literal["data-quality", "compliance", "weak-signal", "conflict"]
    description: str
    severity: Literal["low", "medium", "high"]


class CandidateEvidence(BaseModel):
    field: str
    value: Any
    source_url: str
    source_type: Literal["opt-in", "public-api", "web-search"]
    verified: bool
    inferred: bool
    inference_basis: str | None = None


class CandidateLead(BaseModel):
    source: str
    raw_id: str
    name: str | None = None
    headline: str | None = None
    profile_url: str
    evidence: list[CandidateEvidence] = Field(default_factory=list)


class JobDescription(BaseModel):
    raw_text: str
    title: str | None = None
    company: str | None = None


class HiringRequirements(BaseModel):
    required_skills: list[str]
    preferred_skills: list[str] = Field(default_factory=list)
    seniority: Literal["junior", "mid", "senior", "staff"] = "mid"
    location_constraint: str | None = None
    work_mode: Literal["remote", "hybrid"]
    domain: str = ""


class SourceQuery(BaseModel):
    source: str
    query_params: dict[str, Any]
    rationale: str


class SearchPlan(BaseModel):
    sources: list[str]
    queries: list[SourceQuery]


class CandidateIdentity(BaseModel):
    canonical_id: str
    merged_leads: list[CandidateLead] = Field(default_factory=list)
    github_url: str | None = None
    linkedin_url: str | None = None
    first_seen_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    last_seen_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class CandidateScore(BaseModel):
    candidate_id: str
    score: float
    reasoning: str
    risk_flags: list[RiskFlag] = Field(default_factory=list)


class ShortlistReport(BaseModel):
    job_title: str
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    candidates: list[CandidateScore]
    sources_used: list[str]
    caveats: list[str]


class StateKeys:
    JOB_DESCRIPTION = "job_description"
    LOCATION = "location"
    WORK_MODE = "work_mode"
    HIRING_REQUIREMENTS = "hiring_requirements"
    SEARCH_PLAN = "search_plan"
    LEADS_HIMALAYAS = "leads_himalayas"
    LEADS_GITHUB = "leads_github"
    LEADS_TAVILY = "leads_tavily"
    CANDIDATE_IDENTITIES = "candidate_identities"
    CANDIDATE_SCORES = "candidate_scores"
    RISK_FLAGS = "risk_flags"
    SHORTLIST_REPORT = "shortlist_report"
    PIPELINE_RUN_ID = "pipeline_run_id"
