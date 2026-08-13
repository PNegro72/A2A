import json
import logging
import uuid
from datetime import datetime, timezone

import aiosqlite
from pydantic import ValidationError

from src.domain.models import CandidateIdentity, CandidateLead, ShortlistReport

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteCandidateRepository:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self.db = db

    async def get(self, canonical_id: str) -> CandidateIdentity | None:
        async with self.db.execute(
            "SELECT first_seen_at, merged_leads FROM candidate_identities "
            "WHERE canonical_id = ?",
            (canonical_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        first_seen_at, leads_raw = row
        leads = []
        for lead in json.loads(leads_raw):
            try:
                leads.append(CandidateLead.model_validate(lead))
            except ValidationError:
                # Historical row written before the evidence contract was
                # enforced. Drop it with a warning rather than letting stale
                # storage break the current run — leads produced *by this run*
                # are validated at the deduplicator and fail loudly there.
                logger.warning(
                    "candidate %s: dropping stored lead that violates the current "
                    "evidence contract",
                    canonical_id,
                    exc_info=True,
                )
        identity = CandidateIdentity(canonical_id=canonical_id, merged_leads=leads)
        if first_seen_at:
            try:
                identity.first_seen_at = datetime.fromisoformat(first_seen_at)
            except ValueError:
                logger.warning(
                    "candidate %s: unparseable first_seen_at %r", canonical_id, first_seen_at
                )
        return identity

    async def upsert(self, identity: CandidateIdentity) -> None:
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
            (
                identity.canonical_id,
                identity.first_seen_at.isoformat(),
                _now(),
                leads_json,
            ),
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
