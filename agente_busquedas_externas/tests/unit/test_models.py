import pytest
from pydantic import ValidationError

from src.domain.models import (
    CandidateEvidence,
    CandidateScore,
    HiringRequirements,
    RiskFlag,
    StateKeys,
)


# --- CandidateEvidence ---

def test_evidence_requires_source_url():
    with pytest.raises(ValidationError):
        CandidateEvidence(
            field="name",
            value="John",
            source_type="opt-in",
            verified=True,
            inferred=False,
            # source_url missing
        )


def test_evidence_rejects_invalid_source_type():
    with pytest.raises(ValidationError):
        CandidateEvidence(
            field="name",
            value="John",
            source_url="https://himalayas.app/u/john",
            source_type="scraped",  # not in Literal
            verified=True,
            inferred=False,
        )


def test_evidence_valid_with_inference():
    ev = CandidateEvidence(
        field="seniority",
        value="senior",
        source_url="https://github.com/john",
        source_type="public-api",
        verified=False,
        inferred=True,
        inference_basis="commit frequency over 3 years",
    )
    assert ev.inferred is True
    assert ev.inference_basis == "commit frequency over 3 years"


# --- RiskFlag ---

def test_risk_flag_rejects_unknown_type():
    with pytest.raises(ValidationError):
        RiskFlag(type="unknown", description="test", severity="low")


def test_risk_flag_valid():
    flag = RiskFlag(type="weak-signal", description="inferred seniority", severity="medium")
    assert flag.type == "weak-signal"
    assert flag.severity == "medium"


def test_risk_flag_rejects_invalid_severity():
    with pytest.raises(ValidationError):
        RiskFlag(type="data-quality", description="x", severity="critical")


# --- HiringRequirements ---

def test_hiring_requirements_rejects_invalid_work_mode():
    with pytest.raises(ValidationError):
        HiringRequirements(required_skills=["Python"], work_mode="onsite")


def test_hiring_requirements_defaults_seniority_to_mid():
    req = HiringRequirements(required_skills=["Python"], work_mode="remote")
    assert req.seniority == "mid"


def test_hiring_requirements_hybrid_mode():
    req = HiringRequirements(
        required_skills=["Go", "Kubernetes"],
        work_mode="hybrid",
        location_constraint="Buenos Aires",
    )
    assert req.work_mode == "hybrid"
    assert req.location_constraint == "Buenos Aires"


# --- CandidateScore ---

def test_candidate_score_stores_score_and_reasoning():
    score = CandidateScore(candidate_id="gh:user1", score=0.85, reasoning="strong match")
    assert score.score == 0.85
    assert score.candidate_id == "gh:user1"


def test_candidate_score_with_risk_flags():
    flag = RiskFlag(type="weak-signal", description="inferred", severity="low")
    score = CandidateScore(candidate_id="gh:user2", score=0.4, reasoning="partial", risk_flags=[flag])
    assert len(score.risk_flags) == 1
    assert score.risk_flags[0].type == "weak-signal"


# --- StateKeys ---

def test_state_keys_are_unique_strings():
    keys = [
        StateKeys.JOB_DESCRIPTION,
        StateKeys.LOCATION,
        StateKeys.WORK_MODE,
        StateKeys.HIRING_REQUIREMENTS,
        StateKeys.SEARCH_PLAN,
        StateKeys.LEADS_HIMALAYAS,
        StateKeys.LEADS_GITHUB,
        StateKeys.LEADS_TAVILY,
        StateKeys.CANDIDATE_IDENTITIES,
        StateKeys.CANDIDATE_SCORES,
        StateKeys.RISK_FLAGS,
        StateKeys.SHORTLIST_REPORT,
        StateKeys.PIPELINE_RUN_ID,
    ]
    assert all(isinstance(k, str) for k in keys)
    assert len(set(keys)) == len(keys), "StateKeys must all be unique"
