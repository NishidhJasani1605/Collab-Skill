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

## Install COLLAB — Paste into your AI coding agent

> [!TIP]
> **Clean Workspace Guarantee**: COLLAB installs globally into your user environment by default (`~/.claude/skills/`, `~/.agents/skills/`, etc.). It **never** pollutes your project directory with `.claude` or `.agents` folders at install time. The single `.collab/` coordination directory only appears when you actually trigger `/collab <task>` in that project.

### Method 1 — Paste into your AI coding agent (Recommended)

Copy and paste the block below into a compatible AI coding agent (**Claude Code**, **OpenAI Codex**, **Google Antigravity**, **Kimi Code**, **Cursor**, **Gemini CLI**, or **OpenCode**) that has internet/Git, local terminal, and filesystem permissions:

```text
https://github.com/NishidhJasani1605/Collab-Skill

Install the COLLAB skill from this GitHub repository. Detect my current AI coding environment, choose its supported Agent Skills installation method, install all required files, verify Python prerequisites, and confirm that COLLAB is available. Use `/collab` where supported or tell me the correct equivalent invocation.
```

> **Note**: Paste-to-install requires an AI coding agent with local shell and file-writing capabilities. A browser-only chat interface without local filesystem/terminal execution cannot install local skills. When prompted by your agent, review and approve the git clone / installer execution steps. Agents can follow the repository's [INSTALL.md](INSTALL.md) playbook to run `python3 scripts/install_collab.py`.

---

### Method 2 — Agent Skills CLI

