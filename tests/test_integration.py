"""Independent-process acceptance tests for the public COLLAB helper.

These tests simulate agent clients. They do not claim live IDE integration.
Only the standard library and the installed Python interpreter are required.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import uuid


REPOSITORY = Path(__file__).resolve().parents[1]
HELPER = REPOSITORY / "skills" / "collab" / "scripts" / "collab.py"


class ProcessIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="collab-integration-")
        self.addCleanup(self.temporary.cleanup)
        self.project = (Path(self.temporary.name) / "shared project").resolve()
        self.project.mkdir()
        self.environment = dict(os.environ, PYTHONUTF8="1")

    def cli(self, command, data, *, succeeds=True, helper=HELPER):
        completed = subprocess.run(
            [sys.executable, str(helper), "--root", str(self.project), command,
             "--data", json.dumps(data, ensure_ascii=False)],
            capture_output=True, text=True, encoding="utf-8",
            env=self.environment, timeout=120,
        )
        try:
            response = json.loads(completed.stdout)
        except json.JSONDecodeError:
            self.fail(
                f"{command}: expected one JSON response; exit={completed.returncode}; "
                f"stdout={completed.stdout!r}; stderr={completed.stderr!r}"
            )
        self.assertEqual(response.get("ok"), succeeds, (command, response))
        self.assertEqual(completed.returncode, 0 if succeeds else 2,
                         (command, completed.stdout, completed.stderr))
        if not succeeds:
            self.assertIn("code", response["error"])
            self.assertIn("message", response["error"])
        return response

    def start(self, name, **extra):
        data = {
            "name": name,
            "platform": "independent-process-test",
            "model": "unknown",
            "session_id": str(uuid.uuid4()),
            "objective": "Verify collaboration in a shared local project",
        }
        data.update(extra)
        result = self.cli("start", data)
        return {"agent_id": result["agent"]["id"], "token": result["token"],
                "task_id": result["task"]["id"]}, result, data

    def events_on_disk(self):
        path = self.project / ".collab" / "GROUP_CHAT.jsonl"
        raw = path.read_bytes()
        self.assertTrue(raw.endswith(b"\n"), "Authoritative log has a torn final line")
        return [json.loads(line) for line in raw.decode("utf-8").splitlines()]

    def test_01_two_independent_agents_exchange_and_resume(self):
        agent_a, joined_a, original_start = self.start("Agent A")
        sent_a = self.cli("send", dict(agent_a, type="PLAN", content="A → B: inspect parser", key="plan-a"))
        agent_b, joined_b, _ = self.start("Agent B")
        self.assertEqual(agent_a["task_id"], agent_b["task_id"])
        self.assertNotEqual(agent_a["agent_id"], agent_b["agent_id"])
        read_b = self.cli("read", dict(agent_b, after=0, limit=100))
        self.assertIn("A → B: inspect parser", [event["content"] for event in read_b["events"]])
        cursor = read_b["cursor"]
        self.cli("send", dict(agent_b, type="REPLY", content="B → A: parser checked", key="reply-b"))
        read_a = self.cli("read", dict(agent_a, after=cursor, limit=100))
        self.assertIn("B → A: parser checked", [event["content"] for event in read_a["events"]])
        self.assertNotIn("A → B: inspect parser", [event["content"] for event in read_a["events"]])
        self.cli("send", dict(agent_a, type="PLAN", content="A → B: inspect parser", key="plan-a"))
        recovered = self.cli("start", dict(original_start, token=agent_a["token"]))
        self.assertEqual(recovered["agent"]["id"], agent_a["agent_id"])
        self.assertEqual(recovered["task"]["id"], agent_a["task_id"])
        events = self.events_on_disk()
        self.assertEqual(sum(event["content"] == "A → B: inspect parser" for event in events), 1)
        self.assertEqual(sum(event["content"] == "B → A: parser checked" for event in events), 1)
        transcript = (self.project / ".collab" / "GROUP_CHAT.md").read_text(encoding="utf-8")
        self.assertIn("A → B: inspect parser", transcript)
        self.assertIn("B → A: parser checked", transcript)

    def _barrier_commands(self, operations, *, allow_errors=False):
        """Release already-running, independent Python clients at the same time.

        Each child executes the real CLI with runpy after its ready marker is
        acknowledged. No in-process engine calls replace the CLI operations.
        """
        gate = Path(self.temporary.name) / ("gate-" + uuid.uuid4().hex)
        gate.mkdir()
        barrier_script = (
            "import pathlib,runpy,sys,time\n"
            "helper,root,command,payload,gate,index=sys.argv[1:]\n"
            "gate=pathlib.Path(gate)\n"
            "(gate/('ready-'+index)).touch()\n"
            "deadline=time.monotonic()+120\n"
            "while not (gate/'release').exists():\n"
            " if time.monotonic()>deadline: raise SystemExit('barrier timed out')\n"
            " time.sleep(0.02)\n"
            "sys.path.insert(0,str(pathlib.Path(helper).parent))\n"
            "sys.argv=[helper,'--root',root,command,'--input',payload]\n"
            "runpy.run_path(helper,run_name='__main__')\n"
        )
        children = []
        try:
            for index, (command, data) in enumerate(operations):
                payload = gate / f"input-{index}.json"
                payload.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                child = subprocess.Popen(
                    [sys.executable, "-c", barrier_script, str(HELPER), str(self.project),
                     command, str(payload), str(gate), str(index)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                    encoding="utf-8", env=self.environment,
                )
                children.append(child)
            deadline = time.monotonic() + 120
            while len(list(gate.glob("ready-*"))) != len(children):
                self.assertTrue(all(child.poll() is None for child in children),
                                "A client exited before the barrier was released")
                self.assertLess(time.monotonic(), deadline, "Clients did not reach the barrier")
                time.sleep(0.02)
            self.assertTrue(all(child.poll() is None for child in children))
            (gate / "release").touch()
            results = []
            for index, child in enumerate(children):
                stdout, stderr = child.communicate(timeout=180)
                response = json.loads(stdout)
                self.assertEqual(child.returncode, 0 if response["ok"] else 2,
                                 (index, stdout, stderr))
                if not allow_errors:
                    self.assertTrue(response["ok"], response)
                results.append(response)
            return results
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.communicate()

    def test_02_120_simultaneous_submissions_have_no_loss_or_corruption(self):
        agent, _, _ = self.start("Concurrent client")
        count = 120
        messages = [f"parallel message {index:03d} / 雪 / café" for index in range(count)]
        self._barrier_commands([
            ("send", dict(agent, type="STATUS", content=message, key=f"parallel-{index}"))
            for index, message in enumerate(messages)
        ])
        events = self.events_on_disk()
        submitted = [event for event in events if event["content"] in messages]
        self.assertEqual(len(submitted), count)
        self.assertEqual({event["content"] for event in submitted}, set(messages))
        self.assertEqual(len({event["id"] for event in events}), len(events))
        sequences = [event["seq"] for event in events]
        self.assertEqual(sequences, list(range(1, len(events) + 1)))
        transcript = (self.project / ".collab" / "GROUP_CHAT.md").read_text(encoding="utf-8")
        for message in messages:
            self.assertEqual(transcript.count(message), 1)
        all_read = self.cli("read", dict(agent, after=0, limit=1000))
        self.assertEqual(len(all_read["events"]), len(events))

    def test_03_parallel_first_join_creates_one_task_and_unique_agents(self):
        starts = [
            ("start", {"name": f"Agent {index}", "platform": "same-platform",
                       "model": "unknown", "session_id": str(uuid.uuid4()),
                       "objective": "One shared objective"})
            for index in range(12)
        ]
        joined = self._barrier_commands(starts)
        self.assertEqual(len({result["agent"]["id"] for result in joined}), 12)
        self.assertEqual(len({result["task"]["id"] for result in joined}), 1)
        events = self.events_on_disk()
        self.assertEqual(len([event for event in events if event["type"] == "JOIN"]), 12)

    def test_04_three_agent_collaboration_review_and_atomic_completion(self):
        agent_a, _, _ = self.start(
            "Agent A", criteria=["All three responsibilities finished", "Independent review recorded"],
            checks=[{"name": "artifact-content", "argv": [sys.executable, "-c",
                    "from pathlib import Path; assert Path('result.txt').read_text() == 'verified result\\n'; print('artifact verified')"]}],
            artifacts=["result.txt"],
        )
        agent_b, _, _ = self.start("Agent B")
        agent_c, _, c_start = self.start("Agent C")
        self.assertEqual({agent_a["task_id"], agent_b["task_id"], agent_c["task_id"]},
                         {agent_a["task_id"]})
        discovery = self.cli("status", agent_a)
        self.assertEqual(len(discovery["task"]["participants"]), 3)

        assignment_ids = []
        for agent, title in [(agent_a, "Analyze requirements"), (agent_b, "Implement result"),
                             (agent_c, "Independently validate result")]:
            assignment = self.cli("assignment-add", dict(agent, title=title, required=True,
                                                          depends_on=[], files=[]))["assignment"]
            assignment_ids.append(assignment["id"])
            self.cli("claim", dict(agent, assignment_id=assignment["id"]))
        self.cli("claim", dict(agent_b, assignment_id=assignment_ids[0]), succeeds=False)
        self.cli("progress", dict(agent_a, assignment_id=assignment_ids[0], percent=99,
                                   content="Requirements mapped to evidence"))
        self.cli("work-complete", dict(agent_a, assignment_id=assignment_ids[0],
                                        result="Requirements inspected", evidence=["requirements mapped"]))
        task_after_individual_completion = self.cli("status", agent_a)["task"]
        self.assertNotEqual(task_after_individual_completion["status"], "TEAM_COMPLETE")
        self.assertNotEqual(task_after_individual_completion["status"], "COMPLETED")

        help_request = self.cli("help-request", dict(agent_b, assignment_id=assignment_ids[1],
                                                     content="Please verify the expected artifact text"))
        help_id = help_request["help"]["id"]
        self.cli("help-respond", dict(agent_a, help_id=help_id,
                                       content="Checked: use 'verified result' followed by a newline"))
        self.cli("help-resolve", dict(agent_b, help_id=help_id, content="Confirmed; implementation can continue"))
        disagreement = self.cli("send", dict(agent_c, type="DISAGREEMENT",
                                              content="The initial conclusion lacks a reproducible artifact check"))
        blocker = self.cli("issue", dict(agent_c, content="Artifact check must pass", blocking=True))
        issue_id = blocker["issue"]["id"]
        self.cli("finding", dict(agent_a, content="A file assertion reproduces the acceptance condition",
                                  evidence=["check artifact-content asserts exact bytes"]))

        (self.project / "result.txt").write_text("verified result\n", encoding="utf-8")
        first = self.cli("propose", dict(agent_a, content="Initial shared conclusion", files=["result.txt"],
                                          artifacts=["result.txt"], limitations=[]))["revision"]
        self.cli("finalize", dict(agent_a, revision=first), succeeds=False)
        self.cli("review", dict(agent_c, revision=first, verdict="REJECT",
                                 content="Required assignments and a recorded check are still outstanding",
                                 evidence=["assignment completion state"]))
        self.cli("work-complete", dict(agent_b, assignment_id=assignment_ids[1],
                                        result="Artifact implemented", evidence=["result.txt"]))
        self.cli("work-complete", dict(agent_c, assignment_id=assignment_ids[2],
                                        result="Verified artifact and check independently", evidence=["result.txt"]))

        second = self.cli("propose", dict(agent_a, content="Revised conclusion with complete responsibilities",
                                           files=["result.txt"], artifacts=["result.txt"], limitations=[]))["revision"]
        self.assertGreater(second, first)
        self.cli("approve", dict(agent_b, revision=first, content="Stale revision must be refused"), succeeds=False)
        self.cli("check", dict(agent_a, name="artifact-content"))
        self.cli("review", dict(agent_c, revision=second, verdict="APPROVE",
                                 content="Independently verified the exact artifact and required check",
                                 evidence=["result.txt", "artifact-content"]))
        self.cli("finalize", dict(agent_a, revision=second), succeeds=False)
        self.cli("resolve", dict(agent_c, issue_id=issue_id,
                                  content="The reproducible check passed", evidence=["artifact-content"]))
        self.cli("resolve", dict(agent_c, issue_id=disagreement["issue"]["id"],
                                  content="The revised result includes reproducible validation", evidence=["artifact-content"]))

        # Resolving a material blocker may invalidate the prior review round.
        final_revision = self.cli("propose", dict(agent_a, content="Agreed result after resolving the review concern",
                                                   files=["result.txt"], artifacts=["result.txt"],
                                                   limitations=["Simulated subprocess clients, not live IDE integration"]))["revision"]
        self.cli("check", dict(agent_b, name="artifact-content"))
        self.cli("review", dict(agent_c, revision=final_revision, verdict="APPROVE",
                                 content="Reviewed the final revision against the artifact and successful check",
                                 evidence=["result.txt", "artifact-content"]))
        self.cli("approve", dict(agent_a, revision=final_revision, content="Requirements satisfied"))
        self.cli("approve", dict(agent_b, revision=final_revision, content="Implementation verified"))
        self.cli("finalize", dict(agent_a, revision=final_revision), succeeds=False)
        self.cli("approve", dict(agent_c, revision=final_revision, content="Independent review complete"))
        completions = self._barrier_commands([
            ("finalize", dict(agent, revision=final_revision)) for agent in [agent_a, agent_b, agent_c]
        ], allow_errors=True)
        self.assertTrue(any(result["ok"] for result in completions), completions)
        events = self.events_on_disk()
        self.assertEqual(len([event for event in events if event["type"] == "TEAM_COMPLETE"]), 1)
        report = (self.project / ".collab" / "FINAL_REPORT.md").read_text(encoding="utf-8")
        for expected in ["Agent A", "Agent B", "Agent C", "result.txt", "artifact-content",
                         "Agreed result after resolving the review concern"]:
            self.assertIn(expected, report)
        self.assertFalse(any(agent["token"] in report for agent in [agent_a, agent_b, agent_c]))
        restored = self.cli("status", agent_c)
        self.assertIn(restored["task"]["status"], ["TEAM_COMPLETE", "COMPLETED"])
        self.assertEqual(len(self.events_on_disk()), len(events))

    def test_05_mutation_requires_token_and_session_resume_keeps_identity(self):
        agent, _, original = self.start("Authenticated agent")
        self.cli("send", {"agent_id": agent["agent_id"], "task_id": agent["task_id"],
                          "type": "STATUS", "content": "Unauthenticated write"}, succeeds=False)
        self.cli("send", dict(agent, token="incorrect-token", type="STATUS", content="Forged write"), succeeds=False)
        self.cli("start", original, succeeds=False)
        recovered = self.cli("start", dict(original, token=agent["token"]))
        self.assertEqual(recovered["agent"]["id"], agent["agent_id"])
        self.cli("send", dict(agent, type="STATUS", content="Authenticated write"))
        events = self.events_on_disk()
        self.assertNotIn("Unauthenticated write", [event["content"] for event in events])
        self.assertNotIn("Forged write", [event["content"] for event in events])
        self.assertIn("Authenticated write", [event["content"] for event in events])
        public_read = self.cli("read", {"after": 0, "limit": 100})
        self.assertNotIn(agent["token"], json.dumps(public_read))

    def test_06_competing_claims_have_exactly_one_owner(self):
        first, _, _ = self.start("Claimant A")
        second, _, _ = self.start("Claimant B")
        assignment_id = self.cli("assignment-add", dict(first, title="One exclusive responsibility",
                                                         depends_on=[], files=[], required=True))["assignment"]["id"]
        claims = self._barrier_commands([
            ("claim", dict(agent, assignment_id=assignment_id)) for agent in [first, second]
        ], allow_errors=True)
        self.assertEqual(sum(response["ok"] for response in claims), 1, claims)

    def prepared_pair(self, **start_options):
        first, _, _ = self.start("Author", **start_options)
        second, _, _ = self.start("Reviewer")
        for agent in [first, second]:
            assignment_id = self.cli("assignment-add", dict(agent, title="Assigned verification",
                                                             required=True, depends_on=[], files=[]))["assignment"]["id"]
            self.cli("claim", dict(agent, assignment_id=assignment_id))
            self.cli("work-complete", dict(agent, assignment_id=assignment_id,
                                            result="Finished assigned verification", evidence=["recorded analysis"]))
        return first, second

    def approve_pair(self, first, second, revision):
        self.cli("review", dict(second, revision=revision, verdict="APPROVE",
                                 content="Independently inspected the result", evidence=["independent inspection"]))
        for agent in [first, second]:
            self.cli("approve", dict(agent, revision=revision, content="Verified this specific revision"))

    def test_07_external_changes_and_missing_required_artifacts_block_completion(self):
        artifact = self.project / "required.txt"
        artifact.write_text("initial result", encoding="utf-8")
        first, second = self.prepared_pair(artifacts=["required.txt"])
        revision = self.cli("propose", dict(first, content="Initial conclusion", files=[], artifacts=[], limitations=[]))["revision"]
        self.approve_pair(first, second, revision)
        artifact.write_text("externally changed result", encoding="utf-8")
        changed = self.cli("finalize", dict(first, revision=revision), succeeds=False)
        self.assertEqual(changed["error"]["code"], "RESULT_CHANGED")
        self.cli("approve", dict(second, revision=revision, content="Cannot approve outdated bytes"), succeeds=False)
        revised = self.cli("propose", dict(first, content="Revised conclusion", files=[], artifacts=[], limitations=[]))["revision"]
        self.assertGreater(revised, revision)
        self.assertEqual(self.cli("status", first)["task"]["approvals"], {})
        self.cli("finalize", dict(first, revision=revised), succeeds=False)
        self.approve_pair(first, second, revised)
        artifact.unlink()
        self.cli("finalize", dict(first, revision=revised), succeeds=False)
        self.assertFalse((self.project / ".collab" / "FINAL_REPORT.md").exists())

    def test_08_self_review_does_not_count_and_late_join_is_observer(self):
        first, second = self.prepared_pair()
        proposal = self.cli("propose", dict(first, content="Reviewed conclusion", files=[], artifacts=[], limitations=[]))
        revision = proposal["revision"]
        self.cli("review", dict(first, revision=revision, verdict="APPROVE",
                                 content="Author's own inspection", evidence=["self inspection"]))
        for agent in [first, second]:
            self.cli("approve", dict(agent, revision=revision, content="This revision is accepted"))
        refused = self.cli("finalize", dict(first, revision=revision), succeeds=False)
        self.assertIn("independent review", json.dumps(refused).lower())
        self.cli("review", dict(second, revision=revision, verdict="APPROVE",
                                 content="Evidence omitted", evidence=[]), succeeds=False)
        self.cli("review", dict(second, revision=revision, verdict="APPROVE",
                                 content="Independent analysis supplied", evidence=["separate verification"]))
        observer, joined, _ = self.start("Late observer")
        self.assertTrue(joined["observer"])
        self.assertNotIn(observer["agent_id"], joined["task"]["decision"]["members"])
        self.assertEqual(joined["task"]["decision"]["digest"], proposal["decision"]["digest"])
        self.cli("approve", dict(observer, revision=revision, content="Observer cannot become required"), succeeds=False)
        self.cli("finalize", dict(first, revision=revision))

    def test_09_required_checks_record_actual_failures_then_verified_success(self):
        first, second = self.prepared_pair(checks=[{
            "name": "gate", "argv": [sys.executable, "-c",
                "from pathlib import Path; import sys; print('gate checked'); sys.exit(0 if Path('gate-ready').exists() else 9)"]}])
        revision = self.cli("propose", dict(first, content="Result requiring an executable check", files=[], artifacts=[], limitations=[]))["revision"]
        self.approve_pair(first, second, revision)
        missing = self.cli("finalize", dict(first, revision=revision), succeeds=False)
        self.assertIn("passing check", json.dumps(missing).lower())
        self.cli("check", dict(first, name="not-allowlisted"), succeeds=False)
        failed = self.cli("check", dict(first, name="gate"))
        self.assertEqual(failed["check"]["returncode"], 9)
        self.cli("finalize", dict(first, revision=revision), succeeds=False)
        (self.project / "gate-ready").touch()
        succeeded = self.cli("check", dict(second, name="gate"))
        self.assertEqual(succeeded["check"]["returncode"], 0)
        self.assertEqual(succeeded["check"]["revision"], revision)
        log = self.project / succeeded["check"]["log_path"]
        self.assertIn("gate checked", log.read_text(encoding="utf-8"))
        self.approve_pair(first, second, revision)
        self.cli("finalize", dict(first, revision=revision))

    def test_10_another_agents_token_cannot_impersonate_identity(self):
        first, _, _ = self.start("First identity")
        second, _, _ = self.start("Second identity")
        self.cli("send", dict(first, token=second["token"], type="STATUS", content="Impersonation attempt"), succeeds=False)
        self.cli("agent-status", dict(first, status="TEAM_COMPLETE"), succeeds=False)
        public = self.cli("status", {})
        serialized = json.dumps(public)
        for agent in [first, second]:
            self.assertNotIn(agent["token"], serialized)
        self.assertNotIn("token_hash", serialized)
        self.assertNotIn("Impersonation attempt", [event["content"] for event in self.events_on_disk()])


if __name__ == "__main__":
    unittest.main()
