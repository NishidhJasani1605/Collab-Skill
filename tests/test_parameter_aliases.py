"""Regression tests verifying parameter compatibility between commands.md and engine.py.

Tests parameter aliases, edge cases, and bug fixes including:
- criteria / acceptance_criteria (in start and propose)
- artifacts / required_artifacts (in start and propose, including readiness enforcement)
- content / summary / status_message / description / solution / resolution / detail / result
- file-record optional expected_hash handling
- finalize idempotency without explicit revision parameter
- read cursor alias and status blockers projection
- progress.json projection synchronization
- strict validation on empty/non-string text parameters and checkpoint active_file path safety
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "collab" / "scripts"
sys.path.insert(0, str(SCRIPTS))
from collablib.engine import execute
from collablib.storage import CollabError
import collab_operator


class ParameterAliasesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def invoke(self, command, agent=None, **data):
        credentials = {} if agent is None else {
            "agent_id": agent["agent"]["id"],
            "token": agent["token"],
            "task_id": agent["task"]["id"]
        }
        return execute(self.root, command, {**credentials, **data})

    def test_start_accepts_acceptance_criteria_and_required_artifacts(self):
        """Verify start accepts acceptance_criteria and required_artifacts aliases and merges both."""
        target_file = self.root / "output.txt"
        target_file.write_text("initial output", encoding="utf-8")

        agent = self.invoke(
            "start",
            name="Alice",
            session_id="alice-sess-001",
            objective="Test parameter aliases",
            criteria=["Criterion 1"],
            acceptance_criteria=["Must pass unit tests", "Must produce output.txt"],
            artifacts=["extra.txt"],
            required_artifacts=["output.txt"],
            independent_reviews=1,
        )

        task = agent["task"]
        self.assertEqual(
            task["criteria"],
            ["Criterion 1", "Must pass unit tests", "Must produce output.txt"],
        )
        self.assertEqual(task["acceptance_criteria"], task["criteria"])
        self.assertIn("output.txt", task["required_artifacts"])
        self.assertIn("extra.txt", task["required_artifacts"])
        self.assertEqual(task["artifacts"], task["required_artifacts"])

    def test_checkpoint_accepts_summary_and_validates_active_file(self):
        """Verify checkpoint accepts summary and active_file aliases and rejects unsafe paths."""
        agent = self.invoke("start", name="Bob", session_id="bob-sess-001", objective="Checkpoint test")
        res = self.invoke("checkpoint", agent, summary="Refactored parser module", active_file="src/parser.py")

        self.assertEqual(res["checkpoint"]["content"], "Refactored parser module")
        self.assertEqual(res["checkpoint"]["active_file"], "src/parser.py")

        with self.assertRaises(CollabError) as caught:
            self.invoke("checkpoint", agent, summary="Bad path", active_file="../escape.py")
        self.assertEqual(caught.exception.code, "UNSAFE_PATH")

    def test_assignment_and_progress_parameter_aliases_and_progress_json(self):
        """Verify assignment-add aliases, progress status_message, and .collab/progress.json sync."""
        agent = self.invoke("start", name="Charlie", session_id="charlie-sess-001", objective="Work flow")
        task_id = agent["task"]["id"]

        # assignment-add with name, description, and dependencies alias
        created = self.invoke("assignment-add", agent, name="Code Review", description="Review all PRs", dependencies=[])
        assignment = created["assignment"]
        self.assertEqual(assignment["title"], "Code Review")
        self.assertEqual(assignment["description"], "Review all PRs")

        # claim using id alias
        self.invoke("claim", agent, id=assignment["id"])

        # progress with status_message
        prog = self.invoke("progress", agent, id=assignment["id"], percent=50, status_message="Halfway done")
        self.assertEqual(prog["assignment"]["percent"], 50)

        progress_disk = json.loads((self.root / ".collab" / "progress.json").read_text(encoding="utf-8"))
        self.assertIn(task_id, progress_disk)
        self.assertEqual(progress_disk[task_id]["percent"], 50)
        self.assertEqual(progress_disk[task_id]["assignments_total"], 1)
        self.assertEqual(progress_disk[task_id]["assignments_completed"], 0)

        # work-complete using content instead of result
        comp = self.invoke("work-complete", agent, id=assignment["id"], content="All reviews done", evidence=["ok"])
        self.assertEqual(comp["assignment"]["result"], "All reviews done")
        self.assertEqual(comp["assignment"]["status"], "WORK_COMPLETE")

        progress_disk = json.loads((self.root / ".collab" / "progress.json").read_text(encoding="utf-8"))
        self.assertEqual(progress_disk[task_id]["percent"], 100)
        self.assertEqual(progress_disk[task_id]["assignments_completed"], 1)

    def test_help_request_and_resolution_aliases(self):
        """Verify help-request with title/description, help-respond with solution, and help-resolve with solution."""
        author = self.invoke("start", name="Author", session_id="author-sess", objective="Help flow")
        helper = self.invoke("start", name="Helper", session_id="helper-sess", task_id=author["task"]["id"])

        # help-request using title and description
        req = self.invoke("help-request", author, title="Build error", description="Missing compiler flag")
        help_id = req["help"]["id"]
        self.assertEqual(req["help"]["content"], "Build error: Missing compiler flag")
        self.assertEqual(req["help"]["title"], "Build error")

        # help-respond using solution
        resp = self.invoke("help-respond", helper, help_id=help_id, solution="Add -std=c++20 to flags")
        self.assertEqual(len(resp["help"]["responses"]), 1)
        self.assertEqual(resp["help"]["responses"][0]["content"], "Add -std=c++20 to flags")

        # help-resolve using solution
        resolved = self.invoke("help-resolve", author, help_id=help_id, solution="Verified flag fixed build")
        self.assertEqual(resolved["help"]["status"], "RESOLVED")
        self.assertEqual(resolved["help"]["resolution"], "Verified flag fixed build")

    def test_issue_and_finding_aliases(self):
        """Verify issue title/description and resolution, and finding title/detail."""
        agent = self.invoke("start", name="Tester", session_id="tester-sess", objective="Issues flow")

        # issue with title and description
        iss = self.invoke("issue", agent, title="Memory leak", description="Buffer not freed in loop", blocking=True)
        issue_id = iss["issue"]["id"]
        self.assertEqual(iss["issue"]["content"], "Memory leak: Buffer not freed in loop")
        self.assertEqual(iss["issue"]["title"], "Memory leak")

        # resolve with resolution
        res = self.invoke("resolve", agent, issue_id=issue_id, resolution="Added free(buffer)", evidence=["valgrind clean"])
        self.assertEqual(res["issue"]["status"], "RESOLVED")
        self.assertEqual(res["issue"]["resolution"], "Added free(buffer)")

        # finding with title and detail
        fnd = self.invoke("finding", agent, title="Benchmark metric", detail="10k req/s achieved", evidence=["loadtest.log"])
        self.assertEqual(fnd["finding"]["content"], "Benchmark metric: 10k req/s achieved")
        self.assertEqual(fnd["finding"]["title"], "Benchmark metric")

    def test_propose_artifacts_gate_and_finalize_idempotency_without_revision(self):
        """Verify propose binds required_artifacts, review/approve work without revision, and finalize is idempotent without revision."""
        a = self.invoke("start", name="Lead", session_id="lead-sess", objective="Proposal flow")
        b = self.invoke("start", name="Reviewer", session_id="rev-sess", task_id=a["task"]["id"])

        assignment = self.invoke("assignment-add", a, title="Feature")["assignment"]
        self.invoke("claim", a, assignment_id=assignment["id"])
        self.invoke("work-complete", a, assignment_id=assignment["id"], result="Feature complete", evidence=["tests pass"])
        part_res = self.invoke("participant-result", b, result="Peer verification complete", evidence=["reproduced"])
        self.assertEqual(part_res["participant_result"]["content"], "Peer verification complete")

        # Propose binding an artifact that does not yet exist on disk
        prop1 = self.invoke("propose", a, summary="Missing artifact proposal", required_artifacts=["deliverable.txt"], criteria=["Deliverable exists"])
        self.invoke("review", b, verdict="APPROVE", critique="Looks good", evidence=["checked"])
        self.invoke("approve", a, approval="Lead sign-off")
        self.invoke("approve", b, approval="Reviewer sign-off")

        # Finalize must reject because deliverable.txt is missing on disk
        with self.assertRaises(CollabError) as caught:
            self.invoke("finalize", a)
        self.assertEqual(caught.exception.code, "NOT_READY")
        self.assertTrue(any("deliverable.txt" in b_msg for b_msg in caught.exception.details["blockers"]))

        # Create deliverable.txt and propose revision 2
        (self.root / "deliverable.txt").write_text("final deliverable content\n", encoding="utf-8")
        prop2 = self.invoke("propose", a, summary="Ready for team verification", limitations=["Local test only"])
        self.assertEqual(prop2["revision"], 2)

        # review and approve omitting explicit revision (defaults to active revision)
        rev = self.invoke("review", b, verdict="APPROVE", critique="LGTM with evidence", evidence=["verified deliverable.txt"])
        self.assertEqual(rev["review"]["verdict"], "APPROVE")
        self.assertEqual(rev["review"]["revision"], 2)

        self.invoke("approve", a, approval="Signed off by lead")
        self.invoke("approve", b, approval="Signed off by reviewer")

        # finalize without explicit revision parameter
        fin = self.invoke("finalize", a)
        self.assertEqual(fin["task"]["status"], "TEAM_COMPLETE")

        # Calling finalize again without revision parameter must be idempotent (duplicate=True)
        dup = self.invoke("finalize", a)
        self.assertTrue(dup.get("duplicate"))
        self.assertEqual(dup["task"]["status"], "TEAM_COMPLETE")

    def test_file_record_optional_expected_hash_and_aliases(self):
        """Verify file-record works when expected_hash is omitted, and validates when expected_hash is provided."""
        target = self.root / "module.py"
        target.write_text("x = 1\n", encoding="utf-8")
        agent = self.invoke("start", name="Editor", session_id="editor-sess", objective="Test file-record")

        # reserve using single path alias and ttl alias
        res = self.invoke("reserve", agent, path="module.py", ttl=300)["reservation"]

        # Simulate native host edit
        target.write_text("x = 2\n", encoding="utf-8")

        # file-record without expected_hash (documented as optional in commands.md)
        rec = self.invoke("file-record", agent, id=res["id"], file="module.py")
        self.assertEqual(rec["change"]["method"], "file-record")
        self.assertNotEqual(rec["change"]["before"], rec["change"]["after"])

        # file-record with wrong expected_hash must fail with FILE_CHANGED
        with self.assertRaises(CollabError) as caught:
            self.invoke("file-record", agent, reservation_id=res["id"], path="module.py", expected_hash="0" * 64)
        self.assertEqual(caught.exception.code, "FILE_CHANGED")

        # release reservation
        rel = self.invoke("release", agent, id=res["id"])
        self.assertTrue(rel["reservation"]["released"])

    def test_read_cursor_alias_status_blockers_and_strict_text_validation(self):
        """Verify read accepts cursor alias, status returns blockers, and invalid text types/empty strings are rejected."""
        agent = self.invoke("start", name="Reader", session_id="reader-sess", objective="Read & validation")
        initial_cursor = agent["cursor"]

        # send with message alias and PLAN type transitions JOINED -> PLANNING
        sent = self.invoke("send", agent, type="PLAN", message="Planning architecture")
        self.assertEqual(sent["event"]["type"], "PLAN")

        # read using cursor alias instead of after
        incremental = self.invoke("read", cursor=initial_cursor, task_id=agent["task"]["id"])
        self.assertEqual(len(incremental["events"]), 1)
        self.assertEqual(incremental["events"][0]["content"], "Planning architecture")

        # status returns blockers even before propose
        st = self.invoke("status", task_id=agent["task"]["id"])
        self.assertIn("blockers", st)
        self.assertTrue(len(st["blockers"]) > 0)

        # case-insensitive agent-status
        ast = self.invoke("agent-status", agent, status="working")
        self.assertEqual(ast["agent"]["status"], "WORKING")

        # Explicitly passing empty string or non-string to text_content must fail even when default exists
        assignment = self.invoke("assignment-add", agent, title="Task 1")["assignment"]
        self.invoke("claim", agent, assignment_id=assignment["id"])
        with self.assertRaises(CollabError) as caught_empty:
            self.invoke("progress", agent, assignment_id=assignment["id"], percent=20, content="   ")
        self.assertEqual(caught_empty.exception.code, "INVALID_INPUT")

        with self.assertRaises(CollabError) as caught_type:
            self.invoke("progress", agent, assignment_id=assignment["id"], percent=20, status_message=12345)
        self.assertEqual(caught_type.exception.code, "INVALID_INPUT")


if __name__ == "__main__":
    unittest.main()
