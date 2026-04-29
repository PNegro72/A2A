import json
import uuid
from datetime import datetime, timezone

import aiosqlite

from src.domain.models import CandidateIdentity, CandidateLead, ShortlistReport


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteCandidateRepository:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self.db = db

    async def get(self, canonical_id: str) -> CandidateIdentity | None:
        async with self.db.execute(
            "SELECT merged_leads FROM candidate_identities WHERE canonical_id = ?",
            (canonical_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        leads_raw = json.loads(row[0])
        return CandidateIdentity(
            canonical_id=canonical_id,
            merged_leads=[CandidateLead(**lead) for lead in leads_raw],
        )

    async def upsert(self, identity: CandidateIdentity) -> None:
        now = _now()
        leads_json = json.dumps([lead.model_dump() for lead in identity.merged_leads])
        await self.db.execute(
            """
            INSERT INTO candidate_identities
                (canonical_id, first_seen_at, last_seen_at, merged_leads)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(canonical_id) DO UPDATE SET
                last_seen_at = excluded.last_seen_at,
                merged_leads = excluded.merged_leads
            """,
            (identity.canonical_id, now, now, leads_json),
        )
        await self.db.commit()


class SQLitePipelineRunRepository:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self.db = db

    async def create(self, run_id: str, jd: str, location: str, work_mode: str) -> None:
        await self.db.execute(
            "INSERT INTO pipeline_runs (id, status, job_description, location, work_mode) "
            "VALUES (?, 'running', ?, ?, ?)",
            (run_id, jd, location, work_mode),
        )
        await self.db.commit()

    async def complete(self, run_id: str) -> None:
        await self.db.execute(
            "UPDATE pipeline_runs SET status = 'completed', completed_at = ? WHERE id = ?",
            (_now(), run_id),
        )
        await self.db.commit()

    async def fail(self, run_id: str, error: str) -> None:  # noqa: ARG002
        await self.db.execute(
            "UPDATE pipeline_runs SET status = 'failed', completed_at = ? WHERE id = ?",
            (_now(), run_id),
        )
        await self.db.commit()


class SQLiteShortlistReportRepository:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self.db = db

    async def save(self, run_id: str, report: ShortlistReport) -> None:
        await self.db.execute(
            "INSERT INTO shortlist_reports (id, run_id, report, sources_used, caveats) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                run_id,
                report.model_dump_json(),
                json.dumps(report.sources_used),
                json.dumps(report.caveats),
            ),
        )
        await self.db.commit()
