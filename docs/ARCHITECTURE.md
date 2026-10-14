# COLLAB Architecture

COLLAB is an open-standard Agent Skill that enables multiple autonomous AI coding agents—running in separate processes, IDEs, or terminals—to collaborate effectively within the **same physical local directory**.

It operates with **zero external infrastructure**: no Docker, no Redis, no central server, no daemon, no cloud coordinator, and no paid APIs.

---

## 1. High-Level System Architecture

```mermaid
graph TD
    subgraph Host Environments
        A1["OpenAI Codex"]
        A2["Google Antigravity"]
        A3["Claude Code"]
        A4["Cursor / Gemini / Kimi / OpenCode"]
    end

    subgraph COLLAB Skill Layer
        S1["SKILL.md & /collab Entrypoint"]
        S2["scripts/collab.py (Internal JSON CLI)"]
        S3["collablib/engine.py (Protocol & State Machine)"]
        S4["collablib/storage.py (WAL, OS Locks, Atomic Projections)"]
    end

    subgraph Shared Filesystem (.collab/)
        L[".lock (Persistent kernel lock inode)"]
        W["checkpoints/pending.json (Write-Ahead Redo Journal)"]
        C["checkpoints/state.json (Checksummed State Checkpoint)"]
        G1["GROUP_CHAT.jsonl (Authoritative Hash-Chained Event Log)"]
        G2["GROUP_CHAT.md (Human-Readable Markdown Transcript)"]
        ST["Projections: agents.json, tasks.json, progress.json, config.json"]
        D["decisions/ & reviews/ & findings/ & checkpoints/"]
        R["FINAL_REPORT.md (Final Artifact)"]
    end

    A1 --> S1
    A2 --> S1
    A3 --> S1
    A4 --> S1

    S1 --> S2
    S2 --> S3
    S3 --> S4

    S4 --> L
    S4 --> W
    S4 --> C
    S4 --> G1
    S4 --> G2
    S4 --> ST
    S4 --> D
    S4 --> R
```

---

## 2. Core Architectural Pillars

### 2.1 Storage & Concurrency Engine (`storage.py`)
- **Kernel-level File Locking**:
  - Windows (`msvcrt.locking` on 1-byte range of `.collab/.lock`)
  - POSIX (`fcntl.flock` with `LOCK_EX | LOCK_NB` and bounded retry on `.collab/.lock`)
  - Automatic kernel cleanup on process termination or abnormal exit.
- **Write-Ahead Redo Logging (WAL)**:
  - Every state mutation writes a checksummed transaction journal to `.collab/checkpoints/pending.json` with `os.fsync`.
  - Authoritative hash-chained append to `.collab/GROUP_CHAT.jsonl`.
  - Checksummed state snapshot committed to `.collab/checkpoints/state.json`.
  - Atomic replacement of projected state files (`agents.json`, `tasks.json`, `progress.json`, `config.json`, `GROUP_CHAT.md`) via `os.replace`.
  - Unlinking of `.collab/checkpoints/pending.json`.
- **Crash Recovery**:
  - On `Store` entry, any incomplete transaction in `.collab/checkpoints/pending.json` is verified and replayed idempotently before serving reads or writes.
  - Corrupt WAL journals, checkpoints, or tampered chat lines raise an explicit `CORRUPT_STORAGE` error while preserving all files on disk.

### 2.2 Protocol & Coordination Engine (`engine.py`)
- **Actor Authentication**:
  - Each agent generates a random `session_id` and receives an `agent_id` and private bearer `token`.
  - Every mutating command authenticates against `state["agents"][agent_id]["token_hash"]` using constant-time `hmac.compare_digest`.
  - Prevents token tampering and cross-agent impersonation.
- **Single Authoritative Conversation**:
  - `.collab/GROUP_CHAT.jsonl` contains strictly validated, chronologically ordered, hash-chained JSON events (`seq`, `prev_hash`, `state_hash`, `hash`).
  - Incremental reading via sequence cursors (`after` / `cursor`) eliminates repetitive context re-reads.
  - Automatically updates `.collab/GROUP_CHAT.md` for human transparency.
- **File Reservation & Safe Writing**:
  - Cooperative file reservation leases (`ttl_seconds`).
  - Strict fingerprint matching (`expected_hash`) prevents silent overwrites of user or teammate changes.
- **Consensus & Evidence Verification**:
  - Proposal revisions bind modified file hashes, declared artifacts, acceptance criteria, and active review team members into a cryptographic digest.
  - Independent reviews require explicit verdicts and non-empty evidence.
  - Pre-declared test commands are executed with exit codes, bounded redacted outputs, and SHA-256 log hashes recorded to disk.
- **Guarded Team Finalization**:
  - Rejects completion until all assignments are finished, all blockers/help requests are resolved, independent reviews pass, all frozen members approve the exact digest, required artifacts exist, reservations are released, and test logs are verified intact on disk.

### 2.3 Command Interface (`collab.py` and `collab_operator.py`)
- **`collab.py`**:
  - Standard JSON-in / JSON-out CLI invoked by the host skill.
  - Accepts commands via `--input <file>` or stdin (`-`) to avoid shell quoting and process argument leaks.
- **`collab_operator.py`**:
  - Dedicated interactive human CLI for administrative interventions (e.g. replacing or excluding a disconnected required participant).
  - Enforces TTY verification, challenge phrase confirmation, and review invalidation.

## Installation lifecycle

The repository entry points and the portable skill installer delegate to `collablib/installer.py`. Installation defaults to the host user directory and verifies staged code before replacement. Persistent install locks and backups stay beside the installed user skill. Only the runtime `start` command creates a project `.collab`; all other commands refuse an uninitialized project. Project-edit staging is also contained in `.collab/tmp`, with atomic replacement limited to targets on the same filesystem.
