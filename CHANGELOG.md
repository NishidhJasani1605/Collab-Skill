# Changelog

All notable changes to the **COLLAB** skill are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0-beta.1] - 2026-10-14

### Initial Release

#### Added
- **Core Skill Specification**:
  - `skills/collab/SKILL.md` conforming to the open Agent Skills standard.
  - Portable script invocation from installed locations without repository dependencies.
- **Single Universal Group Chat**:
  - Append-only authoritative event stream (`.collab/GROUP_CHAT.jsonl`).
  - Automatically maintained human-readable Markdown transcript (`.collab/GROUP_CHAT.md`).
  - Incremental byte-offset cursor reading (`read`) to eliminate redundant token consumption.
- **Concurrency & Storage Engine**:
  - Kernel-level byte-range file locking (`msvcrt.locking` on Windows, `fcntl.flock` on POSIX).
  - Write-Ahead Logging (`wal.jsonl`) with crash recovery boundaries.
  - High-concurrency verified: 100 simultaneous processes writing concurrently with 0 dropped events and 0 byte corruption.
- **Dynamic Agent Coordination**:
  - Bearer token authentication preventing impersonation.
  - Continuous teamwork: Finished assignments never prematurely finalize team tasks.
  - Assignment claiming, dependency tracking, and progress reporting.
  - Peer help requests (`help-request`, `help-respond`, `help-resolve`).
  - Blocking issue tracking and material disagreement handling.
- **Conflict Prevention**:
  - Cooperative file leases (`reserve`, `release`).
  - Hash-verified atomic file writes (`file-write`) and native host edit tracking (`file-record`).
- **Guarded Consensus & Finalization**:
  - Cryptographic proposal digests binding revisions, required members, and file fingerprints.
  - Independent review requirements with non-empty evidence.
  - Automated check runner (`check`) executing pre-declared commands with output and hash verification.
  - Strict 9-gate completion verification in `engine.py`.
- **Human Operator CLI**:
  - `collab_operator.py` for interactive emergency participant recovery with TTY checks and challenge confirmation.
- **Testing & Documentation**:
  - 34 comprehensive test cases covering packaging, storage, integration, and security.
  - Complete documentation suite (`ARCHITECTURE.md`, `PROTOCOL.md`, `INSTALLATION.md`, `COMPATIBILITY.md`, `VALIDATION_REPORT.md`, `commands.md`, `safety.md`).
