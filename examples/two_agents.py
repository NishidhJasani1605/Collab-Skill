"""Show independent CLI processes exchanging messages through one local folder.

Run: python examples/two_agents.py [--project /path/to/a/test/project]
This simulates agent clients; it does not start or impersonate any real IDE.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, help="Folder for the demonstration's .collab state")
    arguments = parser.parse_args()
    project = (arguments.project or Path(tempfile.mkdtemp(prefix="collab-two-agents-"))).resolve()
    project.mkdir(parents=True, exist_ok=True)
    helper = Path(__file__).resolve().parents[1] / "skills" / "collab" / "scripts" / "collab.py"

    def call(command, **data):
        process = subprocess.run(
            [sys.executable, str(helper), "--root", str(project), command,
             "--data", json.dumps(data)],
            text=True, encoding="utf-8", capture_output=True,
            env=dict(os.environ, PYTHONUTF8="1"), timeout=120,
        )
        try:
            result = json.loads(process.stdout)
        except json.JSONDecodeError as error:
            raise RuntimeError(process.stderr or process.stdout) from error
        if process.returncode or not result.get("ok"):
            raise RuntimeError(result)
        return result

    def join(name, task_id=None):
        data = {"name": name, "platform": "subprocess-demo", "model": "unknown",
                "session_id": str(uuid.uuid4()), "objective": "Demonstrate a shared group conversation"}
        if task_id:
            data["task_id"] = task_id
        result = call("start", **data)
        return {"agent_id": result["agent"]["id"], "token": result["token"], "task_id": result["task"]["id"]}

    agent_a = join("Demo Agent A")
    call("send", **agent_a, type="PLAN", content="A: I will inspect the project structure.")
    agent_b = join("Demo Agent B", agent_a["task_id"])
    messages_b = call("read", **agent_b, after=0, limit=100)
    assert any(event["content"] == "A: I will inspect the project structure." for event in messages_b["events"])
    call("send", **agent_b, type="REPLY", content="B: I read your plan. I will review the tests.")
    messages_a = call("read", **agent_a, after=messages_b["cursor"], limit=100)
    assert any(event["content"] == "B: I read your plan. I will review the tests." for event in messages_a["events"])
    print("Independent-process A -> B -> A communication verified.")
    print(f"Project: {project}")
    print(f"Shared task: {agent_a['task_id']}")
    print(f"Transcript: {project / '.collab' / 'GROUP_CHAT.md'}")
    print("The demonstration task remains open; exchanging messages does not complete it.")


if __name__ == "__main__":
    main()
