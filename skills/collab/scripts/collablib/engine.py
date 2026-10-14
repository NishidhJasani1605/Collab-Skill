"""Provider-neutral COLLAB coordination. All state transitions run under Store's lock."""
from __future__ import annotations

import copy
import hashlib
import hmac
import html
import json
import os
from pathlib import Path
import re
import secrets
import tempfile
import time
import uuid
from datetime import datetime, timezone

from .storage import CollabError, Store, fingerprint, safe_project_path
from . import __version__
from .checks import capture_check

VERSION = __version__
TYPES = set("JOIN PLAN STATUS QUESTION REPLY FINDING SUGGESTION HELP_REQUEST HELP_RESPONSE FILE_CHANGE ISSUE REVIEW DISAGREEMENT DECISION APPROVAL REJECTION WORK_COMPLETE TEAM_COMPLETE".split())
CHAT_TYPES = TYPES - {"JOIN", "APPROVAL", "WORK_COMPLETE", "TEAM_COMPLETE"}
STATUSES = set("JOINED PLANNING WORKING BLOCKED WORK_COMPLETE HELPING REVIEWING APPROVED OFFLINE TEAM_COMPLETE".split())


def fail(code, message, details=None):
    raise CollabError(code, message, details)


def uid(prefix):
    return prefix + "_" + uuid.uuid4().hex


def utc():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def string(data, key, default=None, maximum=32000):
    value = data.get(key, default)
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        fail("INVALID_INPUT", f"{key} must be a nonempty string of at most {maximum} characters")
    return value


def text_content(data, *keys, default=None, maximum=32000):
    candidate_keys = list(dict.fromkeys(["content", *keys, "description", "detail", "title"]))
    explicitly_supplied = False
    for k in candidate_keys:
        if k in data and data[k] is not None:
            explicitly_supplied = True
            if not isinstance(data[k], str):
                fail("INVALID_INPUT", f"{k} must be a string")
    if "content" in data and isinstance(data["content"], str) and data["content"].strip():
        val = data["content"].strip()
        if len(val) > maximum:
            fail("INVALID_INPUT", f"content must be at most {maximum} characters")
        return redact(val)
    if "title" in data and ("description" in data or "detail" in data):
        t = data.get("title") or ""
        d = data.get("description") or data.get("detail") or ""
        if isinstance(t, str) and isinstance(d, str) and (t.strip() or d.strip()):
            combined = f"{t.strip()}: {d.strip()}" if t.strip() and d.strip() else (t.strip() or d.strip())
            if len(combined) > maximum:
                fail("INVALID_INPUT", f"Combined content must be at most {maximum} characters")
            return redact(combined)
    for k in keys:
        if k in data and isinstance(data[k], str) and data[k].strip():
            val = data[k].strip()
            if len(val) > maximum:
                fail("INVALID_INPUT", f"{k} must be at most {maximum} characters")
            return redact(val)
    if "content" in keys:
        for fallback_k in ("description", "detail", "title"):
            if fallback_k in data and isinstance(data[fallback_k], str) and data[fallback_k].strip():
                val = data[fallback_k].strip()
                if len(val) > maximum:
                    fail("INVALID_INPUT", f"{fallback_k} must be at most {maximum} characters")
                return redact(val)
    if explicitly_supplied:
        fail("INVALID_INPUT", f"Provided text field cannot be empty (expected nonempty {', '.join(keys)})")
    if default is not None:
        return default
    fail("INVALID_INPUT", f"Missing required text content (expected one of: {', '.join(keys)})")


def strings(data, key, default=None):
    value = data.get(key, [] if default is None else default)
    if not isinstance(value, list) or len(value) > 1000 or any(not isinstance(x, str) or not x.strip() or len(x) > 32000 for x in value):
        fail("INVALID_INPUT", f"{key} must be a list of nonempty strings")
    return value


def strings_alias(data, *keys):
    merged = []
    for k in keys:
        if k in data and data[k] is not None:
            for item in strings(data, k):
                if item not in merged:
                    merged.append(item)
    return merged


def integer(data, key, default, low, high):
    value = data.get(key, default)
    if type(value) is not int or not low <= value <= high:
        fail("INVALID_INPUT", f"{key} must be an integer between {low} and {high}")
    return value


def boolean(data, key, default):
    value = data.get(key, default)
    if type(value) is not bool:
        fail("INVALID_INPUT", f"{key} must be a boolean")
    return value


def redact(text):
    """Best effort. Never treat this as a guarantee that arbitrary text is secret-free."""
    for key, value in os.environ.items():
        if re.search(r"(?:TOKEN|SECRET|PASSWORD|API_KEY|PRIVATE_KEY)$", key, re.I) and len(value) >= 8:
            text = text.replace(value, "[REDACTED]")
    text = re.sub(r"(?i)\b((?:api[_-]?key|password|secret|access[_-]?token)\s*[:=]\s*)[^\s,;]+", r"\1[REDACTED]", text)
    text = re.sub(r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,})\b", "[REDACTED]", text)
    return text


def clean(value):
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [clean(x) for x in value]
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    return value


def evidence(data):
    value = data.get("evidence", [])
    if not isinstance(value, list) or len(json.dumps(value)) > 64000:
        fail("INVALID_INPUT", "evidence must be a JSON list below 64 KB")
    return clean(value)


