"""Comprehensive automated tests for the COLLAB Universal Paste-to-Install workflow and installer."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid

REPOSITORY = Path(__file__).resolve().parents[1]
INSTALLER = REPOSITORY / "scripts" / "install_collab.py"
SKILL_SOURCE = REPOSITORY / "skills" / "collab"

sys.path.insert(0, str(REPOSITORY / "scripts"))
import install_collab


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="collab-installer-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.project = self.base / "user_project"
        self.project.mkdir()
        self.home = self.base / "user_home"
        self.home.mkdir()

    def run_cli(self, *args, env_overrides=None, expect_ok=True):
        env = dict(os.environ, PYTHONUTF8="1")
        for key in (
            "CLAUDECODE",
            "CLAUDE_CODE_ENTRYPOINT",
            "ANTHROPIC_CLAUDE_CODE",
            "CODEX_HOME",
            "OPENAI_CODEX",
            "ANTIGRAVITY_CLI",
            "ANTIGRAVITY_APP",
            "KIMI_CODE_HOME",
            "CURSOR_TRACE_ID",
            "GEMINI_CLI",
            "OPENCODE",
            "COLLAB_TEST_PYTHON_VERSION",
        ):
            env.pop(key, None)
        if env_overrides:
            env.update(env_overrides)
        completed = subprocess.run(
            [sys.executable, str(INSTALLER), "--json", *map(str, args)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            timeout=60,
        )
        try:
            payload = json.loads(completed.stdout)
        except Exception as exc:
            raise AssertionError(f"Failed to parse JSON output: {completed.stdout}\nstderr: {completed.stderr}") from exc
        self.assertEqual(payload.get("ok"), expect_ok, (completed.stdout, completed.stderr))
        self.assertEqual(completed.returncode, 0 if expect_ok else 2)
        return payload

    def test_01_skill_directory_metadata_scripts_and_relative_paths(self):
        """Verify items 1-4: skill structure, metadata, complete script packaging, and no broken relative links."""
        res = self.run_cli("--verify-only")
        self.assertEqual(res["skill"]["name"], "collab")
        for rel in install_collab.REQUIRED_RELATIVE_FILES:
            self.assertIn(rel, res["skill"]["files_verified"])
            self.assertTrue((SKILL_SOURCE / rel).is_file(), f"Missing {rel}")

        # Verify broken relative path detection on a mutated copy
        broken_skill = self.base / "broken_skill"
        shutil.copytree(SKILL_SOURCE, broken_skill)
        skill_md = broken_skill / "SKILL.md"
        skill_md.write_text(skill_md.read_text(encoding="utf-8") + "\nSee [missing](references/nonexistent.md).\n", encoding="utf-8")
        err = self.run_cli("--verify-only", "--source", broken_skill, expect_ok=False)
        self.assertEqual(err["error"]["code"], "BROKEN_RELATIVE_PATHS")

    def test_02_project_and_global_installation_for_supported_agents(self):
        """Verify items 5 & 6: installation across project-local and global scopes for all supported platforms."""
        # 1. Project-local installation targeting Claude Code, Codex, and Antigravity
        proj_res = self.run_cli("--scope", "project", "--agent", "claude-code", "--agent", "codex", "--agent", "antigravity", "--target", self.project, "--home", self.home)
        self.assertTrue(proj_res["ok"])
        self.assertTrue((self.project / ".claude" / "skills" / "collab" / "SKILL.md").is_file())
        self.assertTrue((self.project / ".agents" / "skills" / "collab" / "SKILL.md").is_file())

        # 2. Global installation across all agents
        glob_res = self.run_cli("--scope", "global", "--agent", "all", "--target", self.project, "--home", self.home)
        self.assertTrue(glob_res["ok"])
        expected_global = [
            self.home / ".claude" / "skills" / "collab" / "SKILL.md",
            self.home / ".agents" / "skills" / "collab" / "SKILL.md",
            self.home / ".gemini" / "antigravity" / "skills" / "collab" / "SKILL.md",
            self.home / ".kimi-code" / "skills" / "collab" / "SKILL.md",
            self.home / ".cursor" / "skills" / "collab" / "SKILL.md",
            self.home / ".gemini" / "skills" / "collab" / "SKILL.md",
            self.home / ".config" / "opencode" / "skills" / "collab" / "SKILL.md",
        ]
        for path in expected_global:
            self.assertTrue(path.is_file(), f"Missing global skill at {path}")
        self.assertEqual(len(glob_res["installations"]), len(install_collab.PLATFORMS))

    def test_03_paths_with_spaces_and_end_to_end_installed_helper_execution(self):
        """Verify item 7 & 16: installation into paths with spaces and multi-agent communication across installed skills."""
        spaced_project = self.base / "My Test Project With Spaces"
        spaced_project.mkdir()
        spaced_home = self.base / "Home Directory With Spaces"
        spaced_home.mkdir()

        self.run_cli("--scope", "project", "--agent", "claude-code", "--agent", "codex", "--target", spaced_project, "--home", spaced_home)
        claude_helper = spaced_project / ".claude" / "skills" / "collab" / "scripts" / "collab.py"
        codex_helper = spaced_project / ".agents" / "skills" / "collab" / "scripts" / "collab.py"
        self.assertTrue(claude_helper.is_file())
        self.assertTrue(codex_helper.is_file())

        # Agent 1 (via Claude Code installed copy) starts a task and sends a message
        start_a = subprocess.run(
            [
                sys.executable,
                str(claude_helper),
                "--root",
                str(spaced_project),
                "start",
                "--data",
                json.dumps({"name": "Claude Agent", "platform": "claude-code", "session_id": str(uuid.uuid4()), "objective": "Cross-IDE install verification"}),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
        res_a = json.loads(start_a.stdout)
        self.assertTrue(res_a["ok"])

        # Agent 2 (via Codex installed copy) joins the same task and reads Agent 1's JOIN event
        start_b = subprocess.run(
            [
                sys.executable,
                str(codex_helper),
                "--root",
                str(spaced_project),
                "start",
                "--data",
                json.dumps({"name": "Codex Agent", "platform": "codex", "session_id": str(uuid.uuid4()), "task_id": res_a["task"]["id"]}),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
        res_b = json.loads(start_b.stdout)
        self.assertTrue(res_b["ok"])
        self.assertEqual(res_a["task"]["id"], res_b["task"]["id"])
        self.assertEqual(len(res_b["task"]["participants"]), 2)

    def test_04_repeated_install_update_backup_and_safe_uninstall(self):
        """Verify items 8, 9, 10: idempotent reinstall, backup on update, preserving unrelated skills/files, and safe uninstall."""
        user_file = self.project / "important_code.py"
        user_file.write_text("print('keep me')\n", encoding="utf-8")
        unrelated_skill = self.project / ".agents" / "skills" / "other-skill"
        unrelated_skill.mkdir(parents=True)
        (unrelated_skill / "SKILL.md").write_text("---\nname: other-skill\ndescription: keep\n---\n", encoding="utf-8")

        # First install -> status 'installed'
        first = self.run_cli("--scope", "project", "--agent", "universal", "--target", self.project, "--home", self.home)
        self.assertEqual(first["installations"][0]["status"], "installed")

        # Second identical install -> status 'up_to_date'
        second = self.run_cli("--scope", "project", "--agent", "universal", "--target", self.project, "--home", self.home)
        self.assertEqual(second["installations"][0]["status"], "up_to_date")

        # Modify installed file to simulate an older version, then reinstall -> status 'updated' with backup
        installed_readme = self.project / ".agents" / "skills" / "collab" / "references" / "commands.md"
        installed_readme.write_text("# Old commands reference\n", encoding="utf-8")
        third = self.run_cli("--scope", "project", "--agent", "universal", "--target", self.project, "--home", self.home)
        self.assertEqual(third["installations"][0]["status"], "updated")
        backup_path = Path(third["installations"][0]["backup_path"])
        self.assertTrue((backup_path / "references" / "commands.md").is_file())
        self.assertEqual((backup_path / "references" / "commands.md").read_text(encoding="utf-8"), "# Old commands reference\n")

        # Verify unrelated skill and user project file are untouched
        self.assertTrue((unrelated_skill / "SKILL.md").is_file())
        self.assertEqual(user_file.read_text(encoding="utf-8"), "print('keep me')\n")

        # Uninstall COLLAB -> removes collab skill, preserves unrelated_skill and user_file
        uninst = self.run_cli("--uninstall", "--purge-backups", "--scope", "project", "--agent", "universal", "--target", self.project, "--home", self.home)
        self.assertFalse((self.project / ".agents" / "skills" / "collab").exists())
        self.assertFalse((self.project / ".agents" / "skills" / ".collab-backups").exists())
        self.assertTrue((unrelated_skill / "SKILL.md").is_file())
        self.assertEqual(user_file.read_text(encoding="utf-8"), "print('keep me')\n")
        self.assertTrue(len(uninst["removed"]) >= 1)

        # UNSAFE UNINSTALL GUARD: If an unrelated directory named 'collab' exists without COLLAB markers, uninstall must REFUSE
        fake_collab = self.project / ".agents" / "skills" / "collab"
        fake_collab.mkdir(parents=True, exist_ok=True)
        (fake_collab / "user_data.txt").write_text("Do not delete this!\n", encoding="utf-8")
        err = self.run_cli("--uninstall", "--scope", "project", "--agent", "universal", "--target", self.project, "--home", self.home, expect_ok=False)
        self.assertEqual(err["error"]["code"], "UNSAFE_UNINSTALL")
        self.assertTrue((fake_collab / "user_data.txt").is_file())
        shutil.rmtree(fake_collab)

    def test_05_unsupported_python_version_and_environment_detection(self):
        """Verify items 11 & 13: Python prerequisite failure handling and host environment auto-detection."""
        err = self.run_cli(
            "--scope",
            "project",
            "--target",
            self.project,
            "--home",
            self.home,
            env_overrides={"COLLAB_TEST_PYTHON_VERSION": "3.9"},
            expect_ok=False,
        )
        self.assertEqual(err["error"]["code"], "PYTHON_VERSION_UNSUPPORTED")

        # Missing Python executable check via API
        with self.assertRaises(install_collab.InstallError) as caught:
            install_collab.check_python_version(executable=str(self.base / "nonexistent-python"))
        self.assertEqual(caught.exception.code, "PYTHON_MISSING")

        # Environment detection via env vars
        detected = install_collab.detect_environments(
            self.project,
            self.home,
            env={"CLAUDECODE": "1", "CODEX_HOME": str(self.home / ".codex"), "KIMI_CODE_HOME": str(self.home / ".kimi")},
        )
        self.assertEqual(detected, ["claude-code", "codex", "kimi-code"])

    def test_06_readme_and_plugin_manifests_match_requirements(self):
        """Verify item 12: README.md paste-to-install section, Method 1-4, invocation accuracy, and .claude-plugin manifests."""
        readme = (REPOSITORY / "README.md").read_text(encoding="utf-8")
        self.assertIn("Install COLLAB", readme)
        self.assertIn("https://github.com/NishidhJasani1605/Collab-Skill", readme)
        self.assertIn("Install the COLLAB skill from this GitHub repository.", readme)
        self.assertIn("Method 1", readme)
        self.assertIn("Method 2", readme)
        self.assertIn("npx skills add NishidhJasani1605/Collab-Skill", readme)
        self.assertIn("Method 3", readme)
        self.assertIn("Method 4", readme)
        self.assertIn("/collab:collab", readme)
        self.assertIn("$collab", readme)
        self.assertIn("/skill:collab", readme)

        plugin_json = json.loads((REPOSITORY / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        marketplace_json = json.loads((REPOSITORY / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual(plugin_json["name"], "collab")
        self.assertEqual(marketplace_json["plugins"][0]["name"], "collab")


if __name__ == "__main__":
    unittest.main()
