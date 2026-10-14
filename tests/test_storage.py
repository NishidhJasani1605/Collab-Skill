"""Persistence checks use actual child processes, including abrupt death."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "collab" / "scripts"
sys.path.insert(0, str(SCRIPTS))
from collablib.storage import CollabError, Store, fingerprint, safe_project_path


WORKER = """
import sys,time
from pathlib import Path
from collablib.storage import Store
root,identity,count=sys.argv[1:]
for n in range(int(count)):
    with Store(root,timeout=60) as store:
        state=dict(store.state)
        state['count']=state.get('count',0)+1
        store.commit(state,{'type':'MESSAGE','body':identity+':'+str(n)})
"""

CRASH_WRITER = """
import sys
from collablib.storage import Store
with Store(sys.argv[1]) as store:
    store.commit({'value':2},{'type':'MESSAGE','body':'after crash'},
                 {'reports/proof.md':'Durable report\n'})
""".replace("'Durable report\n'", "'Durable report\\n'")


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env = dict(os.environ, PYTHONPATH=str(SCRIPTS))
        self.env.pop("COLLAB_TEST_CRASH", None)

    def tearDown(self):
        self.temp.cleanup()

    def child(self, code, *args, env=None):
        return subprocess.Popen([sys.executable, "-c", code, str(self.root), *map(str, args)],
                                env=env or self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def successful(self, process):
        out, err = process.communicate(timeout=90)
        self.assertEqual(process.returncode, 0, (out + err).decode(errors="replace"))
        return out

    def test_first_repeat_and_transcript(self):
        with Store(self.root) as store:
            self.assertEqual(store.state, {})
            event = store.commit({"agents": {"a": {"name": "A"}}},
                                 {"type": "MESSAGE", "body": "hi\n## fake header 🦊"})
        with Store(self.root) as store:
            self.assertEqual(store.events, [event])
            self.assertEqual(store.state["agents"]["a"]["name"], "A")
        runtime = self.root / ".collab"
        self.assertEqual((runtime / ".gitignore").read_text(), "*\n")
        self.assertEqual(json.loads((runtime / "agents.json").read_text())["a"]["name"], "A")
        self.assertNotIn("\n## fake header", (runtime / "GROUP_CHAT.md").read_text(encoding="utf-8"))
        self.assertTrue((runtime / ".lock").exists())
        self.assertFalse((runtime / "checkpoints/pending.json").exists())

    def test_120_messages_from_12_independent_processes(self):
        processes = [self.child(WORKER, identity, 10) for identity in range(12)]
        try:
            for process in processes:
                self.successful(process)
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.communicate()
        with Store(self.root) as store:
            self.assertEqual(store.state["count"], 120)
            self.assertEqual(len(store.events), 120)
            self.assertEqual(len({event["id"] for event in store.events}), 120)
            self.assertEqual({event["body"] for event in store.events},
                             {f"{identity}:{n}" for identity in range(12) for n in range(10)})
            self.assertEqual([event["seq"] for event in store.events], list(range(1, 121)))

    def test_100_simultaneous_independent_submissions(self):
        burst = """
import sys,time
from pathlib import Path
from collablib.storage import Store
root,identity=sys.argv[1:]
Path(root,'ready-'+identity).touch()
deadline=time.monotonic()+60
while not Path(root,'go').exists():
    if time.monotonic()>deadline:
        raise RuntimeError('test barrier timed out')
    time.sleep(0.025)
with Store(root,timeout=90) as store:
    state=dict(store.state)
    state['count']=state.get('count',0)+1
    store.commit(state,{'type':'MESSAGE','body':'burst-'+identity})
"""
        processes = [self.child(burst, identity) for identity in range(100)]
        try:
            deadline = time.monotonic() + 60
            while len(list(self.root.glob("ready-*"))) < 100 and time.monotonic() < deadline:
                time.sleep(0.025)
            self.assertEqual(len(list(self.root.glob("ready-*"))), 100, "All 100 processes must reach barrier")
            (self.root / "go").touch()
            for process in processes:
                self.successful(process)
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                process.communicate(timeout=10)
        with Store(self.root) as store:
            self.assertEqual(store.state["count"], 100)
            self.assertEqual(len(store.events), 100)
            self.assertEqual(len({event["id"] for event in store.events}), 100)
            self.assertEqual({event["body"] for event in store.events}, {f"burst-{n}" for n in range(100)})

    def test_lock_timeout_and_dead_process_releases_lock(self):
        holder = self.child("""
