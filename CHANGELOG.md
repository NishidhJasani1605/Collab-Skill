# Changelog

All notable changes to the **COLLAB** skill are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.1.0] - 2026-11-18

### Live-Test Reliability, Fast Mode, `MEMBERS.md` & `TASKS.md`

Upgraded the pure-Markdown skill based on live two-IDE testing (Antigravity + Codex) — zero coding files added.

#### Added & Improved
- **Zero-Question Turn-1 Startup:** Agents immediately check `<project-root>/.collab/` on their very first tool call without stalling or asking upfront questions.
- **Dedicated 5-Column `.collab/MEMBERS.md`:** Tracks every joining agent (`No. | Platform | Model | Entry Status | Exit Status`), written exclusively by each side's `Chat Messenger` sub-agent. Agents may stop only after recording `All tasks are completed and now I am leaving` once all joined teammates approve completion.
- **Dedicated `.collab/TASKS.md` Live Tracker:** Replaces `PLAN.md` with a clean, visual task-tracking & agreed-plan file so users can see at a glance who is building/done with every part of the application (e.g., Frontend vs. Backend), exclusive owned files, review status, and real verification output.
- **Guaranteed Active Chatting (Fixes Silent Antigravity Bug):**
  - Explicitly mandates spawning a **write-enabled** `Chat Messenger` sub-agent (never a read-only `research` sub-agent), with immediate direct-write fallback if sub-agent spawning fails.
  - Enforces a **Proof-of-Chat Gate** verifying the agent's row in `MEMBERS.md` and `JOIN` message in `CHAT.md` before writing project code.
- **Proactive Helping When Finishing Early:** Faster agents immediately review finished peer code, suggest fixes, run tests, and offer to take over unstarted subtasks in `TASKS.md` while their `Chat Messenger` continuously answers peer messages and reports live status.
- **Fast Execution Mode (3x–5x Faster):** Cut chat polling to **3–5 seconds** (20–25s one-shot heartbeat), switched to 1-round crisp planning, concise 2–4 line chat messages, parallel tool calls, and lightweight models for `Chat Messenger`.

---

## [2.0.0] - 2026-11-18

### Major Architectural Redesign — 100% Pure-Markdown Skill (Zero Code)

Rebuilt COLLAB from a 26-file Python codebase into a **zero-code, pure-Markdown Agent Skill** that works universally across every AI coding assistant with zero setup friction.

#### Added
- **Dedicated `Chat Messenger` Sub-Agent Architecture** (`skills/collab/references/chat-messenger.md`):
  - Each participating coding agent spawns one lightweight `Chat Messenger` sub-agent whose sole responsibility is watching `.collab/CHAT.md`, appending clean Markdown messages, and relaying updates to its parent agent.
  - Includes collision-safe append-only verification and automatic built-in checkpoint fallback for hosts without sub-agent support.
- **Ultra-Simple 2-File `.collab/` Runtime Room** (`skills/collab/references/templates.md`):
  - Replaced ~12 complex runtime files/subfolders with just `.collab/.gitignore`, `.collab/CHAT.md`, and `.collab/PLAN.md` (with automatic `.collab/archive/` preservation for subsequent tasks).
- **Capability-Aware & Cost-Aware Task Division** (`skills/collab/references/rules.md`):
  - Agents declare their exact platform, model, strengths, and cost/quota tier on entry.
  - Equal-capability work is assigned to the lower-cost / higher-quota model to conserve expensive limits; harder/specialized tasks go to whichever model is genuinely stronger.
- **Strict 6-Stage Collaboration Protocol** (`skills/collab/SKILL.md`, `docs/PROTOCOL.md`):
  - Safe discovery (late-joining agents **never** delete an existing `.collab/` folder).
  - Mandatory `JOIN` entry announcement, mutual `PLAN APPROVED` gate before coding, live milestone updates & independent cross-reviews, **Golden Team Rule** (never stop while a peer is still working), real command verification, and mandatory mutual closing sign-off (`"My task is done and I am now stopping."`).
- **Universal Compatibility & Discovery Positioning** (`README.md`, `INSTALL.md`, `docs/COMPATIBILITY.md`):
  - Expanded compatibility coverage to Antigravity, Codex, Claude Code, Cursor, Kimi Code, DeepSeek (Cline/Roo/Continue/Aider), Devin, Trae, Windsurf, Gemini CLI, OpenCode, and GitHub Copilot.
  - Added clear problem-solution positioning for pairing different AI models on the same project.
- **Pure-Markdown CI Verification** (`.github/workflows/ci.yml`):
  - Enforces zero `.py` coding files, required skill files, valid `SKILL.md` frontmatter, and zero broken relative Markdown links.

#### Removed
- Removed all 26 `.py` files (`install.py`, `scripts/`, `skills/collab/scripts/`, `examples/`, `tests/`) and Python 3.10+ runtime requirement.
- Removed obsolete Python-engine documentation and local test/log artifacts.

---

## [1.0.0-beta.4] - 2026-10-28

Legacy Python-helper beta release (archived in Git history prior to the v2.0.0 pure-Markdown redesign).
