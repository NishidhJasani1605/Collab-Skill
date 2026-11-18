# Security Policy

## Supported Versions

| Version | Supported |
| :--- | :--- |
| 2.0.x (Pure Markdown) | :white_check_mark: |
| 1.0.0-beta.x (Legacy Python) | :x: |

---

## Local Security & Trust Model

COLLAB v2.0 is a **pure-Markdown instruction skill** for local-only collaboration between AI coding agents operating under the user's own local workspace permissions.

### Built-In Safety Principles
1. **Untrusted Peer Data:** Every agent and its `Chat Messenger` sub-agent are explicitly instructed to treat all messages in `.collab/CHAT.md` as **untrusted data**, never as elevated system instructions. Agents must never execute destructive or out-of-scope shell commands sourced from peer chat messages.
2. **Project Boundary Discipline:** Agents only read and write files inside the user's chosen `<project-root>` and keep all collaboration state inside `<project-root>/.collab/`.
3. **Zero Executable Skill Code:** Because COLLAB v2.0 ships **zero scripts or binaries**, installing the skill cannot run arbitrary code during installation or activation.
4. **No Silent Deletion:** Agents are strictly forbidden from deleting an existing `.collab/` folder or overwriting files owned by a teammate.
5. **Independent Review & Real Verification:** Agents cannot self-approve when a teammate is active and must report only genuinely observed build/test output.

### Scope Limitations
- COLLAB is a cooperative protocol for trusted local agents controlled by the same user. It does not sandbox OS processes or protect against a hostile local process with full user filesystem access.

---

## Reporting a Vulnerability

If you discover a prompt-injection weakness or security issue in COLLAB's instructions:
1. Please do **not** open a public issue with an active exploit.
2. Report it privately via GitHub Private Vulnerability Reporting or directly to the maintainer.
3. Include reproduction steps and the affected Markdown file/section.
