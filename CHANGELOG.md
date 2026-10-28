# Changelog

All notable changes to the **COLLAB** skill are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0-beta.4] - 2026-10-28

Local repair; no remote publication implied.

- Added authenticated bounded `wait`, presence renewal, incremental messages, explicit team completion, and actionable follow-up after individual completion.
- Replaced stop-when-idle guidance with an executable work/wait loop; corrected JSON command examples and clarified missing-runtime repair versus creating new project files.
- Removed filename and depth exceptions that hid nested sessions; recognize Git worktree roots and reject ambiguous roots.
- Replaced unsafe nested-directory moves with locked snapshots and retirement markers. Active/corrupt sessions, original history, and lock files are preserved; misleading `merge` is refused.
- Added regressions for waiting, message delivery across processes, stale presence, task completion, root discovery, live-state protection, and CLI validation. Simulation fixtures now explicitly isolate fake identities from the invoking IDE.
- Verified installed-version skew and an older helper bypassing newer required-platform gates in a disposable simulation. All collaborating installations must be updated together.

## [1.0.0-beta.3] - 2026-10-14

Local candidate; no tag or remote publication implied.

### Root-Cause Repairs & Hardening
- Prevent split-brain workspace state: Auto-bind nested project folders to ancestor `.collab` workspaces, detect `NESTED_WORKSPACE_CONFLICT`, and provide `collab migrate-nested` CLI command.
- Real Google Antigravity detection: Added detection for `ANTIGRAVITY_AGENT`, `ANTIGRAVITY_CONVERSATION_ID`, `ANTIGRAVITY_PROJECT_ID`, `ANTIGRAVITY_TRAJECTORY_ID`, and `ANTIGRAVITY_APP_DATA_DIR`.
- Enforce cross-IDE collaboration: Reject duplicate host sessions from registering multiple agents (`DUPLICATE_SESSION`), prevent self-review (`self_review`), enforce genuine assignment division across distinct participants, and require both agents to verify the identical revision.
- Add comprehensive 17-test regression suite covering all cross-IDE edge cases and complete end-to-end calculator collaboration scenario.

## [1.0.0-beta.2] - 2026-10-14

Local candidate; no tag or remote publication implied.

### Cross-IDE fixes
- Require configurable platform families/minimum distinct IDEs at completion; aliases and duplicate Codex identities cannot satisfy Antigravity requirements.
- Invalidate review on required late joins or stronger requirements; preserve mandatory results and approvals.
- Bind schema-2 tasks/state to canonical roots with additive locked migration and unchanged v1 journals.
- Preserve exact IDE/model/reasoning metadata with conservative host defaults and explicit provenance.
- Return teamwork follow-up and support PENDING checkpoints/PAUSED agents.
- Require actual helper initialization on explicit skill activation; verify registration in an isolated installer probe and propagate failures.
- Add cross-IDE unit, installed-helper, concurrent registration/finalization, migration, and security regressions. All automated identities are simulations.


### Fixed
- Canonicalized validated installer paths so Windows short-name aliases do not produce false broken-reference errors; accepted only macOS's exact standard `/private` system aliases while retaining user-link rejection.
- Added platform-specific regression tests for temporary-directory aliases and updated CI actions to pinned current releases.
- Unified all three installer entry points around one portable implementation with user-level defaults. Installation and verification leave project folders unchanged.
- Deferred `.collab` creation to explicit collaboration startup; read/status/check operations refuse uninitialized projects. Added explicit invocation policies for supported hosts.
- Updated Antigravity App/IDE and CLI discovery paths and prioritized active-host detection over unrelated installed tools.
- Staged and verified updates before replacing working installations, with rollback, serialized installers, legacy-install recognition, and preservation of unrelated files.
- Refused linked destinations, recursive source/destination layouts, and accidental global installs inside project folders.
- Made identical reinstalls leave installed files unchanged and normalized installer CLI errors to JSON when requested.
- Bounded validation-command output capture, removed internal credentials from child environments, and rejected stale check revisions before execution.
- Corrected installation, uninstall, compatibility, and validation documentation; expanded dependency-free CI and lifecycle regression coverage.

## [1.0.0-beta.1] - 2026-10-14

### Initial Release

#### Added
- **Universal Paste-to-Install Experience**:
  - `README.md` "Install COLLAB — Paste into your AI coding agent" workflow modeled on `Jakeschincariol/arena-skill` and adapted across Claude Code, OpenAI Codex, Google Antigravity, Kimi Code, Cursor, Gemini CLI, and OpenCode.
  - `INSTALL.md` agent playbook and `scripts/install_collab.py` cross-platform standard-library installer supporting environment auto-detection, `--scope project|global`, backup-on-update (`.collab-backups/`), integrity and relative-link checks, runtime `--version` self-test, and non-destructive `--uninstall`.
  - `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` manifests for optional Claude Code `/plugin` installation (with explicit documentation of `/collab:collab` vs. `/collab` namespacing).
- **Core Skill Specification**:
  - `skills/collab/SKILL.md` conforming to the open Agent Skills standard.
  - Portable script invocation from installed locations without repository dependencies.
- **Single Universal Group Chat**:
  - Append-only authoritative hash-chained event stream (`.collab/GROUP_CHAT.jsonl`).
  - Automatically maintained human-readable Markdown transcript (`.collab/GROUP_CHAT.md`).
  - Incremental sequence-number cursor reading (`read` via `after` or `cursor`) to eliminate redundant token consumption.
- **Concurrency & Storage Engine**:
  - Kernel-level file locking (`msvcrt.locking` on Windows, `fcntl.flock` on POSIX) using persistent `.collab/.lock`.
  - Checksummed Write-Ahead Redo Journal (`.collab/checkpoints/pending.json`) and state snapshots (`.collab/checkpoints/state.json`) with crash recovery across all commit boundaries.
  - High-concurrency verified: 100 simultaneous processes writing concurrently with 0 dropped events and 0 byte corruption.
- **Dynamic Agent Coordination**:
  - Bearer token authentication preventing impersonation.
  - Continuous teamwork: Finished assignments never prematurely finalize team tasks.
  - Assignment claiming, dependency tracking, progress reporting, and live `.collab/progress.json` aggregation.
  - Peer help requests (`help-request`, `help-respond`, `help-resolve`).
  - Blocking issue tracking and material disagreement handling.
- **Conflict Prevention**:
  - Cooperative file leases (`reserve`, `release`).
  - Hash-verified atomic file writes (`file-write`) and native host edit tracking (`file-record` with optional `expected_hash`).
- **Guarded Consensus & Finalization**:
  - Cryptographic proposal digests binding revisions, required members, criteria, and file fingerprints.
  - Independent review requirements with non-empty evidence.
  - Automated check runner (`check`) executing pre-declared commands with output and SHA-256 log verification.
  - Strict 9-gate completion verification in `engine.py`.
- **Human Operator CLI**:
  - `collab_operator.py` for interactive emergency participant recovery with TTY checks and challenge confirmation.
- **Testing & Documentation**:
  - 48 comprehensive test cases across 6 test modules (`test_installer.py`, `test_parameter_aliases.py`, `test_engine_security.py`, `test_integration.py`, `test_storage.py`, `test_skill.py`).
  - Complete documentation suite (`INSTALL.md`, `ARCHITECTURE.md`, `PROTOCOL.md`, `INSTALLATION.md`, `COMPATIBILITY.md`, `VALIDATION_REPORT.md`, `commands.md`, `safety.md`).
