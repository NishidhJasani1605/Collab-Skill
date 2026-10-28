# COLLAB collaboration repair

Local repair: 1.0.0-beta.4. Investigation began 2026-10-27; final verification and installation completed 2026-10-28 (Asia/Calcutta). This report distinguishes code/process tests from live IDE behavior.

## What this skill is

COLLAB is a local collaboration protocol packaged as a skill. Its Python helper maintains one shared task, participant roster, chat journal, assignments, file reservations, checks, reviews, and approvals under the project's `.collab` directory. Each agent must invoke the helper itself. Merely opening the same folder does not link the agents' private chats.

Python 3.10+ runs the helper; no third-party Python packages are required. Python 3.13.5 was available on this machine. The application project can be empty or use any language. The rewritten instructions tell agents to create missing application/test files after claiming and reserving work. Missing skill runtime modules require restoring the complete trusted package, not inventing replacement scripts or resetting shared state.

## Verified causes and repairs

| Observed issue | Evidence | Repair |
| --- | --- | --- |
| Different agents enforce different rules | Actual Codex installation was beta.1; actual Antigravity plugin copy was beta.2; working checkout was beta.3. In a disposable mixed-version reproduction, beta.2 reported missing Antigravity while beta.1 finalized the same task. | Update both exact installed locations together; verify identical package hashes and helper versions. |
| Finished agent stops | Installed beta.1 instructed OFFLINE/resume-next-invocation behavior; beta.2 allowed a pending checkpoint. Current engine's idle guidance also suggested checkpointing. | Authenticated bounded `wait`, presence renewal, explicit `continue_waiting` and `team_complete`, and a documented work/wait loop. An empty timeout does not finish the task. |
| Folder/session disappears during recovery | Previous `migrate-nested` used `shutil.move` on the nested `.collab` and its live lock without acquiring the source lock or checking unfinished tasks. | Refuse active/corrupt session retirement. Snapshot completed state under locks, preserving original files and the permanent lock; mark retired state explicitly. No automatic live-session migration in skill instructions. |
| Agents create disconnected runtimes | Discovery ignored names ending in ` project`, stopped searching after three levels, ignored Git worktree `.git` files, and selected a conflicting ancestor silently. | Remove name/depth exceptions, recognize worktrees, report conflicts, and retain explicit canonical root/task identity. |
| Instructions do not execute | Old skill examples used unsupported `--after` / `--nested-path` flags and omitted the wait command recipe. | Use actual JSON CLI input, exact helper paths, verified registration, and executable loop guidance. |
| Startup recovery can undermine concurrency | Failed initialization could delete the permanent lock while another client waited on it. | Preserve the lock; use normal locked recovery instead of removing runtime state. |

The unsafe migration mechanism is reproduced from code and tests. The original user's particular deletion incident cannot be attributed to a command with certainty without that session's logs. An agent bypassing the helper and deleting files directly is outside these cooperative filesystem protections.

## Checks and coverage

- Regression tests exercise concurrent initialization and messages, matching task IDs, missing/late required participants, independent reviews, current approvals, edited-file invalidation, and refusal of premature finalization.
- New wait tests exercise timeout without pause, authenticated presence renewal, peer writes while waiting, invalid credentials/durations, and terminal completion visible to both clients.
- Session-safety tests cover nested/deep roots, suffix names, worktree discovery, preserved history/lock, corrupt or active migration refusal, and Windows junction protections.
- An independent forward scenario used the skill in a disposable project: preserved existing sentinel bytes, created a new text file with no project `.py` files, continued after an empty wait, received a concurrent peer message, and finished checks/review/approvals before both clients observed completion.
- The bundled package verifier checks all required scripts and runs a startup probe in a temporary workspace. Its `activation_verified` field refers to that helper probe, not live native IDE discovery.
- The generic skill-creator validator rejects the existing cross-host `compatibility` and `disable-model-invocation` frontmatter keys. They remain intentional host metadata; the package's own manifest and portable execution tests validate the distributable skill.

Final Windows/Python 3.13.5 suite: `python -m unittest discover -s tests -v` ran **142 tests in 202.351 seconds: 140 passed, 2 skipped, no failures**. Skips were the macOS-only alias check and Windows symlink privilege; actual Windows junction tests passed. Raw local log: `verification-beta4-tests.log`. The initial full suite had inherited-host simulation failures; the final run uses explicit simulated identities while retaining genuine duplicate-host protection tests.

The actual installed Codex and Antigravity helpers then completed a separate **33-command** disposable workflow: same task, preserved existing bytes, no project Python files, late join, individual completion followed by continued waiting, empty timeout followed by waiting again, bidirectional messages, peer message delivered while another process waited, checks in both clients, independent review, both approvals, and team completion observed by both. The result explicitly records `simulation: true` and `live_ide_test: false`; raw output is `verification-beta4-installed.json`.

## Installed repair and backups

Both actual installed skill trees were verified byte-for-byte against the repaired source, excluding generated caches. Their helpers return `1.0.0-beta.4`:

- Codex: `C:\Users\nishi\.codex\skills\collab`. Backup: `C:\Users\nishi\.codex\skills\.collab-backups\collab-ms2xgddi`.
- Antigravity plugin: `C:\Users\nishi\.gemini\config\plugins\collab-skill\skills\collab`. Backup: `C:\Users\nishi\.gemini\config\.collab-local-repair-backups\20261027-beta4-kazzoxmk\antigravity-collab-before`.
- Repair provenance, source/previous hashes, and verification: `C:\Users\nishi\.gemini\config\.collab-local-repair-backups\20261027-beta4-kazzoxmk\repair.json`.

The Antigravity plugin manifest version was updated with a separate manifest backup. This is a local repair of the existing plugin checkout; a future plugin-manager update can replace it. No duplicate standalone Antigravity installation was created. Refresh loaded host skills/session context to use the new instructions.

## Using the repaired skill

Refresh the loaded skill in both hosts before starting. Each must report beta.4 or newer from its actual loaded helper path. Give both the same absolute project path and task:

```text
Use the collab skill with Codex and Antigravity in <absolute project path> for: <task>.
Require both platforms. Inspect and join the existing task before creating files.
Preserve existing work and .collab. Create missing project files as needed.
Divide work, exchange messages, and continue the work/wait loop after your own
assignment until the helper reports TEAM_COMPLETE. Report the shared task ID.
```

The second agent can also join the exact task ID reported by the first. Both should report that same ID. Shared messages appear in `.collab/GROUP_CHAT.md` and the verified result in `.collab/FINAL_REPORT.md`.

## Limits that remain visible

This repair does not create a native-IDE scheduler. The wait loop works while the host permits tool execution. If an IDE ends its turn, loses access, or hits a usage limit, the helper cannot restart it; resume the host with its task/credentials. Existing active conflicting roots require coordinated recovery and are preserved instead of being silently combined. Old helpers remain unsafe for newer completion rules and must not be mixed with the repaired version.

Automated clients are explicitly simulated. They establish filesystem/protocol behavior, not a completed live Codex-plus-Antigravity UI test. Follow [the live two-IDE procedure](TWO_IDE_VERIFICATION.md) to verify host discovery, continued native execution, and interaction under the user's actual host limits. Official skill discovery references: [OpenAI](https://learn.chatgpt.com/docs/build-skills) and [Antigravity](https://antigravity.google/docs/skills?app=antigravity-ide).