def public_agent(agent):
    result = {k: copy.deepcopy(v) for k, v in agent.items() if k != "token_hash"}
    result["stale"] = time.time() - agent["last_seen_epoch"] > 1800
    return result


def fresh_state():
    return {"config": {"protocol_version": 1, "version": VERSION, "stale_after_seconds": 1800},
            "agents": {}, "tasks": {}, "progress": {}, "requests": {}, "reservations": {}}


def sync_progress(state):
    prog = {}
    for tid, t in state.get("tasks", {}).items():
        assignments = list(t.get("assignments", {}).values())
        total = len(assignments)
        completed = sum(1 for a in assignments if a.get("status") == "WORK_COMPLETE")
        if t.get("status") == "TEAM_COMPLETE":
            pct = 100
        elif total > 0:
            pct = int(round(sum(a.get("percent", 0) for a in assignments) / total))
        else:
            pct = 0
        prog[tid] = {
            "task_id": tid,
            "objective": t.get("objective", ""),
            "status": t.get("status", "WORKING"),
            "revision": t.get("revision", 0),
            "percent": pct,
            "assignments_total": total,
            "assignments_completed": completed,
            "participants_count": len(t.get("participants", [])),
            "required_participants_count": len(t.get("required_participants", [])),
            "open_issues": sum(1 for i in t.get("issues", {}).values() if i.get("status") == "OPEN"),
            "open_help_requests": sum(1 for h in t.get("help", {}).values() if h.get("status") != "RESOLVED"),
        }
    state["progress"] = prog


def actor(state, data):
    a = state["agents"].get(data.get("agent_id"))
    supplied = data.get("token", "")
    if not a or not isinstance(supplied, str) or not hmac.compare_digest(a["token_hash"], hashlib.sha256(supplied.encode()).hexdigest()):
        fail("AUTH_REQUIRED", "Use the agent_id and private token returned by start")
    return a


def task_for(state, data, a=None, writable=False):
    t = state["tasks"].get(data.get("task_id"))
    if t is None:
        fail("TASK_NOT_FOUND", "Supply an existing task_id")
    if a and a["id"] not in t["participants"]:
        fail("NOT_PARTICIPANT", "Join this task with start first")
    if writable and t["status"] == "TEAM_COMPLETE":
        fail("TASK_COMPLETE", "Completed tasks are immutable; start a new task")
    return t


def invalidate(t, reason):
    if t.get("decision"):
        t["decision"]["valid"] = False
        t["decision"]["invalidated_reason"] = reason
    t["approvals"] = {}
    t["status"] = "WORKING"


def paths(root, values):
    result = []
    for name in values:
        p = safe_project_path(root, name)
        if p.exists() and not p.is_file():
            fail("INVALID_PATH", "Expected a regular project file", {"path": name})
        canonical = p.relative_to(Path(root).resolve()).as_posix()
        if os.name == "nt":
            canonical = canonical.lower()
        if canonical not in result:
            result.append(canonical)
    return result


def hashes(root, names, require=False):
    found = {name: fingerprint(safe_project_path(root, name)) for name in names}
    if require and "missing" in found.values():
        fail("ARTIFACT_MISSING", "Required result files must exist", {"files": [n for n, h in found.items() if h == "missing"]})
    return found


def current_decision(root, t, data):
    d = t.get("decision")
    if not d or not d["valid"]:
        fail("STALE_REVISION", "No valid proposed revision exists for this task")
    if data.get("revision") is not None and data.get("revision") != d["revision"]:
        fail("STALE_REVISION", "Use a current, valid proposed revision")
    if hashes(root, list(d["file_hashes"])) != d["file_hashes"]:
        fail("RESULT_CHANGED", "A reviewed file changed; propose a new revision")
    return d


def event_for(a, t, kind, content, data):
    return {"id": uid("msg"), "agent_id": a["id"], "agent_name": a["name"],
            "platform": a["platform"], "model": a["model"], "session_id": a["session_id"],
            "task_id": t["id"] if t else None, "type": kind, "content": redact(content),
            "recipient": data.get("recipient"), "reply_to": data.get("reply_to"),
            "files": data.get("files", []), "evidence": evidence(data),
            "protocol_version": 1, "timestamp": utc()}


def new_task(root, state, data):
    objective = redact(string(data, "objective"))
    checks = data.get("checks", [])
    if not isinstance(checks, list) or len(checks) > 100:
        fail("INVALID_INPUT", "checks must be a list with at most 100 entries")
    validated = {}
    for entry in checks:
        if not isinstance(entry, dict):
            fail("INVALID_INPUT", "Each check needs name and argv")
        name = string(entry, "name", maximum=128)
        argv = strings(entry, "argv")
        if not argv or name in validated:
            fail("INVALID_INPUT", "Check names must be unique and argv cannot be empty")
        # Commands are explicitly declared by the invoking agent from the user's task;
        # group messages never define executable commands.
        if clean(argv) != argv:
            fail("SECRET_INPUT", "Do not place credentials in check command arguments")
        validated[name] = {"name": name, "argv": argv, "timeout": integer(entry, "timeout", 120, 1, 3600)}
    criteria_list = strings_alias(data, "criteria", "acceptance_criteria")
    artifacts_list = strings_alias(data, "artifacts", "required_artifacts")
    canonical_artifacts = paths(root, artifacts_list)
    t = {"id": uid("task"), "objective": objective, "created_at": utc(), "status": "WORKING",
          "criteria": clean(criteria_list), "acceptance_criteria": clean(criteria_list), "checks": validated,
          "required_artifacts": canonical_artifacts, "artifacts": list(canonical_artifacts),
          "independent_reviews": integer(data, "independent_reviews", 1, 1, 1000),
          "participants": [], "required_participants": [], "assignments": {}, "issues": {},
          "help": {}, "findings": {}, "decisions": [], "reviews": [], "approvals": {},
          "check_runs": {}, "participant_results": {}, "changes": [], "checkpoints": [],
          "decision": None, "revision": 0, "final_decision": None, "completed_at": None}
    state["tasks"][t["id"]] = t
    return t


