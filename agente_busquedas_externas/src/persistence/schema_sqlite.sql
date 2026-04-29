CREATE TABLE IF NOT EXISTS pipeline_runs (
    id              TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at    TEXT,
    status          TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
    job_description TEXT NOT NULL,
    location        TEXT NOT NULL,
    work_mode       TEXT NOT NULL CHECK (work_mode IN ('remote', 'hybrid'))
);

CREATE TABLE IF NOT EXISTS shortlist_reports (
    id           TEXT PRIMARY KEY,
    run_id       TEXT NOT NULL REFERENCES pipeline_runs(id),
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    report       TEXT NOT NULL,
    sources_used TEXT NOT NULL,
    caveats      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS candidate_identities (
    canonical_id  TEXT PRIMARY KEY,
    first_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at  TEXT NOT NULL DEFAULT (datetime('now')),
    merged_leads  TEXT NOT NULL,
    scores        TEXT,
    risk_flags    TEXT
);
