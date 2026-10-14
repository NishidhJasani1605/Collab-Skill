"""Installation and activation contracts, exercised in isolated user profiles."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "skills" / "collab"
sys.path.insert(0, str(SKILL / "scripts"))
from collablib import installer


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="collab lifecycle ")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.project = self.base / "project"
        self.home = self.base / "home"
        self.project.mkdir()
        self.home.mkdir()
        self.env = dict(os.environ, PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
        for key in ("CODEX_HOME", "CODEX_THREAD_ID", "OPENAI_CODEX", "CLAUDECODE",
                    "CLAUDE_CODE_ENTRYPOINT", "ANTHROPIC_CLAUDE_CODE", "KIMI_CODE_HOME",
                    "ANTIGRAVITY_CLI", "ANTIGRAVITY_APP", "CURSOR_TRACE_ID", "GEMINI_CLI",
                    "OPENCODE", "COLLAB_TEST_PYTHON_VERSION", "COLLAB_TOKEN", "COLLAB_TEST_CRASH"):
            self.env.pop(key, None)
        self.kw = dict(source_dir=SKILL, agents=["codex"], project_root=self.project,
                       home_dir=self.home, env={})
        self.dest = self.home / ".agents/skills/collab"

    def call(self, script, *args, data=None, ok=True):
        run = subprocess.run([sys.executable, str(script), *map(str, args)], cwd=self.project,
                             input=json.dumps(data) if data is not None else None,
                             env=self.env, text=True, encoding="utf-8", capture_output=True, timeout=60)
        self.assertEqual(run.returncode, 0 if ok else 2, run.stdout + run.stderr)
        return json.loads(run.stdout)

    def test_every_entrypoint_installs_globally_and_only_start_creates_runtime(self):
        for script in (REPO / "install.py", REPO / "scripts/install_collab.py", SKILL / "scripts/install.py"):
            with self.subTest(script=script):
                result = self.call(script, "--json", "--agent", "codex", "--home", self.home)
                self.assertEqual(result["scope"], "global")
                self.assertEqual(list(self.project.iterdir()), [])
        # The installed copy includes the same installer and works without the repository.
        self.call(self.dest / "scripts/install.py", "--json", "--verify-only")
        helper = self.dest / "scripts/collab.py"
        for command in ("status", "read", "check", "send", "finalize"):
            result = self.call(helper, command, ok=False)
            self.assertEqual(result["error"]["code"], "NOT_INITIALIZED")
            self.assertEqual(list(self.project.iterdir()), [])
        first = self.call(helper, "start", "--input", "-", data={
            "name": "First", "session_id": "first", "objective": "Lifecycle test"})
        second = self.call(helper, "start", "--input", "-", data={
            "name": "Second", "session_id": "second", "task_id": first["task"]["id"]})
        self.assertEqual(first["task"]["id"], second["task"]["id"])
        self.assertEqual([p.name for p in self.project.iterdir()], [".collab"])
        self.assertEqual((self.project / ".collab/.gitignore").read_text(), "*\n")
        self.assertEqual(len(self.call(helper, "status")["agents"]), 2)

    def test_reinstallation_does_not_rewrite_identical_files(self):
        installer.install_skill(**self.kw)
        before = {p.relative_to(self.dest): (p.stat().st_mtime_ns, p.read_bytes())
                  for p in self.dest.rglob("*") if p.is_file()}
        result = installer.install_skill(**self.kw)
        self.assertEqual(result["installations"][0]["status"], "up_to_date")
        after = {p.relative_to(self.dest): (p.stat().st_mtime_ns, p.read_bytes())
                 for p in self.dest.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_broken_update_keeps_working_installation(self):
        installer.install_skill(**self.kw)
        original = (self.dest / "scripts/collab.py").read_bytes()
        broken = self.base / "broken"
        shutil.copytree(SKILL, broken)
        (broken / "scripts/collab.py").write_text("raise RuntimeError('broken release')\n")
        with self.assertRaises(installer.InstallError) as error:
            installer.install_skill(**dict(self.kw, source_dir=broken))
        self.assertEqual(error.exception.code, "RUNTIME_VERIFICATION_FAILED")
        self.assertEqual((self.dest / "scripts/collab.py").read_bytes(), original)
        self.assertTrue(installer.verify_installed_runtime(self.dest)["verified"])

    def test_publish_failure_rolls_back_even_without_backup(self):
        installer.install_skill(**self.kw)
        marker = self.dest / "references/commands.md"
        marker.write_text("previous installation")
        rename = Path.rename
        def failing_publish(path, target):
            if path.parent.name.startswith(".collab-install-") and path.name == "collab":
                raise OSError("simulated publish failure")
            return rename(path, target)
        with mock.patch.object(Path, "rename", failing_publish):
            with self.assertRaises(OSError):
                installer.install_skill(**dict(self.kw, backup_on_update=False))
        self.assertEqual(marker.read_text(), "previous installation")

    def test_unrecognized_destination_is_preserved_on_install(self):
        self.dest.mkdir(parents=True)
        marker = self.dest / "personal.txt"
        marker.write_text("keep")
        with self.assertRaises(installer.InstallError) as error:
            installer.install_skill(**self.kw)
        self.assertEqual(error.exception.code, "UNSAFE_UPDATE")
        self.assertEqual(marker.read_text(), "keep")

    def test_legacy_installation_without_manifest_can_be_updated(self):
        shutil.copytree(SKILL, self.dest)
        (self.dest / "scripts/collablib/installer.py").unlink()
        (self.dest / "scripts/collablib/checks.py").unlink()
        shutil.rmtree(self.dest / "agents")
        result = installer.install_skill(**self.kw)
        self.assertEqual(result["installations"][0]["status"], "updated")
        backup = Path(result["installations"][0]["backup_path"])
        self.assertTrue((backup / "SKILL.md").is_file())
        self.assertTrue(installer.verify_installed_runtime(self.dest)["verified"])

    def test_nested_source_and_destination_are_rejected(self):
        # A recursive copy into the source would grow indefinitely.
        source = self.home / ".agents"
        shutil.copytree(SKILL, source)
        with self.assertRaises(installer.InstallError) as error:
            installer.install_skill(**dict(self.kw, source_dir=source))
        self.assertEqual(error.exception.code, "OVERLAPPING_PATHS")
        self.assertFalse(self.dest.exists())

    def test_global_target_inside_project_is_rejected_before_writing(self):
        with self.assertRaises(installer.InstallError) as error:
            installer.install_skill(**dict(self.kw, env={"CODEX_HOME": str(self.project / ".codex")}))
        self.assertEqual(error.exception.code, "PROJECT_DESTINATION")
        self.assertEqual(list(self.project.iterdir()), [])

    def test_bad_agent_plan_does_not_partially_install(self):
        with self.assertRaises(installer.InstallError):
            installer.install_skill(**dict(self.kw, agents=["codex", "unknown"]))
        self.assertEqual(list(self.home.iterdir()), [])

    def test_install_from_user_home_is_supported(self):
        result = installer.install_skill(**dict(self.kw, project_root=self.home))
        self.assertTrue(result["ok"])
        self.assertTrue((self.dest / "SKILL.md").is_file())
        self.assertFalse((self.home / ".collab").exists())

    def test_active_host_takes_priority_over_unrelated_installed_hosts(self):
        (self.home / ".claude").mkdir()
        (self.home / ".cursor").mkdir()
        result = installer.install_skill(**dict(self.kw, agents=None, env={"OPENAI_CODEX": "1"}))
        self.assertEqual([x["agent"] for x in result["installations"]], ["codex"])
        self.assertFalse((self.home / ".claude/skills").exists())
        self.assertFalse((self.home / ".cursor/skills").exists())

    def test_uninstall_preserves_runtime_unrelated_skills_and_backups(self):
        installer.install_skill(**self.kw)
        (self.project / ".collab").mkdir()
        history = self.project / ".collab/history.txt"
        history.write_text("keep history")
        unrelated = self.dest.parent / "another-skill"
        unrelated.mkdir()
        backups = self.dest.parent / ".collab-backups"
        backups.mkdir()
        (backups / "personal.txt").write_text("keep backup")
        installer.uninstall_skill(agents=["codex"], project_root=self.project, home_dir=self.home,
                                  env={}, purge_backups=True)
        self.assertFalse(self.dest.exists())
        self.assertTrue(unrelated.is_dir())
        self.assertEqual(history.read_text(), "keep history")
        self.assertEqual((backups / "personal.txt").read_text(), "keep backup")

    def test_linked_destination_is_never_followed_for_update_or_uninstall(self):
        outside = self.base / "outside"
        shutil.copytree(SKILL, outside)
        self.dest.parent.mkdir(parents=True)
        if os.name == "nt":
            completed = subprocess.run(["cmd", "/c", "mklink", "/J", str(self.dest), str(outside)],
                                       capture_output=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
        else:
            self.dest.symlink_to(outside, target_is_directory=True)
        for action in (lambda: installer.install_skill(**self.kw), lambda: installer.uninstall_skill(
                agents=["codex"], home_dir=self.home, project_root=self.project, env={} )):
            with self.assertRaises(installer.InstallError) as error:
                action()
            self.assertEqual(error.exception.code, "UNSAFE_PATH")
            self.assertTrue((outside / "SKILL.md").is_file())

    def test_concurrent_installers_leave_one_complete_installation(self):
        processes = [subprocess.Popen([sys.executable, str(REPO / "install.py"), "--json",
                                      "--agent", "codex", "--home", str(self.home)],
                                     cwd=self.project, env=self.env, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE) for _ in range(3)]
        try:
            for process in processes:
                out, err = process.communicate(timeout=60)
                self.assertEqual(process.returncode, 0, (out, err))
                self.assertTrue(json.loads(out)["ok"])
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.communicate()
        self.assertTrue(installer.verify_installed_runtime(self.dest)["verified"])
        self.assertEqual(list(self.project.iterdir()), [])

    def test_cli_invalid_arguments_and_io_failures_are_json(self):
        script = REPO / "install.py"
        invalid = self.call(script, "--json", "--global", "--local", ok=False)
        self.assertEqual(invalid["error"]["code"], "INVALID_INPUT")
        (self.home / ".agents").write_text("not a directory")
        failed = self.call(script, "--json", "--agent", "codex", "--home", self.home, ok=False)
        self.assertFalse(failed["ok"])


if __name__ == "__main__":
    unittest.main()
