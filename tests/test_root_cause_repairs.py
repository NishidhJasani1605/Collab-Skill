"""Comprehensive regression test suite for COLLAB root-cause repairs.

Covers all 16 core requirements:
1. Two independent processes joining the same workspace.
2. Concurrent initialization without duplicate tasks.
3. Preventing nested .collab split-brain states (NESTED_WORKSPACE_CONFLICT & migrate-nested).
4. Rejecting a fake second agent in non-simulated mode (DUPLICATE_SESSION).
5. Rejecting self-review and impersonated approvals.
6. Waiting correctly for an absent collaborator ("Waiting for Google Antigravity").
7. Incorporating a late required collaborator (invalidating previous approvals).
8. Real bidirectional message exchange.
9. Independent task ownership and cross-review.
10. Rejecting premature finalization.
11. Invalidating approvals after code changes.
12. Both agents verifying the same revision.
13. Concurrent writes and message-log integrity.
14. Windows path handling and process restarts.
15. Existing-state migration and backward compatibility.
16. Exact available IDE/model metadata preservation.

Plus Section 7: Complete Calculator Collaboration scenario.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import uuid

import test_integration as integration

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "collab" / "scripts"))
from collablib.engine import execute, load_state, fresh_state, readiness
from collablib.storage import Store, canonical_root, migrate_nested_collab, CollabError


HELPER = integration.HELPER


class RootCauseRepairsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="collab-repairs-")
        self.addCleanup(self.temporary.cleanup)
        self.project = (Path(self.temporary.name) / "shared project").resolve()
        self.project.mkdir()
        self.environment = dict(os.environ, PYTHONUTF8="1")
        for key in list(self.environment):
            if any(key.startswith(p) for p in ("ANTIGRAVITY_", "CODEX_", "CURSOR_", "CLAUDE_", "COLLAB_HOST_", "COLLAB_SIMULATION", "PYTEST_CURRENT_TEST")):
                self.environment.pop(key, None)

    def cli(self, command, data, *, succeeds=True, env=None, project=None):
        target_root = str(project or self.project)
        run_env = self.environment if env is None else env
        completed = subprocess.run(
            [sys.executable, str(HELPER), "--root", target_root, command,
             "--data", json.dumps(data, ensure_ascii=False)],
            capture_output=True, text=True, encoding="utf-8",
            env=run_env, timeout=120,
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
        return response

    def start(self, name, platform="independent-process-test", env=None, project=None, **extra):
        data = {
            "name": name,
            "platform": platform,
            "model": "gpt-4o",
            "session_id": str(uuid.uuid4()),
            "objective": "Verify collaboration repairs",
        }
        data.update(extra)
        res = self.cli("start", data, env=env, project=project)
        return {"agent_id": res["agent"]["id"], "token": res["token"],
                "task_id": res["task"]["id"]}, res

    # 1. Two independent processes joining the same workspace
    def test_01_two_independent_processes_join_same_workspace(self):
        client_a, resp_a = self.start("Agent A", platform="codex")
        client_b, resp_b = self.start("Agent B", platform="antigravity")

        self.assertEqual(client_a["task_id"], client_b["task_id"])
        self.assertNotEqual(client_a["agent_id"], client_b["agent_id"])
        self.assertNotEqual(client_a["token"], client_b["token"])

        state_file = self.project / ".collab" / "checkpoints" / "state.json"
        self.assertTrue(state_file.exists())
        checkpoint = json.loads(state_file.read_text(encoding="utf-8"))
        self.assertIn("state", checkpoint)
        state = checkpoint["state"]
        self.assertIn(client_a["agent_id"], state["agents"])
        self.assertIn(client_b["agent_id"], state["agents"])

    # 2. Concurrent initialization without duplicate tasks
    def test_02_concurrent_initialization_without_duplicate_tasks(self):
        barrier_dir = Path(self.temporary.name) / "barrier"
        barrier_dir.mkdir()
        ready_a = barrier_dir / "ready_a"
        ready_b = barrier_dir / "ready_b"
        go = barrier_dir / "go"

        script = (
            "import os, sys, time, json, subprocess\n"
            "ready, go, root, name = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]\n"
            "with open(ready, 'w') as f: f.write('1')\n"
            "while not os.path.exists(go): time.sleep(0.01)\n"
            "data = json.dumps({'name': name, 'platform': 'test', 'objective': 'Same objective', 'session_id': name})\n"
            "p = subprocess.run([sys.executable, sys.argv[5], '--root', root, 'start', '--data', data], capture_output=True, text=True)\n"
            "print(p.stdout)\n"
        )
        runner = Path(self.temporary.name) / "run_concurrent.py"
        runner.write_text(script, encoding="utf-8")

        p1 = subprocess.Popen([sys.executable, str(runner), str(ready_a), str(go), str(self.project), "Agent1", str(HELPER)],
                              stdout=subprocess.PIPE, text=True)
        p2 = subprocess.Popen([sys.executable, str(runner), str(ready_b), str(go), str(self.project), "Agent2", str(HELPER)],
                              stdout=subprocess.PIPE, text=True)

        for _ in range(200):
            if ready_a.exists() and ready_b.exists():
                break
            time.sleep(0.05)
        go.write_text("1")

        out1, _ = p1.communicate(timeout=60)
        out2, _ = p2.communicate(timeout=60)

        res1 = json.loads(out1.strip())
        res2 = json.loads(out2.strip())
        self.assertTrue(res1["ok"])
        self.assertTrue(res2["ok"])
        self.assertEqual(res1["task"]["id"], res2["task"]["id"])

    # 3. Preventing nested .collab split-brain states (NESTED_WORKSPACE_CONFLICT & migrate-nested)
    def test_03_prevent_nested_collab_and_migrate(self):
        # Start in project root
        client_a, _ = self.start("Root Agent")

        # Create a valid, inactive nested runtime. Corrupt or active runtimes
        # must now be preserved and refused (covered in test_session_safety).
        sub = self.project / "calculator-test"
        sub.mkdir()
        sub_collab = sub / ".collab"
        with Store(sub, validate_ancestors=False):
            pass

        # Accessing root or sub with existing conflicting state raises NESTED_WORKSPACE_CONFLICT
        resp = self.cli("status", {"task_id": client_a["task_id"]}, succeeds=False)
        self.assertEqual(resp["error"]["code"], "NESTED_WORKSPACE_CONFLICT")

        # Migrate nested collab
        mig_resp = self.cli("migrate-nested", {"nested_path": str(sub_collab)})
        self.assertTrue(mig_resp["ok"])
        self.assertTrue((sub_collab / "retired.json").is_file())
        archived = self.project / ".collab" / "archived_nested"
        self.assertTrue(archived.exists())

        # Now root access works normally
        status_resp = self.cli("status", {"task_id": client_a["task_id"]})
        self.assertTrue(status_resp["ok"])

        # Also verify that starting in a subfolder when parent has .collab automatically binds to parent
        sub2 = self.project / "new-subfolder"
        sub2.mkdir()
        client_sub, resp_sub = self.start("Sub Agent", project=sub2)
        self.assertEqual(client_sub["task_id"], client_a["task_id"])
        self.assertFalse((sub2 / ".collab").exists())

    # 4. Rejecting a fake second agent in non-simulated mode (DUPLICATE_SESSION)
    def test_04_reject_duplicate_host_session_in_real_mode(self):
        env = dict(self.environment, CODEX_THREAD_ID="codex-real-thread-123")
        # Remove any test simulation indicators
        env.pop("COLLAB_SIMULATION", None)
        env.pop("PYTEST_CURRENT_TEST", None)

        client_a, resp_a = self.start("CodexAgent1", platform="codex", env=env)
        self.assertEqual(resp_a["agent"]["platform_key"], "codex")

        # Second agent starting in the same task from the same host session must be rejected
        data_b = {
            "name": "FakeAntigravity",
            "platform": "antigravity",
            "task_id": client_a["task_id"],
            "session_id": str(uuid.uuid4()),
        }
        resp_b = self.cli("start", data_b, succeeds=False, env=env)
        self.assertEqual(resp_b["error"]["code"], "DUPLICATE_SESSION")

    # 5. Rejecting self-review and impersonated approvals
    def test_05_reject_self_review_and_impersonated_approval(self):
        client_a, _ = self.start("Agent A", platform="codex")
        client_b, _ = self.start("Agent B", platform="antigravity", task_id=client_a["task_id"])

        asg = self.cli("assignment-add", dict(client_a, title="Work A", required=True))["assignment"]
        self.cli("claim", dict(client_a, assignment_id=asg["id"]))
        self.cli("work-complete", dict(client_a, assignment_id=asg["id"], result="done", evidence=["e1"]))

        prop = self.cli("propose", dict(client_a, content="Proposal 1"))["revision"]

        # Agent A attempts self-review
        rev = self.cli("review", dict(client_a, verdict="APPROVE", evidence=["Self checked"]))
        self.assertTrue(rev["review"]["self_review"])

        status = self.cli("status", dict(client_a))
        self.assertIn("Missing evidence-backed independent review", status["blockers"])

        # Agent A attempts to approve using Agent B's ID with Agent A's token
        impersonate_data = dict(client_a, agent_id=client_b["agent_id"])
        resp = self.cli("approve", impersonate_data, succeeds=False)
        self.assertEqual(resp["error"]["code"], "AUTH_REQUIRED")

    # 6. Waiting correctly for an absent collaborator
    def test_06_waiting_for_absent_collaborator(self):
        client_a, _ = self.start(
            "Codex Alone", platform="codex",
            expected_platforms=["codex", "antigravity"],
            min_distinct_platforms=2
        )
        asg = self.cli("assignment-add", dict(client_a, title="Work", required=True))["assignment"]
        self.cli("claim", dict(client_a, assignment_id=asg["id"]))
        self.cli("work-complete", dict(client_a, assignment_id=asg["id"], result="done", evidence=["e"]))

        status = self.cli("status", dict(client_a))
        self.assertIn("Waiting for Google Antigravity", status["blockers"])
        self.assertIn("Missing required IDE: antigravity", status["blockers"])

        self.cli("propose", dict(client_a, content="Proposal"))
        fin = self.cli("finalize", dict(client_a), succeeds=False)
        self.assertEqual(fin["error"]["code"], "NOT_READY")
        self.assertIn("Waiting for Google Antigravity", fin["error"]["details"]["blockers"])

    # 7. Incorporating a late required collaborator (invalidating previous approvals)
    def test_07_late_collaborator_invalidates_approvals(self):
        client_a, _ = self.start("Agent A", platform="codex", expected_platforms=["codex", "antigravity"])
        client_b, _ = self.start("Agent B", platform="codex", task_id=client_a["task_id"])

        for c in (client_a, client_b):
            asg = self.cli("assignment-add", dict(c, title="Task " + c["agent_id"], required=True))["assignment"]
            self.cli("claim", dict(c, assignment_id=asg["id"]))
            self.cli("work-complete", dict(c, assignment_id=asg["id"], result="done", evidence=["e"]))

        prop = self.cli("propose", dict(client_a, content="Rev 1"))["revision"]
        self.cli("review", dict(client_b, verdict="APPROVE", evidence=["checked"]))
        for c in (client_a, client_b):
            self.cli("approve", dict(c))

        # Late Antigravity collaborator joins
        client_c, resp_c = self.start("Agent C", platform="antigravity", task_id=client_a["task_id"])
        self.assertEqual(resp_c["task"]["status"], "WORKING")
        self.assertFalse(resp_c["task"]["decision"]["valid"])
        self.assertEqual(resp_c["task"]["approvals"], {})

    # 8. Real bidirectional message exchange
    def test_08_bidirectional_message_exchange(self):
        client_a, _ = self.start("Agent A")
        client_b, _ = self.start("Agent B", task_id=client_a["task_id"])

        q = self.cli("send", dict(client_a, type="QUESTION", content="What is 2+2?"))
        read_b = self.cli("read", dict(client_b, after=0))
        questions = [e for e in read_b["events"] if e["type"] == "QUESTION"]
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]["content"], "What is 2+2?")

        self.cli("send", dict(client_b, type="REPLY", reply_to=questions[0]["id"], content="2+2 is 4"))
        read_a = self.cli("read", dict(client_a, after=read_b["cursor"]))
        replies = [e for e in read_a["events"] if e["type"] == "REPLY"]
        self.assertEqual(len(replies), 1)
        self.assertEqual(replies[0]["content"], "2+2 is 4")
        self.assertEqual(replies[0]["reply_to"], questions[0]["id"])

        chat_md = (self.project / ".collab" / "GROUP_CHAT.md").read_text(encoding="utf-8")
        self.assertIn("What is 2+2?", chat_md)
        self.assertIn("2+2 is 4", chat_md)

    # 9. Independent task ownership and cross-review
    def test_09_independent_task_ownership_and_cross_review(self):
        client_a, _ = self.start("Agent A", platform="codex")
        client_b, _ = self.start("Agent B", platform="antigravity", task_id=client_a["task_id"])

        # Agent A creates two assignments and completes both alone
        asg1 = self.cli("assignment-add", dict(client_a, title="Implement logic", required=True))["assignment"]
        asg2 = self.cli("assignment-add", dict(client_a, title="Write tests", required=True))["assignment"]
        self.cli("claim", dict(client_a, assignment_id=asg1["id"]))
        self.cli("work-complete", dict(client_a, assignment_id=asg1["id"], result="done", evidence=["e1"]))
        self.cli("claim", dict(client_a, assignment_id=asg2["id"]))
        self.cli("work-complete", dict(client_a, assignment_id=asg2["id"], result="done", evidence=["e2"]))

        self.cli("propose", dict(client_a, content="Done alone"))
        self.cli("review", dict(client_b, verdict="APPROVE", evidence=["looks good"]))
        self.cli("approve", dict(client_a))
        self.cli("approve", dict(client_b))

        status = self.cli("status", dict(client_a))
        self.assertIn("Work must be divided between participants; assignments owned by only one agent", status["blockers"])
        fin = self.cli("finalize", dict(client_a), succeeds=False)
        self.assertIn("Work must be divided between participants; assignments owned by only one agent", fin["error"]["details"]["blockers"])

        # Agent B claims and completes an assignment and submits participant result to establish genuine contribution
        asg3 = self.cli("assignment-add", dict(client_b, title="Independent verification", required=True))["assignment"]
        self.cli("claim", dict(client_b, assignment_id=asg3["id"]))
        self.cli("work-complete", dict(client_b, assignment_id=asg3["id"], result="verified", evidence=["all tests pass"]))
        self.cli("participant-result", dict(client_b, content="Independently tested all operations"))
        prop2 = self.cli("propose", dict(client_a, content="Done together"))
        self.cli("review", dict(client_b, verdict="APPROVE", evidence=["verified together"]))
        self.cli("approve", dict(client_a))
        self.cli("approve", dict(client_b))

        status2 = self.cli("status", dict(client_a))
        self.assertNotIn("Work must be divided between participants; assignments owned by only one agent", status2["blockers"])

    # 10. Rejecting premature finalization
    def test_10_rejecting_premature_finalization(self):
        client_a, _ = self.start("Agent A", platform="codex")
        fin = self.cli("finalize", dict(client_a), succeeds=False)
        self.assertEqual(fin["error"]["code"], "STALE_REVISION")

        # Propose without completing required assignments
        asg = self.cli("assignment-add", dict(client_a, title="Incomplete", required=True))["assignment"]
        self.cli("propose", dict(client_a, content="Premature"))
        fin2 = self.cli("finalize", dict(client_a), succeeds=False)
        self.assertEqual(fin2["error"]["code"], "NOT_READY")
        self.assertTrue(any("Incomplete assignment" in b for b in fin2["error"]["details"]["blockers"]))

    # 11. Invalidating approvals after code changes
    def test_11_invalidating_approvals_after_code_changes(self):
        client_a, _ = self.start("Agent A", platform="codex")
        client_b, _ = self.start("Agent B", platform="antigravity", task_id=client_a["task_id"])

        code_file = self.project / "code.py"
        code_file.write_text("print('version 1')", encoding="utf-8")

        asg = self.cli("assignment-add", dict(client_a, title="Coding", required=True))["assignment"]
        self.cli("claim", dict(client_a, assignment_id=asg["id"]))
        self.cli("work-complete", dict(client_a, assignment_id=asg["id"], result="done", evidence=["e"]))
        self.cli("participant-result", dict(client_b, content="verified"))

        prop = self.cli("propose", dict(client_a, content="Rev with file", files=["code.py"]))["revision"]
        self.cli("review", dict(client_b, verdict="APPROVE", evidence=["checked"]))
        self.cli("approve", dict(client_a))
        self.cli("approve", dict(client_b))

        # Code file changes after approval
        code_file.write_text("print('tampered version')", encoding="utf-8")

        status = self.cli("status", dict(client_a))
        self.assertIn("Final revision changed after approval", status["blockers"])
        fin = self.cli("finalize", dict(client_a), succeeds=False)
        self.assertEqual(fin["error"]["code"], "RESULT_CHANGED")

    # 12. Both agents verifying the same revision
    def test_12_both_agents_verify_same_revision(self):
        client_a, _ = self.start("Agent A", platform="codex")
        client_b, _ = self.start("Agent B", platform="antigravity", task_id=client_a["task_id"])

        code_file = self.project / "calc.py"
        code_file.write_text("def add(a, b): return a + b\n", encoding="utf-8")

        asg_a = self.cli("assignment-add", dict(client_a, title="Implement calc", required=True))["assignment"]
        self.cli("claim", dict(client_a, assignment_id=asg_a["id"]))
        self.cli("work-complete", dict(client_a, assignment_id=asg_a["id"], result="done", evidence=["e1"]))

        asg_b = self.cli("assignment-add", dict(client_b, title="Verify calc", required=True))["assignment"]
        self.cli("claim", dict(client_b, assignment_id=asg_b["id"]))
        self.cli("work-complete", dict(client_b, assignment_id=asg_b["id"], result="verified", evidence=["e2"]))

        prop = self.cli("propose", dict(client_a, content="Rev 1", files=["calc.py"]))["revision"]
        self.cli("review", dict(client_b, verdict="APPROVE", evidence=["2+2=4 verified"]))
        self.cli("approve", dict(client_a))
        self.cli("approve", dict(client_b))

        fin = self.cli("finalize", dict(client_a))
        self.assertEqual(fin["task"]["status"], "TEAM_COMPLETE")
        report_file = self.project / ".collab" / "FINAL_REPORT.md"
        self.assertTrue(report_file.exists())
        report_text = report_file.read_text(encoding="utf-8")
        self.assertIn("calc.py", report_text)
        self.assertIn("Agent A", report_text)
        self.assertIn("Agent B", report_text)

    # 13. Concurrent writes and message-log integrity
    def test_13_concurrent_writes_and_message_log_integrity(self):
        client, _ = self.start("Writer Agent")
        barrier_dir = Path(self.temporary.name) / "msg_barrier"
        barrier_dir.mkdir()
        go = barrier_dir / "go"

        script = (
            "import os, sys, time, json, subprocess\n"
            "idx, go, root, tid, aid, token, helper = sys.argv[1:8]\n"
            "while not os.path.exists(go): time.sleep(0.005)\n"
            "for i in range(10):\n"
            "    data = json.dumps({'agent_id': aid, 'task_id': tid, 'token': token, 'type': 'STATUS', 'content': f'msg_{idx}_{i}'})\n"
            "    p = subprocess.run([sys.executable, helper, '--root', root, 'send', '--data', data], capture_output=True, text=True)\n"
        )
        writer_script = Path(self.temporary.name) / "run_writer.py"
        writer_script.write_text(script, encoding="utf-8")

        workers = []
        for i in range(4):
            w = subprocess.Popen([sys.executable, str(writer_script), str(i), str(go), str(self.project),
                                  client["task_id"], client["agent_id"], client["token"], str(HELPER)])
            workers.append(w)

        time.sleep(0.2)
        go.write_text("1")
        for w in workers:
            w.communicate(timeout=60)

        events_file = self.project / ".collab" / "GROUP_CHAT.jsonl"
        lines = [json.loads(line) for line in events_file.read_text(encoding="utf-8").splitlines()]
        seqs = [e["seq"] for e in lines]
        self.assertEqual(seqs, list(range(1, len(lines) + 1)), "Sequence numbers must be strictly sequential")

    # 14. Windows path handling and process restarts
    def test_14_windows_path_handling_and_process_restarts(self):
        p1 = canonical_root(self.project)
        # Vary casing and slashes
        mixed = str(self.project).lower().replace("/", "\\")
        p2 = canonical_root(mixed)
        self.assertEqual(p1, p2)

        client, _ = self.start("RestartAgent")
        # Resume with mixed path
        completed = subprocess.run(
            [sys.executable, str(HELPER), "--root", mixed, "status",
             "--data", json.dumps(dict(client))],
            capture_output=True, text=True, encoding="utf-8"
        )
        resp = json.loads(completed.stdout)
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["task"]["id"], client["task_id"])

    # 15. Existing-state migration and backward compatibility
    def test_15_legacy_state_migration(self):
        state = fresh_state()
        state["config"]["schema_version"] = 1
        state["agents"]["old_agent"] = {
            "id": "old_agent", "name": "Legacy", "platform": "codex",
            "model": "gpt-4", "session_id": "sess-1",
            "token_hash": "dummy", "joined_at": "2025-01-01T00:00:00Z",
            "last_activity": "2025-01-01T00:00:00Z", "last_seen_epoch": time.time(),
            "current_task": None, "current_assignment": None, "status": "JOINED"
        }
        migrated = load_state(self.project, state)
        self.assertEqual(migrated["config"]["schema_version"], 2)
        agent = migrated["agents"]["old_agent"]
        self.assertEqual(agent["platform_key"], "codex")
        self.assertEqual(agent["ide_name"], "unknown")
        self.assertEqual(agent["identity_source"]["platform"], "legacy")

    # 16. Exact available IDE/model metadata preservation
    def test_16_exact_host_metadata_preservation(self):
        env = dict(self.environment,
                   ANTIGRAVITY_AGENT="antigravity-worker-1",
                   ANTIGRAVITY_CONVERSATION_ID="antigravity-thread-abc",
                   COLLAB_HOST_MODEL="gemini-2.5-pro",
                   COLLAB_HOST_REASONING_LEVEL="maximum")
        client, resp = self.start("AntigravityAgent", platform="antigravity", env=env, model="unknown")
        agent = resp["agent"]
        self.assertEqual(agent["platform_key"], "antigravity")
        self.assertEqual(agent["model"], "gemini-2.5-pro")
        self.assertEqual(agent["reasoning_level"], "maximum")
        self.assertEqual(agent["ide_name"], "Google Antigravity")
        self.assertEqual(agent["identity_source"]["model"], "host")

    # Section 7: Complete Calculator Collaboration scenario
    def test_17_calculator_cross_ide_collaboration_scenario(self):
        """Simulates full Agent A (Codex) and Agent B (Antigravity) collaboration on calculator.

        Verifies:
        - Exactly one .collab at project root.
        - No .collab inside calculator-test/.
        - Genuine division of assignments.
        - Bidirectional communication.
        - Passing check execution.
        - Mutual independent review and approval.
        - Single FINAL_REPORT.md.
        """
        # Step 1: Agent A (Codex Desktop) starts task at project root
        client_a, resp_a = self.start(
            "Codex", platform="codex",
            objective="Build and verify calculator in calculator-test",
            expected_platforms=["codex", "antigravity"],
            min_distinct_platforms=2,
            checks=[{"name": "test-suite", "argv": [sys.executable, "-m", "unittest", "discover", "-s", "calculator-test", "-p", "test_*.py"]}]
        )
        task_id = client_a["task_id"]

        # Step 2: Agent B (Google Antigravity) joins existing task
        client_b, resp_b = self.start(
            "Antigravity", platform="antigravity",
            task_id=task_id
        )

        # Step 3: Agent A creates calculator-test directory and implementation
        calc_dir = self.project / "calculator-test"
        calc_dir.mkdir()
        calc_file = calc_dir / "calculator.py"
        calc_file.write_text(
            "def add(a, b): return a + b\n"
            "def subtract(a, b): return a - b\n"
            "def multiply(a, b): return a * b\n"
            "def divide(a, b):\n"
            "    if b == 0: raise ValueError('Cannot divide by zero')\n"
            "    return a / b\n",
            encoding="utf-8"
        )

        # Step 4: Division of work - Two assignments
        asg_impl = self.cli("assignment-add", dict(client_a, title="Implement core calculator", required=True))["assignment"]
        asg_test = self.cli("assignment-add", dict(client_b, title="Write unit tests and verify", required=True))["assignment"]

        # Agent A claims and completes implementation assignment
        self.cli("claim", dict(client_a, assignment_id=asg_impl["id"]))
        self.cli("work-complete", dict(client_a, assignment_id=asg_impl["id"],
                                       result="Implemented basic arithmetic operations in calculator.py",
                                       evidence=["add, subtract, multiply, divide implemented"]))

        # Step 5: Bidirectional communication
        msg_a = self.cli("send", dict(client_a, type="STATUS", content="Calculator operations implemented; ready for testing."))
        read_b = self.cli("read", dict(client_b, after=0))
        self.assertTrue(any("Calculator operations implemented" in e["content"] for e in read_b["events"]))
        self.cli("send", dict(client_b, type="REPLY", reply_to=msg_a["event"]["id"], content="Received. Implementing test suite now."))
        self.cli("participant-result", dict(client_a, content="Implemented arithmetic logic in calculator.py"))
        self.cli("participant-result", dict(client_b, content="Implemented test suite and verified arithmetic logic"))

        # Step 6: Agent B implements tests
        test_file = calc_dir / "test_calculator.py"
        test_file.write_text(
            "import unittest\n"
            "import calculator\n\n"
            "class CalculatorTests(unittest.TestCase):\n"
            "    def test_add(self): self.assertEqual(calculator.add(2, 3), 5)\n"
            "    def test_subtract(self): self.assertEqual(calculator.subtract(5, 2), 3)\n"
            "    def test_multiply(self): self.assertEqual(calculator.multiply(4, 3), 12)\n"
            "    def test_divide(self): self.assertEqual(calculator.divide(10, 2), 5)\n"
            "    def test_divide_zero(self):\n"
            "        with self.assertRaises(ValueError): calculator.divide(1, 0)\n\n"
            "if __name__ == '__main__': unittest.main()\n",
            encoding="utf-8"
        )

        # Agent B claims and completes testing assignment
        self.cli("claim", dict(client_b, assignment_id=asg_test["id"]))
        self.cli("work-complete", dict(client_b, assignment_id=asg_test["id"],
                                       result="Implemented unit tests covering all operations and zero-division edge case",
                                       evidence=["5 unit tests passing"]))

        # Step 7: Proposal with files
        rel_files = ["calculator-test/calculator.py", "calculator-test/test_calculator.py"]
        prop = self.cli("propose", dict(client_a, content="Calculator implementation and test suite ready", files=rel_files))["revision"]

        # Step 8: Run check
        check_res = self.cli("check", dict(
            client_a,
            name="test-suite"
        ))
        self.assertEqual(check_res["check"]["returncode"], 0)

        # Section 7 verification: Prove that stopping one participant prevents finalization
        fin_premature = self.cli("finalize", dict(client_a), succeeds=False)
        self.assertEqual(fin_premature["error"]["code"], "NOT_READY")
        self.assertTrue(any("Antigravity verification pending" in b or "Missing Antigravity review" in b
                            for b in fin_premature["error"]["details"]["blockers"]))

        # Step 9: Mutual review and approval
        rev_b = self.cli("review", dict(client_b, verdict="APPROVE", evidence=["All unit tests ran and passed", "Code inspects cleanly"]))
        self.assertFalse(rev_b["review"]["self_review"])

        # Also prove stopping participant (PAUSED/unavailable) blocks finalization
        self.cli("agent-status", dict(client_b, status="PAUSED"))
        stat_paused = self.cli("status", dict(client_a))
        self.assertTrue(any("Required collaborator unavailable" in b for b in stat_paused["blockers"]))
        self.cli("agent-status", dict(client_b, status="JOINED"))

        self.cli("approve", dict(client_a))
        self.cli("approve", dict(client_b))

        # Step 10: Finalize
        fin = self.cli("finalize", dict(client_a))
        self.assertEqual(fin["task"]["status"], "TEAM_COMPLETE")

        # Step 11: Assertions on results
        root_collab = self.project / ".collab"
        self.assertTrue(root_collab.exists())
        self.assertTrue((root_collab / "FINAL_REPORT.md").exists())

        # CRITICAL: Verify NO split-brain .collab inside calculator-test
        self.assertFalse((calc_dir / ".collab").exists(), "Subfolder calculator-test MUST NOT have its own .collab directory!")

        # Verify final report content
        report = (root_collab / "FINAL_REPORT.md").read_text(encoding="utf-8")
        self.assertIn("calculator-test/calculator.py", report)
        self.assertIn("calculator-test/test_calculator.py", report)
        self.assertIn("Codex", report)
        self.assertIn("Antigravity", report)

    # 18. Direct Python execute() handles migrate-nested with and without existing root .collab
    def test_18_direct_execute_migrate_nested_handling(self):
        root = Path(self.temporary.name) / "direct_migrate_test"
        root.mkdir()
        sub = root / "nested_calc"
        sub.mkdir()
        with Store(sub):
            pass

        # Migrate before root .collab exists: must succeed and create archive without NOT_INITIALIZED error
        res1 = execute(root, "migrate-nested", {"nested_path": str(sub)})
        self.assertTrue(res1["ok"])
        self.assertTrue((sub / ".collab/retired.json").is_file())
        self.assertTrue((root / ".collab" / "archived_nested").exists())

        # Start task in root
        execute(root, "start", {"name": "A", "platform": "codex", "session_id": "s1", "objective": "obj", "simulated": True})

        # Create another nested collab while root has active state
        sub2 = root / "another_nested"
        sub2.mkdir()
        with Store(sub2, validate_ancestors=False):
            pass

        # Migrate while root has active state: must NOT trip on descendant validation
        res2 = execute(root, "migrate-nested", {"nested_path": str(sub2)})
        self.assertTrue(res2["ok"])
        self.assertTrue((sub2 / ".collab/retired.json").is_file())

    # 19. Vendor model and reasoning level environment variable extraction
    def test_19_vendor_model_and_reasoning_level_extraction(self):
        from collablib.identity import host_metadata

        # Antigravity vendor variables
        env_ag = {
            "ANTIGRAVITY_APP": "1",
            "ANTIGRAVITY_MODEL": "gemini-3.8-flash-high",
            "ANTIGRAVITY_REASONING_EFFORT": "high",
        }
        meta_ag = host_metadata(env_ag)
        self.assertEqual(meta_ag["platform"], "antigravity")
        self.assertEqual(meta_ag["model"], "gemini-3.8-flash-high")
        self.assertEqual(meta_ag["reasoning_level"], "high")

        # Codex vendor variables
        env_codex = {
            "CODEX_THREAD_ID": "thread_abc",
            "CODEX_MODEL": "gpt-4o-mini",
            "CODEX_REASONING_LEVEL": "medium",
        }
        meta_codex = host_metadata(env_codex)
        self.assertEqual(meta_codex["platform"], "codex")
        self.assertEqual(meta_codex["model"], "gpt-4o-mini")
        self.assertEqual(meta_codex["reasoning_level"], "medium")

    # 20. Store.__enter__ prevents nested .collab creation and leaves NO artifact on disk
    def test_20_store_enter_prevents_nested_collab_creation_on_disk(self):
        root = Path(self.temporary.name) / "nest_prevent_test"
        root.mkdir()
        # Initialize ancestor .collab
        execute(root, "start", {"name": "Root", "platform": "codex", "session_id": "r1", "objective": "parent obj", "simulated": True})

        sub = root / "calculator-test"
        sub.mkdir()
        self.assertFalse((sub / ".collab").exists())

        # Attempt to create .collab in subfolder
        with self.assertRaises(CollabError) as caught:
            with Store(sub, create=True) as s:
                pass
        self.assertEqual(caught.exception.code, "NESTED_WORKSPACE_CONFLICT")
        # Assert NO .collab was created on disk
        self.assertFalse((sub / ".collab").exists(), ".collab directory MUST NOT be created inside subfolder!")

    # 21. Host session fallback to ppid when no thread ID is provided
    def test_21_host_session_ppid_fallback(self):
        from collablib.identity import host_metadata

        env = {"CODEX_APP_TOOLS_PIPE_PATH": "pipe_123"}
        meta = host_metadata(env)
        self.assertEqual(meta["platform"], "codex")
        self.assertTrue(meta["host_session_id"].startswith("proc-"), f"Expected proc- prefix, got {meta['host_session_id']}")
