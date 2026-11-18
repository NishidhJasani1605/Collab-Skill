# Install COLLAB (Zero-Code Pure-Markdown Guide)

Use this playbook when a user asks you to install **COLLAB**. Installing the skill does **not** start a collaboration session and does **not** create `.collab/` in the user's project.

---

## Installation Contract

1. **Zero Code / Zero Prerequisites:** COLLAB v2.0 is **100% pure Markdown**. Do **not** check for Python, do **not** run any `.py` installer, and do **not** install third-party packages.
2. **User-Global Scope by Default:** Copy the entire `skills/collab/` directory into the active host's **user-level skills directory** (outside the user's project).
3. **Keep the User's Project Clean:** Do **not** create `.collab/`, repository clones, or temporary files inside the user's project folder.
4. **Copy Complete Package:** Ensure all 4 Markdown files (plus `agents/openai.yaml` if present) are copied cleanly:
   - `skills/collab/SKILL.md`
   - `skills/collab/references/chat-messenger.md`
   - `skills/collab/references/templates.md`
   - `skills/collab/references/rules.md`
   - `skills/collab/agents/openai.yaml` *(optional Codex policy)*

---

## Target User-Global Directories by Host

Identify the active coding agent and install into its user-level skills directory (see [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md) for full details):

| Host | Target Directory |
| :--- | :--- |
| **Google Antigravity** (App / IDE) | `~/.gemini/config/skills/collab/` |
| **Google Antigravity CLI** | `~/.gemini/antigravity-cli/skills/collab/` |
| **OpenAI Codex** (CLI / IDE / Desktop) | `~/.agents/skills/collab/` (or `$CODEX_HOME/skills/collab/` / `~/.codex/skills/collab/`) |
| **Claude Code** | `~/.claude/skills/collab/` |
| **Cursor** | `~/.cursor/skills/collab/` |
| **Kimi Code** | `~/.kimi-code/skills/collab/` |
| **Gemini CLI** | `~/.gemini/skills/collab/` |
| **OpenCode** | `~/.config/opencode/skills/collab/` |
| **DeepSeek / Cline / Roo / Trae / Windsurf / Devin / Other** | `~/.agents/skills/collab/` (or host's custom skills/rules folder) |

---

## Step-by-Step Copy Instructions

### Option A — Clone to Temp & Copy (Windows PowerShell)

Replace `$target` with your host's user-global skills folder from the table above:

```powershell
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("collab-install-" + [guid]::NewGuid().ToString("N"))
$target = Join-Path $HOME ".agents\skills\collab"
git clone --depth 1 https://github.com/NishidhJasani1605/Collab-Skill.git $tmp
New-Item -ItemType Directory -Force -Path $target | Out-Null
Copy-Item -Path (Join-Path $tmp "skills\collab\*") -Destination $target -Recurse -Force
Remove-Item -Path $tmp -Recurse -Force
```

### Option B — Clone to Temp & Copy (macOS / Linux)

Replace `TARGET` with your host's user-global skills folder from the table above:

```bash
TMP_DIR=$(mktemp -d)
TARGET="$HOME/.agents/skills/collab"
git clone --depth 1 https://github.com/NishidhJasani1605/Collab-Skill.git "$TMP_DIR"
mkdir -p "$TARGET"
cp -R "$TMP_DIR/skills/collab/." "$TARGET/"
rm -rf "$TMP_DIR"
```

### Option C — Agent Skills CLI (Optional)

```bash
npx skills add NishidhJasani1605/Collab-Skill --skill collab -g --copy
```

---

## Verify & Report to User

1. Confirm these files exist in the destination folder:
   - `SKILL.md`
   - `references/chat-messenger.md`
   - `references/templates.md`
   - `references/rules.md`
2. Confirm the user's project directory was left untouched (no `.collab/` created during installation).
3. Tell the user the exact installed path and how to invoke COLLAB in their host (for example: `/collab <task>` in Antigravity/Claude Code/Cursor, `$collab <task>` in Codex, `/skill:collab <task>` in Kimi Code, or *"Use the collab skill"* in any agent).
4. Remind the user to refresh/reload skills if their IDE caches skill lists, and to install the same v2.0 skill in every coding agent they want to collaborate together.

---

## Uninstall

Simply delete the installed `collab` skill directory (for example, `~/.agents/skills/collab/`). Removing the skill leaves your project files and any `.collab/` history untouched.
