"""Self-check for the agent harness.

Verifies the acceptance criteria in .harness/memory/sdd/agent-harness-spec.md — both structural
(links, frontmatter, registry sync) and factual (does the harness still describe the real code?).

Run it after changing the harness, or after changing agent routes, ports, or schemas:

    python .harness/verify.py

Exit code 0 = all pass. Stdlib only, no dependencies. Not wired into CI or any build.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / ".claude" / "skills"
COMMANDS = ROOT / ".claude" / "commands"

results: list[tuple[str, str, str]] = []


def record(ac: str, ok: bool, evidence: str) -> None:
    results.append((ac, "PASS" if ok else "FAIL", evidence))


def read(*parts: str) -> str:
    return (ROOT.joinpath(*parts)).read_text(encoding="utf-8")


agents_md = read("AGENTS.md")
claude_md = read("CLAUDE.md")
registry_md = read(".harness", "skill-registry.md")
harness_files = [ROOT / "AGENTS.md"] + sorted(SKILLS.glob("*/SKILL.md")) + sorted(COMMANDS.glob("*.md"))
blob = "\n".join(p.read_text(encoding="utf-8") for p in harness_files)


# --- Structural ---------------------------------------------------------------------------

proc = subprocess.run(["git", "check-ignore", "AGENTS.md"], cwd=ROOT, capture_output=True, text=True)
record("AC-1", (ROOT / "AGENTS.md").exists() and proc.returncode != 0,
       f"exists=True check-ignore rc={proc.returncode}")

indexed = sorted(set(re.findall(r"\.claude/skills/([a-z0-9-]+)/SKILL\.md", agents_md)))
missing = [s for s in indexed if not (SKILLS / s / "SKILL.md").exists()]
record("AC-2", not missing, f"indexed={len(indexed)} missing={missing}")

bad_fm = []
on_disk = sorted(p.parent.name for p in SKILLS.glob("*/SKILL.md"))
for name in on_disk:
    text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not match:
        bad_fm.append((name, "no frontmatter"))
        continue
    declared = re.search(r"^name:\s*(\S+)", match.group(1), re.M)
    if not declared or declared.group(1) != name:
        bad_fm.append((name, declared.group(1) if declared else None))
record("AC-3", not bad_fm, f"skills={len(on_disk)} mismatches={bad_fm}")

registry_cmds = sorted(set(re.findall(r"`/([a-z-]+)`", registry_md)))
disk_cmds = sorted(p.stem for p in COMMANDS.glob("*.md"))
record("AC-4", registry_cmds == disk_cmds, f"registry={registry_cmds} disk={disk_cmds}")

broken = []
for rel in ("AGENTS.md", "CLAUDE.md", ".harness/README.md",
            ".harness/skill-registry.md", ".harness/memory/index.md"):
    f = ROOT / rel
    for m in re.finditer(r"\]\(([^)]+)\)", f.read_text(encoding="utf-8")):
        target = m.group(1)
        if target.startswith(("http", "#", "mailto:")):
            continue
        if not (f.parent / target.split("#")[0]).resolve().exists():
            broken.append(f"{rel} -> {target}")
record("AC-5", not broken, f"broken={broken}")

registry_skills = sorted(set(re.findall(r"^\| `([a-z0-9-]+)`", registry_md, re.M)))
record("AC-6", registry_skills == indexed, f"registry={len(registry_skills)} index={len(indexed)}")

tracked = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*")
           if p.is_file() and (".harness" in p.parts or ".claude" in p.parts)]
tracked.append("AGENTS.md")
proc = subprocess.run(["git", "check-ignore", "--stdin"], cwd=ROOT, input="\n".join(tracked),
                      capture_output=True, text=True)
ignored = [ln for ln in proc.stdout.splitlines() if ln.strip()]
record("AC-7", not ignored, f"checked={len(tracked)} ignored={ignored}")


# --- Factual accuracy ---------------------------------------------------------------------

adk = read(".claude", "skills", "python-adk-agents", "SKILL.md")
agent_dirs = [p.name for p in ROOT.glob("agente_*") if p.is_dir()]
record("AC-8", all(a in adk for a in agent_dirs) and "do not assume a uniform layout" in adk.lower(),
       f"agent_dirs={len(agent_dirs)} all_listed={all(a in adk for a in agent_dirs)}")

server = read("agente_orchestrator", "server.py")
real_routes = set(re.findall(r'@app\.(?:get|post)\("([^"]+)"', server))
claimed = {"/chat", "/chat/stream/{request_id}", "/chat/status/{request_id}", "/health"}
missing_impl = claimed - real_routes
record("AC-9", not missing_impl and "NOT implemented" not in adk,
       f"real={sorted(real_routes)} missing={sorted(missing_impl)}")

refs = set(re.findall(r'`((?:agente_[a-z_]+|frontend|MCP|Qdrant)/[A-Za-z0-9_./-]+)`', blob))
bad_paths = [r for r in refs if not (ROOT / r.replace("/", "\\")).exists()]
record("AC-10", not bad_paths, f"checked={len(refs)} nonexistent={sorted(bad_paths)}")

PORTS = {"agente_orchestrator": "8000", "agente_job_description": "8001",
         "agente_busquedas_internas": "8002", "agente_entrevistas": "8003",
         "agente_scheduling": "8004", "agente_busquedas_externas": "8080"}
mismatch = []
for agent, port in PORTS.items():
    envf = ROOT / agent / ".env.example"
    if envf.exists() and port not in envf.read_text(encoding="utf-8", errors="ignore"):
        mismatch.append(f"{agent} .env.example lacks {port}")
    if f"| {port} |" not in blob and f"`:{port}`" not in blob:
        mismatch.append(f"{port} absent from harness")
record("AC-11", not mismatch, f"mismatch={mismatch}")

cand = read("agente_busquedas_internas", "schemas", "CandidatoRankeado.py")
real_fields = set(re.findall(r"^\s{4}([a-z_]+)\s*:", cand, re.M))
cited = {"candidato", "score", "justificacion", "habilidades_match", "habilidades_faltantes"}
record("AC-12", not (cited - real_fields), f"cited_not_real={sorted(cited - real_fields)}")

sig = "def call_external_agent(agent_name: str, payload: dict) -> dict:"
record("AC-12b", sig in blob and sig in read("agente_orchestrator", "tools", "call_external_agent.py"),
       "delegation signature quoted verbatim from source")

cp = read(".claude", "skills", "code-python", "SKILL.md")
record("AC-13", "Target convention" in cp and "%" in cp,
       "aspirational rules labelled with measured prevalence")

cm = read(".claude", "skills", "commits", "SKILL.md")
record("AC-14", "new convention" in cm and "%" in cm, "commit convention declared as new")

ghosts = [g for g in ("a2a_policy_agent", "a2a_provider_agent", "a2a_research_agent",
                      "mcpserver.py", "doctors.json", "9997", "9998", "9999") if g in blob]
record("AC-R1", not ghosts, f"references to removed components={ghosts}")

ng = json.loads(read("frontend", "angular.json"))
out = ng["projects"]["frontend"]["architect"]["build"]["options"]["outputPath"]
record("AC-R2", out in read(".claude", "skills", "typescript-angular", "SKILL.md"),
       f"angular.json outputPath={out!r} quoted in skill")

record("AC-15", agents_md.count("SKILL.md") >= 7 and "| Trigger | Skill | Path |" in agents_md,
       "skill index maps triggers to paths")
record("AC-16", ".harness/memory/index.md" in agents_md and "/sync-memory" in agents_md,
       "session protocol names a start file and an end command")
record("AC-17", "AGENTS.md" in claude_md and "CLAUDE.md" in agents_md,
       "AGENTS.md <-> CLAUDE.md cross-linked")


print(f"{'AC':<8} {'STATUS':<6} EVIDENCE")
for ac, status, evidence in results:
    print(f"{ac:<8} {status:<6} {evidence}")
failed = [r for r in results if r[1] == "FAIL"]
print(f"\n{len(results) - len(failed)}/{len(results)} PASS")
sys.exit(1 if failed else 0)
