# Compatibility

Evidence checked: 2026-10-14. Every participant must have local shell execution, Python 3.10+, and read/write access to the **same physical project directory**. Separate remote clones are separate teams. The model provider is not part of COLLAB's protocol.

## Host installation and activation

The paths below are relative to the project root (or user home directory `~` for global scope) and contain the complete `collab` directory (`SKILL.md`, `scripts/`, `references/`). These are official documented discovery paths verified against vendor documentation and the `vercel-labs/skills` registry, not claims of unassisted live IDE execution. New Antigravity installations use `~/.gemini/config/skills/`; older installed paths must be checked in the specific host catalog rather than assumed discoverable.

| Host | Project skill directory | User-global skill directory | Activation after discovery | Evidence |
| :--- | :--- | :--- | :--- | :--- |
| **Claude Code** | `.claude/skills/collab/` | `~/.claude/skills/collab/` | `/collab <task>` (or `/collab:collab <task>` when installed as a plugin via `.claude-plugin/`) | [Claude Code skills](https://code.claude.com/docs/en/skills), [Claude Code plugins](https://code.claude.com/docs/en/plugins/overview) |
| **OpenAI Codex** (CLI / IDE / Desktop) | `.agents/skills/collab/` | `~/.agents/skills/collab/` (or `$CODEX_HOME/skills/collab/`) | `$collab <task>` or select through `/skills`; plain `/collab` is not promised | [Official OpenAI documentation](https://learn.chatgpt.com/docs/build-skills) |
| **Google Antigravity** (App / IDE) | `.agents/skills/collab/` | `~/.gemini/config/skills/collab/` | `/collab <task>` in the App; or ask the agent to use the `collab` skill in standalone IDE surfaces | [Antigravity skills](https://antigravity.google/docs/skills/) |
| **Google Antigravity CLI** | `.agents/skills/collab/` | `~/.gemini/antigravity-cli/skills/collab/` | `/collab <task>` | [Antigravity CLI skills](https://antigravity.google/docs/skills/) |
| **Kimi Code CLI** | `.agents/skills/collab/` (or `.kimi-code/skills/collab/`) | `~/.kimi-code/skills/collab/` (or `$KIMI_CODE_HOME/skills/collab/`, `~/.agents/skills/collab/`) | `/skill:collab <task>` | [Kimi skills](https://www.kimi.com/code/docs/en/kimi-code-cli/customization/skills.html) |
| **Cursor** | `.agents/skills/collab/` (or `.cursor/skills/collab/`) | `~/.cursor/skills/collab/` | `/collab <task>` or select the `collab` skill in Agent chat (Cursor also reads `.claude/skills/`) | [Cursor skills](https://cursor.com/docs/skills) |
| **Gemini CLI** | `.agents/skills/collab/` (or `.gemini/skills/collab/`) | `~/.gemini/skills/collab/` | Ask to use `collab`; accept the host's skill activation prompt. `/skills list` and `/skills reload` manage discovery | [Gemini skills](https://geminicli.com/docs/cli/skills/) |
| **OpenCode** | `.agents/skills/collab/` (or `.opencode/skills/collab/`) | `~/.config/opencode/skills/collab/` | `/collab <task>` on versions supporting `metadata.opencode/slash`; otherwise ask to use `collab` | [OpenCode skills](https://opencode.ai/docs/skills/) |
| **DeepSeek-based or other hosts** | `.agents/skills/collab/` (or host-specific) | `~/.agents/skills/collab/` | Host-specific: must load Agent Skills (`SKILL.md`) and allow local Python execution | [Agent Skills specification](https://agentskills.io/specification) |

The bundled cross-platform installer (`scripts/install_collab.py`) defaults to `--scope global`; `--scope project` is an explicit compatibility option. It supports automatic environment detection (`--agent auto`), single-platform targeting (`--agent claude-code`, `--agent codex`, etc.), and multi-platform installation (`--agent all`). Skills are instructions: the host still controls execution permissions, context lifetime, and user interaction. COLLAB does not bypass host consent.

## What is verified

- Official vendor documentation and the `vercel-labs/skills` agent registry confirm the project and global discovery paths and activation syntax above.
- `scripts/install_collab.py` is tested across simulated project and global installations, paths with spaces, environment auto-detection, idempotent reinstalls, backup-on-update, missing/unsupported Python handling, and safe uninstallation (`tests/test_installer.py`).
- Cross-process simulations exercise independent Python processes communicating between `.claude/skills/collab` and `.agents/skills/collab` installations (`tests/test_installer.py`, `tests/test_integration.py`, `examples/two_agents.py`). They do not claim live interactive GUI automation of commercial IDEs.

## Operational limits

COLLAB is designed for a cooperating team on a local filesystem. It has no hosted transport, daemon, automatic IDE wake-up, or access to private native chats. Each active agent explicitly publishes messages and polls at checkpoints. A suspended agent cannot respond until its host resumes it.

Native Windows and native POSIX implementations use different OS locking primitives. Sharing one state directory between native Windows and WSL processes, through network mounts, or through cloud-sync tools is unverified and unsupported for v1. Use one execution environment and local volume for a team. Sandboxed or remote agents that cannot access that directory cannot participate.

## Explicit activation

COLLAB ships Codex `agents/openai.yaml` with implicit invocation disabled, `disable-model-invocation: true` for [Claude Code](https://code.claude.com/docs/en/skills), [Cursor](https://cursor.com/docs/skills), and [Kimi](https://www.kimi.com/code/docs/en/kimi-code-cli/customization/skills.html), and `metadata.opencode/autoinvoke: "false"` for [OpenCode](https://opencode.ai/docs/skills/). Other hosts must follow the explicit-start instruction in SKILL.md; the Python runtime cannot prove what a human typed into a host. Package installation never initializes the user project; its registration probe uses a disposable temporary runtime. Read/status checks never initialize runtime state.

## Cross-IDE verification and identity (beta.2)

On 2026-10-14 the official [Codex discovery documentation](https://learn.chatgpt.com/docs/build-skills)
still lists `.agents/skills` for project and user scope. This desktop environment
also exposes `~/.codex/skills`; the installer honors an explicit `CODEX_HOME`.
The official [Antigravity skills documentation](https://antigravity.google/docs/skills?app=antigravity-ide)
lists `.agents/skills` and `~/.gemini/config/skills`. The corresponding local
Codex and Antigravity skill files exist, but both inspected copies reported
beta.1. File presence does not establish that the host loaded or invoked them.
The current session's skill catalog did not expose COLLAB. No live Antigravity
registration was observed during this maintenance task.

`--verify-only` now tests installed helper registration in a temporary workspace
and returns `activation_verified`. Tests also install separate Codex/Antigravity
copies in a simulated home, invoke both through independent Python processes,
and complete a shared task. This proves portable helper execution, not native
skill selection. See [two-IDE procedure](TWO_IDE_VERIFICATION.md).

Platform/model/reasoning data is preserved exactly with a separate normalized
platform family. Codex variants count as one IDE family, as do Antigravity
variants. No model is guessed from an IDE or provider name. Active host markers
and optional current-session adapters supply metadata; otherwise use `unknown`.
This local cooperative protocol cannot attest which application a malicious
caller is running. Model providers are not counted as IDE platforms.

Existing schema-1 states remain readable and migrate on the next mutation.
Defaults preserve same-IDE collaboration. Cross-IDE tasks must declare their
requirements; both installed helpers must be beta.2 or newer to enforce them.
