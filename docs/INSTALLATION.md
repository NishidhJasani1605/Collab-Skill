# COLLAB Installation, Upgrade & Uninstall Guide

COLLAB conforms to the open [Agent Skills Specification](https://agentskills.io/specification). It requires **Python 3.10+** (standard library only) and standard read/write permissions in the shared project directory.

No daemons, servers, cloud APIs, databases, MCP servers, or runtime `pip` packages are required.

---

## Method 1 — Paste into your AI coding agent (Recommended)

Paste the following block into any compatible AI coding agent (**Claude Code**, **OpenAI Codex**, **Google Antigravity**, **Kimi Code**, **Cursor**, **Gemini CLI**, or **OpenCode**) that has Git/network, local terminal, and filesystem access:

```text
https://github.com/NishidhJasani1605/Collab-Skill

Install the COLLAB skill from this GitHub repository. Detect my current AI coding environment, choose its supported Agent Skills installation method, install all required files, verify Python prerequisites, and confirm that COLLAB is available. Use `/collab` where supported or tell me the correct equivalent invocation.
```

### What happens when you paste this:
1. Your coding agent reads `README.md` / `INSTALL.md` from the repository.
2. It verifies that **Python 3.10+** is available on your machine.
3. It runs `python3 scripts/install_collab.py` (or `npx skills add`), which auto-detects your active coding environment and copies the complete `skills/collab/` directory (`SKILL.md`, `scripts/`, `references/`) to the official skill path.
4. It runs `collab.py --version` to verify installation integrity and reports the exact activation command for your host.

> **Important**: Browser-only chat interfaces without local filesystem and shell tool access cannot install local skills. Your coding agent may prompt you to approve cloning the repository and writing to `.claude/skills` or `.agents/skills`.

---

## Method 2 — Agent Skills CLI (`npx skills`)

If Node.js is installed, use the [Agent Skills CLI (`vercel-labs/skills`)](https://github.com/vercel-labs/skills):

```bash
# Project-local install (default)
npx skills add NishidhJasani1605/Collab-Skill --skill collab

# Global install across your user profile
npx skills add NishidhJasani1605/Collab-Skill --skill collab -g

# Non-interactive copy install for specific agents
npx skills add NishidhJasani1605/Collab-Skill --skill collab -a claude-code -a codex -a cursor --copy -y
```

---

## Method 3 — Cross-Platform Manual Installation

### 3.1 Using the Bundled Python Installer (`scripts/install_collab.py`)

`scripts/install_collab.py` uses only the Python 3.10+ standard library and supports Windows, Linux, and macOS:

```bash
# Auto-detect current environment and install into a project
python3 scripts/install_collab.py --target /path/to/your/project

# Install for all supported agents in project scope (.claude/skills/collab and .agents/skills/collab)
python3 scripts/install_collab.py --scope project --agent all --target /path/to/your/project

# Install globally for your user account across all supported agents
python3 scripts/install_collab.py --scope global --agent all

# Install globally for a single specific agent (e.g., Claude Code or Kimi Code)
python3 scripts/install_collab.py --scope global --agent claude-code
```

On Windows PowerShell:

```powershell
python .\scripts\install_collab.py --target "C:\path\to\your\project"
python .\scripts\install_collab.py --scope global --agent all
```

### 3.2 Direct Folder Copy

Copy `skills/collab` directly into the target directory:

**macOS / Linux:**
```bash
# Claude Code (project or global)
mkdir -p .claude/skills && cp -r /path/to/collab/skills/collab .claude/skills/collab
mkdir -p ~/.claude/skills && cp -r /path/to/collab/skills/collab ~/.claude/skills/collab

# Codex, Antigravity, Kimi Code, Cursor, Gemini CLI, OpenCode (project)
mkdir -p .agents/skills && cp -r /path/to/collab/skills/collab .agents/skills/collab
```

**Windows PowerShell:**
```powershell
New-Item -ItemType Directory -Force -Path ".claude\skills" | Out-Null
Copy-Item -Recurse -Force "C:\path\to\collab\skills\collab" ".claude\skills\collab"

New-Item -ItemType Directory -Force -Path ".agents\skills" | Out-Null
Copy-Item -Recurse -Force "C:\path\to\collab\skills\collab" ".agents\skills\collab"
```

---

## Method 4 — Optional Claude Code Plugin Installation

For Claude Code users who want to manage skills through `/plugin`:

```text
/plugin marketplace add NishidhJasani1605/Collab-Skill
/plugin install collab@collab
```

- **Command Namespacing**: Claude Code prefixes plugin skills with the plugin name, so installing via `/plugin` exposes **`/collab:collab`** instead of **`/collab`**.
- To use plain **`/collab`**, install the skill directory into `.claude/skills/collab` or `~/.claude/skills/collab` via Methods 1–3.

---

## Host-Specific Paths & Activation Reference

| Host | Project Path | Global Path | Activation Command |
| :--- | :--- | :--- | :--- |
| **Claude Code** | `.claude/skills/collab` | `~/.claude/skills/collab` | `/collab <task>` (or `/collab:collab` via plugin) |
| **OpenAI Codex** | `.agents/skills/collab` | `~/.agents/skills/collab` (`$CODEX_HOME/skills/collab`) | `$collab <task>` or `/skills` selector |
| **Google Antigravity** | `.agents/skills/collab` | `~/.gemini/antigravity/skills/collab` | `/collab <task>` (or ask agent to use `collab` skill) |
| **Kimi Code CLI** | `.agents/skills/collab` | `~/.kimi-code/skills/collab` (`$KIMI_CODE_HOME/skills/collab`) | `/skill:collab <task>` |
| **Cursor** | `.agents/skills/collab` | `~/.cursor/skills/collab` | `/collab <task>` or select `collab` in Agent chat |
| **Gemini CLI** | `.agents/skills/collab` | `~/.gemini/skills/collab` | Ask: `Use the collab skill: <task>` (`/skills reload`) |
| **OpenCode** | `.agents/skills/collab` | `~/.config/opencode/skills/collab` | `/collab <task>` |

---

## Verification, Upgrades & Uninstallation

### Verify Installation
```bash
# Verify source package and Python prerequisite
python3 scripts/install_collab.py --verify-only

# Verify installed helper directly
python3 .agents/skills/collab/scripts/collab.py --version
# Output: 1.0.0-beta.1

# Run two-agent subprocess communication test
python3 examples/two_agents.py
```

### Safe Reinstallation & Upgrades
Running `python3 scripts/install_collab.py` over an existing installation:
- Compares SHA-256 digests of all skill files.
- Reports `up_to_date` if files are identical.
- Automatically backs up the previous `collab` folder to `.collab-backups/collab-<timestamp>` before applying updates (`--no-backup` disables backup creation).
- Never modifies or deletes sibling skills in `.claude/skills/` or `.agents/skills/`.

### Uninstalling COLLAB
```bash
# Remove from project
python3 scripts/install_collab.py --uninstall --target /path/to/your/project

# Remove from global directories and delete backups
python3 scripts/install_collab.py --uninstall --scope global --purge-backups
```
Uninstalling removes only the `collab` skill folder; it never deletes user project files or `.collab/` task history.
