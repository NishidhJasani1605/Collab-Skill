# COLLAB

**Universal, Local-Only, Multi-Agent Collaboration Skill for AI Coding Assistants**

[![CI](https://github.com/NishidhJasani1605/Collab-Skill/actions/workflows/ci.yml/badge.svg)](https://github.com/NishidhJasani1605/Collab-Skill/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Agent Skills Specification](https://img.shields.io/badge/Agent_Skills-Compliant-green.svg)](https://agentskills.io/specification)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)

---

## What is COLLAB?

**COLLAB** (`/collab`) is a universal, filesystem-based collaboration skill that allows multiple AI coding agents—running across different IDEs, terminals, and model providers—to coordinate in the **same physical workspace folder**.

Think of it as a **WhatsApp group chat connected to an atomic task coordinator** for AI agents.

Open the same repository folder in:
- **OpenAI Codex**
- **Google Antigravity**
- **Claude Code**
- **Cursor**
- **Gemini CLI**
- **Kimi Code**
- **OpenCode**
- Any future agent complying with the [Agent Skills standard](https://agentskills.io/specification)

Activate `/collab <task>` in each agent. They discover each other, divide assignments, exchange findings in one shared group conversation, help each other when blocked, review each other's code with reproducible evidence, and collectively reach one verified conclusion.

---

## Key Features

- **Zero Infrastructure**: No Docker, no Redis, no local servers, no continuous background daemon, no cloud accounts, and no paid coordination APIs.
- **Single Universal Group Chat**: All agents read from and post to `.collab/GROUP_CHAT.jsonl` (authoritative) and `.collab/GROUP_CHAT.md` (readable transcript).
- **Process-Safe Concurrency**: Powered by OS-level file locking (`flock` on POSIX, byte-range locking on Windows) with Write-Ahead Logging (WAL) and crash recovery. Tested with **100+ simultaneous processes with zero message loss or corruption**.
- **Dynamic Discovery**: Supports any number of participating agents without hardcoded limits or model vendor lock-in.
- **Conflict Prevention**: Temporary cooperative file reservations (`reserve`), base-hash verification, and atomic writes prevent silent overwrites.
- **The Golden Team Rule**: An agent finishing its own assignment **never** completes the team task. Finished agents stay active to review peer code, run tests, and help unblock teammates.
- **Guarded Finalization**: The shared task can only complete when all 9 gates are satisfied (assignments complete, independent reviews passing, checks verified on disk, unanimous approval of the exact digest).
- **Human Operator Control**: Emergency recovery CLI (`collab_operator.py`) allows human users to reassign or exclude disconnected agents via interactive terminal challenge verification.

---

## Project Runtime Layout

When agents collaborate in your project, COLLAB creates a `.collab/` folder:

```text
your-project/
├── (user project files...)
│
└── .collab/
    ├── config.json               # Task configuration & gates
    ├── agents.json               # Registered agent roster & statuses
    ├── tasks.json                # Shared tasks, assignments, issues
    ├── progress.json             # Aggregate milestones
    │
    ├── GROUP_CHAT.jsonl          # Authoritative append-only event stream
    ├── GROUP_CHAT.md             # Human-readable live group transcript
    │
    ├── wal.jsonl                 # Write-Ahead Log for crash resilience
    ├── locks/store.lock          # Kernel byte-range lock file
    ├── checkpoints/              # Checkpoint logs & test evidence
    ├── decisions/                # Signed proposal digests & reviews
    └── FINAL_REPORT.md           # Comprehensive team completion report
```

---

## Quick Start

### 1. Installation

Install into your target project using `npx skills`:

```bash
npx skills add <repository-url> --skill collab
```

Or manually copy `skills/collab` into `.agents/skills/collab`:

```bash
mkdir -p .agents/skills
cp -r /path/to/COLLAB/skills/collab .agents/skills/collab
```

*See [INSTALLATION.md](docs/INSTALLATION.md) for host-specific details.*

### 2. Activation

In each of your AI agent sessions (e.g. Codex, Antigravity, Claude Code), invoke:

```text
/collab Analyze this project, identify issues, collaborate with teammates, verify fixes, and produce the final report.
```

That is all the user needs to do. COLLAB automatically:
1. Discovers the shared project directory.
2. Registers each agent and joins the shared task.
3. Loads team context and posts an introduction.
4. Coordinates assignments, file edits, help requests, and reviews.
5. Produces `.collab/FINAL_REPORT.md` upon verified completion.

---

## Verifying Local Communication

You can test independent multi-process communication right now with the bundled simulation script:

```bash
python examples/two_agents.py
```

This launches two independent OS processes that discover each other, exchange messages, and update `GROUP_CHAT.jsonl` and `GROUP_CHAT.md`.

---

## Running the Automated Test Suite

COLLAB includes a rigorous test suite covering concurrent processes, lock recovery, path traversal security, and multi-agent consensus:

```bash
# Run with pytest
python -m pytest -v

# Or run with Python's built-in unittest
python -m unittest discover -s tests
```

*All 34 test cases pass with 100% compliance. See [VALIDATION_REPORT.md](docs/VALIDATION_REPORT.md).*

---

## Documentation

- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — Technical architecture, storage engine, WAL, and concurrency model.
- [PROTOCOL.md](docs/PROTOCOL.md) — Wire format, event schemas, state machines, and consensus rules.
- [INSTALLATION.md](docs/INSTALLATION.md) — Detailed host-by-host installation guide.
- [COMPATIBILITY.md](docs/COMPATIBILITY.md) — Supported platforms, IDE discovery mechanisms, and operational bounds.
- [VALIDATION_REPORT.md](docs/VALIDATION_REPORT.md) — Benchmark results, high-concurrency stress tests, and defect fixes.
- [Command Reference](skills/collab/references/commands.md) — Internal JSON CLI command specification.
- [Safety & Recovery](skills/collab/references/safety.md) — Lock semantics, crash recovery, and security model.

---

## Security & Privacy

- **100% Local**: No network requests are made by COLLAB. Your project code and conversation never leave your machine.
- **Untrusted Message Sandboxing**: Teammate chat messages are strictly treated as untrusted data. Commands are never blindly executed from chat.
- **Path Escape Protection**: Path operations are strictly validated against directory traversal and symlink escapes.
- **Interactive Human Intervention**: Required membership changes cannot be automated by agents; they require an interactive human terminal challenge.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
