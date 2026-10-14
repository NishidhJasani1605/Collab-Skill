#!/usr/bin/env python3
"""
COLLAB Skill Installer & Verification Tool.
Pure standard-library installer for project-local and user-global Agent Skills setups.
Supports Claude Code, Codex, Antigravity, Cursor, Gemini CLI, Kimi Code, OpenCode,
and standard Agent Skills environments (https://agentskills.io/specification).
"""

from __future__ import annotations

import argparse
import ast
import datetime
import importlib.util
import json
import os
import pathlib
import platform
import shutil
import sys
from typing import Any, Dict, List, Optional, Tuple

MIN_PYTHON_VERSION = (3, 10)

SUPPORTED_PLATFORMS = (
    "auto",
    "claude",
    "codex",
    "antigravity",
    "cursor",
    "gemini",
    "kimi",
    "opencode",
    "standard",
)

INVOCATIONS: Dict[str, Dict[str, str]] = {
    "claude": {
        "command": "/collab",
        "description": "Invoke /collab with your task in Claude Code.",
        "plugin_note": "If installed via /plugin, invoke with /collab-skill:collab.",
    },
    "codex": {
        "command": "$collab",
        "description": "Invoke with $collab or select 'collab' from the /skills menu in Codex.",
        "plugin_note": "",
    },
    "antigravity": {
        "command": "/collab",
        "description": "Invoke /collab with your task in Antigravity or Antigravity IDE.",
        "plugin_note": "",
    },
    "cursor": {
        "command": "/collab",
        "description": "Invoke /collab or mention @collab in Cursor composer/chat.",
        "plugin_note": "",
    },
    "gemini": {
        "command": "/collab",
        "description": "Ask Gemini CLI: 'Use collab skill: <task>' or invoke /collab.",
        "plugin_note": "Reload skills with /skills reload if newly added.",
    },
    "kimi": {
        "command": "/skill:collab",
        "description": "Invoke /skill:collab <task> or /collab in Kimi Code CLI.",
        "plugin_note": "",
    },
    "opencode": {
        "command": "/collab",
        "description": "Invoke /collab in OpenCode.",
        "plugin_note": "",
    },
    "standard": {
        "command": "/collab",
        "description": "Invoke /collab or use your host's standard Agent Skills activation.",
        "plugin_note": "",
    },
}


def check_python_version() -> Tuple[bool, str]:
    """Verify that current Python meets the minimum version requirement (3.10+)."""
    major = sys.version_info[0]
    minor = sys.version_info[1]
    micro = sys.version_info[2] if len(sys.version_info) > 2 else 0
    if (major, minor) < MIN_PYTHON_VERSION:
        return (
            False,
            f"Python {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]}+ is required. "
            f"Found Python {major}.{minor}.{micro} at '{sys.executable}'.",
        )
    return True, f"Python {major}.{minor}.{micro} meets requirements."


def detect_platform(project_dir: Optional[pathlib.Path] = None) -> str:
    """
    Auto-detect the active AI coding agent environment.
    Inspects environment variables first, then workspace directories.
    """
    env = os.environ

    # Environment variable heuristics
    if "CLAUDE_CODE" in env or "CLAUDE_PROJECT_DIR" in env:
        return "claude"
    if "ANTIGRAVITY" in env or "ANTIGRAVITY_APP" in env:
        return "antigravity"
    if "CODEX_ENV" in env or "OPENAI_CODEX" in env:
        return "codex"
    if "CURSOR_TRACE_ID" in env or "CURSOR_PROJECT_DIR" in env or "CURSOR_VERSION" in env:
        return "cursor"
    if "GEMINI_CLI" in env:
        return "gemini"
    if "KIMI_ENV" in env or "KIMI_CODE" in env:
        return "kimi"
    if "OPENCODE" in env:
        return "opencode"

    # Filesystem heuristics in the project directory
    if project_dir is not None and project_dir.exists():
        if (project_dir / ".claude").is_dir():
            return "claude"
        if (project_dir / ".gemini").is_dir():
            return "antigravity"
        if (project_dir / ".cursor").is_dir():
            return "cursor"
        if (project_dir / ".opencode").is_dir():
            return "opencode"
        if (project_dir / ".kimi").is_dir():
            return "kimi"

    # Default to open Agent Skills standard
    return "standard"


