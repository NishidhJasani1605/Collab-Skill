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
import ast
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time

from . import __version__

sys.dont_write_bytecode = True

SKILL_NAME = "collab"
MIN_PYTHON = (3, 10)
REQUIRED_RELATIVE_FILES = (
    "SKILL.md",
    "scripts/collab.py",
    "scripts/collab_operator.py",
    "scripts/collablib/__init__.py",
    "scripts/collablib/engine.py",
    "scripts/collablib/checks.py",
    "scripts/collablib/installer.py",
    "scripts/install.py",
    "agents/openai.yaml",
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
        "global_rel": ".gemini/config/skills/collab",
        "invocation": "/collab <task>",
        "notes": "Use `/collab <task>` in Antigravity app/CLI, or ask the agent to use the `collab` skill in standalone IDE surfaces.",
    },
    "antigravity-cli": {
        "display_name": "Google Antigravity CLI",
        "project_rel": ".agents/skills/collab",
        "global_rel": ".gemini/antigravity-cli/skills/collab",
        "invocation": "/collab <task>",
        "notes": "The CLI uses a different user skill directory from the app and IDE.",
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
    candidate = Path(__file__).resolve().parents[2]
    if (candidate / "SKILL.md").is_file():
        return candidate
    raise InstallError("SOURCE_NOT_FOUND", f"Could not locate SKILL.md in {candidate}")


def safe_path(path: Path) -> Path:
    """Refuse links/reparse points before resolving any install/delete target."""
    path = Path(os.path.abspath(path))
    for part in reversed((path, *path.parents)):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        # macOS exposes standard OS directories through fixed /private aliases.
        # Accept only those exact system mappings, never arbitrary user links.
        system_alias = (sys.platform == "darwin" and stat.S_ISLNK(info.st_mode)
                        and part in (Path("/var"), Path("/tmp"), Path("/etc"))
                        and part.resolve() == Path("/private") / part.name)
        if not system_alias and (stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400):
            raise InstallError("UNSAFE_PATH", f"Linked installation path refused: {part}")
        if part != path and not system_alias and not stat.S_ISDIR(info.st_mode):
            raise InstallError("UNSAFE_PATH", f"Expected directory: {part}")
    # Resolve only after link checks, so containment checks use the same spelling
    # as resolved references (including Windows short-name directory aliases).
    return path.resolve()


def safe_tree(path: Path):
    safe_path(path)
    if not path.is_dir():
        raise InstallError("INVALID_SKILL_DIR", f"Expected a directory: {path}")
    for base, directories, files in os.walk(path, followlinks=False):
        for name in directories + files:
            item = Path(base) / name
            safe_path(item)
            info = item.stat()
            if not stat.S_ISDIR(info.st_mode) and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1):
                raise InstallError("UNSAFE_PATH", f"Nonregular or hard-linked installation file: {item}")


def require_owned(path: Path, code="UNSAFE_UPDATE"):
    safe_tree(path)
    try:
        manifest = json.loads((path / ".collab_installed.json").read_text(encoding="utf-8"))
        if isinstance(manifest, dict) and manifest.get("name") == SKILL_NAME:
            return
    except (OSError, ValueError):
        pass
    # Recognize older standalone installations that predate manifests and new
    # package files. Ownership is deliberately separate from release validity.
    try:
        text = (path / "SKILL.md").read_text(encoding="utf-8")
        header = re.match(r"\A---\s*\n(.*?)\n---(?:\s*\n|$)", text, re.DOTALL)
        identity = header and re.search(r"^name:\s*['\"]?collab['\"]?\s*$", header[1], re.MULTILINE)
        legacy_files = ("scripts/collab.py", "scripts/collablib/engine.py",
                        "scripts/collablib/storage.py", "references/commands.md")
        if identity and all((path / name).is_file() for name in legacy_files):
            return
    except (OSError, UnicodeError):
        pass
    raise InstallError(code, f"Refusing to modify an unrecognized COLLAB installation: {path}")