def start(root, s, data):
    state = copy.deepcopy(s.state) if s.state else fresh_state()
    session = string(data, "session_id", maximum=256)
    matches = [a for a in state["agents"].values() if a["session_id"] == session]
    token = None
    if matches:
        a = actor(state, {**data, "agent_id": matches[0]["id"]})
    else:
        token = secrets.token_urlsafe(32)
        a = {"id": uid("agent"), "name": redact(string(data, "name", maximum=128)),
             "platform": redact(string(data, "platform", "unknown", 128)),
             "model": redact(string(data, "model", "unknown", 128)), "session_id": session,
             "token_hash": hashlib.sha256(token.encode()).hexdigest(), "joined_at": utc(),
             "last_activity": utc(), "last_seen_epoch": time.time(), "current_task": None,
             "current_assignment": None, "status": "JOINED"}
        state["agents"][a["id"]] = a
    if data.get("task_id"):
        t = task_for(state, data)
        if t["status"] == "TEAM_COMPLETE":
            fail("TASK_COMPLETE", "This task is complete; create a new task")
    else:
        active = [t for t in state["tasks"].values() if t["status"] != "TEAM_COMPLETE"]
        if boolean(data, "new_task", False):
            objective = string(data, "objective")
            same = [t for t in active if " ".join(t["objective"].split()).casefold() == " ".join(redact(objective).split()).casefold()]
            t = same[0] if len(same) == 1 else new_task(root, state, data)
        elif len(active) > 1:
            fail("AMBIGUOUS_TASK", "Multiple tasks are open; ask the user which task to join", {"tasks": [{"id": x["id"], "objective": x["objective"]} for x in active]})
        elif active:
            t = active[0]
            if data.get("objective") and " ".join(redact(string(data, "objective")).split()).casefold() != " ".join(t["objective"].split()).casefold():
                fail("TASK_MISMATCH", "The active task has a different objective; supply its task_id or explicitly create a new task")
        else:
            t = new_task(root, state, data)
    joined = a["id"] not in t["participants"]
    if joined:
        t["participants"].append(a["id"])
        if t["status"] != "REVIEW":
            t["required_participants"].append(a["id"])
    a.update(current_task=t["id"], last_activity=utc(), last_seen_epoch=time.time())
    if a["status"] in {"OFFLINE", "TEAM_COMPLETE"}:
        a["status"] = "JOINED"
    sync_progress(state)
    e = event_for(a, t, "JOIN" if joined else "STATUS", "Joined the shared task" if joined else "Session resumed", {})
    committed = s.commit(state, e)
    return {"agent": public_agent(a), "token": token if token else data["token"], "task": t,
            "agents": [public_agent(x) for x in state["agents"].values()],
            "events": [e for e in s.events if e.get("task_id") == t["id"]][-30:],
            "cursor": committed["seq"], "observer": a["id"] not in t["required_participants"]}


def report(state, t):
    q = lambda value: "\n".join("> " + html.escape(line) for line in str(value).splitlines())
    d = t["decision"]
    lines = ["# COLLAB final report", "", "Status: TEAM_COMPLETE", f"Task: {t['id']}",
             f"Result revision: {d['revision']} / {d['digest']}", "", "## Original task", q(t["objective"]),
             "", "## Acceptance criteria"]
    lines += ["- " + html.escape(x) for x in t["criteria"]] or ["No criteria were declared."]
    lines += ["", "## Participating agents"]
    for aid in t["participants"]:
        a = state["agents"][aid]
        lines.append(f"- {html.escape(a['name'])} ({html.escape(a['platform'])}; model {html.escape(a['model'])}), `{aid}`; " + ("required" if aid in d["members"] else "observer"))
    lines += ["", "## Responsibilities and results"]
    for item in t["assignments"].values():
        lines += [f"### {html.escape(item['title'])}", f"Owner: {item['owner']}; status: {item['status']}", q(item.get("result", "")), "Evidence: " + q(json.dumps(item.get("evidence", []), ensure_ascii=False))]
    lines += ["", "## Findings"]
    lines += [q(f["content"]) + "\nEvidence: " + q(json.dumps(f["evidence"], ensure_ascii=False)) for f in t["findings"].values()] or ["No findings recorded."]
    lines += ["", "## Issues and disagreements"]
    for i in t["issues"].values():
        lines += [q(i["content"]), f"Status: {i['status']}; blocking: {i['blocking']}", q(i.get("resolution", "")), q(json.dumps(i.get("resolution_evidence", []), ensure_ascii=False))]
    lines += ["", "## Fixes, decisions and final agreed result", q(d["content"]), "", "## Validation evidence"]
    for name, run in t["check_runs"].items():
        lines += [f"- {html.escape(name)}: exit {run['returncode']}; revision {run['revision']}; evidence SHA-256 `{run['log_hash']}`; `{run['log_path']}`"]
    if not t["checks"]:
        lines += ["No executable checks were configured; completion relies on the recorded evidence and independent review."]
    lines += ["", "## Independent reviews"]
    lines += [q(json.dumps(r, ensure_ascii=False)) for r in t["reviews"] if r["revision"] == d["revision"]]
    lines += ["", "## Approvals", q(json.dumps(t["approvals"], ensure_ascii=False)), "", "## Modified files"]
    lines += [q(json.dumps(c, ensure_ascii=False)) for c in t["changes"]] or ["No file changes recorded through COLLAB."]
    lines += ["", "## Result fingerprints", q(json.dumps(d["file_hashes"], indent=2)), "", "## Remaining limitations"]
    lines += ["- " + html.escape(x) for x in d["limitations"]] or ["No task-specific limitations submitted. Consensus is not a guarantee of correctness."]
    lines += ["", "COLLAB records deliberate contributions; it does not capture private IDE conversations or prove an AI session is currently running.", ""]
    return "\n".join(lines)