def resolve_target_dir(
    mode: str,
    platform_name: str,
    project_dir: Optional[pathlib.Path] = None,
    dest: Optional[pathlib.Path] = None,
) -> pathlib.Path:
    """
    Determine the target installation directory based on mode and platform.
    """
    if dest is not None:
        return dest.resolve()

    home = pathlib.Path.home().resolve()
    target_platform = platform_name if platform_name != "auto" else detect_platform(project_dir)

    if mode == "global":
        if target_platform == "claude":
            return home / ".claude" / "skills" / "collab"
        elif target_platform == "antigravity":
            # Prefer ~/.gemini/antigravity/skills if exists, otherwise standard ~/.agents/skills
            gemini_skills = home / ".gemini" / "antigravity" / "skills" / "collab"
            if gemini_skills.parent.exists():
                return gemini_skills
            return home / ".agents" / "skills" / "collab"
        elif target_platform == "gemini":
            return home / ".gemini" / "skills" / "collab"
        elif target_platform == "cursor":
            return home / ".cursor" / "skills" / "collab"
        elif target_platform == "kimi":
            return home / ".kimi" / "skills" / "collab"
        elif target_platform == "opencode":
            return home / ".config" / "opencode" / "skills" / "collab"
        else:
            # Standard Agent Skills specification
            return home / ".agents" / "skills" / "collab"
    else:
        # Project-local
        base = project_dir.resolve() if project_dir else pathlib.Path.cwd().resolve()
        if target_platform == "claude":
            return base / ".claude" / "skills" / "collab"
        elif target_platform == "cursor":
            # Cursor supports both .cursor/skills and .agents/skills; prefer .agents/skills standard
            cursor_dir = base / ".cursor" / "skills"
            if cursor_dir.exists():
                return cursor_dir / "collab"
            return base / ".agents" / "skills" / "collab"
        elif target_platform == "gemini":
            gemini_dir = base / ".gemini" / "skills"
            if gemini_dir.exists():
                return gemini_dir / "collab"
            return base / ".agents" / "skills" / "collab"
        else:
            # Universal Agent Skills standard
            return base / ".agents" / "skills" / "collab"


def locate_source_skill_dir(source_override: Optional[pathlib.Path] = None) -> pathlib.Path:
    """
    Locate the canonical 'skills/collab' directory to install from.
    """
    if source_override is not None:
        p = source_override.resolve()
        if (p / "SKILL.md").exists():
            return p
        raise FileNotFoundError(f"Provided source directory '{p}' does not contain SKILL.md.")

    script_path = pathlib.Path(__file__).resolve()
    # If this script is at skills/collab/scripts/install.py, source is skills/collab
    candidate1 = script_path.parent.parent
    if (candidate1 / "SKILL.md").exists():
        return candidate1

    # If this script is at repo root (install.py), source is repo_root/skills/collab
    candidate2 = script_path.parent / "skills" / "collab"
    if (candidate2 / "SKILL.md").exists():
        return candidate2

    # Check current working directory
    candidate3 = pathlib.Path.cwd().resolve() / "skills" / "collab"
    if (candidate3 / "SKILL.md").exists():
        return candidate3

    raise FileNotFoundError(
        "Could not automatically locate the COLLAB skill source directory containing SKILL.md. "
        "Please provide --source <path>."
    )


def backup_directory(target_dir: pathlib.Path) -> Optional[pathlib.Path]:
    """
    Create a timestamped backup of the existing target directory.
    Example: collab -> collab.bak.20261014T120000Z
    """
    if not target_dir.exists():
        return None

    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_name = f"{target_dir.name}.bak.{timestamp}"
    backup_path = target_dir.parent / backup_name

    counter = 1
    while backup_path.exists():
        backup_path = target_dir.parent / f"{target_dir.name}.bak.{timestamp}_{counter}"
        counter += 1

    shutil.move(str(target_dir), str(backup_path))
    return backup_path


