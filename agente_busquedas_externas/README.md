# agente_busquedas_externas

Multi-agent recruiting and candidate-sourcing system built with Google ADK, A2A protocol, and MCP integrations.

Receives a job description, location, and work mode over A2A. Returns a sourced, scored, evidence-attributed candidate shortlist.

---

## Architecture

```mermaid
flowchart TD
    CLIENT([A2A Client]):::external

    subgraph A2A_SERVER["A2A Server · agente_busquedas_externas_orchestrator · :8080"]
        direction TB

        INTAKE["IntakeAgent\nValidate input · create pipeline_run\nwrite state: jd · location · work_mode · run_id"]

        JD["JDAnalystAgent\nExtract HiringRequirements\nfrom job description text"]

        PLANNER["PlannerAgent\nBuild SearchPlan\nwork_mode-aware source queries"]

        subgraph SOURCING["Sourcing Phase · ParallelAgent"]
            HIM["HimalayasSourceAgent\nMCP HTTP · search_talent\nget_talent_profile\nsource_type: opt-in"]
            GH["GitHubSourceAgent\nFunctionTools · httpx\nget_github_profile\nget_github_repos\nsource_type: public-api"]
            TAV["TavilyResearchAgent\nMCP HTTP · web search\nenrichment + verification\nsource_type: web-search"]
        end

        DEDUP["DeduplicatorAgent\nMerge leads by canonical_id\nCheck + upsert candidate_identities\nOne identity per person"]

        SCORER["ScorerAgent\nEvidence-only scoring 0.0–1.0\nRiskFlag on inferred fields\nNo hallucinated facts"]

        REPORTER["ReportAgent\nGenerate ShortlistReport\nPersist to SQLite\nMark run completed"]
    end

    subgraph MCP["MCP Sources"]
        HIM_MCP["Himalayas MCP\nmcp.himalayas.app\nFree · no auth\n100K+ opt-in candidates"]
        TAV_MCP["Tavily MCP\nmcp.tavily.com\nAPI key required\nSource-attributed search"]
        GH_API["GitHub REST API\napi.github.com\nToken required\nPublic profiles + repos"]
    end

    subgraph DB["SQLite · agente_busquedas_externas.db"]
        T1[("pipeline_runs")]
        T2[("shortlist_reports")]
        T3[("candidate_identities")]
    end

    CLIENT -->|"message/send\n{job_description, location, work_mode}"| INTAKE
    INTAKE --> JD
    JD --> PLANNER
    PLANNER --> SOURCING
    HIM <-->|SSE| HIM_MCP
    TAV <-->|SSE| TAV_MCP
    GH <-->|HTTPS| GH_API
    SOURCING --> DEDUP
    DEDUP <-->|read/upsert| T3
    DEDUP --> SCORER
    SCORER --> REPORTER
    REPORTER -->|INSERT| T1
    REPORTER -->|INSERT| T2
    REPORTER -->|"ShortlistReport"| CLIENT

    classDef external fill:#6366f1,color:#fff,stroke:none
    classDef mcp fill:#0ea5e9,color:#fff,stroke:none
    classDef db fill:#f59e0b,color:#fff,stroke:none
```

---

## Protocol Boundaries

| Layer | Technology | Responsibility |
|-------|-----------|----------------|
| External interface | A2A v0.3 | Receive JD + location + work_mode; return ShortlistReport |
| Internal orchestration | Google ADK | SequentialAgent pipeline; shared `session.state` blackboard |
| Source adapters | MCP (HTTP SSE) | Himalayas, Tavily — remote MCP servers, no local process |
| Technical signal | ADK FunctionTools | GitHub REST API via httpx — no Docker, no MCP subprocess |
| Persistence | SQLite → Supabase | Audit trail + cross-run candidate deduplication |

---

## Agent Pipeline

```
IntakeAgent          → validates A2A input, creates pipeline_run in DB
JDAnalystAgent       → extracts HiringRequirements from JD text
PlannerAgent         → builds SearchPlan (work_mode + location aware)
─── ParallelAgent ───────────────────────────────────────────────────
  HimalayasSourceAgent  → opt-in candidate profiles (remote-first)
  GitHubSourceAgent     → technical signal from public repos
  TavilyResearchAgent   → web enrichment + claim verification
─────────────────────────────────────────────────────────────────────
DeduplicatorAgent    → merges leads by GitHub username / email
ScorerAgent          → evidence-only scoring + risk flags
ReportAgent          → ShortlistReport → persisted to SQLite → A2A response
```

---

## Domain Model

```
JobDescription ──→ HiringRequirements ──→ SearchPlan
                                              │
                           ┌──────────────────┤
                           ▼                  ▼
                     CandidateLead     CandidateLead
                     (himalayas)       (github/tavily)
                           │
                    CandidateEvidence
                    {source_url, source_type,
                     verified, inferred}
                           │
                    CandidateIdentity  (deduped)
                           │
                    CandidateScore
                    {score 0–1, reasoning, risk_flags}
                           │
                    ShortlistReport
```

---

## Running

```bash
# Install
pip install -e ".[dev]"

# Configure (copy and fill in your keys)
# DB_PATH=./agente_busquedas_externas.db
# GITHUB_TOKEN=ghp_...
# TAVILY_API_KEY=tvly-...
# GOOGLE_API_KEY=...

# Start the A2A server
python -m src.main

# Send a test request (separate terminal)
python send_task.py
```

---

## Data Trust Model

| Source | Type | Verified | Notes |
|--------|------|----------|-------|
| Himalayas | `opt-in` | ✅ | Candidates self-listed as available |
| GitHub | `public-api` | ✅ | Official API, no scraping |
| Tavily | `web-search` | ❌ | Source-attributed, not verified |

Every `CandidateEvidence` carries `source_url`, `source_type`, `verified`, and `inferred` flags.
The scorer only uses evidence — it never generates or infers facts.

---

## Stack

- **[Google ADK](https://adk.dev)** — multi-agent orchestration
- **[A2A Protocol](https://a2a-protocol.org)** — agent interoperability (Linux Foundation)
- **[Himalayas MCP](https://himalayas.app/mcp)** — candidate sourcing
- **[Tavily MCP](https://docs.tavily.com/documentation/mcp)** — web research
- **[GitHub REST API](https://docs.github.com/en/rest)** — technical signal
- **SQLite** (dev) / **Supabase** (prod) — persistence
