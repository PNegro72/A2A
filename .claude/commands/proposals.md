---
description: List pending skill proposals detected from your recent work patterns.
---

Run `invincible proposals list --json` and parse the result.

For each proposal, show:
- **Topic**: the observed pattern
- **Profile**: which project profile it belongs to (`profile_hint`)
- **Summary**: what the detector noticed
- **ID**: the proposal id

Then offer:
- `/propose-skill <topic>` — manually draft a skill from scratch
- To accept: `invincible proposals accept <id>`
- To dismiss: `invincible proposals dismiss <id> --reason "<short reason>"`

If `invincible proposals list` returns empty, say so briefly. Don't pad the response.
