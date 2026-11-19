# Install or Update COLLAB (Zero-Code Pure-Markdown Guide)

Use this playbook when a user asks you to **install** or **update** **COLLAB**. Installing or updating the skill does **not** start a collaboration session and does **not** create `.collab/` in the user's project.

---

## Installation & Clean-Update Contract

1. **Zero Code / Zero Prerequisites:** COLLAB v2.3 is **100% pure Markdown**. Do **not** check for Python, do **not** run any `.py` installer, and do **not** install third-party packages.
2. **User-Global Scope by Default:** Install into the active host's **user-level skills directory** (outside the user's project).
3. **Clean Upgrade (Remove Old `collab/` First):** If an older version of `collab` is already installed at the target path, **clone/download the latest repo first**, verify the download succeeded, then **completely remove the old installed `collab/` skill folder** (so no leftover v1 `.py` scripts or outdated reference docs remain), and copy the fresh `skills/collab/` directory in its place. Never delete other skills or anything inside the user's project.
4. **Keep the User's Project Clean:** Do **not** create `.collab/`, repository clones, or temporary files inside the user's project folder.
5. **Copy Complete Package:** Ensure all 4 Markdown files (plus `agents/openai.yaml` if present) are installed cleanly:
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

## Step-by-Step Install / Clean-Update Commands

### Option A — Clone to Temp, Remove Old Skill & Copy Fresh (Windows PowerShell)

Replace `$target` with your host's user-global skills folder from the table above:

```powershell
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("collab-install-" + [guid]::NewGuid().ToString("N"))
$target = Join-Path $HOME ".agents\skills\collab"
git clone --depth 1 https://github.com/NishidhJasani1605/Collab-Skill.git $tmp
if ($LASTEXITCODE -ne 0) { throw "Failed to download COLLAB from GitHub" }
if (Test-Path $target) { Remove-Item -Path $target -Recurse -Force }
New-Item -ItemType Directory -Force -Path $target | Out-Null
Copy-Item -Path (Join-Path $tmp "skills\collab\*") -Destination $target -Recurse -Force
Remove-Item -Path $tmp -Recurse -Force
```

### Option B — Clone to Temp, Remove Old Skill & Copy Fresh (macOS / Linux)

Replace `TARGET` with your host's user-global skills folder from the table above:

```bash
TMP_DIR=$(mktemp -d)
TARGET="$HOME/.agents/skills/collab"
if git clone --depth 1 https://github.com/NishidhJasani1605/Collab-Skill.git "$TMP_DIR"; then
  rm -rf "$TARGET"
  mkdir -p "$TARGET"
  cp -R "$TMP_DIR/skills/collab/." "$TARGET/"
fi
rm -rf "$TMP_DIR"
```

### Option C — Agent Skills CLI (Optional)

```bash
npx skills add NishidhJasani1605/Collab-Skill --skill collab -g --copy
```

---

## Verify & Report to User

1. Confirm these files exist in the destination folder and **zero `.py` files** remain:
   - `SKILL.md` (check `version: "2.3.0"`)
   - `references/chat-messenger.md`
   - `references/templates.md`
   - `references/rules.md`
2. Confirm the user's project directory was left untouched (no `.collab/` created during installation).
3. Tell the user the exact installed path and how to invoke COLLAB in their host (for example: `/collab <task>` in Antigravity/Claude Code/Cursor, `$collab <task>` in Codex, `/skill:collab <task>` in Kimi Code, or *"Use the collab skill"* in any agent).
4. Remind the user to refresh/reload skills if their IDE caches skill lists, and to install the same v2.3 skill in every coding agent they want to collaborate together.

---

## Uninstall

Simply delete the installed `collab` skill directory (for example, `~/.agents/skills/collab/`). Removing the skill leaves your project files and any `.collab/` history untouched.