@contextmanager
def destination_lock(dest: Path):
    """Serialize installs, updates and uninstalls using a permanent sibling lock."""
    safe_path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    lock_path = safe_path(dest.parent / ".collab-install.lock")
    if lock_path.exists() and (not lock_path.is_file() or lock_path.stat().st_nlink != 1):
        raise InstallError("UNSAFE_PATH", f"Unsafe installer lock: {lock_path}")
    with open(lock_path, "a+b") as stream:
        deadline = time.monotonic() + 30
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise InstallError("INSTALL_BUSY", f"Another installer holds {lock_path}")
                time.sleep(0.05)
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


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
    skill_dir = safe_path(skill_dir)
    safe_tree(skill_dir)
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

    for source in skill_dir.rglob("*.py"):
        try:
            ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        except (SyntaxError, UnicodeError) as exc:
            raise InstallError("INVALID_PYTHON", f"Invalid Python source {source}: {exc}") from exc

    return {"name": SKILL_NAME, "files_verified": list(REQUIRED_RELATIVE_FILES)}


def detect_environments(project_root: Path, home_dir: Path, env: dict | None = None) -> list[str]:
    env = env if env is not None else os.environ
    active_markers = {
        "claude-code": ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "ANTHROPIC_CLAUDE_CODE"),
        "codex": ("CODEX_HOME", "OPENAI_CODEX", "CODEX_THREAD_ID"),
        "antigravity": ("ANTIGRAVITY_APP",),
        "antigravity-cli": ("ANTIGRAVITY_CLI",),
        "kimi-code": ("KIMI_CODE_HOME",), "cursor": ("CURSOR_TRACE_ID",),
        "gemini-cli": ("GEMINI_CLI",), "opencode": ("OPENCODE",),
    }
    active = [name for name, keys in active_markers.items() if any(env.get(k) for k in keys)]
    if active:
        return active
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
        or (home_dir / ".gemini" / "config").exists()
    ):
        detected.append("antigravity")
    if (home_dir / ".gemini" / "antigravity-cli").exists():
        detected.append("antigravity-cli")
    if env.get("KIMI_CODE_HOME") or (project_root / ".kimi-code").exists() or (home_dir / ".kimi-code").exists():
        detected.append("kimi-code")
    if env.get("CURSOR_TRACE_ID") or (project_root / ".cursor").exists() or (home_dir / ".cursor").exists():
        detected.append("cursor")
    if env.get("GEMINI_CLI") or (project_root / ".gemini").exists() or (home_dir / ".gemini/settings.json").exists() or (home_dir / ".gemini/skills").exists():
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
            return Path(env["CODEX_HOME"]).absolute() / "skills" / SKILL_NAME
        if agent == "kimi-code" and env.get("KIMI_CODE_HOME"):
            return Path(env["KIMI_CODE_HOME"]).absolute() / "skills" / SKILL_NAME
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
    preserve_recovery = False
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
            "version": __version__,
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "manifest": "verified"
        }
        (target_stage / ".collab_installed.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        # Verify staged code before touching the working installation.
        verify_installed_runtime(target_stage)
        previous = tmp_dir / "previous"
        try:
            if dst.exists():
                dst.rename(previous)
            target_stage.rename(dst)
        except BaseException:
            if previous.exists() and not dst.exists():
                try:
                    previous.rename(dst)
                except OSError as exc:
                    preserve_recovery = True
                    raise InstallError("ROLLBACK_FAILED", f"Previous installation preserved at {previous}") from exc
            raise
    finally:
        if tmp_dir.exists() and not preserve_recovery:
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
        env=dict(os.environ, PYTHONUTF8="1", PYTHONPATH="", PYTHONDONTWRITEBYTECODE="1"),
        timeout=30,
    )
    if completed.returncode != 0:
        raise InstallError(
            "RUNTIME_VERIFICATION_FAILED",
            f"Installed helper failed --version check: {completed.stderr or completed.stdout}",
        )
    version = completed.stdout.strip()
    if not version:
        raise InstallError("RUNTIME_VERIFICATION_FAILED", "Installed helper returned an empty version")
    return {"helper": str(helper), "version": version, "verified": True}


