"""Regression tests verifying parameter compatibility between commands.md and engine.py.

Tests parameter aliases and combinations including:
- criteria / acceptance_criteria
- artifacts / required_artifacts
- content / summary / status_message / description / solution / resolution / detail / result
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
        """Verify start accepts acceptance_criteria and required_artifacts aliases."""
        target_file = self.root / "output.txt"
        target_file.write_text("initial output", encoding="utf-8")

        agent = self.invoke(
            "start",
            name="Alice",
            session_id="alice-sess-001",
            objective="Test parameter aliases",
            acceptance_criteria=["Must pass unit tests", "Must produce output.txt"],
            required_artifacts=["output.txt"],
            independent_reviews=1,
        )

        task = agent["task"]
        self.assertEqual(task["criteria"], ["Must pass unit tests", "Must produce output.txt"])
        self.assertEqual(task["acceptance_criteria"], ["Must pass unit tests", "Must produce output.txt"])
        self.assertIn("output.txt", task["required_artifacts"])

    def test_checkpoint_accepts_summary_and_active_file(self):
        """Verify checkpoint accepts summary and active_file aliases."""
        agent = self.invoke("start", name="Bob", session_id="bob-sess-001", objective="Checkpoint test")
        res = self.invoke("checkpoint", agent, summary="Refactored parser module", active_file="src/parser.py")

        self.assertEqual(res["checkpoint"]["content"], "Refactored parser module")
        self.assertEqual(res["checkpoint"]["active_file"], "src/parser.py")

    def test_assignment_and_progress_parameter_aliases(self):
        """Verify assignment-add description and progress status_message."""
        agent = self.invoke("start", name="Charlie", session_id="charlie-sess-001", objective="Work flow")
        
        # assignment-add with description
        created = self.invoke("assignment-add", agent, title="Code Review", description="Review all PRs")
        assignment = created["assignment"]
        self.assertEqual(assignment["title"], "Code Review")
        self.assertEqual(assignment["description"], "Review all PRs")

        # claim
        self.invoke("claim", agent, assignment_id=assignment["id"])

        # progress with status_message
        prog = self.invoke("progress", agent, assignment_id=assignment["id"], percent=50, status_message="Halfway done")
        self.assertEqual(prog["assignment"]["percent"], 50)

        # work-complete using content instead of result
        comp = self.invoke("work-complete", agent, assignment_id=assignment["id"], content="All reviews done", evidence=["ok"])
        self.assertEqual(comp["assignment"]["result"], "All reviews done")
        self.assertEqual(comp["assignment"]["status"], "WORK_COMPLETE")

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

    def test_propose_and_finalize_without_explicit_revision(self):
        """Verify propose with summary and artifacts, and finalize defaulting to active revision."""
        a = self.invoke("start", name="Lead", session_id="lead-sess", objective="Proposal flow")
        b = self.invoke("start", name="Reviewer", session_id="rev-sess", task_id=a["task"]["id"])

        assignment = self.invoke("assignment-add", a, title="Feature")["assignment"]
        self.invoke("claim", a, assignment_id=assignment["id"])
        self.invoke("work-complete", a, assignment_id=assignment["id"], result="Feature complete", evidence=["tests pass"])
        self.invoke("participant-result", b, result="Peer verification complete", evidence=["reproduced"])

        # propose with summary
        prop = self.invoke("propose", a, summary="Ready for team verification", limitations=["Local test only"])
        revision = prop["revision"]
        self.assertEqual(revision, 1)

        # review with critique
        rev = self.invoke("review", b, revision=revision, verdict="APPROVE", critique="LGTM with evidence", evidence=["verified output"])
        self.assertEqual(rev["review"]["verdict"], "APPROVE")

        # approve with approval
        app_a = self.invoke("approve", a, revision=revision, approval="Signed off by lead")
        app_b = self.invoke("approve", b, revision=revision, approval="Signed off by reviewer")

        # finalize without explicit revision parameter (should default to active revision)
        fin = self.invoke("finalize", a)
        self.assertEqual(fin["task"]["status"], "TEAM_COMPLETE")


if __name__ == "__main__":
    unittest.main()
