---
description: Manually propose a new skill from an observed pattern or workflow. Drafts a SKILL.md skeleton, runs the sanitiser and lint, then commits to the invincible clone.
argument-hint: "<topic>"
---

Given the topic $ARGUMENTS:

1. Search memory for related entries: `invincible memory search "$ARGUMENTS"`. If no relevant entry exists, ask the user to describe the pattern, then proceed to step 2.
2. Save at least 1 pattern/discovery memory with a hierarchical topic_key of the form `<area>/<observation>` — e.g. `hub-issues/orphans`, `hub-issues/fifo-surprise`. Use a heredoc:
   ```bash
   cat <<'EOF' | invincible memory save \
     --title "<short title>" \
     --type pattern \
     --topic-key "<area>/<observation>" \
     --content-stdin
   <observation body>
   EOF
   ```
3. Run `invincible proposals scan` and note any new proposal ids in the output.
4. For each relevant new proposal: `invincible proposals accept <id>`. Report the resulting branch, file path, and status (committed | pushed | pr_opened | error).
5. If the rate limit is hit (`error: rate limit reached`), tell the user; do not retry.

If $ARGUMENTS is empty, ask the user to describe the recurring pattern they want to capture before proceeding.
