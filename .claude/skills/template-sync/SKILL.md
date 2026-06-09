---
name: template-sync
description: "Keep live dogfood files, template sources, manifests, docs, and tests synchronized."
when_to_use: "When changing invincible-managed templates, generated surfaces, or propagation rules."
user-invocable: false
hub-skill-ids: [review]
---

# Skill: Template Sync

## When to Use

- Updating an invincible-managed file that also has a template source
- Changing propagation behavior in `init` or `update`
- Fixing drift between dogfood copies, templates, docs, and tests

## Rules

REJECT:
- Editing only the rendered dogfood copy when the canonical source is a template
- Shipping template changes without updating the relevant manifests and tests
- Duplicating commit-policy rules here instead of deferring to the `commits` skill and hook

REQUIRE:
- Change the canonical template under `src/invincible/init/templates/` when the distributed output should change
- Update the matching dogfood copy in this repo when the repo consumes the same guidance
- Check `src/invincible/init/__init__.py` and `src/invincible/init/update.py` for distribution and propagation impact
- Verify whether the affected surface is `OVERWRITE`, `MARKER_MERGE`, `JSON_MERGE`, `SKIP_DEFAULT`, or `CREATE_IF_MISSING`

PREFER:
- `invincible update` as the default propagation path for existing repos
- `invincible init --force` only when a full re-bootstrap is intentional
- Adding parity or propagation tests whenever a live/template pair can drift

## Recommended Workflow

1. Identify the canonical template and every live or generated surface that mirrors it.
2. Update the template first, then the repo's dogfood copy if this repo consumes the same content.
3. Review `FILE_MANIFEST` and `FILE_UPDATE_MANIFEST` for creation and update behavior.
4. Update docs and tests that encode the same behavior or counts.
5. Use `invincible update` to confirm the propagation path still matches the intended ownership model.

## Notes

- Commit policy authority stays in `.claude/skills/commits/SKILL.md` and `.githooks/commit-msg`.
- This skill is about synchronization and propagation, not about redefining commit rules.
