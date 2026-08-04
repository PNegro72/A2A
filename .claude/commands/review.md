Review the code changes in: $ARGUMENTS

If `$ARGUMENTS` is empty, review the uncommitted working-tree changes.
`$ARGUMENTS` may be a branch, a PR number, a path, or a commit range.

## Procedure

1. Read `AGENTS.md` at the repo root.
2. Determine the changed files (`git --no-pager diff --stat <target>`).
3. Load every `.claude/skills/*/SKILL.md` whose trigger matches a changed file. Load all matches —
   project-extension skills override language skills, which override universal ones.
4. Read the full diff, then read enough surrounding code to judge correctness — never review a hunk
   in isolation.
5. Check the **Cross-Agent Change Checklist** in `AGENTS.md`. Contract changes that were not
   propagated to the consumer, the registry, or the fallback cards are CRITICAL findings.

## Output

- One-paragraph summary of what the change does
- Findings grouped as **CRITICAL** / **WARNING** / **SUGGESTION**, each with a `file:line`
  reference, the violated rule, and a concrete fix
- Explicit verdict: APPROVE / REQUEST CHANGES
- If nothing is wrong, say so in one line. Do not invent findings to look thorough.

Do not modify code during a review unless the user asks for the fixes.
