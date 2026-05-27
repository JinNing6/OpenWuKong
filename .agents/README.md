# .agents Rules

These rules apply to every conversation in this repository.

1. Start each conversation by reading:
- `.agents/README.md`
- `.agents/conversation_index.md`

2. Treat `.agents/conversation_index.md` as the current source of truth for:
- product direction
- current stage
- validated progress
- next priorities
- open risks

3. Keep the project scoped to the agreed north star:
- build an `AIOS Copilot`, not a generic "everything assistant"
- first win the developer workstation path:
  `Codex / Cursor / Copilot / Terminal / Git / Browser`

4. Before starting new work:
- compare the user's request with the current stage and priorities
- continue the roadmap when aligned
- if the user changes direction, update the index to reflect the new decision

5. After any substantial task, update `.agents/conversation_index.md`:
- add the date
- record what changed
- record what was validated
- update the next 1-3 concrete actions
- keep blockers and risks current

6. Prefer cumulative progress over rewrite:
- do not delete important historical decisions
- revise status in place and append short session notes
