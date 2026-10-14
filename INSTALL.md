# COLLAB — Agent-Executable Installation Playbook (`INSTALL.md`)

If a user pasted the COLLAB repository URL and asked you (an AI coding agent) to install **COLLAB**, follow these exact, non-destructive steps using your local terminal and filesystem tools.

> **Important Security & Honesty Rules for the Installing Agent**
> 1. Never download or pipe unreviewed remote shell scripts. Only clone or copy from the repository URL explicitly provided by the user.
> 2. Ask the user for permission if your host requires confirmation for cloning a repository, running `python scripts/install_collab.py` (or `python install.py`), or writing to `~/.claude/skills` / `~/.agents/skills` / project skill folders.
> 3. Do not claim `/collab` works as a slash command if you are running inside a host that uses a different invocation syntax (such as `$collab` in OpenAI Codex or `/skill:collab` in Kimi Code CLI). Report the exact activation command for your host.

---

## Step 1: Verify Python 3.10+ Prerequisite

Run one of the following in the user's terminal to locate Python 3.10 or newer:

```bash
python3 --version || python --version || py -3 --version
```

If Python 3.10+ is not installed, stop and explain that COLLAB requires Python 3.10 or newer (standard library only; no `pip install` packages required).

---

## Step 2: Obtain the Repository and Run the Built-In Installer

### Option A: Automated Cross-Platform Installer (Recommended)

Clone the repository to a unique temporary directory and run `install.py` (or `scripts/install_collab.py`). By default, it installs **globally** into the user's environment so that project workspaces remain 100% clean and free of `.claude/` or `.agents/` folders:

On POSIX (Linux / macOS):
```bash
# 1. Clone the repository into a unique temporary folder
TMP_DIR=$(mktemp -d /tmp/collab-install.XXXXXX)
git clone https://github.com/NishidhJasani1605/Collab-Skill.git "$TMP_DIR"

# 2. Run the standard-library installer (defaults to global scope, keeping project clean)
python3 "$TMP_DIR/scripts/install_collab.py" --json

# 3. Clean up the temporary clone
rm -rf "$TMP_DIR"
```

On Windows PowerShell:
```powershell
# 1. Clone into a unique temporary directory
$Tmp = Join-Path $env:TEMP ("collab-install-" + [System.Guid]::NewGuid().ToString("N"))
git clone https://github.com/NishidhJasani1605/Collab-Skill.git $Tmp

# 2. Run the standard-library installer (defaults to global scope, keeping project clean)
python "$Tmp\scripts\install_collab.py" --json

# 3. Clean up the temporary clone
Remove-Item -Recurse -Force $Tmp
```

- **Global Scope (Default)**: Installs into user home directories (`~/.claude/skills`, `~/.agents/skills`, etc.). No folders are created in the project workspace at install time. When `/collab` is activated, only `.collab/` appears in the project.
- **Project-Local Scope**: If the user explicitly asks to install into the current project, pass `--local` (or `--scope project`).
- To install for a specific host explicitly: pass `--agent claude-code`, `--agent codex`, `--agent antigravity`, `--agent kimi-code`, `--agent cursor`, `--agent gemini-cli`, `--agent opencode`, or `--agent all`.
- Existing COLLAB installations are automatically backed up to `.collab-backups/` before updating, and unrelated skills are never touched.
- Uninstallation strictly verifies installation markers before removing any files, preventing accidental deletion of unrelated folders.

### Option B: Agent Skills CLI (`npx skills`)

If Node.js / `npx` is available and preferred:

```bash
npx skills add NishidhJasani1605/Collab-Skill --skill collab --copy -y
```

---

## Step 3: Verify the Installed Skill

Verify that the installed helper executes cleanly and prints its version (`1.0.0-beta.1`):

```bash
# For Claude Code project installations:
python3 .claude/skills/collab/scripts/collab.py --version

# For .agents/skills installations (Codex, Antigravity, Cursor, Kimi Code, Gemini CLI, OpenCode):
python3 .agents/skills/collab/scripts/collab.py --version
```

---

## Step 4: Report the Exact Activation Command to the User

Confirm installation success and tell the user how to activate COLLAB in their current environment:

| Environment | Project Path | Global Path | User Activation Command |
| :--- | :--- | :--- | :--- |
| **Claude Code** | `.claude/skills/collab/` | `~/.claude/skills/collab/` | `/collab <task>` (or `/collab:collab <task>` if installed via `/plugin`) |
| **OpenAI Codex** | `.agents/skills/collab/` | `~/.agents/skills/collab/` | `$collab <task>` or select `collab` via `/skills` |
| **Google Antigravity** | `.agents/skills/collab/` | `~/.gemini/antigravity/skills/collab/` | `/collab <task>` (or ask the agent to use the `collab` skill in standalone IDE surfaces) |
| **Kimi Code CLI** | `.agents/skills/collab/` | `~/.kimi-code/skills/collab/` | `/skill:collab <task>` |
| **Cursor** | `.agents/skills/collab/` | `~/.cursor/skills/collab/` | `/collab <task>` or select `collab` in Agent chat |
| **Gemini CLI** | `.agents/skills/collab/` | `~/.gemini/skills/collab/` | Ask: `Use the collab skill: <task>` (run `/skills reload` if installed mid-session) |
| **OpenCode** | `.agents/skills/collab/` | `~/.config/opencode/skills/collab/` | `/collab <task>` |
