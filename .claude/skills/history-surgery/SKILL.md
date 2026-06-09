---
name: history-surgery
description: "Safe git history rewriting for metadata fixes and commit-chain cleanup."
when_to_use: "When rewriting already-pushed commits, repairing commit metadata, or regrouping commits without changing the intended final tree."
user-invocable: false
hub-skill-ids: [review]
---

# Skill: History Surgery

## When to Use

- Rewriting already-pushed commits to fix metadata
- Splitting, squashing, or regrouping commits while preserving the intended final tree
- Repairing commit chains after a policy or trailer mistake

## Rules

REJECT:
- Rewriting shared history without creating a backup ref or tag first
- Using chained soft-reset loops as the default method for multi-commit regrouping
- Restating commit-policy rules here instead of deferring to the `commits` skill and `.githooks/commit-msg`

REQUIRE:
- Create a reversible backup ref or tag before rewriting history
- Verify the rewritten branch preserves the intended final tree before pushing
- Pre-validate replacement commit messages against `.claude/skills/commits/SKILL.md` and `.githooks/commit-msg`
- Use `git push --force-with-lease` for rewritten published history

PREFER:
- `git commit-tree` or targeted interactive rebase for metadata-only repairs
- Small, explicit rewrite plans that name the commits being replaced
- Capturing the old and new commit IDs in the handoff notes

## Recommended Workflow

1. Create a backup ref or tag for the current branch tip.
2. Identify the exact commits to replace and whether the tree should remain unchanged.
3. If the final tree must stay identical, prefer rebuilding commits from existing trees rather than replaying edits.
4. Validate each rewritten commit message against the current `commits` skill and hook policy before updating refs.
5. Confirm the rewritten branch points at the expected tree, then push with `--force-with-lease`.

## Notes

- Commit policy authority stays in `.claude/skills/commits/SKILL.md` and `.githooks/commit-msg`.
- This skill is about safe rewrite mechanics, not inventing new commit rules.
