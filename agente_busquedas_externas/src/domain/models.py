from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger(__name__)


class RiskFlag(BaseModel):
    type: Literal["data-quality", "compliance", "weak-signal", "conflict"]
    description: str
    severity: Literal["low", "medium", "high"]


_SOURCE_TYPE_MAP = {
    "himalayas": "opt-in",
    "github": "public-api",
    "tavily": "web-search",
    "web": "web-search",
    "web-search": "web-search",
    "opt-in": "opt-in",
    "public-api": "public-api",
    "web_search": "web-search",
}

_VALID_SOURCE_TYPES = {"opt-in", "public-api", "web-search"}


def _normalize_source_type(val: str) -> str:
    if val in _VALID_SOURCE_TYPES:
        return val
    normalized = _SOURCE_TYPE_MAP.get(val.lower())
    if normalized is None:
        logger.warning("Unknown source_type '%s', defaulting to 'web-search'", val[:50])
        return "web-search"
    return normalized


class CandidateEvidence(BaseModel):
    field: str
    value: Any
    source_url: str
    source_type: Literal["opt-in", "public-api", "web-search"] = "opt-in"
    verified: bool = True
    inferred: bool = False
    inference_basis: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data.setdefault("source_url", "")
        if "source_type" in data:
            data["source_type"] = _normalize_source_type(str(data["source_type"]))
        else:
            data["source_type"] = "opt-in"
        data.setdefault("verified", True)
        data.setdefault("inferred", False)
        data.setdefault("inference_basis", None)
        return data


class CandidateLead(BaseModel):
    source: str
    raw_id: str
    name: str | None = None
    headline: str | None = None
    profile_url: str
    evidence: list[CandidateEvidence] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        raw = data.get("raw_id")
        if raw is None or not raw:
            raw = data.get("github_username") or data.get("login") or "unknown"
        data["raw_id"] = str(raw)
        if not data.get("profile_url"):
            data["profile_url"] = data.get("html_url") or f"https://example.com/{data['raw_id']}"
        data.setdefault("source", "unknown")
        # Normalize evidence items, delegating to CandidateEvidence._normalize
        if isinstance(data.get("evidence"), list):
            fallback_url = data.get("profile_url", "")
            for ev in data["evidence"]:
                if isinstance(ev, dict):
                    ev.setdefault("source_url", fallback_url)
                    CandidateEvidence._normalize(ev)
        return data


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
    merged_leads: list[CandidateLead] = Field(
        default_factory=list,
        description="Full candidate profile data from all sources — name, profile_url, evidence. "
        "Essential for the entrevistas_agent to generate interview kits without requiring additional lookups.",
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        # LLM outputs 'canonical_id' instead of 'candidate_id'
        if "candidate_id" not in data and "canonical_id" in data:
            data["candidate_id"] = data.pop("canonical_id")
        # LLM outputs flat dicts with 'name' instead of 'candidate_id'
        if "candidate_id" not in data and "name" in data:
            data["candidate_id"] = str(data["name"])
        if "candidate_id" not in data:
            data["candidate_id"] = "unknown"
        # Coerce score to float
        if "score" in data:
            try:
                data["score"] = float(data["score"])
            except (ValueError, TypeError):
                data["score"] = 0.0
        else:
            data["score"] = 0.0
        # LLM often omits reasoning
        data.setdefault("reasoning", f"Score: {data.get('score', 'N/A')}")
        # Fix risk_flags: LLM may output strings instead of dicts
        if isinstance(data.get("risk_flags"), list):
            fixed = []
            for flag in data["risk_flags"]:
                if isinstance(flag, str):
                    fixed.append({"type": "data-quality", "description": flag, "severity": "low"})
                elif isinstance(flag, dict):
                    fixed.append(flag)
            data["risk_flags"] = fixed
        else:
            data["risk_flags"] = []
        # Normalize merged_leads: LLM may output {} or None instead of list
        raw_leads = data.get("merged_leads")
        if isinstance(raw_leads, dict):
            # Single lead wrapped in dict — wrap in list
            data["merged_leads"] = [raw_leads] if raw_leads else []
        elif not isinstance(raw_leads, list):
            data["merged_leads"] = []
        # Normalize each lead
        for lead in data["merged_leads"]:
            if isinstance(lead, dict):
                CandidateLead._normalize(lead)
        return data


class ShortlistReport(BaseModel):
    job_title: str
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    candidates: list[CandidateScore]
    sources_used: list[str]
    caveats: list[str]

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data.setdefault("job_title", "Unknown Role")
        data.setdefault("caveats", ["No additional caveats."])
        if not isinstance(data.get("caveats"), list):
            data["caveats"] = [str(data["caveats"])] if data.get("caveats") else ["No additional caveats."]
        if not isinstance(data.get("sources_used"), list):
            data["sources_used"] = []
        # Normalize each candidate score — handle flat dicts from LLM
        raw_candidates = data.get("candidates")
        if isinstance(raw_candidates, dict):
            # Single candidate wrapped in dict — wrap in list
            data["candidates"] = [raw_candidates] if raw_candidates else []
        elif not isinstance(raw_candidates, list):
            data["candidates"] = []
        for c in data["candidates"]:
            if isinstance(c, dict):
                CandidateScore._normalize(c)
        return data


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
