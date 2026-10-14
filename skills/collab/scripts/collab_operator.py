#!/usr/bin/env python3
"""Human-operated, interactive membership recovery for cooperative local teams.

No JSON approval flag, piped confirmation, or agent token is accepted. A local
terminal cannot prove personhood against malicious processes with the same OS
permissions; this is an explicit human handoff within the cooperative model.
"""
from __future__ import annotations

import argparse
import copy
import secrets
import sys

sys.dont_write_bytecode = True
from collablib.engine import digest, invalidate, public_agent, uid, utc
from collablib.storage import CollabError, Store


def membership_change(state, task_id, removed, replacement, reason):
    """Validate a proposed change without persisting it. Only main commits."""
    updated = copy.deepcopy(state)
    t = updated.get("tasks", {}).get(task_id)
    if not t or t["status"] == "TEAM_COMPLETE":
        raise CollabError("INVALID_TASK", "Select an unfinished task")
    if removed not in t["required_participants"]:
        raise CollabError("INVALID_PARTICIPANT", "The departing participant must be required")
    if replacement and (replacement not in t["participants"] or replacement == removed):
        raise CollabError("INVALID_REPLACEMENT", "Replacement must be another registered task participant")
    unresolved = [i for i in t["issues"].values() if i["status"] == "OPEN" and i.get("resolution_owner", i["author"]) == removed]
    unresolved += [h for h in t["help"].values() if h["status"] != "RESOLVED" and h.get("resolution_owner", h["requester"]) == removed]
    if unresolved and not replacement:
        raise CollabError("REPLACEMENT_REQUIRED", "Open issues/help need an explicit replacement to verify resolution")
    if len(t["required_participants"]) == 1 and not replacement:
        raise CollabError("EMPTY_TEAM", "Cannot exclude the final required participant")
    t["required_participants"].remove(removed)
    if replacement and replacement not in t["required_participants"]:
        t["required_participants"].append(replacement)
    for item in t["assignments"].values():
        if item["owner"] == removed and item["status"] != "WORK_COMPLETE":
            item.update(owner=replacement, status="WORKING" if replacement else "OPEN", percent=0)
    for item in unresolved:
        item["resolution_owner"] = replacement
    for reservation in updated["reservations"].values():
        if reservation["task_id"] == task_id and reservation["agent_id"] == removed and not reservation["released"]:
            reservation.update(released=True, release_reason="operator membership recovery")
    entry = {"removed": removed, "replacement": replacement, "reason": reason,
             "timestamp": utc(), "authorization": "interactive local operator confirmation"}
    t.setdefault("membership_history", []).append(entry)
    invalidate(t, "Operator changed required membership")
    return updated, entry


def main(argv=None):
    parser = argparse.ArgumentParser(description="User-only recovery: replace or exclude a required COLLAB participant. Agents must hand this command to the human.")
    parser.add_argument("--root", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--exclude", required=True, help="Required participant's agent ID")
    parser.add_argument("--replacement", help="Existing participant to take over unfinished responsibilities")
    parser.add_argument("--reason", required=True)
    args = parser.parse_args(argv)
    try:
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            raise CollabError("HUMAN_TERMINAL_REQUIRED", "Run this yourself in an interactive terminal; piped approval is refused")
        if not args.reason.strip() or len(args.reason) > 4000:
            raise CollabError("INVALID_REASON", "Provide a concise, nonempty reason")
        with Store(args.root) as store:
            baseline = digest(store.state)
            proposed, audit = membership_change(store.state, args.task, args.exclude, args.replacement, args.reason)
            task = store.state["tasks"][args.task]
            print("Task:", task["objective"])
            print("Departing participant:", public_agent(store.state["agents"][args.exclude]))
            print("Replacement:", args.replacement or "None; unfinished assignments remain required and become unclaimed")
            print("Reason:", args.reason)
            print("This restarts review and invalidates approvals. It does not waive checks or blockers.")
        challenge = "CONFIRM " + secrets.token_hex(4).upper()
        print("Type exactly", challenge, "to apply the displayed change:")
        if input().strip() != challenge:
            raise CollabError("CANCELLED", "Membership change cancelled")
        with Store(args.root) as store:
            if digest(store.state) != baseline:
                raise CollabError("STATE_CHANGED", "Team state changed while confirming; inspect and rerun")
            e = {"id": uid("msg"), "agent_id": "local-operator", "agent_name": "Local operator", "platform": "terminal",
                 "model": "not-applicable", "session_id": uid("operator"), "task_id": args.task, "type": "DECISION",
                 "content": "Operator changed required membership: " + args.reason, "evidence": [audit],
                 "recipient": None, "reply_to": None, "files": [], "protocol_version": 1, "timestamp": utc()}
            store.commit(proposed, e)
        print("Membership updated. The task remains open and needs a new review round.")
        return 0
    except (CollabError, EOFError, KeyboardInterrupt) as exc:
        print(f"{getattr(exc, 'code', 'CANCELLED')}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
