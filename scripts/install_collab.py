#!/usr/bin/env python3
"""Cross-platform, standard-library-only installer and verifier for the COLLAB Agent Skill.

Supports:
- Project-local and user-global installation scopes
- Automatic host detection (Claude Code, OpenAI Codex, Google Antigravity,
  Kimi Code, Cursor, Gemini CLI, OpenCode, and universal .agents/skills)
- Safe updates and reinstallations with automatic backups
- Complete file, relative-path, and subprocess execution verification
- Safe uninstallation that preserves unrelated skills and user project files
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True

SKILL_NAME = "collab"
MIN_PYTHON = (3, 10)
REQUIRED_RELATIVE_FILES = (
    "SKILL.md",
    "scripts/collab.py",
    "scripts/collab_operator.py",
    "scripts/collablib/__init__.py",
    "scripts/collablib/engine.py",
    "scripts/collablib/storage.py",
    "references/commands.md",
    "references/safety.md",
)
IGNORE_NAMES = {"__pycache__", ".pytest_cache", ".collab", ".git", ".DS_Store", "Thumbs.db", ".collab_installed.json"}

# Official discovery paths and invocation guidance per supported platform
PLATFORMS = {
    "claude-code": {
        "display_name": "Claude Code",
        "project_rel": ".claude/skills/collab",
        "global_rel": ".claude/skills/collab",
        "invocation": "/collab <task>",
        "notes": "Invoke directly with `/collab <task>`. (If installed via `/plugin`, Claude Code namespaces it as `/collab:collab`.)",
    },
    "codex": {
        "display_name": "OpenAI Codex",
        "project_rel": ".agents/skills/collab",
        "global_rel": ".agents/skills/collab",
        "invocation": "$collab <task> (or select `collab` via `/skills`)",
        "notes": "Codex uses `$collab` or the `/skills` selector rather than `/collab`.",
    },
    "antigravity": {
        "display_name": "Google Antigravity",
        "project_rel": ".agents/skills/collab",
        "global_rel": ".gemini/antigravity/skills/collab",
        "invocation": "/collab <task>",
        "notes": "Use `/collab <task>` in Antigravity app/CLI, or ask the agent to use the `collab` skill in standalone IDE surfaces.",
    },
    "kimi-code": {
        "display_name": "Kimi Code CLI",
        "project_rel": ".agents/skills/collab",
        "global_rel": ".kimi-code/skills/collab",
        "invocation": "/skill:collab <task>",
        "notes": "Kimi Code CLI activates skills with `/skill:collab <task>`.",
    },
    "cursor": {
        "display_name": "Cursor",
        "project_rel": ".agents/skills/collab",
        "global_rel": ".cursor/skills/collab",
        "invocation": "/collab <task>",
        "notes": "Type `/collab <task>` in Cursor Agent chat or select `collab` from the skills menu.",
    },
    "gemini-cli": {
        "display_name": "Gemini CLI",
        "project_rel": ".agents/skills/collab",
        "global_rel": ".gemini/skills/collab",
        "invocation": "Use the collab skill: <task> (run `/skills reload` if already in a session)",
        "notes": "Run `/skills reload` or `/skills list` in Gemini CLI to refresh newly installed skills.",
    },
    "opencode": {
        "display_name": "OpenCode",
        "project_rel": ".agents/skills/collab",
        "global_rel": ".config/opencode/skills/collab",
        "invocation": "/collab <task>",
        "notes": "OpenCode exposes `/collab` via `metadata.opencode/slash`.",
    },
    "universal": {
        "display_name": "Universal Agent Skills (.agents/skills)",
        "project_rel": ".agents/skills/collab",
        "global_rel": ".agents/skills/collab",
        "invocation": "/collab <task> (or host-equivalent skill selector)",
        "notes": "Standard Agent Skills directory compatible with Codex, Antigravity, Kimi Code, Cursor, Gemini CLI, and OpenCode.",
    },
}


class InstallError(Exception):
    def __init__(self, code: str, message: str, details=None):
        self.code = code
        self.details = details
        super().__init__(message)


def default_source_dir() -> Path:
    here = Path(__file__).resolve()
    candidate = here.parents[1] / "skills" / SKILL_NAME
    if (candidate / "SKILL.md").is_file():
        return candidate
    if (here.parent.parent / "SKILL.md").is_file():
        return here.parent.parent
    raise InstallError("SOURCE_NOT_FOUND", f"Could not locate skills/{SKILL_NAME}/SKILL.md relative to {here}")


def check_python_version(version_info=None, executable: str | None = None):
    if os.environ.get("COLLAB_TEST_PYTHON_VERSION"):
        parts = [int(x) for x in os.environ["COLLAB_TEST_PYTHON_VERSION"].split(".")[:2]]
        version_info = tuple(parts)
    actual = tuple(version_info or sys.version_info[:2])
    exe = executable if executable is not None else sys.executable
    if not exe or not Path(exe).exists():
        raise InstallError(
            "PYTHON_MISSING",
            "Python 3.10+ executable was not found. Install Python 3.10 or newer from https://www.python.org/ and ensure it is on PATH.",
        )
    if actual < MIN_PYTHON:
        raise InstallError(
            "PYTHON_VERSION_UNSUPPORTED",
            f"COLLAB requires Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+, but detected Python {actual[0]}.{actual[1]}.",
            {"detected": f"{actual[0]}.{actual[1]}", "required": f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]}+"},
        )
    return {"executable": str(exe), "version": f"{actual[0]}.{actual[1]}"}


def validate_skill_tree(skill_dir: Path) -> dict:
    skill_dir = Path(skill_dir).resolve()
    if not skill_dir.is_dir():
        raise InstallError("INVALID_SKILL_DIR", f"Skill directory does not exist: {skill_dir}")
    missing = [rel for rel in REQUIRED_RELATIVE_FILES if not (skill_dir / rel).is_file()]
    if missing:
        raise InstallError("INCOMPLETE_SKILL", "Skill package is missing required files", {"missing": missing})

    skill_md = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    if not skill_md.startswith("---\n"):
        raise InstallError("INVALID_METADATA", "SKILL.md must begin with YAML frontmatter ('---')")
    parts = skill_md.split("---", 2)
    if len(parts) < 3:
        raise InstallError("INVALID_METADATA", "SKILL.md frontmatter is not properly closed with '---'")
    frontmatter, body = parts[1], parts[2]
    name_match = re.search(r"^name:\s*['\"]?([a-z0-9-]+)['\"]?\s*$", frontmatter, re.MULTILINE)
    desc_match = re.search(r"^description:\s*(.+)$", frontmatter, re.MULTILINE)
    if not name_match or name_match.group(1) != SKILL_NAME:
        raise InstallError("INVALID_METADATA", f"SKILL.md frontmatter must declare name: {SKILL_NAME}")
    if not desc_match or not desc_match.group(1).strip():
        raise InstallError("INVALID_METADATA", "SKILL.md frontmatter must declare a non-empty description")
    if len(skill_md.splitlines()) > 500:
        raise InstallError("INVALID_METADATA", "SKILL.md exceeds 500 lines; keep progressive disclosure concise")

    # Verify all relative markdown links in SKILL.md resolve inside skill_dir
    broken_links = []
    for match in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", body):
        target = match.group(1).strip()
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        rel_path = target.split("#", 1)[0]
        if not rel_path:
            continue
        resolved = (skill_dir / rel_path).resolve()
        try:
            resolved.relative_to(skill_dir)
        except ValueError:
            broken_links.append(target)
            continue
        if not resolved.is_file():
            broken_links.append(target)
    if broken_links:
        raise InstallError("BROKEN_RELATIVE_PATHS", "SKILL.md contains broken relative file references", {"links": broken_links})

    return {"name": SKILL_NAME, "files_verified": list(REQUIRED_RELATIVE_FILES)}


def detect_environments(project_root: Path, home_dir: Path, env: dict | None = None) -> list[str]:
    env = env if env is not None else os.environ
    detected = []
    if (
        env.get("CLAUDECODE")
        or env.get("CLAUDE_CODE_ENTRYPOINT")
        or env.get("ANTHROPIC_CLAUDE_CODE")
        or (project_root / ".claude").exists()
        or (home_dir / ".claude").exists()
    ):
        detected.append("claude-code")
    if env.get("CODEX_HOME") or env.get("OPENAI_CODEX") or (home_dir / ".codex").exists():
        detected.append("codex")
    if (
        env.get("ANTIGRAVITY_CLI")
        or env.get("ANTIGRAVITY_APP")
        or (home_dir / ".gemini" / "antigravity").exists()
    ):
        detected.append("antigravity")
    if env.get("KIMI_CODE_HOME") or (project_root / ".kimi-code").exists() or (home_dir / ".kimi-code").exists():
        detected.append("kimi-code")
    if env.get("CURSOR_TRACE_ID") or (project_root / ".cursor").exists() or (home_dir / ".cursor").exists():
        detected.append("cursor")
    if env.get("GEMINI_CLI") or (project_root / ".gemini").exists() or (home_dir / ".gemini").exists():
        detected.append("gemini-cli")
    if env.get("OPENCODE") or (project_root / ".opencode").exists() or (home_dir / ".config" / "opencode").exists():
        detected.append("opencode")
    if not detected:
        detected.append("universal")
    return detected


def resolve_destination(agent: str, scope: str, project_root: Path, home_dir: Path, env: dict | None = None) -> Path:
    env = env if env is not None else os.environ
    if agent not in PLATFORMS:
        raise InstallError("UNKNOWN_AGENT", f"Unsupported agent '{agent}'. Choose from: {', '.join(sorted(PLATFORMS))}")
    if scope == "project":
        return project_root / PLATFORMS[agent]["project_rel"]
    if scope == "global":
        if agent == "codex" and env.get("CODEX_HOME"):
            return Path(env["CODEX_HOME"]).resolve() / "skills" / SKILL_NAME
        if agent == "kimi-code" and env.get("KIMI_CODE_HOME"):
            return Path(env["KIMI_CODE_HOME"]).resolve() / "skills" / SKILL_NAME
        return home_dir / PLATFORMS[agent]["global_rel"]
    raise InstallError("INVALID_SCOPE", f"Scope must be 'project' or 'global', got '{scope}'")


def _tree_digest(directory: Path) -> dict[str, str]:
    result = {}
    if not directory.is_dir():
        return result
    for path in sorted(directory.rglob("*")):
        rel_parts = path.relative_to(directory).parts
        if any(part in IGNORE_NAMES or part.endswith(".pyc") for part in rel_parts):
            continue
        if path.is_file():
            rel = path.relative_to(directory).as_posix()
            result[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _copy_clean_skill(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = Path(tempfile.mkdtemp(prefix=".collab-install-", dir=str(dst.parent)))
    try:
        target_stage = tmp_dir / SKILL_NAME
        shutil.copytree(
            src,
            target_stage,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", ".collab", ".git", ".DS_Store", "Thumbs.db"),
        )
        validate_skill_tree(target_stage)
        manifest = {
            "name": SKILL_NAME,
            "version": "1.0.0-beta.1",
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "manifest": "verified"
        }
        (target_stage / ".collab_installed.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        if dst.exists():
            shutil.rmtree(dst)
        shutil.move(str(target_stage), str(dst))
    finally:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)


def verify_installed_runtime(installed_dir: Path, python_exe: str | None = None) -> dict:
    validate_skill_tree(installed_dir)
    exe = python_exe or sys.executable
    helper = installed_dir / "scripts" / "collab.py"
    completed = subprocess.run(
        [exe, str(helper), "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=dict(os.environ, PYTHONUTF8="1", PYTHONPATH=""),
        timeout=30,
    )
    if completed.returncode != 0:
        raise InstallError(
            "RUNTIME_VERIFICATION_FAILED",
            f"Installed helper failed --version check: {completed.stderr or completed.stdout}",
        )
    version = completed.stdout.strip()
    return {"helper": str(helper), "version": version, "verified": True}


def install_skill(
    *,
    source_dir: Path | None = None,
    scope: str = "global",
    agents: list[str] | None = None,
    project_root: Path | None = None,
    home_dir: Path | None = None,
    backup_on_update: bool = True,
    env: dict | None = None,
) -> dict:
    env = env if env is not None else os.environ
    py_info = check_python_version()
    src = Path(source_dir).resolve() if source_dir else default_source_dir()
    validate_skill_tree(src)

    proj = Path(project_root).resolve() if project_root else Path.cwd().resolve()
    home = Path(home_dir).resolve() if home_dir else Path.home().resolve()
    if scope == "project" and not proj.is_dir():
        raise InstallError("INVALID_PROJECT_ROOT", f"Project root does not exist: {proj}")
    if scope == "global" and not home.is_dir():
        raise InstallError("INVALID_HOME_DIR", f"Home directory does not exist: {home}")

    detected = detect_environments(proj, home, env=env)
    if not agents or agents == ["auto"]:
        selected_agents = list(detected)
        if "universal" not in selected_agents:
            selected_agents.append("universal")
    elif "all" in agents:
        selected_agents = list(PLATFORMS.keys())
    else:
        selected_agents = list(dict.fromkeys(agents))

    src_digest = _tree_digest(src)
    installations = []
    seen_destinations: dict[Path, dict] = {}

    for agent in selected_agents:
        dest = resolve_destination(agent, scope, proj, home, env=env).resolve()
        if src == dest:
            raise InstallError("SAME_PATH", f"Source and destination are identical: {dest}")
        if dest not in seen_destinations:
            status = "installed"
            backup_path = None
            if dest.exists():
                existing_digest = _tree_digest(dest)
                if existing_digest == src_digest:
                    status = "up_to_date"
                else:
                    status = "updated"
                    if backup_on_update:
                        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                        backup_root = dest.parent / ".collab-backups"
                        backup_root.mkdir(parents=True, exist_ok=True)
                        backup_target = backup_root / f"{SKILL_NAME}-{stamp}"
                        counter = 1
                        while backup_target.exists():
                            backup_target = backup_root / f"{SKILL_NAME}-{stamp}-{counter}"
                            counter += 1
                        shutil.copytree(dest, backup_target)
                        backup_path = str(backup_target)
            _copy_clean_skill(src, dest)
            runtime_check = verify_installed_runtime(dest, py_info["executable"])
            seen_destinations[dest] = {
                "path": str(dest),
                "status": status,
                "backup_path": backup_path,
                "runtime": runtime_check,
                "agents": [],
            }
        seen_destinations[dest]["agents"].append(agent)
        installations.append({
            "agent": agent,
            "display_name": PLATFORMS[agent]["display_name"],
            "destination": str(dest),
            "status": seen_destinations[dest]["status"],
            "backup_path": seen_destinations[dest]["backup_path"],
            "invocation": PLATFORMS[agent]["invocation"],
            "notes": PLATFORMS[agent]["notes"],
        })

    return {
        "ok": True,
        "action": "install",
        "scope": scope,
        "python": py_info,
        "detected_environments": detected,
        "installations": installations,
        "destinations": list(seen_destinations.values()),
    }


def uninstall_skill(
    *,
    scope: str = "global",
    agents: list[str] | None = None,
    project_root: Path | None = None,
    home_dir: Path | None = None,
    purge_backups: bool = False,
    env: dict | None = None,
) -> dict:
    env = env if env is not None else os.environ
    proj = Path(project_root).resolve() if project_root else Path.cwd().resolve()
    home = Path(home_dir).resolve() if home_dir else Path.home().resolve()

    if not agents or agents == ["auto"] or "all" in agents:
        target_agents = list(PLATFORMS.keys())
    else:
        target_agents = list(dict.fromkeys(agents))

    removed = []
    not_installed = []
    checked_paths = set()

    for agent in target_agents:
        dest = resolve_destination(agent, scope, proj, home, env=env).resolve()
        if dest in checked_paths:
            continue
        checked_paths.add(dest)
        if dest.name != SKILL_NAME:
            raise InstallError("UNSAFE_UNINSTALL", f"Refusing to remove directory not named '{SKILL_NAME}': {dest}")
        if dest.exists():
            if not dest.is_dir():
                raise InstallError("UNSAFE_UNINSTALL", f"Refusing to remove '{dest}': not a directory.")
            # Verify ownership: check for installation manifest or valid SKILL.md + scripts/collab.py
            is_verified_collab = False
            manifest_file = dest / ".collab_installed.json"
            skill_md_file = dest / "SKILL.md"
            helper_file = dest / "scripts" / "collab.py"
            if manifest_file.is_file():
                try:
                    data = json.loads(manifest_file.read_text(encoding="utf-8"))
                    if data.get("name") == SKILL_NAME:
                        is_verified_collab = True
                except Exception:
                    pass
            if not is_verified_collab and skill_md_file.is_file() and helper_file.is_file():
                try:
                    content = skill_md_file.read_text(encoding="utf-8")
                    if f"name: {SKILL_NAME}" in content or f'name: "{SKILL_NAME}"' in content or f"name: '{SKILL_NAME}'" in content:
                        is_verified_collab = True
                except Exception:
                    pass
            if not is_verified_collab:
                raise InstallError(
                    "UNSAFE_UNINSTALL",
                    f"Refusing to remove directory '{dest}': directory exists but does not contain a verified COLLAB skill installation or manifest.",
                )
            shutil.rmtree(dest)
            removed.append(str(dest))
        else:
            not_installed.append(str(dest))
        if purge_backups:
            backup_dir = dest.parent / ".collab-backups"
            if backup_dir.exists():
                shutil.rmtree(backup_dir)

    return {
        "ok": True,
        "action": "uninstall",
        "scope": scope,
        "removed": removed,
        "not_installed": not_installed,
    }


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Install, verify, update, or uninstall the local COLLAB Agent Skill."
    )
    parser.add_argument(
        "--scope",
        choices=("global", "project"),
        default="global",
        help="Install scope: 'global' (default, user home directory, keeps project workspaces clean) or 'project' (--local).",
    )
    parser.add_argument(
        "--global",
        "-g",
        dest="is_global",
        action="store_true",
        help="Install globally into user home directory (default).",
    )
    parser.add_argument(
        "--local",
        "-l",
        dest="is_local",
        action="store_true",
        help="Install into current project directory (creates .claude/ or .agents/ in project).",
    )
    parser.add_argument(
        "--agent",
        action="append",
        dest="agents",
        help="Target agent(s): auto (default), all, claude-code, codex, antigravity, kimi-code, cursor, gemini-cli, opencode, universal.",
    )
    parser.add_argument("--target", type=Path, help="Target project directory (defaults to current working directory).")
    parser.add_argument("--home", type=Path, help="Simulated or custom user home directory (for global scope or detection).")
    parser.add_argument("--source", type=Path, help="Path to source skills/collab directory.")
    parser.add_argument("--no-backup", action="store_true", help="Skip creating a backup when updating an existing installation.")
    parser.add_argument("--uninstall", action="store_true", help="Remove installed COLLAB skill files without touching user project files.")
    parser.add_argument("--purge-backups", action="store_true", help="When uninstalling, also remove .collab-backups.")
    parser.add_argument("--verify-only", action="store_true", help="Only validate the source skill package and Python environment.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")
    args = parser.parse_args(argv)

    if args.is_local:
        scope = "project"
    elif args.is_global:
        scope = "global"
    else:
        scope = args.scope

    try:
        if args.verify_only:
            py_info = check_python_version()
            src = Path(args.source).resolve() if args.source else default_source_dir()
            validation = validate_skill_tree(src)
            runtime = verify_installed_runtime(src, py_info["executable"])
            result = {"ok": True, "action": "verify", "python": py_info, "skill": validation, "runtime": runtime}
        elif args.uninstall:
            result = uninstall_skill(
                scope=scope,
                agents=args.agents,
                project_root=args.target,
                home_dir=args.home,
                purge_backups=args.purge_backups,
            )
        else:
            result = install_skill(
                source_dir=args.source,
                scope=scope,
                agents=args.agents,
                project_root=args.target,
                home_dir=args.home,
                backup_on_update=not args.no_backup,
            )

        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            if result["action"] == "uninstall":
                if result["removed"]:
                    print("Removed COLLAB skill from:")
                    for path in result["removed"]:
                        print(f"  - {path}")
                else:
                    print("No COLLAB installation found in the selected scope.")
            elif result["action"] == "verify":
                print(f"Verified COLLAB skill source ({result['runtime']['version']}) with Python {result['python']['version']}.")
            else:
                print(f"COLLAB installed successfully (scope: {result['scope']}, Python {result['python']['version']}).")
                for item in result["installations"]:
                    print(f"  - [{item['display_name']}] {item['destination']} ({item['status']})")
                    if item.get("backup_path"):
                        print(f"    Backup saved to: {item['backup_path']}")
                    print(f"    Activate with: {item['invocation']}")
        return 0
    except InstallError as exc:
        err = {"ok": False, "error": {"code": exc.code, "message": str(exc), "details": exc.details}}
        if args.json:
            print(json.dumps(err, ensure_ascii=False))
        else:
            print(f"ERROR [{exc.code}]: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
