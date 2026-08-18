Write a session summary into the project memory.

## Where

`.harness/memory/sessions/<YYYY-MM-DD>-<slug>.md` — slug is lowercase-hyphenated, derived from
`$ARGUMENTS` or from the main topic of this session.

Durable, topic-scoped knowledge (a convention, a gotcha, an architecture decision that outlives the
session) goes in `.harness/memory/notes/<topic>.md` instead — update the existing topic file if one
exists rather than creating a near-duplicate.

## Format

```markdown
---
date: <YYYY-MM-DD>
type: summary
topic: <slug>
agents_touched: [orchestrator, frontend, ...]
---

# <Title>

## What was worked on
## Decisions made and why
## Discoveries / gotchas
(non-obvious findings only — wrong API flags, edge cases, port conflicts, silent failures)
## Files of interest
## Open items / next step
```

## Then

Append one line to `.harness/memory/index.md` under the right section:

`- YYYY-MM-DD — [<Title>](sessions/<file>.md) — <one-line takeaway>`

## Rules

- Write facts, not narration. No "I then proceeded to…".
- Never record secrets, API keys, tokens, or candidate PII.
- If nothing non-obvious happened, write a two-line entry and say so — do not pad.
