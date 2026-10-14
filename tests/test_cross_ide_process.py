"""Real independent helper processes with simulated IDE identities, not live IDEs."""
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import unittest
import uuid

import test_integration as integration
sys.path.insert(0, str(integration.HELPER.parent))
from collablib import installer


class CrossIDEProcessTests(unittest.TestCase):
    setUp = integration.ProcessIntegrationTests.setUp
    cli = integration.ProcessIntegrationTests.cli
    start = integration.ProcessIntegrationTests.start
    events_on_disk = integration.ProcessIntegrationTests.events_on_disk
    _barrier_commands = integration.ProcessIntegrationTests._barrier_commands

    def work(self, a):
        item = self.cli("assignment-add", dict(a, title="Calculator verification"))["assignment"]
        self.cli("claim", dict(a, assignment_id=item["id"]))
        self.cli("work-complete", dict(a, assignment_id=item["id"], result="2+2=4", evidence=["checked arithmetic"]))

    def approve(self, a, b):
        proposal = self.cli("propose", dict(a, content="Calculator verified"))
        self.cli("review", dict(b, verdict="APPROVE", evidence=["independent arithmetic check"]))
        for member in (a, b):
            self.cli("approve", member)
        return proposal

    def test_independently_installed_codex_and_antigravity_join_help_and_complete(self):
        home = Path(self.temporary.name) / "isolated home"
        home.mkdir()
        installed = installer.install_skill(agents=["codex", "antigravity"], home_dir=home,
                                             project_root=self.project, env={})
        self.assertEqual(list(self.project.iterdir()), [])
        clients = []
        task_id = None
        for item in installed["installations"]:
            helper = Path(item["destination"]) / "scripts/collab.py"
            data = {"name": item["agent"], "platform": item["agent"], "session_id": str(uuid.uuid4()),
                    "objective": "Calculator", "expected_platforms": ["codex", "antigravity"],
                    "model": item["agent"] + "-exact-model-variant", "reasoning_level": "high"}
            if task_id:
                data["task_id"] = task_id
            joined = self.cli("start", data, helper=helper)
            task_id = joined["task"]["id"]
            clients.append({"agent_id": joined["agent"]["id"], "token": joined["token"], "task_id": task_id})
        a, b = clients
        help_item = self.cli("help-request", dict(b, content="Verify arithmetic"))["help"]
        self.cli("help-respond", dict(a, help_id=help_item["id"], content="2 + 2 = 4"))
        self.cli("help-resolve", dict(b, help_id=help_item["id"], content="Reproduced"))
        for client in clients:
            self.work(client)
        self.approve(a, b)
        self.assertEqual(self.cli("finalize", a)["task"]["status"], "TEAM_COMPLETE")
        self.assertEqual(len(self.cli("status", {})["tasks"]), 1)
        events = self.events_on_disk()
        self.assertEqual({e["platform_key"] for e in events if e["type"] == "JOIN"}, {"codex", "antigravity"})
        self.assertEqual(len({e["session_id"] for e in events if e["type"] == "JOIN"}), 2)

    def test_second_codex_is_blocked_then_late_antigravity_must_approve(self):
        a, _, _ = self.start("Codex A", platform="codex", expected_platforms=["codex", "antigravity"])
        b, _, _ = self.start("Codex B", platform="Codex Desktop")
        for client in (a, b):
            self.work(client)
        self.approve(a, b)
        failure = self.cli("finalize", a, succeeds=False)
        self.assertIn("Missing required IDE: antigravity", failure["error"]["details"]["blockers"])
        c, joined, _ = self.start("Antigravity", platform="antigravity", task_id=a["task_id"])
        self.assertFalse(joined["observer"])
        self.assertEqual(self.cli("finalize", a, succeeds=False)["error"]["code"], "STALE_REVISION")
        self.work(c)
        self.approve(a, b)
        self.assertIn(c["agent_id"], json.dumps(self.cli("finalize", a, succeeds=False)))
        self.cli("approve", c)
        self.cli("finalize", a)

    def test_concurrent_same_objective_starts_create_one_task(self):
        operations = [("start", {"name": platform, "platform": platform, "session_id": str(uuid.uuid4()),
                                  "objective": "One calculator", "new_task": True,
                                  "expected_platforms": ["codex", "antigravity"]})
                      for platform in ("codex", "antigravity", "codex-desktop", "antigravity-ide")]
        joined = self._barrier_commands(operations)
        self.assertEqual(len({x["task"]["id"] for x in joined}), 1)
        self.assertEqual(len(self.cli("status", {})["agents"]), 4)

    def test_required_join_racing_finalization_never_completes_old_round(self):
        a, _, _ = self.start("A", platform="codex", expected_platforms=["codex", "antigravity"])
        b, _, _ = self.start("B", platform="codex")
        for client in (a, b):
            self.work(client)
        self.approve(a, b)
        results = self._barrier_commands([
            ("finalize", a),
            ("start", {"name": "C", "platform": "antigravity", "session_id": str(uuid.uuid4()), "task_id": a["task_id"]}),
        ], allow_errors=True)
        self.assertFalse(results[0]["ok"])
        self.assertIn(results[0]["error"]["code"], ("NOT_READY", "STALE_REVISION"))
        self.assertTrue(results[1]["ok"])
        self.assertFalse(any(e["type"] == "TEAM_COMPLETE" for e in self.events_on_disk()))

    def test_cli_registration_error_is_json_and_nonzero(self):
        invalid = self.cli("start", {"name": "A", "session_id": "a", "objective": "x",
                                     "expected_platforms": ["not-a-platform"]}, succeeds=False)
        self.assertEqual(invalid["error"]["code"], "INVALID_INPUT")
        self.assertEqual(self.cli("status", {})["agents"], [])
        completed = subprocess.run([sys.executable, str(integration.HELPER), "start", "--input", "-"],
                                   cwd=self.project, input=json.dumps({"name": "A", "session_id": "a", "objective": "x",
                                                                      "min_distinct_platforms": 2}),
                                   text=True, capture_output=True, encoding="utf-8", timeout=30)
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(json.loads(completed.stdout)["error"]["code"], "ROOT_REQUIRED")

    def test_copied_pending_journal_refuses_recovery_in_another_root(self):
        a, _, _ = self.start("A", platform="codex")
        environment = dict(self.environment, COLLAB_TEST_CRASH="after_wal")
        crashed = subprocess.run([sys.executable, str(integration.HELPER), "--root", str(self.project),
                                  "send", "--input", "-"], input=json.dumps(dict(a, content="Recover at original root")),
                                 env=environment, text=True, capture_output=True, timeout=30)
        self.assertEqual(crashed.returncode, 91)
        other = Path(self.temporary.name) / "copied project"
        shutil.copytree(self.project, other)
        before = {p.relative_to(other): p.read_bytes() for p in other.rglob("*") if p.is_file()}
        run = subprocess.run([sys.executable, str(integration.HELPER), "--root", str(other), "status"],
                             text=True, capture_output=True, timeout=30)
        self.assertEqual(run.returncode, 2)
        self.assertEqual(json.loads(run.stdout)["error"]["code"], "ROOT_MISMATCH")
        self.assertEqual({p.relative_to(other): p.read_bytes() for p in other.rglob("*") if p.is_file()}, before)
        self.assertEqual(self.cli("status", a)["task"]["id"], a["task_id"])


if __name__ == "__main__":
    unittest.main()