def readiness(root, state, t, d):
    blockers = []
    required = [a for a in t["assignments"].values() if a["required"]]
    if not required:
        blockers.append("No required assignment was declared")
    blockers += ["Incomplete assignment: " + x["id"] for x in required if x["status"] != "WORK_COMPLETE"]
    blockers += ["Missing participant result: " + a for a in d["members"] if a not in t["participant_results"]]
    blockers += ["Blocking issue: " + i["id"] for i in t["issues"].values() if i["blocking"] and i["status"] != "RESOLVED"]
    blockers += ["Unresolved help request: " + i["id"] for i in t["help"].values() if i["status"] != "RESOLVED"]
    latest_reviews = {}
    for r in t["reviews"]:
        if r["revision"] == d["revision"]:
            latest_reviews[r["agent_id"]] = r
    blockers += ["Unresolved review rejection: " + a for a, r in latest_reviews.items() if r["verdict"] == "REJECT"]
    independent = [r for a, r in latest_reviews.items() if a != d["author"] and r["verdict"] == "APPROVE" and r["evidence"]]
    if len(independent) < t["independent_reviews"]:
        blockers.append("Missing evidence-backed independent review")
    for aid in d["members"]:
        approval = t["approvals"].get(aid)
        if not approval or approval["revision"] != d["revision"] or approval["digest"] != d["digest"]:
            blockers.append("Missing current approval: " + aid)
    for name in t["checks"]:
        run = t["check_runs"].get(name)
        if not run or run["returncode"] != 0 or run["revision"] != d["revision"] or run["digest"] != d["digest"] or run["file_hashes"] != d["file_hashes"]:
            blockers.append("Missing current passing check: " + name)
        elif fingerprint(root / run["log_path"]) != run.get("log_hash"):
            blockers.append("Tampered or missing check evidence: " + name)
    if hashes(root, list(d["file_hashes"])) != d["file_hashes"]:
        blockers.append("Reviewed files changed")
    req_artifacts = paths(root, list(t.get("required_artifacts", [])) + list(t.get("artifacts", [])) + list(d.get("artifacts", [])))
    for name in req_artifacts:
        if fingerprint(safe_project_path(root, name)) == "missing":
            blockers.append("Missing required artifact: " + name)
    for r in state["reservations"].values():
        if r["task_id"] == t["id"] and not r["released"]:
            blockers.append("Unreleased file reservation: " + r["id"])
    return blockers