If you have Node.js / `npx` installed, you can install COLLAB with the open [Agent Skills CLI](https://github.com/vercel-labs/skills):

```bash
# Install globally for your user account across all supported agents (keeps project clean)
npx skills add NishidhJasani1605/Collab-Skill --skill collab -g

# Or install specifically into the current project
npx skills add NishidhJasani1605/Collab-Skill --skill collab

# Install specifically for Claude Code or Codex (copy mode)
npx skills add NishidhJasani1605/Collab-Skill --skill collab -a claude-code -a codex --copy
```

---

### Method 3 — Manual installation

COLLAB requires **Python 3.10 or newer** (standard library only; zero `pip install` dependencies).

#### Cross-Platform Automated Installer (`scripts/install_collab.py` or `install.py`)

Clone the repository and run the bundled standard-library installer (defaults to global user scope so your project workspaces stay 100% clean):

**macOS / Linux:**

```bash
git clone https://github.com/NishidhJasani1605/Collab-Skill.git
python3 Collab-Skill/install.py

# Or install specifically into the current project (--local):
python3 Collab-Skill/install.py --local
```

**Windows (PowerShell):**

```powershell
git clone https://github.com/NishidhJasani1605/Collab-Skill.git
python .\Collab-Skill\install.py

# Or install specifically into the current project (--local):
python .\Collab-Skill\install.py --local
```

#### Direct Folder Copy (No Installer Script)

You can also copy `skills/collab` directly into your project's or home directory's skill folder:

```bash
# For Claude Code (project-local or user-global):
mkdir -p .claude/skills && cp -r collab/skills/collab .claude/skills/collab
mkdir -p ~/.claude/skills && cp -r collab/skills/collab ~/.claude/skills/collab

# For Codex, Antigravity, Kimi Code, Cursor, Gemini CLI, and OpenCode (project-local):
mkdir -p .agents/skills && cp -r collab/skills/collab .agents/skills/collab
```

---

### Method 4 — Optional platform-specific installation

#### Claude Code Plugin Marketplace (Optional)

The repository includes `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` for users who prefer Claude Code's `/plugin` manager:

```text
/plugin marketplace add NishidhJasani1605/Collab-Skill
/plugin install collab@collab
```

> **Important Namespace Difference**: Claude Code namespaces plugin skills, so installing via `/plugin` exposes the command as **`/collab:collab`** instead of plain **`/collab`**. If you want plain **`/collab`**, use **Method 1**, **Method 2**, or **Method 3** (which install the portable Agent Skill into `.claude/skills/collab` or `~/.claude/skills/collab`).

---

## Supported IDEs, Paths & Activation Syntax

Not every AI coding host uses identical slash-command syntax. Use the activation method supported by your host:

| Host / Agent | Project Skill Path | User-Global Skill Path | How to Activate | Refresh / Session Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Claude Code** | `.claude/skills/collab/` | `~/.claude/skills/collab/` | `/collab <task>` (or `/collab:collab` if installed as a plugin) | Available immediately or at session start |
| **OpenAI Codex** | `.agents/skills/collab/` | `~/.agents/skills/collab/` (`$CODEX_HOME/skills/collab`) | `$collab <task>` or select `collab` via `/skills` | Codex uses `$collab` or `/skills`, not `/collab` |
| **Google Antigravity** | `.agents/skills/collab/` | `~/.gemini/antigravity/skills/collab/` | `/collab <task>` (or ask agent to use `collab` skill) | Start a new session if installed while IDE is open |
| **Kimi Code CLI** | `.agents/skills/collab/` | `~/.kimi-code/skills/collab/` (`$KIMI_CODE_HOME/skills/collab`) | `/skill:collab <task>` | Uses `/skill:<name>` prefix |
| **Cursor** | `.agents/skills/collab/` (or `.cursor/skills/collab/`) | `~/.cursor/skills/collab/` | `/collab <task>` or select `collab` in Agent chat | Reload window or open a new chat if newly added |
| **Gemini CLI** | `.agents/skills/collab/` (or `.gemini/skills/collab/`) | `~/.gemini/skills/collab/` | Ask: `Use the collab skill: <task>` | Run `/skills reload` or `/skills list` to refresh |
| **OpenCode** | `.agents/skills/collab/` (or `.opencode/skills/collab/`) | `~/.config/opencode/skills/collab/` | `/collab <task>` | Enabled via `metadata.opencode/slash: "true"` |

---

## Upgrading, Uninstalling & Troubleshooting

### Project-Local vs. User-Global Scope
- **Project-local (`--scope project`, default)**: Installs into `.claude/skills/collab` and/or `.agents/skills/collab` inside a single repository. Ideal when testing or sharing skill configuration with teammates.
- **User-global (`--scope global`)**: Installs into your user home directory (`~/.claude/skills/collab`, `~/.agents/skills/collab`, etc.) so `/collab` is available across every project on your machine without modifying project repositories.

### Upgrading COLLAB
Re-run `python3 scripts/install_collab.py` (or `npx skills update collab`). When `install_collab.py` detects modified files in an existing `collab` skill directory, it automatically saves a timestamped backup under `.collab-backups/` before updating.

### Uninstalling COLLAB
Remove COLLAB cleanly without touching any other installed skills or user project files:

```bash
# Uninstall from current project
python3 scripts/install_collab.py --uninstall --target /path/to/your/project

# Uninstall from global user directories (and remove backups)
python3 scripts/install_collab.py --uninstall --scope global --purge-backups

# Or via Agent Skills CLI
npx skills remove collab
```

### Troubleshooting
- **Skill does not appear in `/` menu**: Verify the skill folder contains `SKILL.md` at the exact path in the table above, and run `/skills reload` (Gemini CLI), `/reload-plugins` (Claude Code plugins), or start a new agent session.
- **`PYTHON_VERSION_UNSUPPORTED`**: Ensure `python3 --version` (or `python --version` / `py -3 --version` on Windows) reports **Python 3.10+**.
- **`LOCK_TIMEOUT`**: Another process is actively holding `.collab/.lock` or hung. If a process terminated abnormally, the OS kernel automatically releases the lock handle.

---

## Key Features

- **Zero Infrastructure**: No Docker, no Redis, no local servers, no continuous background daemon, no cloud accounts, and no paid coordination APIs.
- **Single Universal Group Chat**: All agents read from and post to `.collab/GROUP_CHAT.jsonl` (authoritative) and `.collab/GROUP_CHAT.md` (readable transcript).
- **Process-Safe Concurrency**: Powered by OS-level file locking (`flock` on POSIX, byte-range locking on Windows) with a checksummed Write-Ahead Redo Journal (`checkpoints/pending.json`) and crash recovery. Tested with **100+ simultaneous processes with zero message loss or corruption**.
- **Dynamic Discovery**: Supports any number of participating agents without hardcoded limits or model vendor lock-in.
- **Conflict Prevention**: Temporary cooperative file reservations (`reserve`), base-hash verification, and atomic writes prevent silent overwrites.
- **The Golden Team Rule**: An agent finishing its own assignment **never** completes the team task. Finished agents stay active to review peer code, run tests, and help unblock teammates.
- **Guarded Finalization**: The shared task can only complete when all 9 gates are satisfied (assignments complete, independent reviews passing, checks verified on disk, required artifacts present, unanimous approval of the exact digest).
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

Run the full automated test suite (48 tests across 6 test modules covering storage concurrency, security, parameter aliases, packaging, and paste-to-install workflows):

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