def select_agents(agents, detected):
    if not agents or agents == ["auto"]:
        return list(detected)
    if agents == ["all"]:
        return list(PLATFORMS)
    if any(name not in PLATFORMS for name in agents):
        raise InstallError("UNKNOWN_AGENT", "Use supported agent names, or auto/all alone")
    return list(dict.fromkeys(agents))


def destinations_for(agents, scope, project, home, env):
    # Validate the complete plan before making any filesystem changes.
    result = []
    for agent in agents:
        dest = safe_path(resolve_destination(agent, scope, project, home, env))
        if scope == "global" and project != home and dest.is_relative_to(project):
            raise InstallError("PROJECT_DESTINATION", "Global skill destination falls inside the project; choose a user-level home outside it")
        result.append((agent, dest))
    return result


def install_skill(*, source_dir=None, scope="global", agents=None, project_root=None,
                  home_dir=None, backup_on_update=True, env=None):
    env = env if env is not None else os.environ
    py_info = check_python_version()
    src = safe_path(source_dir or default_source_dir())
    validate_skill_tree(src)
    proj = Path(project_root).resolve() if project_root else Path.cwd().resolve()
    home = safe_path(home_dir or Path.home())
    if not proj.is_dir():
        raise InstallError("INVALID_PROJECT_ROOT", f"Project root does not exist: {proj}")
    if not home.is_dir():
        raise InstallError("INVALID_HOME_DIR", f"Home directory does not exist: {home}")
    detected = detect_environments(proj, home, env)
    selected = select_agents(agents, detected)
    planned = destinations_for(selected, scope, proj, home, env)
    for _, dest in planned:
        if src != dest and (src.is_relative_to(dest) or dest.is_relative_to(src)):
            raise InstallError("OVERLAPPING_PATHS", "Source and destination cannot contain each other")
        if dest.exists():
            require_owned(dest)
    source_digest = _tree_digest(src)
    installations, seen = [], {}
    for agent, dest in planned:
        if dest not in seen:
            with destination_lock(dest):
                safe_path(dest)
                backup = None
                status = "installed"
                if dest.exists():
                    require_owned(dest)
                    status = "up_to_date" if _tree_digest(dest) == source_digest else "updated"
                if status == "updated" and backup_on_update:
                    backup_root = safe_path(dest.parent / ".collab-backups")
                    backup_root.mkdir(exist_ok=True)
                    backup = Path(tempfile.mkdtemp(prefix="collab-", dir=backup_root))
                    shutil.copytree(dest, backup, dirs_exist_ok=True)
                if status != "up_to_date":
                    _copy_clean_skill(src, dest)
                runtime = verify_installed_runtime(dest, py_info["executable"])
                seen[dest] = {"path": str(dest), "status": status,
                              "backup_path": str(backup) if backup else None,
                              "runtime": runtime, "agents": []}
        item = seen[dest]
        item["agents"].append(agent)
        installations.append({"agent": agent, "display_name": PLATFORMS[agent]["display_name"],
                              "destination": str(dest), "status": item["status"],
                              "backup_path": item["backup_path"],
                              "invocation": PLATFORMS[agent]["invocation"],
                              "notes": PLATFORMS[agent]["notes"]})
    return {"ok": True, "action": "install", "scope": scope, "python": py_info,
            "detected_environments": detected, "installations": installations,
            "destinations": list(seen.values())}


