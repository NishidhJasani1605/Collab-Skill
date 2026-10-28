"""Bounded waits keep a finished participant connected to the shared team.

These clients are simulated; this does not exercise either IDE's scheduler.
"""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/collab/scripts"))
from collablib.engine import execute
from collablib.storage import CollabError, Store

HELPER = Path(__file__).resolve().parents[1] / "skills/collab/scripts/collab.py"


class TeamWaitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="collab team wait ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def call(self, command, agent=None, **data):
        auth = {} if agent is None else {"agent_id": agent["agent"]["id"], "token": agent["token"], "task_id": agent["task"]["id"]}
        return execute(self.root, command, {**auth, **data})

    def join(self, platform):
        return self.call("start", name=platform, platform=platform, simulated=True,
                         session_id=str(uuid.uuid4()), objective="Build shared calculator",
                         expected_platforms=["codex", "antigravity"])

    def work(self, agent):
        item = self.call("assignment-add", agent, title="Implement or independently verify")["assignment"]
        self.call("claim", agent, assignment_id=item["id"])
        return self.call("work-complete", agent, assignment_id=item["id"], result="Verified", evidence=["2 + 2 = 4"])

    def wait(self, agent, **data):
        try:
            return self.call("wait", agent, **data)
        except CollabError as exc:
            self.fail("Waiting must be supported without mutating completion: " + exc.code)

    def test_finishing_own_assignment_explicitly_continues_team_loop(self):
        a = self.join("codex")
        completed = self.work(a)
        self.assertIs(completed.get("team_complete"), False)
        self.assertIs(completed.get("continue_waiting"), True)
        self.assertIn("Missing required IDE: antigravity", completed["teamwork"]["missing_collaborators"])
        self.assertEqual(self.call("status", a)["task"]["status"], "WORKING")

    def test_empty_wait_timeout_does_not_pause_or_complete_team(self):
        a = self.join("codex")
        cursor = self.call("status", a)["cursor"]
        result = self.wait(a, after=cursor, wait_seconds=0.1)
        self.assertEqual(result["events"], [])
        self.assertEqual(result["reason"], "timeout")
        self.assertFalse(result["team_complete"])
        self.assertTrue(result["continue_waiting"])
        self.assertEqual(result["task"]["status"], "WORKING")

    def test_wait_renews_presence_without_self_waking_on_heartbeat(self):
        a = self.join("codex")
        with Store(self.root) as store:
            state = copy.deepcopy(store.state)
            state["agents"][a["agent"]["id"]]["last_seen_epoch"] = time.time() - 3600
            store.commit(state, {"type": "STATUS", "content": "Simulated old presence"})
        cursor = self.call("status", a)["cursor"]
        result = self.wait(a, after=cursor, wait_seconds=0.1)
        self.assertEqual(result["events"], [])
        self.assertEqual(result["reason"], "timeout")
        self.assertGreater(result["cursor"], cursor)
        self.assertEqual(result["teamwork"]["unavailable_participants"], [])
        fresh = self.call("status", a)
        self.assertFalse(fresh["agents"][0]["stale"])
        # Repeated short polls do not grow the event journal indefinitely.
        self.wait(a, after=result["cursor"], wait_seconds=0)
        self.assertEqual(self.call("status", a)["cursor"], fresh["cursor"])

    def test_wait_releases_lock_for_peer_process_and_delivers_message(self):
        a, b = self.join("codex"), self.join("antigravity")
        cursor = self.call("status", a)["cursor"]
        peer_data = {"agent_id": b["agent"]["id"], "token": b["token"],
                     "task_id": b["task"]["id"], "content": "Peer needs review"}
        # The peer must be able to commit while the first process is waiting.
        runner = "import subprocess,sys,time; time.sleep(0.2); sys.exit(subprocess.call(sys.argv[1:]))"
        peer = subprocess.Popen([sys.executable, "-c", runner, sys.executable, str(HELPER),
                                 "--root", str(self.root), "send", "--data", json.dumps(peer_data)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            result = self.wait(a, after=cursor, wait_seconds=3)
            stdout, stderr = peer.communicate(timeout=5)
        finally:
            if peer.poll() is None:
                peer.kill()
                peer.communicate()
        self.assertEqual(peer.returncode, 0, stderr)
        self.assertTrue(json.loads(stdout)["ok"])
        self.assertEqual(result["reason"], "events")
        self.assertIn("Peer needs review", [event["content"] for event in result["events"]])
        self.assertTrue(result["continue_waiting"])

    def test_completed_team_is_terminal_for_wait_without_reopening(self):
        a, b = self.join("codex"), self.join("antigravity")
        self.work(a)
        self.work(b)
        self.call("propose", a, content="Ready for review")
        self.call("review", b, verdict="APPROVE", evidence=["Independently verified"])
        self.call("approve", a)
        self.call("approve", b)
        self.call("finalize", a)
        result = self.wait(b, after=self.call("status", b)["cursor"], wait_seconds=3)
        self.assertEqual(result["reason"], "team_complete")
        self.assertTrue(result["team_complete"])
        self.assertFalse(result["continue_waiting"])
        self.assertEqual(result["blockers"], [])
        self.assertEqual(result["task"]["status"], "TEAM_COMPLETE")

    def test_wait_requires_valid_participant_credentials(self):
        a = self.join("codex")
        with self.assertRaises(CollabError) as caught:
            self.call("wait", a, token="wrong", wait_seconds=0)
        self.assertEqual(caught.exception.code, "AUTH_REQUIRED")

    def test_authenticated_read_renews_presence_but_anonymous_read_is_read_only(self):
        a = self.join("codex")
        with Store(self.root) as store:
            state = copy.deepcopy(store.state)
            state["agents"][a["agent"]["id"]]["last_seen_epoch"] = time.time() - 3600
            store.commit(state, {"type": "STATUS", "content": "Simulated old presence"})
        before = (self.root / ".collab/GROUP_CHAT.jsonl").read_bytes()
        self.call("read", task_id=a["task"]["id"])
        self.assertEqual((self.root / ".collab/GROUP_CHAT.jsonl").read_bytes(), before)
        result = self.call("read", a)
        self.assertIs(result.get("continue_waiting"), True)
        self.assertFalse(self.call("status", a)["agents"][0]["stale"])

    def test_authenticated_read_cannot_renew_another_participant(self):
        a = self.join("codex")
        with self.assertRaises(CollabError) as caught:
            self.call("read", a, token="wrong")
        self.assertEqual(caught.exception.code, "AUTH_REQUIRED")

    def test_invalid_wait_durations_are_rejected_before_presence_changes(self):
        a = self.join("codex")
        before = (self.root / ".collab/GROUP_CHAT.jsonl").read_bytes()
        for value in (-1, 31, "10", True, float("nan"), float("inf"), 10**400):
            with self.subTest(value=value):
                with self.assertRaises(CollabError) as caught:
                    self.call("wait", a, wait_seconds=value)
                self.assertEqual(caught.exception.code, "INVALID_INPUT")
        self.assertEqual((self.root / ".collab/GROUP_CHAT.jsonl").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
