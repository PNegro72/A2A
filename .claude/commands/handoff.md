Create a handoff document for unfinished work: $ARGUMENTS

Use this when stopping mid-task so the next session can resume without re-discovering context.

## Where

`.harness/memory/sessions/<YYYY-MM-DD>-handoff-<slug>.md`

## Required fields — include all four verbatim

- `change_id`: <slug>
- `last_completed_step`: <the last step actually finished, or "not started">
- `current_state`: 2–4 sentences on what exists right now, including what is half-done
- `next_step`: the single most important next action

## Body

1. What was accomplished
2. Current state — including any process left running, any branch left dirty
3. Known issues / blockers (exact error text if there is one)
4. Next steps, ordered
5. Relevant files, with the specific functions or lines in play
6. How to re-verify: the exact command that reproduces the current state

## Then

Append to `.harness/memory/index.md`:

`- YYYY-MM-DD — [HANDOFF: <Title>](sessions/<file>.md) — next: <next_step>`

## Finally

Tell the user: "To resume, open `.harness/memory/sessions/<file>.md` and start from `next_step`."