def execute(root, command, data):
    if not isinstance(data, dict):
        fail("INVALID_INPUT", "Input must be a JSON object")
    if command == "check":
        return run_check(root, data)
    with Store(root, create=command == "start") as s:
        if command == "start":
            return start(root, s, data)
        state = copy.deepcopy(s.state) if s.state else fresh_state()
        if command == "read":
            after_key = "after" if "after" in data else ("cursor" if "cursor" in data else "after")
            after = integer(data, after_key, 0, 0, 2**63-1)
            limit = integer(data, "limit", 100, 1, 1000)
            # Cursor advances only through scanned events, never skips matching unread events.
            found, cursor = [], after
            for e in s.events:
                if e["seq"] <= after:
                    continue
                cursor = e["seq"]
                if not data.get("task_id") or e.get("task_id") == data["task_id"]:
                    found.append(e)
                if len(found) == limit:
                    break
            return {"events": found, "cursor": cursor, "latest": s.events[-1]["seq"] if s.events else 0}
        if command == "status":
            result = {"agents": [public_agent(a) for a in state["agents"].values()], "reservations": list(state["reservations"].values()), "cursor": s.events[-1]["seq"] if s.events else 0}
            if data.get("task_id"):
                t = task_for(state, data)
                result["task"] = t
                if t.get("decision") and t["decision"]["valid"]:
                    result["blockers"] = readiness(root, state, t, t["decision"])
                elif t["status"] == "TEAM_COMPLETE":
                    result["blockers"] = []
                else:
                    synthetic = {"revision": t["revision"], "digest": "", "author": None, "members": list(t["required_participants"]), "file_hashes": {}}
                    result["blockers"] = ["No active proposed revision"] + readiness(root, state, t, synthetic)
            else:
                result["tasks"] = list(state["tasks"].values())
            return result
        a = actor(state, data)
        t = task_for(state, data, a)
        key = data.get("key")
        request_key = None
        request_hash = digest({k: v for k, v in data.items() if k != "token"})
        if key is not None:
            string(data, "key", maximum=256)
            request_key = a["id"] + ":" + command + ":" + key
            prior = state["requests"].get(request_key)
            if prior:
                if prior["hash"] != request_hash:
                    fail("IDEMPOTENCY_CONFLICT", "This key was already used for different content")
                return {**prior["response"], "duplicate": True}
        if command == "finalize" and t["status"] == "TEAM_COMPLETE":
            if data.get("revision") is not None and data.get("revision") != t["revision"]:
                fail("STALE_REVISION", "This completed task has another revision")
            return {"task": t, "report": ".collab/decisions/" + t["id"] + "-final.md", "duplicate": True}
        task_for(state, data, a, writable=command not in {"checkpoint", "agent-status"})
        a.update(last_activity=utc(), last_seen_epoch=time.time())
        artifacts, response = {}, {}
        kind, content = "STATUS", ""
        if command == "send":
            kind = string(data, "type", "STATUS", 32).upper()
            if kind not in CHAT_TYPES:
                fail("INVALID_MESSAGE_TYPE", "Use dedicated commands for joins, approvals and completion")
            content = text_content(data, "content", "message", "summary")
            if data.get("recipient") and data["recipient"] not in state["agents"]:
                fail("AGENT_NOT_FOUND", "Recipient is not registered")
            if data.get("reply_to") and not any(e["id"] == data["reply_to"] for e in s.events):
                fail("MESSAGE_NOT_FOUND", "reply_to must refer to an existing message")
            data = {**data, "files": paths(root, strings(data, "files"))}
            if kind == "PLAN" and a["status"] == "JOINED":
                a["status"] = "PLANNING"
            if kind == "DISAGREEMENT":
                issue = {"id": uid("issue"), "author": a["id"], "content": redact(content), "blocking": True, "status": "OPEN", "evidence": evidence(data)}
                t["issues"][issue["id"]] = issue
                invalidate(t, "New disagreement")
                response["issue"] = issue
        elif command == "assignment-add":
            deps = strings_alias(data, "depends_on", "dependencies")
            if any(x not in t["assignments"] for x in deps):
                fail("ASSIGNMENT_NOT_FOUND", "Dependencies must already exist in this task")
            title_val = string(data, "title") if "title" in data else string(data, "name")
            desc = ""
            for desc_k in ("description", "content", "summary", "detail"):
                if desc_k in data and data[desc_k] is not None:
                    if not isinstance(data[desc_k], str) or len(data[desc_k]) > 32000:
                        fail("INVALID_INPUT", f"{desc_k} must be a string of at most 32000 characters")
                    if data[desc_k].strip():
                        desc = data[desc_k].strip()
                        break
            item = {"id": uid("assignment"), "title": redact(title_val), "description": redact(desc),
                    "depends_on": deps, "files": paths(root, strings(data, "files")), "required": boolean(data, "required", True),
                    "owner": None, "status": "OPEN", "percent": 0, "result": None, "evidence": []}
            t["assignments"][item["id"]] = item
            invalidate(t, "Assignment added")
            response["assignment"], kind, content = item, "PLAN", "Assignment created: " + item["title"]
        elif command in {"claim", "progress", "work-complete"}:
            aid = data.get("assignment_id") or data.get("id")
            item = t["assignments"].get(aid)
            if not item:
                fail("ASSIGNMENT_NOT_FOUND", "Unknown assignment_id")
            if item["owner"] and item["owner"] != a["id"]:
                fail("ALREADY_CLAIMED", "Another agent owns this assignment")
            if command == "claim":
                if any(t["assignments"][x]["status"] != "WORK_COMPLETE" for x in item["depends_on"]):
                    fail("DEPENDENCY_INCOMPLETE", "Complete dependencies before claiming")
                if item["status"] == "WORK_COMPLETE":
                    fail("ASSIGNMENT_COMPLETE", "This assignment is already complete")
                item.update(owner=a["id"], status="WORKING")
                a.update(current_assignment=item["id"], status="WORKING")
                content = "Claimed assignment: " + item["title"]
            else:
                if item["owner"] != a["id"] or item["status"] == "WORK_COMPLETE":
                    fail("NOT_OWNER", "Claim an open assignment first")
                if command == "progress":
                    item["percent"] = integer(data, "percent", item["percent"], 0, 99)
                    content = text_content(data, "content", "status_message", "message", "summary", default="Progress updated")
                else:
                    result_str = text_content(data, "result", "content", "summary")
                    item.update(status="WORK_COMPLETE", percent=100, result=redact(result_str), evidence=evidence(data))
                    t["participant_results"][a["id"]] = {"content": item["result"], "evidence": item["evidence"], "timestamp": utc()}
                    a.update(current_assignment=None, status="WORK_COMPLETE")
                    kind, content = "WORK_COMPLETE", item["result"]
                item["updated_at"] = utc()
            invalidate(t, "Assignment changed")
            response["assignment"] = item
        elif command == "participant-result":
            content = text_content(data, "content", "result", "summary")
            rec = {"content": redact(content), "evidence": evidence(data), "timestamp": utc()}
            t["participant_results"][a["id"]] = rec
            invalidate(t, "Participant result changed")
            kind = "WORK_COMPLETE"
            a["status"] = "WORK_COMPLETE"
            response["participant_result"] = rec
        elif command == "help-request":
            content = text_content(data, "content", "description", "detail", "summary")
            if data.get("assignment_id") and data["assignment_id"] not in t["assignments"]:
                fail("ASSIGNMENT_NOT_FOUND", "Unknown help assignment")
            help_item = {"id": uid("help"), "requester": a["id"], "assignment_id": data.get("assignment_id"), "content": redact(content), "status": "OPEN", "responses": []}
            if "title" in data and data["title"] is not None:
                help_item["title"] = redact(string(data, "title", maximum=512).strip())
            t["help"][help_item["id"]] = help_item
            response["help"], kind = help_item, "HELP_REQUEST"
            a["status"] = "BLOCKED"
            invalidate(t, "Help requested")
        elif command in {"help-respond", "help-resolve"}:
            hid = data.get("help_id") or data.get("id")
            h = t["help"].get(hid)
            if not h or h["status"] == "RESOLVED":
                fail("HELP_NOT_OPEN", "Select an open help request")
            content = text_content(data, "content", "solution", "resolution", "response", "summary")
            if command == "help-resolve":
                if a["id"] != h.get("resolution_owner", h["requester"]):
                    fail("NOT_OWNER", "Only the requester can confirm that help resolved the block")
                h.update(status="RESOLVED", resolution=redact(content))
                a["status"] = "WORKING"
                kind = "DECISION"
            else:
                h["responses"].append({"agent_id": a["id"], "content": redact(content), "evidence": evidence(data)})
                h["status"] = "ASSISTING"
                a["status"] = "HELPING"
                kind = "HELP_RESPONSE"
            invalidate(t, "Help updated")
            response["help"] = h
        elif command == "issue":
            content = text_content(data, "content", "description", "detail", "summary")
            i = {"id": uid("issue"), "author": a["id"], "content": redact(content), "blocking": boolean(data, "blocking", True), "status": "OPEN", "evidence": evidence(data)}
            if "title" in data and data["title"] is not None:
                i["title"] = redact(string(data, "title", maximum=512).strip())
            t["issues"][i["id"]] = i
            invalidate(t, "Issue raised")
            response["issue"], kind = i, "ISSUE"
        elif command == "resolve":
            iid = data.get("issue_id") or data.get("id")
            i = t["issues"].get(iid)
            if not i or i["status"] != "OPEN":
                fail("ISSUE_NOT_OPEN", "Select an open issue")
            if i.get("resolution_owner", i["author"]) != a["id"]:
                fail("NOT_OWNER", "The agent that raised the issue must confirm its resolution")
            ev = evidence(data)
            if i["blocking"] and not ev:
                fail("EVIDENCE_REQUIRED", "Resolve blocking issues with reproducible evidence")
            content = text_content(data, "content", "resolution", "solution", "summary")
            i.update(status="RESOLVED", resolution=redact(content), resolution_evidence=ev, resolved_by=a["id"])
            invalidate(t, "Issue resolved")
            response["issue"], kind = i, "DECISION"
        elif command == "finding":
            content = text_content(data, "content", "detail", "description", "summary", "result")
            f = {"id": uid("finding"), "agent_id": a["id"], "content": redact(content), "evidence": evidence(data),
                 "files": paths(root, strings(data, "files")), "timestamp": utc()}
            if "title" in data and data["title"] is not None:
                f["title"] = redact(string(data, "title", maximum=512).strip())
            t["findings"][f["id"]] = f
            artifacts["findings/" + f["id"] + ".json"] = json.dumps(f, ensure_ascii=False, indent=2)
            invalidate(t, "Finding added")
            response["finding"], kind = f, "FINDING"
        elif command == "propose":
            content = text_content(data, "content", "summary", "result", "description")
            prop_artifacts = strings_alias(data, "artifacts", "required_artifacts")
            if prop_artifacts:
                merged_artifacts = paths(root, t["required_artifacts"] + prop_artifacts)
                t["required_artifacts"] = merged_artifacts
                t["artifacts"] = list(merged_artifacts)
            prop_criteria = strings_alias(data, "criteria", "acceptance_criteria")
            if prop_criteria:
                merged_criteria = list(dict.fromkeys(t["criteria"] + clean(prop_criteria)))
                t["criteria"] = merged_criteria
                t["acceptance_criteria"] = list(merged_criteria)
            tracked = paths(root, strings(data, "files") + prop_artifacts + t["required_artifacts"] + [f for c in t["changes"] for f in c["files"]])
            # Include declared assignment files so omitting files from a proposal cannot
            # accidentally bypass revision invalidation.
            tracked = paths(root, tracked + [f for item in t["assignments"].values() for f in item["files"]])
            file_hashes = hashes(root, tracked)
            revision = t["revision"] + 1
            d = {"revision": revision, "content": redact(content), "author": a["id"], "file_hashes": file_hashes,
                 "members": list(t["required_participants"]), "limitations": clean(strings(data, "limitations")),
                 "timestamp": utc(), "valid": True}
            d["digest"] = digest({"content": d["content"], "file_hashes": file_hashes, "revision": revision,
                                  "members": d["members"], "limitations": d["limitations"],
                                  "criteria": t["criteria"], "assignments": t["assignments"], "issues": t["issues"],
                                  "findings": t["findings"], "participant_results": t["participant_results"], "checks": t["checks"]})
            t.update(revision=revision, decision=d, status="REVIEW", approvals={})
            t["decisions"].append(copy.deepcopy(d))
            artifacts[f"decisions/{t['id']}-r{revision}.json"] = json.dumps(d, ensure_ascii=False, indent=2)
            response.update(revision=revision, decision=d)
            kind = "DECISION"
        elif command == "review":
            d = current_decision(root, t, data)
            verdict = string(data, "verdict", maximum=16).upper()
            if verdict not in {"APPROVE", "REJECT"}:
                fail("INVALID_INPUT", "verdict must be APPROVE or REJECT")
            content = text_content(data, "content", "critique", "review", "summary", "comment", default="Independent review completed")
            ev = evidence(data)
            if not ev:
                fail("EVIDENCE_REQUIRED", "Reviews must state independent evidence")
            r = {"id": uid("review"), "agent_id": a["id"], "revision": d["revision"], "digest": d["digest"], "verdict": verdict, "content": redact(content), "evidence": ev, "timestamp": utc()}
            t["reviews"].append(r)
            if verdict == "REJECT":
                t["approvals"] = {}
            a["status"] = "REVIEWING"
            artifacts["reviews/" + r["id"] + ".json"] = json.dumps(r, ensure_ascii=False, indent=2)
            response["review"], kind = r, "REVIEW" if verdict == "APPROVE" else "REJECTION"
        elif command == "approve":
            d = current_decision(root, t, data)
            if a["id"] not in d["members"]:
                fail("OBSERVER", "Review-round observers do not supply required approvals")
            latest = {}
            for r in t["reviews"]:
                if r["revision"] == d["revision"]:
                    latest[r["agent_id"]] = r
            if any(r["verdict"] == "REJECT" for r in latest.values()):
                fail("REVIEW_REJECTED", "Resolve review rejections before approving")
            content = text_content(data, "content", "approval", "summary", "comment", default="Approved active revision")
            approval = {"agent_id": a["id"], "revision": d["revision"], "digest": d["digest"], "content": redact(content), "timestamp": utc()}
            t["approvals"][a["id"]] = approval
            a["status"] = "APPROVED"
            response["approval"], kind = approval, "APPROVAL"
        elif command == "finalize":
            d = current_decision(root, t, data)
            blockers = readiness(root, state, t, d)
            if blockers:
                fail("NOT_READY", "Team finalization requirements are not satisfied", {"blockers": blockers})
            t.update(status="TEAM_COMPLETE", completed_at=utc(), final_decision=copy.deepcopy(d))
            for aid in d["members"]:
                if state["agents"][aid]["current_task"] == t["id"]:
                    state["agents"][aid]["status"] = "TEAM_COMPLETE"
            final = report(state, t)
            artifacts["FINAL_REPORT.md"] = final
            artifacts[f"decisions/{t['id']}-final.md"] = final
            response.update(task=t, report=f".collab/decisions/{t['id']}-final.md")
            kind, content = "TEAM_COMPLETE", f"Team completed revision {d['revision']} ({d['digest']}); all declared gates satisfied"
        elif command == "reserve":
            raw_files = strings_alias(data, "files", "paths")
            if not raw_files and ("path" in data or "file" in data):
                single_key = "path" if "path" in data else "file"
                raw_files = [string(data, single_key)]
            files = paths(root, raw_files)
            if not files:
                fail("INVALID_INPUT", "Reserve at least one file")
            now = time.time()
            conflicts = [r for r in state["reservations"].values() if not r["released"] and r["expires_at"] > now and set(r["files"]) & set(files)]
            if conflicts:
                fail("FILE_RESERVED", "Files are already reserved", {"reservations": conflicts})
            # Expired records remain in the audit trail but cannot obstruct new owners.
            for old in state["reservations"].values():
                if not old["released"] and old["expires_at"] <= now:
                    old.update(released=True, release_reason="lease expired")
            ttl_key = "ttl_seconds" if "ttl_seconds" in data else ("ttl" if "ttl" in data else "ttl_seconds")
            r = {"id": uid("reservation"), "agent_id": a["id"], "task_id": t["id"], "files": files,
                 "base_hashes": hashes(root, files), "expires_at": now + integer(data, ttl_key, 900, 1, 3600), "released": False}
            state["reservations"][r["id"]] = r
            invalidate(t, "Files reserved for editing")
            response["reservation"], kind, content = r, "PLAN", "Reserved files: " + ", ".join(files)
        elif command in {"release", "file-write", "file-record"}:
            rid = data.get("reservation_id") or data.get("id")
            r = state["reservations"].get(rid)
            if not r or r["agent_id"] != a["id"] or r["task_id"] != t["id"] or r["released"]:
                fail("NOT_OWNER", "Select your own active reservation")
            if command == "release":
                r.update(released=True, release_reason="owner released")
                content = "Released reservation " + r["id"]
            else:
                if r["expires_at"] <= time.time():
                    fail("RESERVATION_EXPIRED", "Re-reserve and inspect current files before writing")
                path_key = "path" if "path" in data else ("file" if "file" in data else "path")
                name = paths(root, [string(data, path_key)])[0]
                if name not in r["files"]:
                    fail("FILE_NOT_RESERVED", "Reserve this file first")
                p = safe_project_path(root, name)
                before = fingerprint(p)
                if command == "file-write":
                    expected = string(data, "expected_hash", maximum=128)
                    if expected != r["base_hashes"][name] or before != expected:
                        fail("FILE_CHANGED", "File differs from the reserved revision; inspect and coordinate")
                    body = data.get("content")
                    if not isinstance(body, str) or len(body.encode("utf-8")) > 4*1024*1024:
                        fail("INVALID_INPUT", "file-write content must be UTF-8 text below 4 MiB")
                    if not p.parent.is_dir():
                        fail("INVALID_PATH", "Create the intended project directory before reserving files")
                    # Keep even interrupted edit staging inside the single runtime
                    # directory. Atomic replacement requires the same filesystem.
                    if p.parent.stat().st_dev != s.path.stat().st_dev:
                        fail("FILESYSTEM_MISMATCH", "Project file and .collab must be on the same filesystem")
                    staging = s._runtime("tmp/write", create_parents=True).parent
                    fd, temp_name = tempfile.mkstemp(prefix="write-", dir=staging)
                    try:
                        with os.fdopen(fd, "wb") as stream:
                            stream.write(body.encode("utf-8")); stream.flush(); os.fsync(stream.fileno())
                        safe_project_path(root, name)
                        if fingerprint(p) != expected:
                            fail("FILE_CHANGED", "File changed before atomic replacement")
                        if p.exists():
                            os.chmod(temp_name, p.stat().st_mode & 0o777)
                        os.replace(temp_name, p)
                    finally:
                        if os.path.exists(temp_name):
                            os.unlink(temp_name)
                else:
                    if data.get("expected_hash") is not None:
                        expected = string(data, "expected_hash", maximum=128)
                        if expected != before:
                            fail("FILE_CHANGED", "The externally edited file changed before recording")
                after = fingerprint(p)
                change = {"agent_id": a["id"], "files": [name], "before": r["base_hashes"][name], "after": after, "timestamp": utc(), "method": command}
                r["base_hashes"][name] = after
                t["changes"].append(change)
                invalidate(t, "Project file changed")
                response["change"], kind, content = change, "FILE_CHANGE", "Recorded change to " + name
            response["reservation"] = r
        elif command == "checkpoint":
            content = text_content(data, "content", "summary", "description")
            checkpoint = {"agent_id": a["id"], "content": redact(content), "cursor": s.events[-1]["seq"] if s.events else 0, "timestamp": utc()}
            if "active_file" in data and data["active_file"] is not None:
                checkpoint["active_file"] = paths(root, [string(data, "active_file", maximum=1024)])[0]
            t["checkpoints"].append(checkpoint)
            artifacts[f"checkpoints/{a['id']}-summary.json"] = json.dumps(checkpoint, ensure_ascii=False, indent=2)
            response["checkpoint"] = checkpoint
        elif command == "agent-status":
            status = string(data, "status", maximum=32).upper()
            if status not in STATUSES - {"APPROVED", "TEAM_COMPLETE", "WORK_COMPLETE"}:
                fail("INVALID_STATUS", "Completion and approval statuses require their dedicated commands")
            a["status"] = status
            content = "Agent status: " + status
            response["agent"] = public_agent(a)
        else:
            fail("UNKNOWN_COMMAND", "Unknown command: " + command)
        sync_progress(state)
        e = event_for(a, t, kind, content, data)
        # Responses are stored before commit so a crash after commit remains retryable.
        response["event"] = e
        if request_key:
            state["requests"][request_key] = {"hash": request_hash, "response": copy.deepcopy(response)}
        committed = s.commit(state, e, artifacts)
        response["event"] = committed
        return response


