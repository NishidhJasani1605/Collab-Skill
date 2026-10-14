# Installation, upgrade, and recovery

The [installation playbook](../INSTALL.md) is the canonical paste-to-install procedure. It applies to the original short prompt and the expanded prompt in the [README](../README.md). Python 3.10+ is required; there are no runtime pip dependencies.

## Scope and lifecycle

All three Python entry points default to `--scope global`. The implementation lives in `skills/collab/scripts/collablib/installer.py`, inside the distributable package. `--target` selects the project used for detection; it does not switch installation scope. `--home` supplies an alternate user home for testing. Custom `CODEX_HOME` and `KIMI_CODE_HOME` roots are honored; a global destination inside a project is refused. Launching from the user home itself is supported as a user-scope installation.

Installation and `--verify-only` leave project files unchanged. Helper commands other than `start` return `NOT_INITIALIZED` before activation. After explicit activation, all persistent collaboration metadata lives under the project's single `.collab/`. Repeated activation joins or resumes existing state. Actual source changes and task deliverables live in their intended project paths.

## Selecting hosts

Specify `--agent codex`, `claude-code`, `antigravity` (App/IDE), `antigravity-cli`, `kimi-code`, `cursor`, `gemini-cli`, `opencode`, or `universal`. Repeat `--agent` for several hosts. `--agent all` explicitly selects all hosts. Without a selection, active environment markers take precedence over installed-host directories. With no evidence, the installer uses the shared user `.agents/skills/collab` directory. See [Compatibility](COMPATIBILITY.md) for exact paths and sources.

Only for users explicitly requesting repository-scoped skills, the compatibility option `--local` / `--scope project` creates host discovery directories in the project. This is outside the clean-project installation contract and must never be selected merely because the installer was launched inside a project. It does not initialize `.collab`.

## Verification

```bash
# Source package: Python prerequisite, complete files, links, syntax and startup
python install.py --verify-only --json
```

For an installed copy, invoke its `scripts/install.py --verify-only --json` at the exact path returned during installation. Verification starts and deletes a simulated session in a temporary workspace; it leaves the user project untouched. Helper execution does not prove the host has refreshed its skill catalog. The verifier reports `activation_verified` separately from live IDE discovery.

## Updates

Run the same installer and host selection again. Identical installations are verified without rewriting files. Changed installations are backed up, copied to a sibling staging directory, checked, then published. A permanent `.collab-install.lock` beside user-level skill folders serializes installers and removals. Update failures during staging leave the old installation intact; publish failures attempt rollback, including when `--no-backup` was specified. Backup and installer files are outside the project in normal user scope.

Backups live at `<user-skill-parent>/.collab-backups/collab-<unique-id>`. `--no-backup` disables the retained backup only. Linked paths, source/destination containment, and unrecognized existing destinations are refused. Use the same package manager that owns a symlink-based installation.

An update is transactional per destination, not across all hosts. If one host update fails, successful updates to other hosts may remain; rerun after resolving the error. Do not update skill code while another process is importing it. Stop active helper calls before upgrading.

## Uninstall

```bash
python install.py --global --agent codex --uninstall
# Explicitly remove all supported host installations and recognized backups:
python install.py --global --agent all --uninstall --purge-backups
```

Default uninstall selects the detected environment, like installation. Select the same host used during installation. For a legacy local copy, use `--scope project --target <project> --agent <host> --uninstall` explicitly. Uninstallation preserves `.collab` history, project files, sibling skills, unrelated backup files, and backups unless requested. The installer lock remains to avoid lock-file replacement races.

## Existing project folders

Global installation does not automatically remove older project-local installations. Inspect them first: `.agents` and `.claude` may contain unrelated settings or skills. Remove only a verified COLLAB skill using the explicit project-scope uninstall command. Never delete the entire host directory. Old local copies may shadow new global copies, so refresh the host after removing an obsolete copy.

## Interrupted installation recovery

A failed ordinary update rolls back. An abrupt process or machine failure between directory renames may leave a `.collab-install-*` directory beside the installed skill with a `previous/` copy. That copy is intentionally retained on failed rollback. Inspect it and the retained backups before retrying; restore only the recognized COLLAB directory. Installer publication is not guaranteed power-loss atomic on every filesystem.

## Runtime recovery and limits

`LOCK_TIMEOUT` means another helper holds the project lock. A terminated process releases its OS lock automatically; do not delete `.collab/.lock`. Valid pending transactions recover when the next helper opens the store. Unknown corruption is preserved and reported instead of discarded. See [Safety and Recovery](../skills/collab/references/safety.md).

Use local filesystems and cooperating processes with the same execution environment. Mixed Windows/WSL access to a shared runtime, network drives, and cloud-synced state are unsupported. Use bounded tasks: authoritative state and chat are read under one lock and retained for the lifetime of the workspace. Validation commands must terminate and must not launch persistent services.
