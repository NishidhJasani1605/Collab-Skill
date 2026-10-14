# COLLAB cross-IDE validation report

Date: 2026-10-14 (Asia/Calcutta). Local candidate `1.0.0-beta.2`, based on
`67922a5`. No release, tag, push, or live two-IDE result is implied.

## Reproduced baseline defects

The original, unchanged suite passed: Windows/Python 3.13.5,
`python -m unittest discover -s tests -v`: **73 run, 71 passed, 2 skipped,
0 failures, 82.855 seconds**. That suite did not enforce cross-IDE requirements.

A disposable copy of the original tracked scripts from `67922a5` was exercised
through independent CLI processes. With `expected_platforms` declaring Codex
and Antigravity, two Codex identities completed the work, review, and approvals.
Antigravity then joined late without supplying a result or approval. Observed:

```json
{
  "codex_only_review_completed_without_antigravity_result_or_approval": "TEAM_COMPLETE",
  "late_antigravity_is_observer": true,
  "copied_state_wrong_root_accepted": true,
  "simulation": true
}
```

These are reproduced defects in simulated clients, consistent with the reported
live symptom; this maintenance session did not reproduce the native IDE UI flow.

## Final automated verification

Both final runs executed `python -m unittest discover -s tests -v` (Linux uses
`python3` in its isolated copy):

| Environment | Run / passed / skipped | Failures | Time | Exit |
| --- | --- | --- | --- | --- |
| Windows, Python 3.13.5 | 97 / 95 / 2 | 0 | 159.811 s | 0 |
| Linux via WSL, Python 3.12.3 | 97 / 94 / 3 | 0 | 80.737 s | 0 |

Windows skips: macOS system aliases and unavailable symlink privileges
(WinError 1314); Windows junction and short-name alias tests passed.
Linux skips: macOS system aliases, Windows short-name aliases, and Windows
junction coverage; Linux symlink tests passed.

Local ignored raw logs: `baseline-test.log`, `baseline-defects.log`,
`cross-ide-process.log`, `cross-ide-process-fixed.log`, `cross-ide-final.log`,
`linux-test.log`, `final-windows-tests.log`, `final-linux-tests.log`,
`security-checks.log`, and `skill-validator.log`. This report retains the outcomes
in Git without committing ephemeral test logs or runtime credentials.

Additional observed checks:

| Check | Exact outcome |
| --- | --- |
| `python -m unittest discover -s tests -p 'test_cross_ide*.py' -v` | 23 passed, 0 failures, 35.999 seconds (before the final unknown-metadata resume assertion, also covered by the final full suites) |
| `python -m unittest discover -s tests -p test_engine_security.py -v` | 7 passed, 0 failures, 5.730 seconds |
| `python install.py --verify-only --json` | Exit 0; beta.2; `verified: true`, `activation_verified: true`; isolated temporary registration |
| `python examples/two_agents.py` | Exit 0; independent-process A → B → A message exchange; task deliberately remains open |
| Python AST parsing, local Markdown links, JSON manifests | Syntax valid; 0 broken local links; both manifests beta.2 |
| `git diff --check` | Exit 0; no whitespace errors |
| `git check-ignore` for runtime/session/credentials fixtures | All three private paths ignored |

The Linux suite runs in a copied repository under a native Linux temporary
directory, using WSL Python 3.12.3. Windows uses Python 3.13.5. Neither test shares
one `.collab` between Windows and Linux locking implementations.

## Behavioral coverage

- Codex alone and a second Codex identity cannot satisfy Codex-plus-Antigravity;
  aliases count as one family, and unknown/custom labels do not count.
- Required late joins invalidate review/approvals, become mandatory, and cannot
  be omitted from result or approval gates. Explicitly required existing
  observers can be promoted. Strengthening requirements cannot weaken them.
- Separate Codex/Antigravity installations in a simulated home execute their
  actual helpers, register one task with distinct sessions/platforms, exchange
  help, submit results, review, approve, and complete.
- Barrier-synchronized initial starts deduplicate the task. A required join
  racing finalization cannot complete the old round. Existing tests also cover
  120 concurrent messages, 100 concurrent storage submissions, competing claims,
  finalization races, and concurrent installers.
- Exact model variants, IDE names, reasoning levels and metadata provenance
  survive state, chat, and final reports. Missing/ambiguous metadata stays
  unknown; a different declared client does not inherit the shell host's model.
- Completion remains blocked by unfinished required/claimed assignments,
  missing results/reviews/approvals, issues/help, checks, artifact changes,
  unreleased reservations, and tampered/deleted evidence.
- Finished clients receive remaining work/help. PENDING checkpoints invalidate
  review and mark the caller PAUSED. Unavailable required participants are
  named. Operator replacement with another Codex cannot waive Antigravity.
- Root copies are rejected for reads, writes, and pending-journal recovery
  without altering copied history. An empty other root cannot adopt an existing
  task ID. Legacy migration preserves the exact historical byte prefix and
  credentials, adding defaults on the next normal locked mutation.
- Installer activation failure propagates structured errors and preserves the
  previous installation even if `--version` succeeds.
- Existing authentication, path traversal, symlink/junction/hardlink, crash
  recovery, check timeout/output bounding, and secret-handling tests remain.

## Failed checks and corrections

- Initial standalone `test_cross_ide_process.py` discovery: 1 import error,
  `ModuleNotFoundError: No module named 'collablib'`. Fixed the test's standalone
  import path; rerun: **5 passed, 12.518 seconds** before later coverage additions.
- First Linux full run with the new recovery test: **97 run, 1 failure,
  3 skipped, 65.255 seconds**. The test used nonexistent fault stage
  `after_journal`, so the process exited 0 rather than the expected 91. Corrected
  to the existing `after_wal`; the Windows targeted rerun passed. The final Linux
  suite below covers the correction.
- Bundled skill-creator `quick_validate.py skills/collab`: **exit 1**, rejecting
  pre-existing `compatibility` and `disable-model-invocation` frontmatter keys.
  Its allowlist omits these host-specific fields. They were preserved for host
  compatibility; COLLAB's package validator, syntax/link checks, and installed
  helper execution pass. This external validator failure remains disclosed.

## Live verification boundary and remaining limits

Read-only inspection found beta.1 copies at `~/.codex/skills/collab` and
`~/.gemini/config/skills/collab`. The current Codex skill catalog did not expose
COLLAB. No native Antigravity session was activated or observed registering in
this maintenance task. Installed copies were not overwritten during source
maintenance. Update both before the [live verification procedure](TWO_IDE_VERIFICATION.md).
Official discovery references are linked in [Compatibility](COMPATIBILITY.md).

Platform identities are cooperative declarations, not host attestation. Optional
COLLAB_HOST_* variables are an adapter contract, not invented vendor APIs.
Unavailable exact model/reasoning metadata remains unknown. A passive skill
cannot force an IDE to load it, wake paused sessions, or prove that a recent
heartbeat means a process is running.

Schema-1 roots cannot be recovered retroactively; they bind on the first normal
mutation. Previously completed reports stay historical, with no retroactive
claim that they passed the new gates. Both IDEs need upgraded helpers; old
executables do not enforce new requirements. Same-user hostile processes,
network/cloud-sync filesystems, mixed Windows/WSL access to one state directory,
and detached check descendants remain outside the documented guarantees.
macOS and the remote CI matrix were not executed in this session.