def run_check(root, data):
    """Execute outside the coordination lock, then validate the same result revision."""
    with Store(root, create=False) as s:
        state = copy.deepcopy(s.state) if s.state else fresh_state()
        a = actor(state, data)
        t = task_for(state, data, a, writable=True)
        name_key = "name" if "name" in data else ("check" if "check" in data else "name")
        name = string(data, name_key, maximum=128)
        if name not in t["checks"]:
            fail("CHECK_NOT_DECLARED", "Only checks explicitly declared at task creation can run")
        d = current_decision(root, t, data)
        spec, baseline = copy.deepcopy(t["checks"][name]), copy.deepcopy(d)
    started = utc()
    output, code = capture_check(spec["argv"], root, spec["timeout"])
    log = redact(output.decode("utf-8", errors="replace"))
    with Store(root, create=False) as s:
        state = copy.deepcopy(s.state)
        a = actor(state, data)
        t = task_for(state, data, a, writable=True)
        d = current_decision(root, t, {"revision": baseline["revision"]})
        if d["digest"] != baseline["digest"] or hashes(root, list(baseline["file_hashes"])) != baseline["file_hashes"]:
            fail("RESULT_CHANGED", "Result changed while check ran; rerun on the new proposal")
        run_id = uid("check")
        log_path = "checkpoints/" + run_id + ".log"
        run = {"id": run_id, "name": name, "agent_id": a["id"], "argv": spec["argv"], "returncode": code,
               "revision": d["revision"], "digest": d["digest"], "file_hashes": d["file_hashes"],
               "started_at": started, "finished_at": utc(), "log_path": ".collab/" + log_path,
               "log_hash": hashlib.sha256(log.encode("utf-8")).hexdigest()}
        t["check_runs"][name] = run
        if code:
            t["approvals"] = {}
        a.update(last_activity=utc(), last_seen_epoch=time.time())
        sync_progress(state)
        e = event_for(a, t, "STATUS" if code == 0 else "ISSUE", f"Check {name} exited {code} on revision {d['revision']}", {"evidence": [run]})
        committed = s.commit(state, e, {log_path: log})
        return {"check": run, "event": committed}