import sys,time
from collablib.storage import Store
with Store(sys.argv[1]) as store:
    print('locked',flush=True)
    time.sleep(60)
""")
        try:
            self.assertEqual(holder.stdout.readline().strip(), b"locked")
            with self.assertRaises(CollabError) as caught:
                with Store(self.root, timeout=0.08):
                    pass
            self.assertEqual(caught.exception.code, "LOCK_TIMEOUT")
        finally:
            holder.kill()
            holder.communicate(timeout=10)
        with Store(self.root, timeout=2) as store:
            store.commit({}, {"type": "recovered-lock"})
        self.assertTrue((self.root / ".collab/.lock").exists())

    def test_recover_each_transaction_crash_boundary(self):
        for stage in ("after_wal", "partial_event", "after_event", "after_state", "after_projections", "before_clear"):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                with Store(root) as store:
                    store.commit({"value": 1}, {"type": "MESSAGE", "body": "before"})
                child = subprocess.run([sys.executable, "-c", CRASH_WRITER, str(root)],
                                       env=dict(self.env, COLLAB_TEST_CRASH=stage),
                                       capture_output=True, timeout=30)
                self.assertEqual(child.returncode, 91, child.stderr.decode())
                self.assertTrue((root / ".collab/checkpoints/pending.json").exists())
                with Store(root) as store:
                    self.assertEqual(store.state, {"value": 2})
                    self.assertEqual([e["body"] for e in store.events], ["before", "after crash"])
                self.assertEqual((root / ".collab/reports/proof.md").read_text(), "Durable report\n")
                with Store(root) as store:
                    self.assertEqual(len(store.events), 2)

    def test_unknown_partial_append_refuses_and_preserves(self):
        with Store(self.root) as store:
            store.commit({}, {"type": "MESSAGE"})
        path = self.root / ".collab/GROUP_CHAT.jsonl"
        with path.open("ab") as stream:
            stream.write(b'{"unexpected":')
        before = path.read_bytes()
        with self.assertRaises(CollabError) as caught:
            with Store(self.root):
                pass
        self.assertEqual(caught.exception.code, "CORRUPT_STORAGE")
        self.assertEqual(path.read_bytes(), before)

    def test_invalid_chat_hash_refuses_and_preserves(self):
        with Store(self.root) as store:
            store.commit({}, {"body": "original"})
        path = self.root / ".collab/GROUP_CHAT.jsonl"
        path.write_bytes(path.read_bytes().replace(b"original", b"tampered"))
        before = path.read_bytes()
        with self.assertRaises(CollabError):
            with Store(self.root):
                pass
        self.assertEqual(path.read_bytes(), before)

    def test_recovery_rejects_unknown_tail_and_preserves_wal(self):
        with Store(self.root) as store:
            store.commit({}, {"body": "original"})
        child = self.child(CRASH_WRITER, env=dict(self.env, COLLAB_TEST_CRASH="partial_event"))
        child.communicate(timeout=30)
        self.assertEqual(child.returncode, 91)
        path = self.root / ".collab/GROUP_CHAT.jsonl"
        with path.open("ab") as stream:
            stream.write(b"UNEXPECTED")
        before = path.read_bytes()
        with self.assertRaises(CollabError):
            with Store(self.root):
                pass
        self.assertEqual(path.read_bytes(), before)
        self.assertTrue((self.root / ".collab/checkpoints/pending.json").exists())

    def test_corrupt_checkpoint_is_not_silently_reset(self):
        with Store(self.root) as store:
            store.commit({"private": "retained"}, {"body": "hello"})
        path = self.root / ".collab/checkpoints/state.json"
        path.write_text('{"broken":true}')
        with self.assertRaises(CollabError):
            with Store(self.root):
                pass
        self.assertEqual(path.read_text(), '{"broken":true}')

    def test_corrupt_wal_is_not_silently_reset(self):
        with Store(self.root):
            pass
        child = self.child(CRASH_WRITER, env=dict(self.env, COLLAB_TEST_CRASH="after_wal"))
        child.communicate(timeout=30)
        self.assertEqual(child.returncode, 91)
        path = self.root / ".collab/checkpoints/pending.json"
        path.write_bytes(path.read_bytes().replace(b"after crash", b"tampered"))
        before = path.read_bytes()
        with self.assertRaises(CollabError):
            with Store(self.root):
                pass
        self.assertEqual(path.read_bytes(), before)

    def test_corrupt_projection_can_be_rebuilt_from_authority(self):
        with Store(self.root) as store:
            store.commit({"agents": {"a": {"name": "kept"}}}, {"body": "hello"})
        projection = self.root / ".collab/agents.json"
        projection.write_text("corrupt")
        with Store(self.root):
            pass
        self.assertEqual(json.loads(projection.read_text())["a"]["name"], "kept")

    def test_path_traversal_and_reserved_paths(self):
        for relative in ("../escape", "/abs", "C:\\abs", "C:relative", "x/../../escape",
                         ".collab/agents.json", ".git/config", "x/.git/config", "a:stream",
                         "a/../b", "a./file", "CON", "nested/NUL.txt"):
            with self.subTest(relative=relative), self.assertRaises(CollabError):
                safe_project_path(self.root, relative)
        self.assertEqual(safe_project_path(self.root, "new/file.py"), self.root / "new/file.py")
        self.assertEqual(fingerprint(self.root / "missing.txt"), "missing")
        (self.root / "real.txt").write_bytes(b"value")
        self.assertEqual(fingerprint(self.root / "real.txt"), hashlib.sha256(b"value").hexdigest())

    def test_runtime_hardlinks_rejected_without_writing_target(self):
        with Store(self.root):
            pass
        target = self.root / "user.txt"
        target.write_bytes(b"user contents")
        projection = self.root / ".collab/agents.json"
        projection.unlink()
        try:
            os.link(target, projection)
        except OSError as exc:
            self.skipTest(f"Hard links unavailable: {exc}")
        with self.assertRaises(CollabError) as caught:
            with Store(self.root):
                pass
        self.assertEqual(caught.exception.code, "UNSAFE_PATH")
        self.assertEqual(target.read_bytes(), b"user contents")

    def test_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside)
            try:
                (self.root / "link").symlink_to(target, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"Symlinks unavailable: {exc}")
            with self.assertRaises(CollabError):
                safe_project_path(self.root, "link/write.txt")
            (self.root / ".collab").symlink_to(target, target_is_directory=True)
            with self.assertRaises(CollabError):
                with Store(self.root):
                    pass
            self.assertEqual(list(target.iterdir()), [])

    @unittest.skipUnless(os.name == "nt", "Windows junction coverage")
    def test_windows_junction_escape_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside)
            for name in ("linked", ".collab"):
                link = self.root / name
                quote = lambda value: "'" + str(value).replace("'", "''") + "'"
                command = f"New-Item -ItemType Junction -Path {quote(link)} -Target {quote(target)} | Out-Null"
                made = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
                                      capture_output=True, timeout=30)
                self.assertEqual(made.returncode, 0, made.stderr.decode(errors="replace"))
                with self.assertRaises(CollabError) as caught:
                    if name == ".collab":
                        with Store(self.root):
                            pass
                    else:
                        safe_project_path(self.root, "linked/write.txt")
                self.assertEqual(caught.exception.code, "UNSAFE_PATH")
            self.assertEqual(list(target.iterdir()), [])

    def test_artifacts_cannot_replace_authoritative_metadata(self):
        with Store(self.root) as store:
            for relative in ("../escape", ".lock", "GROUP_CHAT.jsonl", "checkpoints/state.json", "agents.json"):
                with self.subTest(relative=relative), self.assertRaises(CollabError):
                    store.commit({}, {"body": "rejected"}, {relative: "bad"})
            self.assertEqual(store.events, [])

    def test_commit_requires_lock(self):
        with self.assertRaises(CollabError) as caught:
            Store(self.root).commit({}, {})
        self.assertEqual(caught.exception.code, "LOCK_REQUIRED")


if __name__ == "__main__":
    unittest.main()
