"""Cross-IDE protocol regressions. All identities here are simulated clients."""
import copy
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/collab/scripts"))
from collablib.engine import execute
from collablib.identity import host_metadata
from collablib.storage import CollabError, Store


class CrossIDETests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="collab cross ide ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.env = mock.patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def call(self, command, agent=None, **data):
        auth = {} if agent is None else {"agent_id": agent["agent"]["id"], "token": agent["token"], "task_id": agent["task"]["id"]}
        return execute(self.root, command, {**auth, **data})

    def join(self, platform="codex", **data):
        return self.call("start", name=platform, platform=platform, session_id=str(uuid.uuid4()),
                         objective="Build the calculator", **data)

    def work(self, a):
        item = self.call("assignment-add", a, title="Implement or verify calculator")["assignment"]
        self.call("claim", a, assignment_id=item["id"])
        return self.call("work-complete", a, assignment_id=item["id"], result="Checked arithmetic", evidence=["2 + 2 = 4"])

    def review(self, a, b):
        revision = self.call("propose", a, content="Calculator works")["revision"]
        self.call("review", b, verdict="APPROVE", evidence=["Independently checked arithmetic"])
        for member in (a, b):
            self.call("approve", member)
        return revision

    def error(self, code, command, agent=None, **data):
        with self.assertRaises(CollabError) as caught:
            self.call(command, agent, **data)
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_codex_alone_and_second_codex_cannot_satisfy_required_antigravity(self):
        a = self.join(expected_platforms=["Codex Desktop", "Google Antigravity"], min_distinct_platforms=2)
        self.work(a)
        self.assertIn("Missing required IDE: antigravity", self.call("status", a)["blockers"])
        b = self.join("OpenAI Codex", task_id=a["task"]["id"])
        self.work(b)
        self.review(a, b)
        failure = self.error("NOT_READY", "finalize", a)
        self.assertIn("Missing required IDE: antigravity", failure.details["blockers"])
        self.assertTrue(any("need 2, have 1" in x for x in failure.details["blockers"]))
        self.assertFalse((self.root / ".collab/FINAL_REPORT.md").exists())

    def test_minimum_distinct_platforms_excludes_unknown_and_aliases(self):
        a = self.join(min_distinct_platforms=2)
        b = self.join("codex-desktop")
        unknown = self.join("made-up-ide")
        for member in (a, b, unknown):
            self.work(member)
        self.review(a, b)
        self.call("approve", unknown)
        self.error("NOT_READY", "finalize", a)
        c = self.join("antigravity")
        self.assertFalse(c["observer"])
        self.work(c)
        self.review(a, c)
        for member in (b, unknown):
            self.call("approve", member)
        self.assertEqual(self.call("finalize", a)["task"]["status"], "TEAM_COMPLETE")

    def test_late_required_ide_invalidates_approvals_and_must_submit_result(self):
        a = self.join(expected_platforms=["codex", "antigravity"])
        b = self.join("codex")
        for member in (a, b):
            self.work(member)
        revision = self.review(a, b)
        c = self.join("antigravity", task_id=a["task"]["id"])
        self.assertFalse(c["observer"])
        self.assertEqual(c["task"]["status"], "WORKING")
        self.assertFalse(c["task"]["decision"]["valid"])
        self.assertEqual(c["task"]["approvals"], {})
        self.error("STALE_REVISION", "finalize", a, revision=revision)
        self.review(a, b)
        missing = self.error("NOT_READY", "finalize", a).details["blockers"]
        self.assertTrue(any("Missing participant result" in x and "antigravity" in x for x in missing))
        self.assertTrue(any("Missing current approval" in x and "antigravity" in x for x in missing))
        self.call("participant-result", c, content="Verified independently")
        self.review(a, c)
        self.error("NOT_READY", "finalize", a)  # Codex B must reapprove too.
        self.call("approve", b)
        self.assertEqual(self.call("finalize", a)["task"]["status"], "TEAM_COMPLETE")

    def test_existing_expected_platform_late_agent_is_still_required(self):
        a = self.join(expected_platforms=["codex", "antigravity"])
        b = self.join("antigravity")
        for member in (a, b):
            self.work(member)
        self.review(a, b)
        c = self.join("antigravity")
        self.assertFalse(c["observer"])
        self.error("STALE_REVISION", "finalize", a)

    def test_requirements_strengthen_existing_task_and_cannot_be_weakened(self):
        a = self.join()
        b = self.join("codex")
        for member in (a, b):
            self.work(member)
        self.review(a, b)
        c = self.join("antigravity", expected_platforms=["codex", "antigravity"], min_distinct_platforms=2)
        self.assertEqual(a["task"]["id"], c["task"]["id"])
        d = self.join("codex", expected_platforms=[], min_distinct_platforms=0, new_task=True)
        self.assertEqual(d["task"]["team_requirements"], c["task"]["team_requirements"])
        self.assertEqual(len(self.call("status")["tasks"]), 1)

    def test_unfinished_assignment_and_missing_review_and_approval_block(self):
        a = self.join(expected_platforms=["codex", "antigravity"])
        b = self.join("antigravity")
        item = self.call("assignment-add", a, title="Unfinished")["assignment"]
        for member in (a, b):
            self.call("participant-result", member, content="Partial findings")
        self.call("propose", a, content="Premature")
        blockers = self.error("NOT_READY", "finalize", a).details["blockers"]
        for text in ("Incomplete assignment", "independent review", "Missing current approval"):
            self.assertTrue(any(text in x for x in blockers), blockers)
        self.assertEqual(self.call("status", a)["teamwork"]["remaining_assignments"][0]["id"], item["id"])

    def test_finished_agent_gets_help_and_pending_checkpoint(self):
        a = self.join(expected_platforms=["codex", "antigravity"])
        b = self.join("antigravity")
        help_item = self.call("help-request", b, content="Need arithmetic verification")["help"]
        completed = self.work(a)
        self.assertEqual(completed["teamwork"]["help_requests"][0]["id"], help_item["id"])
        self.call("help-respond", a, help_id=help_item["id"], content="Here are the checked examples")
        self.call("help-resolve", b, help_id=help_item["id"], content="Confirmed")
        self.call("agent-status", b, status="OFFLINE")
        self.call("checkpoint", a, content="Waiting for Antigravity result and approval", pending=True)
        status = self.call("status", a)
        self.assertEqual(status["task"]["status"], "PENDING")
        self.assertEqual({x["availability"] for x in status["teamwork"]["unavailable_participants"]}, {"unavailable"})
        self.error("STALE_REVISION", "finalize", a)

    def test_exact_identity_preserved_in_state_events_and_report(self):
        with mock.patch.dict(os.environ, {"CODEX_THREAD_ID": "host-thread", "CODEX_APP_TOOLS_PIPE_PATH": "host-pipe",
                                         "COLLAB_HOST_MODEL": "gpt-6.1-sol-exact-variant", "COLLAB_HOST_REASONING_LEVEL": "xhigh"}):
            a = self.call("start", name="A", session_id="fresh", objective="Build the calculator")
        b = self.join("antigravity", model="Gemini Exact Preview Variant", reasoning_level="high", ide_name="Google Antigravity")
        self.assertEqual(a["agent"]["ide_name"], "Codex Desktop")
        self.assertEqual(a["agent"]["model"], "gpt-6.1-sol-exact-variant")
        for member in (a, b):
            self.work(member)
        self.review(a, b)
        result = self.call("finalize", a)
        report = (self.root / result["report"]).read_text(encoding="utf-8")
        for value in ("gpt-6.1-sol-exact-variant", "Gemini Exact Preview Variant", "xhigh"):
            self.assertIn(value, report)
            self.assertIn(value, json.dumps(self.call("read")))
        self.error("IDENTITY_MISMATCH", "start", name="renamed", session_id="fresh", token=a["token"], model="shortened")

    def test_missing_or_ambiguous_host_metadata_is_unknown(self):
        self.assertEqual(set(host_metadata({}).values()), {"unknown"})
        self.assertEqual(host_metadata({"CODEX_HOME": "/installed"})["platform"], "unknown")
        self.assertEqual(host_metadata({"CODEX_THREAD_ID": "x", "ANTIGRAVITY_APP": "1"})["platform"], "unknown")
        a = self.join("unknown")
        for field in ("model", "reasoning_level", "ide_name"):
            self.assertEqual(a["agent"][field], "unknown")

    def test_unknown_identity_defaults_use_current_host_but_not_other_host_model(self):
        with mock.patch.dict(os.environ, {"CODEX_THREAD_ID": "thread", "COLLAB_HOST_MODEL": "exact-sol-variant",
                                         "COLLAB_HOST_REASONING_LEVEL": "high"}):
            a = self.join("unknown", model="unknown")
            b = self.join("antigravity")
        self.assertEqual(a["agent"]["platform_key"], "codex")
        self.assertEqual(a["agent"]["model"], "exact-sol-variant")
        self.assertEqual(a["agent"]["identity_source"]["model"], "host")
        resumed = self.call("start", session_id=a["agent"]["session_id"], token=a["token"],
                            task_id=a["task"]["id"], platform="unknown", model="unknown")
        self.assertEqual(resumed["agent"]["model"], "exact-sol-variant")
        self.assertEqual(b["agent"]["model"], "unknown")
        self.assertEqual(b["agent"]["ide_name"], "unknown")

    def test_existing_observer_can_resume_as_explicitly_required(self):
        a, b = self.join(), self.join("codex")
        for member in (a, b):
            self.work(member)
        self.review(a, b)
        observer = self.join("cursor")
        self.assertTrue(observer["observer"])
        promoted = self.call("start", session_id=observer["agent"]["session_id"], token=observer["token"],
                             task_id=a["task"]["id"], required=True)
        self.assertFalse(promoted["observer"])
        self.error("STALE_REVISION", "finalize", a)

    def test_unavailable_required_participant_is_named_and_cannot_be_waived_by_alias(self):
        a = self.join(expected_platforms=["codex", "antigravity"])
        b = self.join("antigravity")
        self.work(a)
        self.call("participant-result", b, content="Independent result")
        self.call("propose", a, content="Ready")
        self.call("review", b, verdict="APPROVE", evidence=["Arithmetic checked"])
        self.call("approve", a)
        self.call("agent-status", b, status="PAUSED")
        blockers = self.error("NOT_READY", "finalize", a).details["blockers"]
        self.assertTrue(any("Required collaborator unavailable" in x and "antigravity" in x for x in blockers))

    def test_operator_replacing_antigravity_with_codex_does_not_waive_platform_gate(self):
        from collab_operator import membership_change
        a = self.join(expected_platforms=["codex", "antigravity"])
        b = self.join("antigravity")
        with Store(self.root) as store:
            state, _ = membership_change(store.state, a["task"]["id"], b["agent"]["id"], a["agent"]["id"], "User recovery fixture")
            store.commit(state, {"type": "DECISION", "content": "Simulated operator recovery"})
        self.assertIn("Missing required IDE: antigravity", self.call("status", a)["blockers"])

    def test_root_copy_rejected_for_reads_and_writes_without_history_changes(self):
        a = self.join()
        other = self.root / "different project"
        other.mkdir()
        shutil.copytree(self.root / ".collab", other / ".collab")
        before = (other / ".collab/GROUP_CHAT.jsonl").read_bytes()
        for command in ("status", "read", "start", "check"):
            with self.assertRaises(CollabError) as caught:
                execute(other, command, {"task_id": a["task"]["id"]})
            self.assertEqual(caught.exception.code, "ROOT_MISMATCH")
        self.assertEqual((other / ".collab/GROUP_CHAT.jsonl").read_bytes(), before)

    def test_different_empty_root_does_not_create_requested_task_identity(self):
        a = self.join()
        other = self.root / "empty project"
        other.mkdir()
        with self.assertRaises(CollabError) as caught:
            execute(other, "start", {"name": "B", "session_id": "b", "task_id": a["task"]["id"]})
        self.assertEqual(caught.exception.code, "TASK_NOT_FOUND")
        self.assertEqual(execute(other, "status", {})["tasks"], [])

    def test_legacy_schema_migrates_without_rewriting_history(self):
        a = self.join()
        with Store(self.root) as store:
            legacy = copy.deepcopy(store.state)
            for field in ("project_root", "schema_version"):
                legacy["config"].pop(field, None)
            for task in legacy["tasks"].values():
                task.pop("project_root")
                task.pop("team_requirements")
            for agent in legacy["agents"].values():
                for field in ("platform_key", "ide_name", "reasoning_level", "identity_source"):
                    agent.pop(field)
            store.commit(legacy, {"type": "STATUS", "content": "Legacy fixture"})
        before = (self.root / ".collab/GROUP_CHAT.jsonl").read_bytes()
        self.call("status", a)
        self.assertEqual((self.root / ".collab/GROUP_CHAT.jsonl").read_bytes(), before)
        self.call("send", a, content="Migrated safely")
        self.assertTrue((self.root / ".collab/GROUP_CHAT.jsonl").read_bytes().startswith(before))
        with Store(self.root) as store:
            self.assertEqual(store.state["config"]["schema_version"], 2)
            self.assertEqual(store.state["agents"][a["agent"]["id"]]["reasoning_level"], "unknown")

    def test_cross_ide_start_requires_explicit_root_but_legacy_cli_remains_valid(self):
        with self.assertRaises(CollabError) as caught:
            execute(self.root, "start", {"name": "A", "session_id": "a", "objective": "x",
                                        "expected_platforms": ["codex", "antigravity"]}, explicit_root=False)
        self.assertEqual(caught.exception.code, "ROOT_REQUIRED")
        self.assertEqual(self.call("status")["tasks"], [])


if __name__ == "__main__":
    unittest.main()