def uninstall_skill(*, scope="global", agents=None, project_root=None, home_dir=None,
                    purge_backups=False, env=None):
    env = env if env is not None else os.environ
    proj = Path(project_root).resolve() if project_root else Path.cwd().resolve()
    home = safe_path(home_dir or Path.home())
    selected = select_agents(agents, detect_environments(proj, home, env))
    planned = destinations_for(selected, scope, proj, home, env)
    for _, dest in planned:
        if dest.exists():
            require_owned(dest, "UNSAFE_UNINSTALL")
    removed, missing, checked = [], [], set()
    for _, dest in planned:
        if dest in checked:
            continue
        checked.add(dest)
        if not dest.parent.exists():
            missing.append(str(dest))
            continue
        with destination_lock(dest):
            safe_path(dest)
            if dest.exists():
                require_owned(dest, "UNSAFE_UNINSTALL")
                shutil.rmtree(dest)
                removed.append(str(dest))
            else:
                missing.append(str(dest))
            if purge_backups:
                backups = safe_path(dest.parent / ".collab-backups")
                if backups.exists():
                    safe_tree(backups)
                    # Preserve unrelated contents instead of deleting the whole directory.
                    for child in backups.iterdir():
                        if child.is_dir() and child.name.startswith("collab-"):
                            require_owned(child, "UNSAFE_UNINSTALL")
                            shutil.rmtree(child)
                    if not any(backups.iterdir()):
                        backups.rmdir()
    return {"ok": True, "action": "uninstall", "scope": scope,
            "removed": removed, "not_installed": missing}


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    class JsonParser(argparse.ArgumentParser):
        def error(self, message):
            if "--json" in (sys.argv[1:] if argv is None else argv):
                print(json.dumps({"ok": False, "error": {"code": "INVALID_INPUT", "message": message}}))
                raise SystemExit(2)
            super().error(message)

    parser = JsonParser(
        description="Install, verify, update, or uninstall the local COLLAB Agent Skill."
    )
    parser.add_argument(
        "--scope", "--mode",
        choices=("global", "project"),
        default="global",
        help="Install scope: 'global' (default, user home directory, keeps project workspaces clean) or 'project' (--local).",
    )
    scope_flags = parser.add_mutually_exclusive_group()
    scope_flags.add_argument(
        "--global",
        "-g",
        dest="is_global",
        action="store_true",
        help="Install globally into user home directory (default).",
    )
    scope_flags.add_argument(
        "--local",
        "-l",
        dest="is_local",
        action="store_true",
        help="Install into current project directory (creates .claude/ or .agents/ in project).",
    )
    parser.add_argument(
        "--agent", "--platform",
        action="append",
        dest="agents",
        help="Target agent(s): auto (default), all, " + ", ".join(PLATFORMS) + ".",
    )
    parser.add_argument("--target", "--project", type=Path, help="Project directory for detection; does not enable project installation.")
    parser.add_argument("--home", type=Path, help="Simulated or custom user home directory (for global scope or detection).")
    parser.add_argument("--source", type=Path, help="Path to source skills/collab directory.")
    parser.add_argument("--no-backup", action="store_true", help="Skip creating a backup when updating an existing installation.")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--uninstall", action="store_true", help="Remove installed COLLAB skill files without touching user project files.")
    parser.add_argument("--purge-backups", action="store_true", help="When uninstalling, also remove .collab-backups.")
    actions.add_argument("--verify-only", "--verify", action="store_true", help="Validate --source (or this package), Python and helper startup without creating project state.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")
    args = parser.parse_args(argv)
    aliases = {"claude": "claude-code", "kimi": "kimi-code", "gemini": "gemini-cli", "standard": "universal"}
    if args.agents:
        args.agents = [aliases.get(name, name) for name in args.agents]

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
    except (InstallError, OSError, ValueError, subprocess.SubprocessError) as exc:
        code = exc.code if isinstance(exc, InstallError) else "INSTALL_FAILED"
        err = {"ok": False, "error": {"code": code, "message": str(exc), "details": getattr(exc, "details", None)}}
        if args.json:
            print(json.dumps(err, ensure_ascii=False))
        else:
            print(f"ERROR [{code}]: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