def verify_installation(target_dir: pathlib.Path) -> Tuple[bool, List[str]]:
    """
    Inspect an installed COLLAB skill folder for completeness and validity.
    """
    issues: List[str] = []

    if not target_dir.exists():
        return False, [f"Target directory '{target_dir}' does not exist."]
    if not target_dir.is_dir():
        return False, [f"Target '{target_dir}' is not a directory."]

    skill_md = target_dir / "SKILL.md"
    if not skill_md.exists():
        issues.append("Missing SKILL.md")
    else:
        try:
            content = skill_md.read_text(encoding="utf-8")
            if "name: collab" not in content and 'name: "collab"' not in content:
                issues.append("SKILL.md missing 'name: collab' metadata.")
        except Exception as exc:
            issues.append(f"Failed reading SKILL.md: {exc}")

    required_files = [
        target_dir / "references" / "commands.md",
        target_dir / "references" / "safety.md",
        target_dir / "scripts" / "collab.py",
        target_dir / "scripts" / "collab_operator.py",
        target_dir / "scripts" / "collablib" / "__init__.py",
        target_dir / "scripts" / "collablib" / "storage.py",
        target_dir / "scripts" / "collablib" / "engine.py",
    ]

    for req in required_files:
        if not req.exists():
            issues.append(f"Missing required file: {req.relative_to(target_dir)}")
        elif req.suffix == ".py":
            # Verify Python syntax parses cleanly
            try:
                code = req.read_text(encoding="utf-8")
                ast.parse(code, filename=str(req))
            except SyntaxError as syn_err:
                issues.append(f"Syntax error in {req.name}: {syn_err}")
            except Exception as exc:
                issues.append(f"Cannot read {req.name}: {exc}")

    # Test importing storage and engine modules dynamically from the target
    scripts_dir = target_dir / "scripts"
    if scripts_dir.exists():
        engine_path = scripts_dir / "collablib" / "engine.py"
        if engine_path.exists():
            orig_path = list(sys.path)
            try:
                if str(scripts_dir) not in sys.path:
                    sys.path.insert(0, str(scripts_dir))
                for mod_name in list(sys.modules.keys()):
                    if mod_name == "collablib" or mod_name.startswith("collablib."):
                        del sys.modules[mod_name]
                import collablib.engine
                if not hasattr(collablib.engine, "execute"):
                    issues.append("Installed engine.py is missing execute function.")
            except Exception as exc:
                issues.append(f"Failed importing installed collablib: {exc}")
            finally:
                sys.path = orig_path

    return len(issues) == 0, issues


def install_skill(
    source_dir: pathlib.Path,
    target_dir: pathlib.Path,
    backup: bool = True,
    platform_name: str = "auto",
    mode: str = "project",
) -> Dict[str, Any]:
    """
    Safely install COLLAB from source_dir to target_dir.
    """
    py_ok, py_msg = check_python_version()
    if not py_ok:
        return {
            "success": False,
            "error": py_msg,
            "target_dir": str(target_dir),
            "action": "install",
        }

    backup_path: Optional[pathlib.Path] = None

    if target_dir.exists():
        if backup:
            try:
                backup_path = backup_directory(target_dir)
            except Exception as exc:
                return {
                    "success": False,
                    "error": f"Failed creating backup of existing installation: {exc}",
                    "target_dir": str(target_dir),
                    "action": "install",
                }
        else:
            try:
                shutil.rmtree(str(target_dir))
            except Exception as exc:
                return {
                    "success": False,
                    "error": f"Failed removing existing target without backup: {exc}",
                    "target_dir": str(target_dir),
                    "action": "install",
                }

    target_dir.parent.mkdir(parents=True, exist_ok=True)

    def ignore_patterns(folder: str, names: List[str]) -> List[str]:
        ignored = []
        for name in names:
            if name.startswith("__pycache__") or name.endswith((".pyc", ".pyo", ".bak")):
                ignored.append(name)
            elif name in (".git", ".pytest_cache", ".DS_Store"):
                ignored.append(name)
        return ignored

    try:
        shutil.copytree(str(source_dir), str(target_dir), ignore=ignore_patterns)
    except Exception as exc:
        # Restore backup if available and copy failed
        if backup_path and backup_path.exists() and not target_dir.exists():
            shutil.move(str(backup_path), str(target_dir))
        return {
            "success": False,
            "error": f"Copy failed: {exc}",
            "target_dir": str(target_dir),
            "action": "install",
        }

    # Set execution permissions on POSIX systems
    if platform.system() != "Windows":
        for script_file in (target_dir / "scripts").glob("*.py"):
            try:
                script_file.chmod(script_file.stat().st_mode | 0o755)
            except Exception:
                pass

    valid, issues = verify_installation(target_dir)
    if not valid:
        return {
            "success": False,
            "error": f"Installation verification failed: {'; '.join(issues)}",
            "target_dir": str(target_dir),
            "backup_dir": str(backup_path) if backup_path else None,
            "action": "install",
        }

    detected_platform = platform_name if platform_name != "auto" else detect_platform()
    inv_info = INVOCATIONS.get(detected_platform, INVOCATIONS["standard"])

    return {
        "success": True,
        "action": "install",
        "target_dir": str(target_dir),
        "source_dir": str(source_dir),
        "platform": detected_platform,
        "mode": mode,
        "backup_dir": str(backup_path) if backup_path else None,
        "invocation": inv_info["command"],
        "description": inv_info["description"],
        "plugin_note": inv_info.get("plugin_note", ""),
        "python_executable": sys.executable,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "message": f"COLLAB v1.0.0-beta.1 installed successfully. Activate using {inv_info['command']}.",
    }


