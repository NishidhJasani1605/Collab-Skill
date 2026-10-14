# COLLAB Installation & Setup Guide

COLLAB conforms to the open [Agent Skills Specification](https://agentskills.io/specification). It requires **Python 3.10+** installed on the local system and standard read/write permissions in the shared project directory.

No daemons, servers, cloud APIs, databases, or Node.js runtime packages are required during runtime.

---

## 1. Quick Installation via Package Manager

If your environment supports `npx skills`:

```bash
# Install into your project's .agents/skills directory
npx skills add <repository-url> --skill collab
```

---

## 2. Universal Local Installation (Any IDE / Agent)

You can install COLLAB into any local project repository by placing the `skills/collab` folder into the appropriate skills directory for your agent:

### 2.1 Standard Discovery Directory (`.agents/skills`)
Most modern coding agents (Codex, Antigravity, Cursor, Gemini CLI, OpenCode) discover skills in the project root's `.agents/skills` directory:

```bash
# Navigate to your target project folder
cd "path/to/your/project"

# Create the standard skills directory
mkdir -p .agents/skills

# Copy the collab skill directory
cp -r "path/to/COLLAB/skills/collab" .agents/skills/collab
```

On Windows PowerShell:
```powershell
New-Item -ItemType Directory -Force -Path ".agents\skills"
Copy-Item -Recurse -Force "path\to\COLLAB\skills\collab" ".agents\skills\collab"
```

---

## 3. Host-Specific Activation Cheat Sheet

| Host | Recommended Path | How to Activate | Notes |
| --- | --- | --- | --- |
| **OpenAI Codex** | `.agents/skills/collab` | `$collab <task>` or `/skills` selector | Codex mounts skills into `.agents/skills` |
| **Google Antigravity** | `.agents/skills/collab` | `/collab <task>` | Recognized as an agent skill slash command |
| **Claude Code** | `.claude/skills/collab` | `/collab <task>` | Place in `.claude/skills/` |
| **Cursor** | `.agents/skills/collab` or `.cursor/skills/collab` | `/collab <task>` | Discovered in workspace settings |
| **Gemini CLI** | `.agents/skills/collab` | Ask agent: `Use collab skill: <task>` | Reload skills with `/skills reload` |
| **Kimi Code CLI** | `.agents/skills/collab` | `/skill:collab <task>` | Follows Kimi CLI skill activation syntax |
| **OpenCode** | `.agents/skills/collab` | `/collab <task>` | Supports `metadata.opencode/slash` |

---

## 4. Verification

To verify that the COLLAB helper script runs properly in your environment:

```bash
# Test the helper version
python .agents/skills/collab/scripts/collab.py --version
# Output: 1.0.0-beta.1
```

To run a two-agent local simulation test verifying independent process communication:

```bash
python examples/two_agents.py
```
