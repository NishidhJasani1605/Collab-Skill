# Changelog

All notable changes to the **COLLAB** skill are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

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
