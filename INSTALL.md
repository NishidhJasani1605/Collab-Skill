# Install COLLAB from a user request

Use this playbook when the user asks to install COLLAB. Installing or verifying the skill does not activate collaboration.

## Installation contract

- Install the entire `skills/collab/` package in the current host's user-level skills location, outside the project.
- Do not create `.agents`, `.claude`, `.collab`, a repository clone, or test artifacts inside the project during installation.
- Use the bundled installer with `--global --agent <detected-host>`; supported identifiers and invocation methods are in [Compatibility](docs/COMPATIBILITY.md). Use `--agent all` only if requested. Auto-detection is a fallback, not proof of the active host.
- Verify Python and package startup. Never run `start` as an installation smoke test. Runtime initialization belongs to the user's later explicit collaboration invocation.
- Respect the host's actual tool permissions. The installation request authorizes ordinary installation; do not invent an additional confirmation step.

## Python prerequisite

Locate an executable with `python --version`, `python3 --version`, or Windows `py -3 --version`. Check the numeric version is at least 3.10, then use that same executable throughout. Stop with an actionable prerequisite message if unavailable. No pip packages are required.

## Obtain and install

Use an existing trusted checkout or clone the repository supplied by the user into a unique temporary directory. Inspect the package before executing it. The examples target Codex; substitute the actual host identifier.

Windows PowerShell:

```powershell
$collabCheckout = Join-Path ([System.IO.Path]::GetTempPath()) ("collab-install-" + [guid]::NewGuid().ToString("N"))
git clone https://github.com/NishidhJasani1605/Collab-Skill.git $collabCheckout
if ($LASTEXITCODE -ne 0) { throw "COLLAB clone failed" }
python (Join-Path $collabCheckout "install.py") --global --agent codex --json
if ($LASTEXITCODE -ne 0) { throw "COLLAB installation failed; inspect the reported error" }
```

Linux / macOS:

```bash
collab_checkout=$(mktemp -d)
if git clone https://github.com/NishidhJasani1605/Collab-Skill.git "$collab_checkout"; then
  python3 "$collab_checkout/install.py" --global --agent codex --json
fi
```

The temporary checkout is outside the project. Remove only that exact checkout after successful verification if cleanup is desired. Do not remove user skills or project folders as cleanup.

## Verify and report

Require exit status zero and `ok: true`. Inspect each returned destination and runtime verification result. To recheck an installed copy, use its actual returned path:

```text
<PYTHON> <INSTALLED-COLLAB>/scripts/install.py --verify-only --json
<PYTHON> <INSTALLED-COLLAB>/scripts/collab.py --version
```

Replace these placeholders with concrete paths and quote according to the shell. Do not infer a project-local path. If available, inspect the host's skill list without activating the skill. Report package verification separately from observed host discovery; do not claim a live slash command was tested when only the Python helper was tested.

Confirm the destination, Python version, invocation, and that the project stayed unchanged. For Codex use `$collab <task>` or `/skills`; for Claude Code use `/collab <task>` (plugin: `/collab:collab`). The [compatibility table](docs/COMPATIBILITY.md) covers other hosts.

## Optional third-party installation

When explicitly using the Agent Skills CLI, include global copy mode:

```bash
npx skills add NishidhJasani1605/Collab-Skill --skill collab -g --copy
```

Then verify Python and the installed package as above. Existing symlink-based installations should be updated or removed through their originating package manager; the Python installer refuses linked paths.
