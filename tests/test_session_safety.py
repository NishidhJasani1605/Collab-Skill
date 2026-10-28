"""Root selection and recovery must never retire a live collaborator."""
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/collab/scripts"))
from collab import discover_root
from collablib.storage import (CollabError, Store, find_ancestor_collab,
                               find_descendant_collab, migrate_nested_collab)


class SessionSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="collab-session-safety-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def nested_state(self, status):
        sub = self.root / "app"
        sub.mkdir()
        with Store(sub) as store:
            store.commit({"tasks": {"task": {"status": status}}}, {"body": "history"})
        return sub

    def test_project_suffix_does_not_hide_ancestor_session(self):
        with Store(self.root):
            pass
        sub = self.root / "frontend project"
        sub.mkdir()
        self.assertEqual(find_ancestor_collab(sub), self.root)

    def test_project_suffix_does_not_hide_descendant_session(self):
        sub = self.root / "frontend project"
        sub.mkdir()
        with Store(sub):
            pass
        self.assertEqual(find_descendant_collab(self.root), sub)

    def test_deep_nested_session_is_found_before_parent_init(self):
        sub = self.root / "a/b/c/d/e"
        sub.mkdir(parents=True)
        with Store(sub):
            pass
        with self.assertRaises(CollabError) as caught:
            with Store(self.root):
                pass
        self.assertEqual(caught.exception.code, "NESTED_WORKSPACE_CONFLICT")

    def test_git_worktree_file_is_a_project_boundary(self):
        (self.root / ".git").write_text("gitdir: ../repo/.git/worktrees/test\n")
        sub = self.root / "src"
        sub.mkdir()
        self.assertEqual(discover_root(sub), self.root)

    def test_conflicting_implicit_roots_are_reported(self):
        (self.root / ".collab").mkdir()
        sub = self.root / "app"
        (sub / ".collab").mkdir(parents=True)
        with self.assertRaises(CollabError) as caught:
            discover_root(sub)
        self.assertEqual(caught.exception.code, "NESTED_WORKSPACE_CONFLICT")

    def test_migration_preserves_active_nested_session(self):
        sub = self.nested_state("WORKING")
        original = (sub / ".collab/GROUP_CHAT.jsonl").read_bytes()
        with self.assertRaises(CollabError) as caught:
            migrate_nested_collab(self.root, sub)
        self.assertEqual(caught.exception.code, "ACTIVE_WORKSPACE")
        self.assertEqual((sub / ".collab/GROUP_CHAT.jsonl").read_bytes(), original)
        self.assertFalse((self.root / ".collab").exists())

    def test_migration_preserves_corrupt_nested_session(self):
        sub = self.root / "app"
        (sub / ".collab").mkdir(parents=True)
        history = sub / ".collab/GROUP_CHAT.jsonl"
        history.write_bytes(b"unrecognized history\n")
        with self.assertRaises(CollabError) as caught:
            migrate_nested_collab(self.root, sub)
        self.assertEqual(caught.exception.code, "CORRUPT_STORAGE")
        self.assertEqual(history.read_bytes(), b"unrecognized history\n")
        self.assertFalse((self.root / ".collab").exists())

    def test_retirement_archives_history_and_preserves_lock(self):
        sub = self.nested_state("TEAM_COMPLETE")
        history = (sub / ".collab/GROUP_CHAT.jsonl").read_bytes()
        lock = sub / ".collab/.lock"
        inode = lock.stat().st_ino
        result = migrate_nested_collab(self.root, "app")
        self.assertEqual((Path(result["archived_to"]) / "GROUP_CHAT.jsonl").read_bytes(), history)
        self.assertEqual(lock.stat().st_ino, inode)
        self.assertEqual((sub / ".collab/GROUP_CHAT.jsonl").read_bytes(), history)
        self.assertIsNone(find_descendant_collab(self.root))
        with self.assertRaises(CollabError) as caught:
            with Store(sub):
                pass
        self.assertEqual(caught.exception.code, "WORKSPACE_RETIRED")
        with Store(self.root):
            pass

    def test_merge_is_not_presented_as_real_session_merge(self):
        sub = self.nested_state("TEAM_COMPLETE")
        with self.assertRaises(CollabError) as caught:
            migrate_nested_collab(self.root, sub, action="merge")
        self.assertEqual(caught.exception.code, "INVALID_INPUT")
        self.assertTrue((sub / ".collab/GROUP_CHAT.jsonl").exists())

    def test_failed_initialization_keeps_permanent_lock_for_other_clients(self):
        with mock.patch.object(Store, "_load", side_effect=CollabError("INJECTED")):
            with self.assertRaises(CollabError):
                with Store(self.root):
                    pass
        lock = self.root / ".collab/.lock"
        self.assertTrue(lock.is_file())
        inode = lock.stat().st_ino
        with Store(self.root):
            pass
        self.assertEqual(lock.stat().st_ino, inode)

    def test_existing_parent_history_is_preserved_by_inactive_retirement(self):
        with Store(self.root) as store:
            store.commit({}, {"body": "parent history"})
        before = (self.root / ".collab/GROUP_CHAT.jsonl").read_bytes()
        sub = self.root / "app"
        sub.mkdir()
        with Store(sub, validate_ancestors=False):
            pass
        migrate_nested_collab(self.root, sub)
        with Store(self.root):
            pass
        self.assertEqual((self.root / ".collab/GROUP_CHAT.jsonl").read_bytes(), before)

    def test_migration_rejects_links_inside_snapshot(self):
        sub = self.nested_state("TEAM_COMPLETE")
        target = self.root / "user-data.txt"
        target.write_text("preserve")
        linked = sub / ".collab/linked.txt"
        try:
            os.link(target, linked)
        except OSError as exc:
            self.skipTest(str(exc))
        with self.assertRaises(CollabError) as caught:
            migrate_nested_collab(self.root, sub)
        self.assertEqual(caught.exception.code, "UNSAFE_PATH")
        self.assertEqual(target.read_text(), "preserve")
        self.assertFalse((sub / ".collab/retired.json").exists())

    @unittest.skipUnless(os.name == "nt", "Windows junction coverage")
    def test_migration_rejects_junction_inside_snapshot(self):
        sub = self.nested_state("TEAM_COMPLETE")
        with tempfile.TemporaryDirectory(prefix="collab-outside-") as outside:
            target = Path(outside)
            (target / "keep.txt").write_text("preserve")
            link = sub / ".collab/linked-dir"
            quote = lambda value: "'" + str(value).replace("'", "''") + "'"
            command = f"New-Item -ItemType Junction -Path {quote(link)} -Target {quote(target)} | Out-Null"
            run = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
                                 capture_output=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stderr)
            with self.assertRaises(CollabError) as caught:
                migrate_nested_collab(self.root, sub)
            self.assertEqual(caught.exception.code, "UNSAFE_PATH")
            self.assertEqual((target / "keep.txt").read_text(), "preserve")
            self.assertFalse((sub / ".collab/retired.json").exists())


if __name__ == "__main__":
    unittest.main()
