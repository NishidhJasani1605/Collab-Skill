"""CLI contracts for cooperative waiting and invalid polling inputs."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


HELPER = Path(__file__).resolve().parents[1] / "skills/collab/scripts/collab.py"


class WaitCLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="collab-wait-cli-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def call(self, command, data):
        result = subprocess.run(
            [sys.executable, str(HELPER), "--root", str(self.root), command, "--input", "-"],
            input=json.dumps(data), text=True, encoding="utf-8", capture_output=True,
            env=dict(os.environ, PYTHONUTF8="1"), timeout=10,
        )
        self.assertEqual(result.stderr, "")
        return result.returncode, json.loads(result.stdout)

    def test_wait_cli_keeps_unfinished_task_pending_and_returns_cursor(self):
        code, joined = self.call("start", {
            "name": "CLI participant", "session_id": "cli-wait-session",
            "platform": "test", "objective": "Wait for peer contribution",
        })
        self.assertEqual(code, 0, joined)
        code, waited = self.call("wait", {
            "agent_id": joined["agent"]["id"], "token": joined["token"],
            "task_id": joined["task"]["id"], "after": joined["cursor"],
            "wait_seconds": 0,
        })
        self.assertEqual(code, 0, waited)
        self.assertTrue(waited["continue_waiting"])
        self.assertFalse(waited["team_complete"])
        self.assertGreaterEqual(waited["cursor"], joined["cursor"])

    def test_read_rejects_invalid_wait_without_initializing(self):
        for value in (-1, 31, True, "1", None, 10**400):
            with self.subTest(value=value):
                code, result = self.call("read", {"wait_seconds": value})
                self.assertEqual(code, 2, result)
                self.assertEqual(result["error"]["code"], "INVALID_INPUT", result)
                self.assertFalse((self.root / ".collab").exists())


if __name__ == "__main__":
    unittest.main()
