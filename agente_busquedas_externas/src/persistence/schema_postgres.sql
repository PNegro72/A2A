-- PostgreSQL/Supabase schema — future migration target
-- Apply with: psql $DATABASE_URL -f schema_postgres.sql

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    status          TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
    job_description TEXT NOT NULL,
    location        TEXT NOT NULL,
    work_mode       TEXT NOT NULL CHECK (work_mode IN ('remote', 'hybrid'))
);

CREATE TABLE IF NOT EXISTS shortlist_reports (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id       UUID NOT NULL REFERENCES pipeline_runs(id),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    report       JSONB NOT NULL,
    sources_used TEXT[] NOT NULL,
    caveats      TEXT[] NOT NULL
);

CREATE TABLE IF NOT EXISTS candidate_identities (
    canonical_id  TEXT PRIMARY KEY,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    merged_leads  JSONB NOT NULL,
    scores        JSONB,
    risk_flags    JSONB
);
