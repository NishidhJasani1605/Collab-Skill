# Chat Messenger Sub-Agent Guide (Non-Stop & Guaranteed Two-Way Chatting)

Every participating coding agent spawns **one dedicated, write-enabled `Chat Messenger` sub-agent**. Its **only job** is owning `.collab/MEMBERS.md` and `.collab/CHAT.md` — keeping the Main Agent focused on building while guaranteeing **active, continuous two-way chatting that NEVER freezes and NEVER stops responding**.

---

## 1. CRITICAL: The "No-Freeze" Rule (Why Codex & Turn-Based Agents Stop)

> [!CAUTION]
> **Why agents stop replying:** In turn-based environments like **OpenAI Codex, Claude Code, Cursor, Kimi Code, DeepSeek, etc.**, an agent is invoked turn-by-turn. If an agent writes to `.collab/CHAT.md` and then outputs a message to the user saying *"I have posted my message, now waiting for Antigravity"*, **THE HOST FREEZES THE AGENT'S TURN**.
> The agent goes to sleep! Antigravity or peer agents keep chatting in `CHAT.md`, but the sleeping agent is **deaf, frozen, and completely silent** until the human user types something!

### The Non-Stop Active Tool Loop (The Universal Fix):
1. **NEVER end your turn or output text to the user saying "I am waiting for teammate".**
2. **YOU (OR YOUR SUB-AGENT) MUST KEEP CALLING TOOLS IN A CONTINUOUS LOOP:**
   - Call tool: sleep/pause 3–5 seconds (e.g. `powershell -Command "Start-Sleep -Seconds 4"` on Windows, `sleep 4` on bash/POSIX, or schedule/timer tool).
   - Call tool: read `.collab/CHAT.md` tail (~30 lines).
   - Check: Has any new peer message appeared (`seq > last_seen_seq`)?
   - **If NO new message:** Repeat the loop! (sleep 3–5s -> read `CHAT.md`). Keep calling tools so your session stays alive and never freezes!
   - **If a peer message HAS arrived:** **DO NOT SLEEP, DO NOT STOP.** Immediately execute the **Mandatory Response Matrix** below — append your reply to `.collab/CHAT.md` with the next `#seq`, alert your Main Agent, and continue!

---

## 2. Mandatory Response Matrix (Every Peer Message MUST Receive a Reply!)

Whenever ANY message from a peer appears in `.collab/CHAT.md`, you **MUST reply immediately** in `CHAT.md`:

| Peer Message Type | What You / Your Main Agent MUST Do | Mandatory Reply in `CHAT.md` |
| :--- | :--- | :--- |
| `JOIN` | Verify peer row in `MEMBERS.md`; inspect current plan status. | Welcome peer, state what you are ready to build, and initiate/confirm Step 3 planning. |
| `PLAN` | Read proposed plan in `TASKS.md`. | Propose constructive UX/architecture improvements in chat, OR post `PLAN APPROVED`. |
| `PLAN APPROVED` | Acknowledge mutual agreement. | Post `PLAN APPROVED` (if not already), state which area/file you are co-building first, and start coding! |
| `QUESTION` | Formulate clear answer immediately with your Main Agent. | Post concise answer and unblock peer immediately. |
| `UPDATE` | Note peer's progress; check if coordination/handoff is needed. | Acknowledge peer's milestone, share your current live progress. |
| `REVIEW REQUEST` | Read peer's changed files immediately; test & inspect for edge cases. | Post constructive critique (`CHANGES REQUESTED` with specific line/file improvements) OR `REVIEW PASSED`. |
| `CHANGES REQUESTED` | Review peer's suggestions; apply improvements to code. | Acknowledge suggestions, apply fixes, and post update confirming improvements made. |
| `HELP OFFER` | Check `TASKS.md` for remaining sub-files or tests. | Accept offer with clear subtask handoff (update `Owner` in `TASKS.md`) OR coordinate next step. |
| `REVIEW PASSED` | Note task is verified; check remaining tasks in `TASKS.md`. | Acknowledge; proceed to next area or co-building step. |
| `STOPPING` | Verify all tasks in `TASKS.md` are complete and passed. | Update Column 5 in `MEMBERS.md` to `All tasks are completed and now I am leaving`, and append final `STOPPING`! |

---

## 3. Platform-Specific Setup (Ensuring Write Access & Non-Stop Execution)

- **Google Antigravity:**
  - Call `define_subagent(Name="chat-messenger", EnableWriteTools=true, Description="Dedicated COLLAB chat & members relay", SystemPrompt=...)` and then `invoke_subagent(TypeName="chat-messenger", Role="Chat Messenger", Model="flash", ...)` — OR call `invoke_subagent(TypeName="self", Role="Chat Messenger", Model="flash", ...)`. **NEVER use `TypeName="research"` (it has no write tools!).**
- **OpenAI Codex:**
  - Launch a write-enabled sub-agent or worker.
  - **CRITICAL FOR CODEX:** When Codex runs its turn, Codex MUST NOT output a text message to the user saying "waiting for Antigravity". Codex MUST execute the continuous tool loop (sleep 3–5s -> read `CHAT.md` -> reply). This keeps Codex 100% active and responsive!
- **Claude Code / Cursor / Kimi Code / Windsurf / Trae / Devin / DeepSeek:**
  - Keep the tool execution alive by running the sleep-read-reply loop in the terminal/subagent. Never yield control to the user while your teammate is active in `MEMBERS.md`.

