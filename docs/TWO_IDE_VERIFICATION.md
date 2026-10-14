# Two-IDE verification

This is a **manual live test**, not a claim that one has already passed. The
automated tests use simulated identities in independent Python processes.

1. From this checkout, update both installed copies:
   `python install.py --global --agent codex --agent antigravity --json`.
   Require `ok: true`, beta.2 or newer, and `activation_verified: true` for each
   destination. Refresh each host's skill catalog/session. If an older duplicate
   appears, use the exact installed path returned by the installer; do not assume
   a previously loaded skill automatically refreshed. Codex supports
   `~/.agents/skills` and this Desktop also exposes `~/.codex/skills`; an explicit
   `CODEX_HOME` selects its `skills` directory. Antigravity uses
   `~/.gemini/config/skills`.
2. Open the **same canonical absolute project directory** in both IDEs. In Codex,
   select `$collab` and say: “Build a calculator with Codex and Antigravity in
   `<absolute-root>`. Require both IDEs. Initialize COLLAB now and report the task
   ID and missing collaborator.” Codex must execute the installed helper's
   `start --input -` with `--root`, a fresh UUID session, its actual platform, and
   `expected_platforms: ["codex", "antigravity"]`. Model and reasoning must be
   exact if known, otherwise unknown. Confirm its JOIN and task ID. Even after
   its work is finished, `status.blockers` must name missing Antigravity.
3. In Antigravity invoke `/collab` (or explicitly ask to use the installed skill):
   “Join task `<task-id>` at `<absolute-root>` with Codex; require both IDEs.” It
   must run its own installed helper `start` with a fresh UUID, actual Antigravity
   platform, the **same root and task ID**, and check exit zero/`ok: true`. Verify
   two JOIN events, distinct platform families, and exactly one task in
   `.collab/GROUP_CHAT.md` and helper `status`. If registration fails, record the
   JSON error and stop claiming the IDE is participating.
4. Have each IDE claim real work, share findings/help, and publish its result.
   Let Codex propose before Antigravity joins in a separate test: the late join
   must invalidate review and clear approvals. Both must then review/approve the
   new revision as required. Only after assignments, results, independent review,
   configured checks, and approvals pass may `finalize` emit TEAM_COMPLETE.

For an unavailable IDE, complete any useful remaining work, then save
`checkpoint` with `pending: true`, the missing collaborator and next steps. Expect
PENDING/PAUSED, not TEAM_COMPLETE. Never create another Codex identity to fill the
Antigravity slot. Retain credentials privately; do not paste tokens into the group
chat or Git. Record actual host versions, installed helper paths, exact task ID,
JOIN platforms, blockers, and final outcome as the live-test evidence.
