# COLLAB Installation & Setup Guide

COLLAB conforms to the open [Agent Skills Specification](https://agentskills.io/specification). It operates locally on your machine, requiring **Python 3.10+** and standard read/write filesystem permissions in the shared project directory.

Zero external infrastructure is required: no background daemons, local servers, cloud coordination APIs, databases, or Node.js runtime packages.

---

## 1. Install via Natural Language (Paste-to-Install)

The fastest and most natural way to install COLLAB is to paste the installation instruction directly into your coding agent's chat session.

### The Universal Prompt

Copy and paste this into **Claude Code, OpenAI Codex, Google Antigravity, Cursor, Gemini CLI, Kimi Code, or OpenCode**:

```text
https://github.com/NishidhJasani1605/Collab-Skill

Install the COLLAB skill from this GitHub repository. Detect my current AI coding environment, choose its supported Agent Skills installation method, install all required files, verify Python prerequisites, and confirm that COLLAB is available. Use `/collab` where supported or tell me the correct equivalent invocation.
```

### Quick Prompt

```text
https://github.com/NishidhJasani1605/Collab-Skill

Install this skill, then confirm /collab works.
```

### What Happens Behind the Scenes
When pasted into a capable coding agent with internet and filesystem tools:
1. The agent fetches or clones the `Collab-Skill` repository.
2. The agent executes the bundled `install.py` script or copies the skill folder into the appropriate directory.
3. The installer checks that Python 3.10+ is installed and that the OS supports file locks.
4. The installer copies the complete `skills/collab` directory (including `SKILL.md`, references, and Python engine).
5. The installer runs self-verification to ensure all scripts and modules are complete and valid.
6. The agent confirms installation and reports the exact activation command (e.g. `/collab` or `$collab`).

---

## 2. Using the Cross-Platform Python Installer (`install.py`)

COLLAB includes a pure standard-library installer (`install.py`) that works identically across Windows, macOS, and Linux without installing any third-party packages.

### Usage Examples

```bash
# Clone the repository
git clone https://github.com/NishidhJasani1605/Collab-Skill.git

# Install into current project (auto-detects agent environment)
python Collab-Skill/install.py

# Install globally in your user home directory (~/.agents/skills/collab or ~/.claude/skills/collab)
python Collab-Skill/install.py --global

# Install into a specific project directory
python Collab-Skill/install.py --project "/path/to/my-project"

# Explicitly target a specific agent platform
python Collab-Skill/install.py --platform claude --project "/path/to/my-project"

# Output JSON result (ideal for agent automation)
python Collab-Skill/install.py --json

# Verify an existing installation
python Collab-Skill/install.py --project "/path/to/my-project" --verify

# Cleanly uninstall COLLAB
python Collab-Skill/install.py --project "/path/to/my-project" --uninstall
```

### Installer CLI Flags

| Flag | Default | Description |
| --- | --- | --- |
| `--mode {project,global}` | `project` | Whether to install into the current project or user home directory. |
| `--global`, `-g` | `false` | Shorthand for `--mode global`. |
| `--platform {auto,claude,codex,antigravity,cursor,gemini,kimi,opencode,standard}` | `auto` | Target platform for path resolution. |
| `--project <path>` | Current dir | Target project directory when installing in project mode. |
| `--dest <path>` | Auto-resolved | Explicit destination directory (overrides platform resolution). |
| `--source <path>` | Auto-resolved | Explicit source skill directory containing `SKILL.md`. |
| `--no-backup` | `false` | Overwrite destination directly without creating a timestamped backup. |
| `--verify` | `false` | Run integrity verification on the target directory without modifying files. |
| `--uninstall` | `false` | Safely remove the installed skill from the target directory. |
| `--json` | `false` | Output machine-readable JSON status. |
| `--quiet`, `-q` | `false` | Suppress non-essential terminal messages. |

---

## 3. Manual Installation (File Copy)

If you prefer to copy the folder manually, place `skills/collab` into your agent's documented skills directory:

### Claude Code

```bash
git clone https://github.com/NishidhJasani1605/Collab-Skill.git

# Global installation (recommended for Claude Code):
cp -r Collab-Skill/skills/collab ~/.claude/skills/

# Project-local installation:
mkdir -p .claude/skills
cp -r Collab-Skill/skills/collab .claude/skills/
```

### Universal Agent Skills Standard (Codex, Antigravity, Cursor, Gemini CLI, OpenCode, Kimi Code)

```bash
git clone https://github.com/NishidhJasani1605/Collab-Skill.git

# Global installation:
cp -r Collab-Skill/skills/collab ~/.agents/skills/

# Project-local installation:
mkdir -p .agents/skills
cp -r Collab-Skill/skills/collab .agents/skills/
```

### Windows PowerShell

```powershell
git clone https://github.com/NishidhJasani1605/Collab-Skill.git

# Project-local installation:
New-Item -ItemType Directory -Force -Path ".agents\skills"
Copy-Item -Recurse -Force "Collab-Skill\skills\collab" ".agents\skills\collab"

# User-global installation:
$globalSkills = [System.IO.Path]::Combine($env:USERPROFILE, ".agents", "skills")
New-Item -ItemType Directory -Force -Path $globalSkills
Copy-Item -Recurse -Force "Collab-Skill\skills\collab" "$globalSkills\collab"
```

---

## 4. Install as a Claude Code / Antigravity Plugin

COLLAB provides a compliant `plugin.json` at the root of the repository, enabling native plugin installation:

```text
/plugin marketplace add NishidhJasani1605/Collab-Skill
/plugin install collab-skill@collab-skill
```

> [!NOTE]
> Claude Code namespaces skills installed via plugins, so it appears as `/collab-skill:collab`. If you prefer the clean `/collab` slash command, install via file copy (Method 2) or the installer script (Method 3).

---

## 5. Install via Agent Skills CLI (`npx skills`)

If you have Node.js and `npx` installed, you can use the official `skills` CLI:

```bash
npx skills add NishidhJasani1605/Collab-Skill
```

---

## 6. Target Directory & Activation Matrix

| Agent Host | Project Path | Global Path | Invocation Command |
| --- | --- | --- | --- |
| **Claude Code** | `.claude/skills/collab` | `~/.claude/skills/collab` | `/collab <task>` *(or `/collab-skill:collab` if plugin)* |
| **OpenAI Codex** | `.agents/skills/collab` | `~/.agents/skills/collab` | `$collab <task>` or select from `/skills` menu |
| **Google Antigravity** | `.agents/skills/collab` | `~/.gemini/antigravity/skills/collab` or `~/.agents/skills/collab` | `/collab <task>` |
| **Cursor** | `.agents/skills/collab` or `.cursor/skills/collab` | `~/.agents/skills/collab` or `~/.cursor/skills/collab` | `/collab <task>` or `@collab` |
| **Gemini CLI** | `.agents/skills/collab` or `.gemini/skills/collab` | `~/.gemini/skills/collab` or `~/.agents/skills/collab` | Ask: `Use collab skill: <task>` *(refresh with `/skills reload`)* |
| **Kimi Code CLI** | `.agents/skills/collab` | `~/.kimi/skills/collab` or `~/.agents/skills/collab` | `/skill:collab <task>` or `/collab <task>` |
| **OpenCode** | `.agents/skills/collab` | `~/.config/opencode/skills/collab` or `~/.agents/skills/collab` | `/collab <task>` |

---

## 7. Verification & Health Check

After installation, verify that the COLLAB runtime engine is functioning properly:

```bash
# Test the helper CLI directly
python .agents/skills/collab/scripts/collab.py --version
# Output: 1.0.0-beta.1

# Run the installer verification check
python Collab-Skill/install.py --verify

# Run the multi-process local collaboration simulation
python examples/two_agents.py
```

---

## 8. Backup, Rollback & Uninstallation

### Automatic Backups
Whenever `install.py` is executed against an existing COLLAB installation, it automatically creates a timestamped backup before modifying files:
```text
.agents/skills/
├── collab/                # Newly installed version
└── collab.bak.20261014T120000Z/   # Preserved previous version
```

To prevent backup creation during automated CI builds, pass `--no-backup`.

### Uninstallation
To cleanly remove COLLAB:
```bash
python Collab-Skill/install.py --uninstall
```
This removes the installed skill directory while safely preserving any existing backup directories for audit or rollback purposes.

---

## 9. Troubleshooting

### Skill is not visible after installation
- **Claude Code**: Run `/help` or start a new terminal session.
- **Gemini CLI**: Run `/skills reload` to refresh active skills.
- **Codex**: Type `/skills` to open the interactive skills selector.
- **Cursor / Antigravity**: Restart the editor window or open a new chat session to trigger workspace discovery.

### Python executable not found
COLLAB requires Python 3.10 or higher. Verify your Python version:
```bash
python --version   # or python3 --version, or py -3 --version
```
Ensure that Python is included in your system `PATH`.
