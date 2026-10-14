# Compatibility

Evidence checked: 2026-10-14. Every participant must have local shell execution, Python 3.10+, and read/write access to the **same physical project directory**. Separate remote clones are separate teams. The model provider is not part of COLLAB's protocol.

## Host installation and activation

The paths below are relative to the project root and contain the complete `collab` directory. These are documented discovery paths, not claims of completed live IDE integration.

| Host | Project skill directory | Activation after discovery | Evidence |
| --- | --- | --- | --- |
| Codex CLI / IDE extension | `.agents/skills/collab/` | `$collab <task>` or select through `/skills`; plain `/collab` is not promised | [Official OpenAI documentation](https://learn.chatgpt.com/docs/build-skills) |
| Codex desktop | `.agents/skills/collab/` | Select/mention the installed `collab` skill or ask to use it | [Official OpenAI documentation](https://learn.chatgpt.com/docs/build-skills) |
| Claude Code | `.claude/skills/collab/` | `/collab <task>` | [Claude Code skills](https://code.claude.com/docs/en/skills) |
| Antigravity app / CLI | `.agents/skills/collab/` | `/collab <task>` | [Antigravity skills](https://antigravity.google/docs/skills) |
| Antigravity standalone IDE | `.agents/skills/collab/` | Ask to use the `collab` skill; inspect Customizations for discovery. Direct slash support for this surface was not independently established | [Antigravity skills](https://antigravity.google/docs/skills) |
| Kimi Code CLI | `.agents/skills/collab/` | `/skill:collab <task>` | [Kimi skills](https://www.kimi.com/code/docs/en/kimi-code-cli/customization/skills.html) |
| Gemini CLI | `.agents/skills/collab/` | Ask to use `collab`; accept the host's skill activation prompt. `/skills list` and `/skills reload` manage discovery | [Gemini skills](https://geminicli.com/docs/cli/skills/) |
| Cursor | `.agents/skills/collab/` | `/collab <task>` or select the skill | [Cursor skills](https://prod.cursor.com/help/customization/skills) |
| OpenCode | `.agents/skills/collab/` | `/collab` on versions supporting `metadata.opencode/slash`; otherwise ask to use `collab` | [OpenCode skills](https://opencode.ai/docs/skills/) |
| DeepSeek-based or other hosts | Host-specific | Unverified: the host must load Agent Skills and execute local Python | No universal host contract established |

The offline installer uses the shared `.agents/skills` directory for these supported hosts except Claude Code. Host-native alternatives include `.cursor/skills`, `.gemini/skills`, `.opencode/skills`, and `.kimi-code/skills`; see the linked documentation before using version-specific paths. Skills are instructions: the host still controls execution permissions, context lifetime, and user interaction. COLLAB does not bypass host consent.

## What is verified

- Official documentation supports the discovery and activation mechanisms above.
- Source inspection confirms that the optional Vercel installer includes bundled scripts and resources; see [RESEARCH.md](RESEARCH.md).
- Actual packaging tests and operating-system test results are recorded in [VALIDATION_REPORT.md](VALIDATION_REPORT.md). A configured CI matrix is not a completed CI run.
- Cross-process simulations exercise independent Python processes. They are not live Codex-to-Antigravity tests.

## Operational limits

COLLAB is designed for a cooperating team on a local filesystem. It has no hosted transport, daemon, automatic IDE wake-up, or access to private native chats. Each active agent explicitly publishes messages and polls at checkpoints. A suspended agent cannot respond until its host resumes it.

Native Windows and native POSIX implementations use different OS locking primitives. Sharing one state directory between native Windows and WSL processes, through network mounts, or through cloud-sync tools is unverified and unsupported for v1. Use one execution environment and local volume for a team. Sandboxed or remote agents that cannot access that directory cannot participate.

No list of model names limits participation. Unknown model identifiers stay `unknown`; sharing a display name or model does not merge agent identities. More participants increase contention and review work even though the protocol does not impose a fixed participant count.
