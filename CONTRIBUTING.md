# Contributing to COLLAB

Thank you for contributing to **COLLAB**! COLLAB v2.0 is a **100% pure-Markdown Agent Skill** — contributions focus on clear, unambiguous, battle-tested Markdown instructions, templates, and documentation.

---

## Core Contribution Rules

1. **Zero Coding Files (Pure Markdown Skill):**
   - Do **not** add `.py`, `.js`, `.ts`, `.sh`, or compiled helper scripts to the skill or repository.
   - All skill behavior must be expressed cleanly in Markdown under `skills/collab/`.
2. **Keep `.collab/` Ultra-Simple:**
   - Runtime collaboration inside a user's project stays strictly inside `.collab/` with only `.gitignore`, `MEMBERS.md`, `CHAT.md`, and `TASKS.md` (plus `.collab/archive/` when preserving older completed sessions).
3. **Progressive Disclosure:**
   - Keep `skills/collab/SKILL.md` crisp, scannable, and under ~250 lines.
   - Put detailed prompts, templates, and edge-case playbooks in `skills/collab/references/`.
4. **Universal Agent Compatibility:**
   - Never lock instructions to a single IDE or model provider. Any coding agent (Antigravity, Codex, Claude Code, Cursor, Kimi Code, DeepSeek, Devin, Trae, Windsurf, Gemini CLI, OpenCode, etc.) must be able to follow the skill out of the box.
5. **No Broken Links:**
   - Verify all relative Markdown links across `README.md`, `INSTALL.md`, `docs/`, and `skills/collab/` resolve to real files.

---

## Pull Request Checklist

- [ ] Zero `.py` or coding script files added.
- [ ] `skills/collab/SKILL.md` frontmatter (`name`, `description`, `compatibility`, `metadata.version`) is valid.
- [ ] All relative links in modified `.md` files are valid.
- [ ] Changes are reflected in `docs/PROTOCOL.md`, `docs/COMPATIBILITY.md`, or `CHANGELOG.md` where appropriate.
- [ ] Tested live with at least two AI coding agents in a shared local folder (if changing collaboration rules).
