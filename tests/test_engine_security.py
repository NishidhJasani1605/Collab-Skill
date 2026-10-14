"""Targeted protocol regression checks from independent security review."""

import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "collab" / "scripts"
sys.path.insert(0, str(SCRIPTS))
from collablib.engine import execute
from collablib.storage import CollabError


class EngineSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()

    def tearDown(self):
        self.temp.cleanup()

    def invoke(self, command, agent=None, **data):
        credentials = {} if agent is None else {
            "agent_id": agent["agent"]["id"], "token": agent["token"], "task_id": agent["task"]["id"]}
        return execute(self.root, command, {**credentials, **data})

    def prepared_team(self, checks=None):
        a = self.invoke("start", name="Author", platform="test", session_id="author",
                        objective="Verify revision and durable evidence", checks=checks or [])
        b = self.invoke("start", name="Reviewer", platform="test", session_id="reviewer",
                        task_id=a["task"]["id"])
        assignment = self.invoke("assignment-add", a, title="Implementation")["assignment"]
        self.invoke("claim", a, assignment_id=assignment["id"])
        self.invoke("work-complete", a, assignment_id=assignment["id"], result="Completed implementation",
                    evidence=["Implementation inspected"])
        self.invoke("participant-result", b, content="Independent review complete", evidence=["Reproduced output"])
        proposal = self.invoke("propose", a, content="Ready for final verification")
        self.invoke("review", b, revision=proposal["revision"], verdict="APPROVE",
                    content="Verified independently", evidence=["Reviewed requirements and observed output"])
        for member in (a, b):
            self.invoke("approve", member, revision=proposal["revision"], content="Approve this exact revision")
        return a, b, proposal["revision"]

    def test_deleted_check_evidence_blocks_finalization(self):
        a, b, revision = self.prepared_team([
            {"name": "proof", "argv": [sys.executable, "-c", "print('verified')"]}])
        run = self.invoke("check", b, name="proof")["check"]
        (self.root / run["log_path"]).unlink()
        with self.assertRaises(CollabError) as caught:
            self.invoke("finalize", a, revision=revision)
        self.assertEqual(caught.exception.code, "NOT_READY")

    def test_tampered_check_evidence_blocks_finalization(self):
        a, b, revision = self.prepared_team([
            {"name": "proof", "argv": [sys.executable, "-c", "print('verified')"]}])
        run = self.invoke("check", b, name="proof")["check"]
        (self.root / run["log_path"]).write_text("different evidence", encoding="utf-8")
        with self.assertRaises(CollabError) as caught:
            self.invoke("finalize", a, revision=revision)
        self.assertEqual(caught.exception.code, "NOT_READY")

    def test_check_with_stale_revision_does_not_execute(self):
        a, b, revision = self.prepared_team([
            {"name": "proof", "argv": [sys.executable, "-c",
             "from pathlib import Path; Path('ran.txt').write_text('ran')"]}])
        self.invoke("propose", a, content="New result revision")
        with self.assertRaises(CollabError) as caught:
            self.invoke("check", b, name="proof", revision=revision)
        self.assertEqual(caught.exception.code, "STALE_REVISION")
        self.assertFalse((self.root / "ran.txt").exists())

    def test_agent_cannot_impersonate_another_or_resume_without_token(self):
        a = self.invoke("start", name="Author", session_id="author", objective="Authentication test")
        with self.assertRaises(CollabError) as caught:
            self.invoke("send", a, token="wrong", content="forged")
        self.assertEqual(caught.exception.code, "AUTH_REQUIRED")
        with self.assertRaises(CollabError) as caught:
            self.invoke("start", name="Attacker", session_id="author", task_id=a["task"]["id"])
        self.assertEqual(caught.exception.code, "AUTH_REQUIRED")

    def test_external_file_change_does_not_get_overwritten(self):
        path = self.root / "result.txt"
        path.write_text("original", encoding="utf-8")
        a = self.invoke("start", name="Author", session_id="author", objective="Safe file update")
        reservation = self.invoke("reserve", a, files=["result.txt"])["reservation"]
        path.write_text("user's concurrent change", encoding="utf-8")
        with self.assertRaises(CollabError) as caught:
            self.invoke("file-write", a, reservation_id=reservation["id"], path="result.txt",
                        expected_hash=reservation["base_hashes"]["result.txt"], content="agent change")
        self.assertEqual(caught.exception.code, "FILE_CHANGED")
        self.assertEqual(path.read_text(encoding="utf-8"), "user's concurrent change")

    def test_observer_join_does_not_change_review_membership(self):
        a, b, revision = self.prepared_team()
        before = self.invoke("status", task_id=a["task"]["id"])["task"]
        observer = self.invoke("start", name="Observer", session_id="observer", task_id=a["task"]["id"])
        self.assertTrue(observer["observer"])
        after = self.invoke("status", task_id=a["task"]["id"])["task"]
        self.assertEqual(after["decision"], before["decision"])
        self.assertEqual(after["approvals"], before["approvals"])
        with self.assertRaises(CollabError) as caught:
            self.invoke("approve", observer, revision=revision, content="Cannot supply required approval")
        self.assertEqual(caught.exception.code, "OBSERVER")

    def test_file_write_stages_only_inside_runtime_and_preserves_file_on_failure(self):
        path = self.root / "result.txt"
        path.write_text("original", encoding="utf-8")
        a = self.invoke("start", name="Author", session_id="author", objective="Contained write staging")
        reservation = self.invoke("reserve", a, files=["result.txt"])["reservation"]
        replace = os.replace
        def fail_replace(source, destination):
            if Path(destination) == path:
                self.assertEqual(Path(source).parent, self.root / ".collab/tmp")
                raise OSError("simulated interrupted edit")
            return replace(source, destination)
        with mock.patch("collablib.engine.os.replace", side_effect=fail_replace):
            with self.assertRaises(OSError):
                self.invoke("file-write", a, reservation_id=reservation["id"], path="result.txt",
                            expected_hash=reservation["base_hashes"]["result.txt"], content="new")
        self.assertEqual(path.read_text(), "original")
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), [".collab", "result.txt"])
        self.invoke("file-write", a, reservation_id=reservation["id"], path="result.txt",
                    expected_hash=reservation["base_hashes"]["result.txt"], content="new")
        self.assertEqual(path.read_text(), "new")
        self.assertEqual(list((self.root / ".collab/tmp").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
