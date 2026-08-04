---
date: 2026-08-04
type: spec
change_id: agent-harness
topic: harness
---

# SDD Spec: agent-harness

## Goals

Provide an Invincible-inspired, self-contained agent harness for this repository so that any coding
agent (Claude Code, Copilot CLI, Cursor) picks up consistent, **accurate** standards and carries
context across sessions — without the repo becoming an Invincible-managed project.

## Non-Goals

- Depending on the `invincible` CLI, hub state, or `invincible update` propagation.
- Enrolling this repo as an Invincible-managed repository.
- Adding any runtime component, hook, or daemon that can break the build.
- Porting the full Invincible feature set (wiki sync, dual-model adversarial review, template sync).

## Acceptance Criteria

### Structural

- [ ] **AC-1** `AGENTS.md` exists at repo root and is not matched by `.gitignore`
      (`git check-ignore AGENTS.md` exits non-zero).
- [ ] **AC-2** Every skill referenced in the `AGENTS.md` Skill Index resolves to an existing file.
- [ ] **AC-3** Every `.claude/skills/*/SKILL.md` has valid YAML frontmatter whose `name` equals its
      parent directory name.
- [ ] **AC-4** Every `.claude/commands/*.md` referenced in `.harness/skill-registry.md` exists, and
      every command file that exists is listed in the registry (bidirectional, no orphans).
- [ ] **AC-5** All relative markdown links in `AGENTS.md`, `CLAUDE.md`, `.harness/README.md`,
      `.harness/skill-registry.md`, and `.harness/memory/index.md` resolve to existing paths.
- [ ] **AC-6** The skill list in `.harness/skill-registry.md` matches the `AGENTS.md` Skill Index
      exactly (same set of skill names).
- [ ] **AC-7** No file added by the harness is ignored by `.gitignore` (the harness is fully
      tracked and shareable).

### Factual accuracy — the core criterion

- [ ] **AC-8** Every structural claim about agent layout in `python-adk-agents/SKILL.md` is either
      true for all `agente_*/` packages, or explicitly marked as the target convention with the
      known deviations named.
- [ ] **AC-9** Every HTTP endpoint path stated in the harness matches a real route in
      `agente_orchestrator/`.
- [ ] **AC-10** Every symbol named in the harness (Pydantic models, modules, functions, env vars,
      file paths) exists in the repo, or is removed/corrected.
- [ ] **AC-11** Every port number stated in the harness matches the value used in code, `.env.example`,
      or `start_all.sh`.
- [ ] **AC-12** Code examples in skills use field names and APIs that exist in this repo — no
      invented model fields.
- [ ] **AC-13** Claims about prevailing convention (Python version, Pydantic version, HTTP client,
      Angular version, commit style, identifier language) are labelled as either **current reality**
      or **target to converge on**. An aspirational rule presented as current reality is a FAIL.
- [ ] **AC-14** The `commits` skill describes a convention consistent with the repo's actual git
      history, or explicitly states it is a new convention starting now.

### Behavioural

- [ ] **AC-15** A fresh agent session reading only `AGENTS.md` can determine which skills to load
      for a given changed file path, with no ambiguity.
- [ ] **AC-16** The session protocol names a concrete file to read at start and a concrete file to
      write at end — no tooling required.
- [ ] **AC-17** `CLAUDE.md` (what the system is) and `AGENTS.md` (how to change it) cross-link and
      do not contradict each other.

## Constraints

- ~~Markdown and YAML only. No executable code~~ — **amended during the cycle (2026-08-04):** the
  factual criteria (AC-8 → AC-14) are only trustworthy if they are re-checkable, so one stdlib-only
  script, `.harness/verify.py`, is allowed. It has no dependencies, is not wired into CI or any
  build, and touches nothing outside the harness. Everything else stays markdown/YAML.
- Must not modify any agent source, test, or build configuration.
- Must not weaken existing `.gitignore` secret protections (`.env`, `credentials.json`,
  `token.json`, service-account JSON stay ignored).
- Spanish/English convention stated in the harness must reflect what the codebase actually does.
- Each skill file stays under ~150 lines.
- Corrections to `CLAUDE.md` are in scope where it states something factually false; rewriting it is
  not.

## Added during the cycle

- [ ] **AC-18** `python .harness/verify.py` exits 0, with every AC above checked mechanically where
      mechanically checkable.

## Out of Scope

- Automating the memory writes (staying manual/agent-driven by design).
- Enforcing any of these rules in CI or via git hooks.
- Refactoring existing agent code to comply with the skills — the harness documents and guides;
  convergence happens per-change.
