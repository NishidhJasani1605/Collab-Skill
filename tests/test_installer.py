"""
Tests for COLLAB universal skill installer and verification script.
"""

from __future__ import annotations

import io
import json
import os
import pathlib
import shutil
import sys
import tempfile
import unittest
from unittest import mock

# Ensure skills/collab/scripts is importable
repo_root = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / "skills" / "collab" / "scripts"))

import install


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_root = pathlib.Path(self.temp_dir.name)
        self.source_skill = repo_root / "skills" / "collab"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_check_python_version(self):
        ok, msg = install.check_python_version()
        self.assertTrue(ok)
        self.assertIn("meets requirements", msg)

        # Mock an older version (Python 3.9)
        with mock.patch.object(sys, "version_info", (3, 9, 10, "final", 0)):
            fail_ok, fail_msg = install.check_python_version()
            self.assertFalse(fail_ok)
            self.assertIn("Python 3.10+ is required", fail_msg)

    def test_detect_platform_from_env(self):
        # Claude Code
        with mock.patch.dict(os.environ, {"CLAUDE_CODE": "1"}):
            self.assertEqual(install.detect_platform(), "claude")

        # Antigravity
        with mock.patch.dict(os.environ, {"ANTIGRAVITY": "1"}, clear=True):
            self.assertEqual(install.detect_platform(), "antigravity")

        # Codex
        with mock.patch.dict(os.environ, {"CODEX_ENV": "1"}, clear=True):
            self.assertEqual(install.detect_platform(), "codex")

        # Cursor
        with mock.patch.dict(os.environ, {"CURSOR_PROJECT_DIR": "/path"}, clear=True):
            self.assertEqual(install.detect_platform(), "cursor")

        # Gemini CLI
        with mock.patch.dict(os.environ, {"GEMINI_CLI": "1"}, clear=True):
            self.assertEqual(install.detect_platform(), "gemini")

        # Kimi
        with mock.patch.dict(os.environ, {"KIMI_ENV": "1"}, clear=True):
            self.assertEqual(install.detect_platform(), "kimi")

        # OpenCode
        with mock.patch.dict(os.environ, {"OPENCODE": "1"}, clear=True):
            self.assertEqual(install.detect_platform(), "opencode")

    def test_detect_platform_from_workspace_dir(self):
        workspace = self.test_root / "test_workspace"
        workspace.mkdir()

        (workspace / ".claude").mkdir()
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(install.detect_platform(workspace), "claude")

    def test_resolve_target_dir_project_and_global(self):
        workspace = self.test_root / "my_project"
        workspace.mkdir()

        # Project standard
        p_std = install.resolve_target_dir("project", "standard", workspace)
        self.assertEqual(p_std, (workspace / ".agents" / "skills" / "collab").resolve())

        # Project claude
        p_claude = install.resolve_target_dir("project", "claude", workspace)
        self.assertEqual(p_claude, (workspace / ".claude" / "skills" / "collab").resolve())

        # Global mode with mock home
        fake_home = self.test_root / "fake_home"
        fake_home.mkdir()
        with mock.patch.object(pathlib.Path, "home", return_value=fake_home):
            g_std = install.resolve_target_dir("global", "standard")
            self.assertEqual(g_std, (fake_home / ".agents" / "skills" / "collab").resolve())

            g_claude = install.resolve_target_dir("global", "claude")
            self.assertEqual(g_claude, (fake_home / ".claude" / "skills" / "collab").resolve())

    def test_fresh_project_install_and_verification(self):
        project_dir = self.test_root / "project_alpha"
        project_dir.mkdir()
        target_dir = project_dir / ".agents" / "skills" / "collab"

        res = install.install_skill(
            source_dir=self.source_skill,
            target_dir=target_dir,
            backup=True,
            platform_name="standard",
            mode="project",
        )

        self.assertTrue(res["success"], res.get("error"))
        self.assertEqual(res["target_dir"], str(target_dir.resolve()))
        self.assertEqual(res["invocation"], "/collab")

        # Verify filesystem contents
        self.assertTrue((target_dir / "SKILL.md").is_file())
        self.assertTrue((target_dir / "references" / "commands.md").is_file())
        self.assertTrue((target_dir / "references" / "safety.md").is_file())
        self.assertTrue((target_dir / "scripts" / "collab.py").is_file())
        self.assertTrue((target_dir / "scripts" / "collablib" / "engine.py").is_file())
        self.assertTrue((target_dir / "scripts" / "collablib" / "storage.py").is_file())

        # Run verification function
        valid, issues = install.verify_installation(target_dir)
        self.assertTrue(valid, f"Issues: {issues}")
        self.assertEqual(len(issues), 0)

    def test_install_path_with_spaces(self):
        project_with_spaces = self.test_root / "My Cool AI Project With Spaces"
        project_with_spaces.mkdir()
        target_dir = project_with_spaces / ".agents" / "skills" / "collab"

        res = install.install_skill(
            source_dir=self.source_skill,
            target_dir=target_dir,
            backup=True,
            platform_name="standard",
            mode="project",
        )
        self.assertTrue(res["success"], res.get("error"))
        self.assertTrue((target_dir / "SKILL.md").is_file())

        valid, issues = install.verify_installation(target_dir)
        self.assertTrue(valid, f"Issues: {issues}")

    def test_reinstall_creates_backup(self):
        project_dir = self.test_root / "project_beta"
        project_dir.mkdir()
        target_dir = project_dir / ".agents" / "skills" / "collab"

        # First install
        res1 = install.install_skill(
            source_dir=self.source_skill,
            target_dir=target_dir,
            backup=True,
        )
        self.assertTrue(res1["success"])
        self.assertIsNone(res1.get("backup_dir"))

        # Put a marker file in the first install
        (target_dir / "custom_marker.txt").write_text("v1_marker", encoding="utf-8")

        # Reinstall (should trigger backup)
        res2 = install.install_skill(
            source_dir=self.source_skill,
            target_dir=target_dir,
            backup=True,
        )
        self.assertTrue(res2["success"])
        self.assertIsNotNone(res2.get("backup_dir"))

        backup_path = pathlib.Path(res2["backup_dir"])
        self.assertTrue(backup_path.is_dir())
        self.assertTrue((backup_path / "custom_marker.txt").is_file())
        self.assertEqual(
            (backup_path / "custom_marker.txt").read_text(encoding="utf-8"),
            "v1_marker",
        )
        # New install should not have marker
        self.assertFalse((target_dir / "custom_marker.txt").exists())

    def test_reinstall_no_backup_flag(self):
        project_dir = self.test_root / "project_gamma"
        project_dir.mkdir()
        target_dir = project_dir / ".agents" / "skills" / "collab"

        install.install_skill(source_dir=self.source_skill, target_dir=target_dir)
        (target_dir / "old_marker.txt").write_text("old", encoding="utf-8")

        res = install.install_skill(
            source_dir=self.source_skill,
            target_dir=target_dir,
            backup=False,
        )
        self.assertTrue(res["success"])
        self.assertIsNone(res.get("backup_dir"))
        self.assertFalse((target_dir / "old_marker.txt").exists())

        # Confirm no .bak directories created
        backups = list(target_dir.parent.glob("collab.bak.*"))
        self.assertEqual(len(backups), 0)

    def test_verification_detects_tampered_or_missing_files(self):
        project_dir = self.test_root / "project_tamper"
        project_dir.mkdir()
        target_dir = project_dir / ".agents" / "skills" / "collab"

        install.install_skill(source_dir=self.source_skill, target_dir=target_dir)

        # Remove SKILL.md
        (target_dir / "SKILL.md").unlink()
        valid, issues = install.verify_installation(target_dir)
        self.assertFalse(valid)
        self.assertTrue(any("Missing SKILL.md" in issue for issue in issues))

        # Restore broken SKILL.md
        (target_dir / "SKILL.md").write_text("invalid_frontmatter", encoding="utf-8")
        valid, issues = install.verify_installation(target_dir)
        self.assertFalse(valid)
        self.assertTrue(any("metadata" in issue for issue in issues))

    def test_uninstall_cleanly_removes_skill_and_preserves_backups(self):
        project_dir = self.test_root / "project_uninstall"
        project_dir.mkdir()
        target_dir = project_dir / ".agents" / "skills" / "collab"

        # Install twice to get a backup
        install.install_skill(source_dir=self.source_skill, target_dir=target_dir)
        install.install_skill(source_dir=self.source_skill, target_dir=target_dir)

        self.assertTrue(target_dir.is_dir())
        backups_before = list(target_dir.parent.glob("collab.bak.*"))
        self.assertGreaterEqual(len(backups_before), 1)

        un_res = install.uninstall_skill(target_dir)
        self.assertTrue(un_res["success"])
        self.assertFalse(target_dir.exists())

        # Backups are still preserved
        backups_after = list(target_dir.parent.glob("collab.bak.*"))
        self.assertEqual(len(backups_after), len(backups_before))

    def test_cli_json_workflow(self):
        project_dir = self.test_root / "project_cli"
        project_dir.mkdir()
        target_dir = project_dir / ".claude" / "skills" / "collab"

        # 1. Install via CLI arguments
        stdout_capture = io.StringIO()
        with mock.patch("sys.stdout", stdout_capture):
            code = install.main([
                "--project", str(project_dir),
                "--platform", "claude",
                "--json",
            ])
        self.assertEqual(code, 0)
        output = json.loads(stdout_capture.getvalue())
        self.assertTrue(output["success"])
        self.assertEqual(output["platform"], "claude")
        self.assertEqual(output["invocation"], "/collab")
        self.assertTrue(target_dir.is_dir())

        # 2. Verify via CLI
        stdout_capture2 = io.StringIO()
        with mock.patch("sys.stdout", stdout_capture2):
            code_verify = install.main([
                "--project", str(project_dir),
                "--platform", "claude",
                "--verify",
                "--json",
            ])
        self.assertEqual(code_verify, 0)
        verify_output = json.loads(stdout_capture2.getvalue())
        self.assertTrue(verify_output["success"])

        # 3. Uninstall via CLI
        stdout_capture3 = io.StringIO()
        with mock.patch("sys.stdout", stdout_capture3):
            code_un = install.main([
                "--project", str(project_dir),
                "--platform", "claude",
                "--uninstall",
                "--json",
            ])
        self.assertEqual(code_un, 0)
        un_output = json.loads(stdout_capture3.getvalue())
        self.assertTrue(un_output["success"])
        self.assertFalse(target_dir.exists())


if __name__ == "__main__":
    unittest.main()
