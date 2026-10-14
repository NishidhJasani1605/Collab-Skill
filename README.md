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
- **Claude Code**
- **OpenAI Codex**
- **Google Antigravity**
- **Kimi Code**
- **Cursor**
- **Gemini CLI**
- **OpenCode**
- Any compatible agent supporting the [Agent Skills standard](https://agentskills.io/specification)

Activate `/collab <task>` (or the host-equivalent invocation) in each agent. They discover each other, divide assignments, exchange findings in one shared group conversation, help each other when blocked, review each other's code with reproducible evidence, and collectively reach one verified conclusion.

---

## Install COLLAB

Installation puts the complete skill in your coding app's **user-level skill directory**. It creates no COLLAB folders in your project. After you explicitly invoke collaboration, the helper creates a single `.collab/` directory for shared chat, tasks, locks, logs, and reports. Each participating agent uses that same directory. Project deliverables stay in their intended locations.

### Method 1 — Paste into your coding agent

```text
https://github.com/NishidhJasani1605/Collab-Skill

Install the COLLAB skill from this GitHub repository. Detect my current AI coding environment, choose its supported Agent Skills installation method, install all required files, verify Python prerequisites, and confirm that COLLAB is available. Use `/collab` where supported or tell me the correct equivalent invocation. Install at user scope, keep the project unchanged, and create .collab only when I explicitly start collaboration.
```

The original shorter prompt also uses these defaults. Agents should follow [INSTALL.md](INSTALL.md). Local shell and filesystem access are required. Verification checks the package and helper; host discovery should be confirmed through the host's skill list when available.

### Method 2 — Agent Skills CLI

With Node.js available, use the [Agent Skills CLI](https://github.com/vercel-labs/skills). Keep `-g` to install at user scope and `--copy` for copies compatible with the bundled updater:

```bash
npx skills add NishidhJasani1605/Collab-Skill --skill collab -g --copy
# To target Codex specifically:
npx skills add NishidhJasani1605/Collab-Skill --skill collab -g -a codex --copy
```

Python 3.10+ is still required to run COLLAB. Third-party installers manage their own paths and update behavior; the bundled Python installer provides the tested lifecycle below.

### Method 3 — Bundled Python installer

Use Python 3.10+; no runtime packages are required. Clone into a temporary directory outside your project, following the [platform-specific commands](INSTALL.md#obtain-and-install). From an existing checkout:

```bash
python install.py --global --agent codex --json
# Or select another host; omit --agent to detect the environment.
python install.py --global --agent claude-code --json
```

`install.py`, `scripts/install_collab.py`, and the portable `skills/collab/scripts/install.py` all use one implementation. All default to user scope. Active-host environment markers take priority over installed-host directories. If detection is ambiguous, specify `--agent`; `--agent all` explicitly installs for every listed host.

### Method 4 — Claude Code plugin

```text
/plugin marketplace add NishidhJasani1605/Collab-Skill
/plugin install collab@collab
```

Select user scope in the host. Plugin installation exposes `/collab:collab`; standalone skill installation exposes `/collab`.

## Cross-IDE completion (beta.2)

When asking Codex and Antigravity to work together, name both IDEs and the same
absolute project root in each activation. The skill registers each real session,
reuses the existing task, and declares `expected_platforms: ["codex", "antigravity"]`.
Two Codex identities cannot satisfy that requirement. Required late joins restart
review; unavailable teammates leave an honest pending checkpoint.

See the [short two-IDE verification procedure](docs/TWO_IDE_VERIFICATION.md) and
[recorded automated evidence](docs/VALIDATION_REPORT.md). Automated client
simulations are not live Codex–Antigravity tests. Update both installed helpers
before testing; package verification now exercises registration in a disposable
workspace without initializing your project.

## Activation

| Host | User invocation |
| --- | --- |
| Claude Code | `/collab <task>`; plugin: `/collab:collab <task>` |
| Codex | `$collab <task>` or select through `/skills` |
| Antigravity App / CLI | `/collab <task>` |
| Antigravity IDE | Ask to use the `collab` skill |
| Kimi Code | `/skill:collab <task>` |
| Cursor | `/collab <task>` |
| Gemini CLI | `Use the collab skill: <task>` |
| OpenCode | `/collab <task>` where supported, or ask to use `collab` |

See [documented paths and host limitations](docs/COMPATIBILITY.md). Refresh skills or restart the host if needed. Installation, explanation, and maintenance requests do not start collaboration. Explicit invocation settings are supplied for Codex, Claude Code, Cursor, Kimi, and OpenCode; other hosts follow the skill's activation instructions.

## Updates and removal

Re-run the installer for the same `--agent`. Identical copies are verified without rewriting them. Changed copies are staged and checked before replacement, with a backup under the user-level skills directory. Updates and removals refuse unrecognized or linked destinations. Keep installations from one package manager under that manager's control.

```bash
python install.py --global --agent codex --uninstall
```

Removal preserves project files, `.collab` history, other skills, and backups. `--purge-backups` additionally removes recognized COLLAB backups. See [installation and recovery](docs/INSTALLATION.md) for explicit project-scope compatibility, legacy cleanup, and recovery after interrupted updates.

---

## Key Features

- **Zero Infrastructure**: No Docker, no Redis, no local servers, no continuous background daemon, no cloud accounts, and no paid coordination APIs.
- **Single Universal Group Chat**: All agents read from and post to `.collab/GROUP_CHAT.jsonl` (authoritative) and `.collab/GROUP_CHAT.md` (readable transcript).
- **Process-Safe Concurrency**: Powered by OS-level file locking (`flock` on POSIX, byte-range locking on Windows) with a checksummed Write-Ahead Redo Journal (`checkpoints/pending.json`) and crash recovery. Tested with **100+ simultaneous processes with zero message loss or corruption**.
- **Dynamic Discovery**: Discovers participants through shared project state without model vendor lock-in. State and history grow with the team; use bounded local tasks.
- **Conflict Prevention**: Temporary cooperative file reservations (`reserve`), base-hash verification, and atomic writes prevent silent overwrites.
- **The Golden Team Rule**: An agent finishing its own assignment **never** completes the team task. Finished agents stay active to review peer code, run tests, and help unblock teammates.
- **Guarded Finalization**: The shared task can only complete when all declared completion gates are satisfied (assignments complete, independent reviews passing, checks verified on disk, required artifacts present, unanimous approval of the exact digest).
- **Human Operator Control**: Emergency recovery CLI (`collab_operator.py`) allows human users to reassign or exclude disconnected agents via interactive terminal challenge verification.

---

## Project Runtime Layout

When agents collaborate in your project, COLLAB creates a `.collab/` folder (automatically ignored by Git via `.collab/.gitignore`):

```text
your-project/
├── (user project files...)
│
└── .collab/
    ├── .lock                     # Persistent kernel lock file
    ├── .gitignore                # Ignores all runtime state from public Git commits
    ├── config.json               # Protocol & workspace configuration
    ├── agents.json               # Registered agent roster & statuses
    ├── tasks.json                # Shared tasks, assignments, issues, proposals
    ├── progress.json             # Aggregate task progress & milestone metrics
    │
    ├── GROUP_CHAT.jsonl          # Authoritative hash-chained append-only event stream
    ├── GROUP_CHAT.md             # Human-readable live group transcript
    │
    ├── checkpoints/
    │   ├── state.json            # Checksummed authoritative state snapshot
    │   ├── pending.json          # Transient Write-Ahead Redo Journal (during commits)
    │   └── *.log / *.json        # Check evidence logs & agent session checkpoints
    ├── tmp/                      # Temporary project-edit staging
    ├── findings/                 # Structured finding records
    ├── reviews/                  # Independent review records
    ├── decisions/                # Proposal revisions & final task reports
    └── FINAL_REPORT.md           # Comprehensive team completion report
```

---

## Verifying Local Communication & Running Tests

Test independent multi-process communication with the bundled simulation script:

```bash
python3 examples/two_agents.py
```

Run the full automated test suite covering storage concurrency, security, parameter aliases, packaging, installation, activation, and check execution:

```bash
# Run with Python's built-in unittest (zero external dependencies)
python3 -m unittest discover -s tests -v

# Or run with pytest if installed
python3 -m pytest -v
```

---

## Documentation

- [INSTALL.md](INSTALL.md) — Step-by-step agent playbook for paste-to-install execution.
- [INSTALLATION.md](docs/INSTALLATION.md) — Detailed host-by-host installation, update, and uninstall guide.
- [COMPATIBILITY.md](docs/COMPATIBILITY.md) — Supported platforms, IDE discovery mechanisms, and operational bounds.
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — Technical architecture, storage engine, WAL, and concurrency model.
- [PROTOCOL.md](docs/PROTOCOL.md) — Wire format, event schemas, state machines, and consensus rules.
- [VALIDATION_REPORT.md](docs/VALIDATION_REPORT.md) — Benchmark results, high-concurrency stress tests, and defect fixes.
- [Command Reference](skills/collab/references/commands.md) — Internal JSON CLI command specification.
- [Safety & Recovery](skills/collab/references/safety.md) — Lock semantics, crash recovery, and security model.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