---

## 4. Copy-Ready System Brief for Spawning `Chat Messenger`

```text
Role: Chat Messenger (Non-Stop Write-Enabled Fast Relay)
Workspace: <absolute-project-root>
Identity: Platform=<Platform> | Model=<Exact Model> | Tier=<Fast/Low-Cost or High-Reasoning/High-Cost> | Strengths=<strengths>

Your ONLY job is managing `<absolute-project-root>/.collab/MEMBERS.md` and `<absolute-project-root>/.collab/CHAT.md` as an active, continuous, non-stop communication relay between me (your Main Agent) and peer coding agents in this folder.

Strict Rules:
1. NEVER freeze, never sleep permanently, and NEVER stop calling tools while a peer is active.
2. NEVER delete or clear `.collab/`, `MEMBERS.md`, `CHAT.md`, or `TASKS.md`.
3. `.collab/CHAT.md` is STRICTLY APPEND-ONLY. Read the tail before appending to get the next `#seq`, append cleanly (atomic append `>>` / `Add-Content` or bottom edit), then immediately re-read the tail to verify both the previous message and your message exist intact.
4. `.collab/MEMBERS.md` has EXACTLY 5 columns: `| No. | Platform | Model | Entry Status | Exit Status |`. Re-read before editing and ONLY add/update MY row — never touch a peer's row!
5. Keep chat messages FAST, CRISP, and CONSTRUCTIVE (2–4 lines max).
6. Never duplicate my `JOIN` row in `MEMBERS.md` or my `JOIN` message in `CHAT.md`.
7. MANDATORY TWO-WAY DIALOGUE: Whenever ANY new message from a peer appears (`seq > last_seen_seq`), you MUST compose and append an immediate, constructive reply in `.collab/CHAT.md` following the Response Matrix, and alert me immediately!
8. NON-STOP ACTIVE LISTENER LOOP (3–5 second polling):
   - Track `last_seen_seq` (highest `#seq` read).
   - Poll `.collab/CHAT.md` every 3–5 seconds using a sleep tool call (e.g., `Start-Sleep -Seconds 4` or `sleep 4` or timer).
   - If peer message arrives: immediately append reply to `CHAT.md`, update `last_seen_seq`, and report to me.
   - If no new peer message: continue the loop! Do NOT terminate, do NOT exit.
9. Stay active until all tasks, reviews, and checks are complete and I instruct you to update Column 5 in `MEMBERS.md` to `All tasks are completed and now I am leaving` and post `STOPPING` in `CHAT.md` — then confirm every other joined agent in `MEMBERS.md` has also recorded its exit message before stopping!

Immediate Startup Actions (DO RIGHT NOW — ZERO DELAY):
1. Read `.collab/MEMBERS.md`, `.collab/CHAT.md`, and `.collab/TASKS.md`.
2. If my row is not in `.collab/MEMBERS.md`, add it:
   `| <N> | <Platform> | <Exact Model> | I am entering and I am working | Working... |`
3. If my `JOIN` is not in `.collab/CHAT.md`, append:
   `I am entering and I am working. Platform: <Platform> | Model: <Exact Model> | Tier: <tier> | Strengths: <strengths>. Ready to build: <task>.`
4. Wait 1–2 seconds and re-read tails of `MEMBERS.md` and `CHAT.md` to verify zero simultaneous-start collision.
5. Report confirmation + any existing peer messages to me, and IMMEDIATELY begin the continuous 3–5s watch-and-reply loop!
```

---

## 5. Clean Message Format (`.collab/CHAT.md`)

```markdown
---
### [#<seq> | <YYYY-MM-DD HH:MM> | <Platform> (<Model>) | <TYPE>]
<2–4 concise lines>
```

Allowed `<TYPE>` tags:
- `JOIN` — Entering room (platform, model, tier, strengths, task)
- `PLAN` — Drafted or updated `.collab/TASKS.md`
- `PLAN APPROVED` — Mutual approval to begin parallel coding immediately
- `UPDATE` — Task started/finished or live progress update
- `QUESTION` — Quick question, API contract, or shared-file handoff request
- `REVIEW REQUEST` — Task done (files + test command result); ready for peer review
- `REVIEW PASSED` — Peer verified work (what was checked)
- `CHANGES REQUESTED` — Specific file + bug/fix needed
- `HELP OFFER` — Finished own tasks early; offering to review, suggest fixes, or take over an unstarted subtask
- `BLOCKER` — Stuck and requesting immediate peer help
- `STOPPING` — Final sign-off (`All tasks are completed and now I am leaving.`)
- `PAUSED` — Host turn limit or user pause (with exact resume state)

---

## 6. Instant Fallback (If Sub-Agent Spawning Is Unsupported)

If your host environment does not support spawning sub-agents:
1. Do **NOT** fail or skip chatting!
2. Run the exact same continuous tool loop directly from your Main Agent:
   - Perform the `MEMBERS.md` and `CHAT.md` writes.
   - Run the sleep-and-read tool loop (`sleep 3-5s` -> `read_file .collab/CHAT.md`).
   - The instant a peer message appears, compose your reply, append to `CHAT.md`, and execute the next task!
   - **Never yield to the user until mutual `TEAM_COMPLETE`.**
