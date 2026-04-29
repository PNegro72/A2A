import uuid
from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

from src.domain.models import CandidateIdentity, CandidateLead, CandidateEvidence, ShortlistReport, CandidateScore
from src.persistence.sqlite_repos import (
    SQLiteCandidateRepository,
    SQLitePipelineRunRepository,
    SQLiteShortlistReportRepository,
)

SCHEMA = (Path(__file__).parent.parent.parent / "src" / "persistence" / "schema_sqlite.sql").read_text()


@pytest_asyncio.fixture
async def db():
    conn = await aiosqlite.connect(":memory:")
    await conn.executescript(SCHEMA)
    await conn.commit()
    yield conn
    await conn.close()


# ── CandidateRepository ────────────────────────────────────────────────────

async def test_candidate_get_returns_none_when_not_found(db):
    repo = SQLiteCandidateRepository(db)
    result = await repo.get("gh:nobody")
    assert result is None


async def test_candidate_upsert_then_get(db):
    repo = SQLiteCandidateRepository(db)
    identity = CandidateIdentity(canonical_id="gh:alice", merged_leads=[])
    await repo.upsert(identity)

    result = await repo.get("gh:alice")
    assert result is not None
    assert result.canonical_id == "gh:alice"


async def test_candidate_upsert_does_not_duplicate(db):
    repo = SQLiteCandidateRepository(db)
    identity = CandidateIdentity(canonical_id="gh:bob", merged_leads=[])
    await repo.upsert(identity)
    await repo.upsert(identity)  # second upsert

    async with db.execute(
        "SELECT COUNT(*) FROM candidate_identities WHERE canonical_id = ?", ("gh:bob",)
    ) as cursor:
        row = await cursor.fetchone()
    assert row[0] == 1


async def test_candidate_upsert_preserves_leads(db):
    repo = SQLiteCandidateRepository(db)
    lead = CandidateLead(
        source="himalayas",
        raw_id="h123",
        profile_url="https://himalayas.app/u/alice",
        evidence=[
            CandidateEvidence(
                field="name",
                value="Alice",
                source_url="https://himalayas.app/u/alice",
                source_type="opt-in",
                verified=True,
                inferred=False,
            )
        ],
    )
    identity = CandidateIdentity(canonical_id="gh:alice2", merged_leads=[lead])
    await repo.upsert(identity)

    result = await repo.get("gh:alice2")
    assert len(result.merged_leads) == 1
    assert result.merged_leads[0].source == "himalayas"


# ── PipelineRunRepository ─────────────────────────────────────────────────

async def test_pipeline_run_create_sets_status_running(db):
    repo = SQLitePipelineRunRepository(db)
    run_id = str(uuid.uuid4())
    await repo.create(run_id, "Senior Python Dev", "Buenos Aires", "hybrid")

    async with db.execute(
        "SELECT status FROM pipeline_runs WHERE id = ?", (run_id,)
    ) as cursor:
        row = await cursor.fetchone()
    assert row[0] == "running"


async def test_pipeline_run_complete_sets_status_and_timestamp(db):
    repo = SQLitePipelineRunRepository(db)
    run_id = str(uuid.uuid4())
    await repo.create(run_id, "Engineer", "Remote", "remote")
    await repo.complete(run_id)

    async with db.execute(
        "SELECT status, completed_at FROM pipeline_runs WHERE id = ?", (run_id,)
    ) as cursor:
        row = await cursor.fetchone()
    assert row[0] == "completed"
    assert row[1] is not None


async def test_pipeline_run_fail_sets_status_failed(db):
    repo = SQLitePipelineRunRepository(db)
    run_id = str(uuid.uuid4())
    await repo.create(run_id, "Engineer", "Remote", "remote")
    await repo.fail(run_id, "MCP unreachable")

    async with db.execute(
        "SELECT status FROM pipeline_runs WHERE id = ?", (run_id,)
    ) as cursor:
        row = await cursor.fetchone()
    assert row[0] == "failed"


# ── ShortlistReportRepository ─────────────────────────────────────────────

async def test_shortlist_report_save_creates_row(db):
    pipeline_repo = SQLitePipelineRunRepository(db)
    report_repo = SQLiteShortlistReportRepository(db)

    run_id = str(uuid.uuid4())
    await pipeline_repo.create(run_id, "Backend Dev", "Remote", "remote")

    report = ShortlistReport(
        job_title="Backend Dev",
        candidates=[CandidateScore(candidate_id="gh:alice", score=0.9, reasoning="great match")],
        sources_used=["himalayas"],
        caveats=["Data from single source"],
    )
    await report_repo.save(run_id, report)

    async with db.execute(
        "SELECT COUNT(*) FROM shortlist_reports WHERE run_id = ?", (run_id,)
    ) as cursor:
        row = await cursor.fetchone()
    assert row[0] == 1
