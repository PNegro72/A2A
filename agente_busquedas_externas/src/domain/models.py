from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)


class RiskFlag(BaseModel):
    type: Literal["data-quality", "compliance", "weak-signal", "conflict"]
    description: str
    severity: Literal["low", "medium", "high"]


# Aliases the sourcing agents legitimately use for a source_type: the *name* of
# the source instead of its provenance class. Anything outside this map is a
# contract violation and must fail — silently rewriting an unknown provenance
# class to "web-search" would launder unverifiable data into the shortlist.
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
    """Map a known source alias to its provenance class.

    Unknown values are returned untouched so the ``Literal`` on
    :class:`CandidateEvidence.source_type` rejects them with a clear error.
    """
    if val in _VALID_SOURCE_TYPES:
        return val
    normalized = _SOURCE_TYPE_MAP.get(val.lower())
    if normalized is None:
        logger.warning(
            "Unknown source_type '%s' — rejecting evidence item (no provenance class)",
            val[:50],
        )
        return val
    return normalized


class CandidateEvidence(BaseModel):
    """A single observable fact plus the URL it was observed at.

    ``source_url`` is mandatory and must be a real http(s) URL: the whole
    scoring model is evidence-only, so an item without provenance is not
    admissible and must never be defaulted into existence.
    """

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
        if "source_type" in data:
            data["source_type"] = _normalize_source_type(str(data["source_type"]))
        return data

    @field_validator("source_url")
    @classmethod
    def _require_real_url(cls, value: str) -> str:
        url = value.strip()
        if not url:
            raise ValueError(
                "source_url must be the real URL the fact was observed at; "
                "evidence without provenance is not admissible"
            )
        if not url.startswith(("http://", "https://")):
            raise ValueError(f"source_url must be an http(s) URL, got {url[:80]!r}")
        return url


class CandidateLead(BaseModel):
    source: str
    raw_id: str
    name: str | None = None
    headline: str | None = None
    profile_url: str
    github_url: str | None = None
    evidence: list[CandidateEvidence] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, data: Any) -> Any:
        """Accept the API field names the sources actually use.

        Only genuine aliases are resolved here (``login``/``github_username``
        for ``raw_id``, ``html_url`` for ``profile_url``). Nothing is
        fabricated: a lead with no real profile URL fails validation instead of
        being given a placeholder.
        """
        if not isinstance(data, dict):
            return data
        raw = data.get("raw_id")
        if not raw:
            raw = data.get("github_username") or data.get("login")
            if raw:
                data["raw_id"] = str(raw)
        else:
            data["raw_id"] = str(raw)
        if not data.get("profile_url") and data.get("html_url"):
            data["profile_url"] = data["html_url"]
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
                elif isinstance(flag, (dict, RiskFlag)):
                    # RiskFlag instances come from Python callers, not the LLM;
                    # dropping them here silently loses the flags.
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


# ─────────────────────────────────────────────────────────────────────────────
# LLM wire contracts (ADK ``output_schema``)
#
# These are the schemas the model is *structurally* forced to emit, not just
# asked to emit: ADK passes them to the provider as a strict JSON schema, so
# every evidence item arrives as an object carrying its own real ``source_url``.
# They are deliberately separate from the domain models above because a strict
# schema cannot express ``Any``-typed fields or optional-with-default fields —
# here every field is required and every type is concrete.
#
# Provenance is pinned per source with ``Literal`` so a sourcing agent cannot
# mislabel where its data came from.
# ─────────────────────────────────────────────────────────────────────────────

_EvidenceValue = str | int | float | bool

# Nullable wire fields carry a `= None` default *only* so these models can
# re-validate their own output: ADK stores an agent's structured output as
# `model_dump(exclude_none=True)`, which drops the nulls the model did emit.
# The default does not loosen the contract towards the model — ADK's strict
# JSON schema lists every property as required regardless of defaults.


class SourcedEvidence(BaseModel):
    """One evidence item as emitted by a sourcing agent."""

    field: str
    value: _EvidenceValue
    source_url: str
    source_type: Literal["opt-in", "public-api", "web-search"]
    verified: bool
    inferred: bool
    inference_basis: str | None = None


class SourcedLead(BaseModel):
    """One candidate lead as emitted by a sourcing agent."""

    source: str
    raw_id: str
    name: str | None = None
    headline: str | None = None
    profile_url: str
    github_url: str | None = None
    evidence: list[SourcedEvidence]


class HimalayasEvidence(SourcedEvidence):
    source_type: Literal["opt-in"]


class HimalayasLead(SourcedLead):
    source: Literal["himalayas"]
    evidence: list[HimalayasEvidence]


class HimalayasLeads(BaseModel):
    """``output_schema`` of the Himalayas sourcing agent."""

    leads: list[HimalayasLead]


class GithubEvidence(SourcedEvidence):
    source_type: Literal["public-api"]


class GithubLead(SourcedLead):
    source: Literal["github"]
    evidence: list[GithubEvidence]


class GithubLeads(BaseModel):
    """``output_schema`` of the GitHub sourcing agent."""

    leads: list[GithubLead]


class TavilyEvidence(SourcedEvidence):
    source_type: Literal["web-search"]


class TavilyLead(SourcedLead):
    source: Literal["tavily"]
    evidence: list[TavilyEvidence]


class TavilyLeads(BaseModel):
    """``output_schema`` of the Tavily research agent."""

    leads: list[TavilyLead]


class MergedIdentity(BaseModel):
    """One deduplicated candidate as emitted by the deduplicator agent."""

    canonical_id: str
    github_url: str | None = None
    merged_leads: list[SourcedLead]


class DedupResult(BaseModel):
    """``output_schema`` of the deduplicator agent."""

    identities: list[MergedIdentity]


class ScoredCandidate(BaseModel):
    """One scored candidate as emitted by the scorer agent."""

    candidate_id: str
    score: float
    reasoning: str
    risk_flags: list[RiskFlag]
    merged_leads: list[SourcedLead]


class ScoringResult(BaseModel):
    """``output_schema`` of the scorer agent."""

    candidates: list[ScoredCandidate]


class ShortlistReportOut(BaseModel):
    """``output_schema`` of the reporter agent.

    Mirrors :class:`ShortlistReport` minus ``generated_at``, which is stamped
    deterministically when the report is persisted.
    """

    job_title: str
    candidates: list[ScoredCandidate]
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