def uninstall_skill(target_dir: pathlib.Path) -> Dict[str, Any]:
    """
    Safely remove the COLLAB skill installation.
    """
    if not target_dir.exists():
        return {
            "success": False,
            "error": f"COLLAB installation not found at '{target_dir}'.",
            "target_dir": str(target_dir),
            "action": "uninstall",
        }

    # Identify existing backups before removing
    backups: List[str] = []
    parent = target_dir.parent
    if parent.exists():
        for item in parent.glob(f"{target_dir.name}.bak.*"):
            backups.append(item.name)

    try:
        shutil.rmtree(str(target_dir))
    except Exception as exc:
        return {
            "success": False,
            "error": f"Failed removing directory '{target_dir}': {exc}",
            "target_dir": str(target_dir),
            "action": "uninstall",
        }

    return {
        "success": True,
        "action": "uninstall",
        "target_dir": str(target_dir),
        "preserved_backups": backups,
        "message": f"COLLAB skill removed from '{target_dir}'.",
    }


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="install.py",
        description="COLLAB Universal Agent Skill Installer & Verifier",
    )
    parser.add_argument(
        "--mode",
        choices=["project", "global"],
        default="project",
        help="Installation scope: 'project' (default) or 'global' (user home).",
    )
    parser.add_argument(
        "--global",
        "-g",
        dest="is_global",
        action="store_true",
        help="Shorthand for --mode global.",
    )
    parser.add_argument(
        "--platform",
        choices=SUPPORTED_PLATFORMS,
        default="auto",
        help="Target AI coding agent platform (default: auto-detect).",
    )
    parser.add_argument(
        "--project",
        type=pathlib.Path,
        default=None,
        help="Target project directory when mode is project (default: current working directory).",
    )
    parser.add_argument(
        "--dest",
        type=pathlib.Path,
        default=None,
        help="Custom destination directory (overrides mode and platform resolution).",
    )
    parser.add_argument(
        "--source",
        type=pathlib.Path,
        default=None,
        help="Custom source directory containing SKILL.md (default: bundled skills/collab).",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Overwrite destination directly without creating a timestamped backup.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify existing installation at target directory without modifying files.",
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Uninstall COLLAB from the target destination.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON results for automated agent callers.",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress informational output.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    mode = "global" if args.is_global else args.mode
    project_dir = args.project.resolve() if args.project else pathlib.Path.cwd().resolve()
    target_dir = resolve_target_dir(
        mode=mode,
        platform_name=args.platform,
        project_dir=project_dir,
        dest=args.dest,
    )

    if args.verify:
        valid, issues = verify_installation(target_dir)
        result = {
            "success": valid,
            "action": "verify",
            "target_dir": str(target_dir),
            "issues": issues,
            "message": "Installation verified successfully." if valid else f"Issues: {'; '.join(issues)}",
        }
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if valid:
                print(f"[OK] COLLAB installation at '{target_dir}' is complete and valid.")
            else:
                print(f"[FAIL] COLLAB installation at '{target_dir}' has issues:")
                for issue in issues:
                    print(f"  - {issue}")
        return 0 if valid else 1

    if args.uninstall:
        result = uninstall_skill(target_dir)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if result["success"]:
                print(f"[OK] {result['message']}")
                if result.get("preserved_backups"):
                    print(f"  Preserved backups: {', '.join(result['preserved_backups'])}")
            else:
                print(f"[ERROR] {result['error']}")
        return 0 if result["success"] else 1

    # Installation
    try:
        source_dir = locate_source_skill_dir(args.source)
    except Exception as exc:
        err_res = {
            "success": False,
            "action": "install",
            "error": str(exc),
            "target_dir": str(target_dir),
        }
        if args.json:
            print(json.dumps(err_res, indent=2))
        else:
            print(f"[ERROR] {exc}")
        return 1

    res = install_skill(
        source_dir=source_dir,
        target_dir=target_dir,
        backup=not args.no_backup,
        platform_name=args.platform,
        mode=mode,
    )

    if args.json:
        print(json.dumps(res, indent=2))
    else:
        if res["success"]:
            print(f"============================================================")
            print(f"  COLLAB -- Universal Agent Collaboration Skill Installed")
            print(f"============================================================")
            print(f"Target Directory: {res['target_dir']}")
            print(f"Platform:         {res['platform']} ({res['mode']})")
            print(f"Python:           {res['python_executable']} ({res['python_version']})")
            if res.get("backup_dir"):
                print(f"Backup Created:   {res['backup_dir']}")
            print(f"")
            print(f"Activation:")
            print(f"  Command:        {res['invocation']}")
            print(f"  Detail:         {res['description']}")
            if res.get("plugin_note"):
                print(f"  Note:           {res['plugin_note']}")
            print(f"")
            print(f"If your agent IDE does not immediately show the new skill,")
            print(f"restart the IDE session or refresh skills to discover it.")
            print(f"============================================================")
        else:
            print(f"[ERROR] Installation failed: {res['error']}")

    return 0 if res["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
