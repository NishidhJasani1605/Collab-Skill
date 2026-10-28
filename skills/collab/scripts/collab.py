#!/usr/bin/env python3
"""COLLAB's internal JSON CLI. Agents invoke this; users activate the skill."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from collablib.engine import VERSION, execute
from collablib.storage import CollabError, active_collab, canonical_root, find_ancestor_collab

COMMANDS = ["start", "read", "wait", "status", "send", "assignment-add", "claim", "progress", "work-complete",
            "participant-result", "help-request", "help-respond", "help-resolve", "issue", "resolve",
            "finding", "propose", "review", "approve", "check", "finalize", "reserve", "release",
            "file-write", "file-record", "checkpoint", "agent-status", "migrate-nested"]


def discover_root(start):
    here = canonical_root(start)
    collab_roots = []
    nearest_git = None
    for directory in (here, *here.parents):
        if active_collab(directory):
            collab_roots.append(directory)
        if (directory / ".git").exists() and nearest_git is None:
            nearest_git = directory
    if len(collab_roots) > 1:
        raise CollabError("NESTED_WORKSPACE_CONFLICT", "Multiple ancestor collaboration roots exist; preserve them and select the intended root explicitly",
                          {"roots": [str(root) for root in collab_roots]})
    if collab_roots:
        return collab_roots[0]
    if nearest_git is not None:
        return nearest_git
    return here


def output(value):
    print(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    class JsonParser(argparse.ArgumentParser):
        def error(self, message):
            output({"ok": False, "error": {"code": "INVALID_INPUT", "message": message}})
            raise SystemExit(2)
    parser = JsonParser(description="Local COLLAB agent protocol. See the bundled SKILL.md; no daemon or network.")
    parser.add_argument("--root", help="Project directory, otherwise discover nearest .collab/.git ancestor")
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("command", choices=COMMANDS)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--data", help="JSON object (prefer --input to avoid shell quoting)")
    group.add_argument("--input", help="UTF-8 JSON file or '-' for stdin")
    args = parser.parse_args(argv)
    try:
        if args.input:
            if args.input == "-":
                raw = sys.stdin.buffer.read(8*1024*1024+1).decode("utf-8-sig")
            else:
                with open(args.input, "rb") as source:
                    raw = source.read(8*1024*1024+1).decode("utf-8-sig")
        else:
            raw = args.data or "{}"
        if len(raw.encode("utf-8")) > 8*1024*1024:
            raise CollabError("INVALID_INPUT", "JSON input exceeds 8 MiB")
        def reject_constant(value):
            raise ValueError("Non-finite JSON number")
        def unique_keys(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("Duplicate JSON key: " + key)
                result[key] = value
            return result
        data = json.loads(raw, parse_constant=reject_constant, object_pairs_hook=unique_keys)
        if not isinstance(data, dict):
            raise CollabError("INVALID_INPUT", "Input must be a JSON object")
        if "token" not in data and os.environ.get("COLLAB_TOKEN"):
            data["token"] = os.environ["COLLAB_TOKEN"]
        if args.root:
            root = canonical_root(args.root)
            ancestor = find_ancestor_collab(root)
            if ancestor is not None and not (root / ".collab").is_dir():
                root = ancestor
        else:
            root = discover_root(Path.cwd())
        if args.command == "migrate-nested":
            nested = data.get("nested_path") or data.get("nested")
            if not nested:
                raise CollabError("INVALID_INPUT", "Supply 'nested_path' to migrate")
            action = data.get("action", "archive")
            res = execute(root, "migrate-nested", {"nested_path": nested, "action": action})
            output({"ok": True, **res})
            return 0
        read_wait = data.get("wait_seconds", 0) if args.command == "read" else 0
        if type(read_wait) not in (int, float) or not 0 <= read_wait <= 30:
            raise CollabError("INVALID_INPUT", "wait_seconds must be a finite number between 0 and 30")
        if args.command == "read" and read_wait > 0:
            import time
            deadline = time.monotonic() + read_wait
            while True:
                result = execute(root, "read", data, explicit_root=bool(args.root))
                if result.get("events") or time.monotonic() >= deadline:
                    output({"ok": True, **result})
                    return 0
                time.sleep(0.5)
        result = execute(root, args.command, data, explicit_root=bool(args.root))
        output({"ok": True, **result})
        return 0
    except CollabError as exc:
        output({"ok": False, "error": {"code": exc.code, "message": str(exc), "details": getattr(exc, "details", None)}})
        return 2
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        output({"ok": False, "error": {"code": "INVALID_INPUT", "message": str(exc)}})
        return 2
    except OSError as exc:
        output({"ok": False, "error": {"code": "IO_ERROR", "message": str(exc)}})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
