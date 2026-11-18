# Universal Host Compatibility

**COLLAB v2.1** is a **fast, 100% pure-Markdown Agent Skill** with **zero code dependencies** (no Python, no Node.js, no server, no OS-specific lock scripts). Any AI coding agent that can read Markdown files and read/write files in a shared local folder can participate in the same COLLAB team.

---

## Supported Coding Agents

| Coding Agent / Platform | Project Skill Path | User-Global Skill Path | Activation | Chat Messenger Mode |
| :--- | :--- | :--- | :--- | :--- |
| **Google Antigravity** (App / IDE) | `.agents/skills/collab/` | `~/.gemini/config/skills/collab/` | `/collab <task>` or ask to use `collab` | Native Sub-Agent (`Chat Messenger`) |
| **Google Antigravity CLI** | `.agents/skills/collab/` | `~/.gemini/antigravity-cli/skills/collab/` | `/collab <task>` | Native Sub-Agent (`Chat Messenger`) |
| **OpenAI Codex** (CLI / IDE / Desktop) | `.agents/skills/collab/` | `~/.agents/skills/collab/` or `$CODEX_HOME/skills/collab/` | `$collab <task>` or `/skills` | Native Sub-Agent (`Chat Messenger`) or Built-in Loop |
| **Claude Code** | `.claude/skills/collab/` | `~/.claude/skills/collab/` | `/collab <task>` (plugin: `/collab:collab`) | Native Sub-Agent (`Chat Messenger`) |
| **Cursor** | `.agents/skills/collab/` or `.cursor/skills/collab/` | `~/.cursor/skills/collab/` | `/collab <task>` or select in Agent chat | Native Sub-Agent or Built-in Loop |
| **Kimi Code** | `.agents/skills/collab/` or `.kimi-code/skills/collab/` | `~/.kimi-code/skills/collab/` | `/skill:collab <task>` | Native Sub-Agent or Built-in Loop |
| **DeepSeek** (via Cline, Roo Code, Continue, Aider, OpenCode, etc.) | `.agents/skills/collab/` (or host rules file) | `~/.agents/skills/collab/` | Reference `skills/collab/SKILL.md` | Native Sub-Agent (if host supports) or Built-in Loop |
| **Trae** | `.agents/skills/collab/` or `.trae/rules/` | `~/.agents/skills/collab/` | Ask to follow `collab` skill | Native Sub-Agent or Built-in Loop |
| **Windsurf** | `.agents/skills/collab/` or `.windsurf/rules/` | `~/.agents/skills/collab/` | Ask to follow `collab` skill | Native Sub-Agent or Built-in Loop |
| **Devin** | `.agents/skills/collab/` | Repository / workspace skill path | Ask to follow `skills/collab/SKILL.md` | Native Sub-Agent or Built-in Loop |
| **Gemini CLI** | `.agents/skills/collab/` or `.gemini/skills/collab/` | `~/.gemini/skills/collab/` | Ask to use `collab` skill | Native Sub-Agent or Built-in Loop |
| **OpenCode** | `.agents/skills/collab/` or `.opencode/skills/collab/` | `~/.config/opencode/skills/collab/` | `/collab <task>` or ask to use `collab` | Native Sub-Agent (`Chat Messenger`) |
| **GitHub Copilot** (Coding Agent / VS Code) | `.github/skills/collab/` or `.agents/skills/collab/` | `~/.agents/skills/collab/` | Reference `collab` skill in chat | Native Sub-Agent or Built-in Loop |
| **Any Other AI Coding Agent** | Point agent at `skills/collab/SKILL.md` | `~/.agents/skills/collab/` | *"Read and follow `skills/collab/SKILL.md`"* | Auto-selects Sub-Agent or Built-in Loop |

---

## Requirements for Any Team

1. **Same Physical Local Folder:** All participating agents must have read/write access to the **exact same local project directory** on disk so they read and write the same `<project-root>/.collab/` files. Separate remote clones or isolated cloud sandboxes cannot see each other's local `.collab/` folder.
2. **Same Skill Version:** Install COLLAB **v2.1** in every participating agent so all agents follow the same 3-file `.collab/` (`MEMBERS.md`, `CHAT.md`, `TASKS.md`) protocol, write-enabled `Chat Messenger` rules, and 5-column exit sign-off gate.
3. **Active Host Sessions:** COLLAB has no background OS daemon and cannot wake a closed IDE or an ended chat turn. Each agent's `Chat Messenger` stays active while its host session is running; if a host pauses or hits a turn limit, it posts a clear `PAUSED` message in `.collab/CHAT.md` and `Paused (resume needed)` in `.collab/MEMBERS.md` so you can resume cleanly.

---

## Mixing Different Models & Cost Tiers

COLLAB is **model-agnostic**. You can freely pair any combination of tools and models:
- **Fast/Low-Cost + High-Reasoning/High-Cost** (e.g., Antigravity + Gemini 3.8 Flash paired with Codex + GPT-6.2 Astra) → saves expensive model quota by assigning equal-capability work to the fast/low-cost model and complex reasoning to the stronger model.
- **Two Strong Specialist Models** (e.g., Claude Code + Codex, or Cursor + Antigravity) → splits domains cleanly (e.g., Frontend/UX vs. Backend/Security) with independent cross-review.
- **3+ Agents Together** → every additional agent adds its row to `.collab/MEMBERS.md`, joins `.collab/CHAT.md`, and claims work in `.collab/TASKS.md` without deleting anything.
