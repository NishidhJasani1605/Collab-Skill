"""Serialized, recoverable filesystem persistence for cooperating local agents.

The lock inode is permanent. All readers and writers must use Store. A durable
redo record precedes the authoritative append, then replaceable projections.
Recovery completes only an exact, checksummed transaction; it never truncates
unknown bytes. This is a same-user cooperative protocol, not an OS sandbox.
Directory fsync is supported on POSIX; Windows power-loss durability depends on
the filesystem. Network filesystems and malicious concurrent path substitution
are outside the supported trust model.
"""

from __future__ import annotations

import copy
import errno
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import stat
import time
from datetime import datetime, timezone
import uuid


PROTOCOL_VERSION = 1
ZERO_HASH = "0" * 64
MISSING = "missing"


class CollabError(Exception):
    """A stable machine-readable error, with optional structured details."""

    def __init__(self, code: str, message: str = "", details=None):
        self.code = code
        self.details = details
        super().__init__(message or code)


def _json(value) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError) as exc:
        raise CollabError("INVALID_JSON", "Value must be valid UTF-8 JSON") from exc


def _digest(value) -> str:
    return hashlib.sha256(_json(value)).hexdigest()


def _decode(raw: bytes, description: str):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                          parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    except (ValueError, UnicodeError) as exc:
        raise CollabError("CORRUPT_STORAGE", f"Invalid JSON in {description}; data preserved") from exc


def _is_link(info) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _inspect(path: Path, *, directory: bool | None = None):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if _is_link(info):
        raise CollabError("UNSAFE_PATH", f"Symlink or reparse point refused: {path}")
    if directory is True and not stat.S_ISDIR(info.st_mode):
        raise CollabError("UNSAFE_PATH", f"Expected directory: {path}")
    if directory is False:
        if not stat.S_ISREG(info.st_mode):
            raise CollabError("UNSAFE_PATH", f"Expected regular file: {path}")
        if info.st_nlink != 1:
            raise CollabError("UNSAFE_PATH", f"Hard-linked file refused: {path}")
    return info


def _parts(relative) -> tuple[str, ...]:
    if not isinstance(relative, (str, os.PathLike)):
        raise CollabError("UNSAFE_PATH", "Path must be a relative string")
    value = os.fspath(relative)
    if not isinstance(value, str) or not value or "\x00" in value:
        raise CollabError("UNSAFE_PATH", "Empty or invalid path")
    # Interpret both separators consistently on every supported OS. Reject
    # drive-relative paths and NTFS alternate streams even when running Unix.
    windows = PureWindowsPath(value)
    if windows.drive or windows.root or PurePosixPath(value).is_absolute():
        raise CollabError("UNSAFE_PATH", "Absolute or drive-relative paths are not allowed")
    parts = value.replace("\\", "/").split("/")
    devices = {"CON", "PRN", "AUX", "NUL"} | {
        f"{prefix}{n}" for prefix in ("COM", "LPT") for n in list(range(1, 10)) + ["¹", "²", "³"]}
    for part in parts:
        if (part in ("", ".", "..") or any(c in part for c in ':<>"|?*')
                or any(ord(c) < 32 for c in part) or part.endswith((" ", "."))
                or part.split(".")[0].upper() in devices):
            raise CollabError("UNSAFE_PATH", "Unsafe relative path component")
    return tuple(parts)


def _root(root) -> Path:
    try:
        result = Path(root).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise CollabError("INVALID_ROOT", "Project root must already exist") from exc
    if not result.is_dir():
        raise CollabError("INVALID_ROOT", "Project root must be a directory")
    return result


def safe_project_path(root, relative, allow_missing=True) -> Path:
    """Validate a project path without following links or reserved metadata."""
    base = _root(root)
    parts = _parts(relative)
    if any(part.casefold() in (".git", ".collab") for part in parts):
        raise CollabError("UNSAFE_PATH", "Project metadata paths are reserved")
    path = base
    for index, part in enumerate(parts):
        path = path / part
        info = _inspect(path, directory=True if index < len(parts) - 1 else None)
        if info is not None and index == len(parts) - 1:
            if not stat.S_ISREG(info.st_mode):
                raise CollabError("UNSAFE_PATH", "Project target must be a regular file")
            if info.st_nlink != 1:
                raise CollabError("UNSAFE_PATH", "Hard-linked project files are not supported")
        if info is None and not allow_missing:
            raise CollabError("MISSING_ARTIFACT", f"Project file does not exist: {relative}")
    return path


def _open(path: Path, flags: int, mode=0o600) -> int:
    _inspect(path, directory=False)
    flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    fd = os.open(path, flags, mode)
    try:
        actual = os.fstat(fd)
        current = _inspect(path, directory=False)
        if current is None or not os.path.samestat(actual, current) or actual.st_nlink != 1:
            raise CollabError("UNSAFE_PATH", f"Path changed while opening: {path}")
        return fd
    except BaseException:
        os.close(fd)
        raise


def fingerprint(path) -> str:
    """SHA-256 of a regular file, or the literal 'missing'."""
    path = Path(path)
    if _inspect(path, directory=False) is None:
        return MISSING
    fd = _open(path, os.O_RDONLY)
    with os.fdopen(fd, "rb") as stream:
        digest = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
        return digest.hexdigest()


def _fsync_dir(path: Path):
    if os.name != "nt":
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _crash(stage):
    # Deliberately opt-in fault injection, used only by subprocess tests. Never
    # set COLLAB_TEST_CRASH in normal use. os._exit simulates abrupt process death.
    if os.environ.get("COLLAB_TEST_CRASH") == stage:
        os._exit(91)


class Store:
    """Context-managed exclusive transaction; never read projections unlocked."""

    def __init__(self, root, timeout=30, *, create=True):
        self.root = _root(root)
        self.path = self.root / ".collab"
        self.create = create
        self.timeout = float(timeout)
        if not math.isfinite(self.timeout) or self.timeout < 0:
            raise CollabError("INVALID_TIMEOUT", "Lock timeout must be finite and nonnegative")
        self.state = {}
        self.events = []
        self._lock_fd = None
        self._locked = False
        self._raw = b""

    def _runtime(self, relative, *, create_parents=False) -> Path:
        parts = _parts(relative)
        _inspect(self.path, directory=True)
        path = self.path
        for part in parts[:-1]:
            path /= part
            if _inspect(path, directory=True) is None and create_parents:
                try:
                    path.mkdir(mode=0o700)
                    _fsync_dir(path.parent)
                except FileExistsError:
                    pass
                _inspect(path, directory=True)
        path /= parts[-1]
        _inspect(path, directory=False)
        return path

    def _read(self, relative) -> bytes | None:
        path = self._runtime(relative)
        try:
            fd = _open(path, os.O_RDONLY)
        except FileNotFoundError:
            return None
        with os.fdopen(fd, "rb") as stream:
            return stream.read()

    def read_artifact(self, relative) -> bytes | None:
        """Read a runtime artifact under the lock with normal path safeguards."""
        if not self._locked:
            raise CollabError("LOCK_REQUIRED", "Use Store as a context manager")
        return self._read(relative)

    def _atomic(self, relative, data: bytes):
        path = self._runtime(relative, create_parents=True)
        temporary = path.with_name(".tmp-" + uuid.uuid4().hex)
        fd = _open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            self._runtime(relative)
            os.replace(temporary, path)
            _fsync_dir(path.parent)
        finally:
            if temporary.exists():
                temporary.unlink()

    def __enter__(self):
        if self._lock_fd is not None:
            raise CollabError("INVALID_OPERATION", "Store context cannot be entered twice")
        if _inspect(self.path, directory=True) is None:
            if not self.create:
                raise CollabError("NOT_INITIALIZED", "Start collaboration explicitly before using this project")
            try:
                self.path.mkdir(mode=0o700)
                _fsync_dir(self.root)
            except FileExistsError:
                pass
        _inspect(self.path, directory=True)
        self._lock_fd = _open(self._runtime(".lock"), os.O_RDWR | os.O_CREAT)
        deadline = time.monotonic() + self.timeout
        try:
            while True:
                try:
                    if os.name == "nt":
                        import msvcrt
                        os.lseek(self._lock_fd, 0, os.SEEK_SET)
                        msvcrt.locking(self._lock_fd, msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self._locked = True
                    break
                except OSError as exc:
                    if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                        raise
                    if time.monotonic() >= deadline:
                        raise CollabError("LOCK_TIMEOUT", "Another local helper holds the workspace lock") from exc
                    time.sleep(min(0.025, max(0, deadline - time.monotonic())))
            # Validate the same persistent inode after acquisition. A replaced
            # lock cannot safely authorize writes to the workspace.
            info = _inspect(self._runtime(".lock"), directory=False)
            if info is None or not os.path.samestat(os.fstat(self._lock_fd), info):
                raise CollabError("UNSAFE_PATH", "Workspace lock was replaced")
            self._load()
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *_):
        if self._lock_fd is not None:
            try:
                if self._locked:
                    if os.name == "nt":
                        import msvcrt
                        os.lseek(self._lock_fd, 0, os.SEEK_SET)
                        msvcrt.locking(self._lock_fd, msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            finally:
                os.close(self._lock_fd)
                self._lock_fd = None
                self._locked = False

    def _parse_events(self, raw):
        if raw and not raw.endswith(b"\n"):
            raise CollabError("CORRUPT_STORAGE", "Incomplete chat append without matching recovery journal; data preserved")
        result, identifiers, previous = [], set(), ZERO_HASH
        for seq, line in enumerate(raw.splitlines(), 1):
            event = _decode(line, f"GROUP_CHAT.jsonl line {seq}")
            if not isinstance(event, dict):
                raise CollabError("CORRUPT_STORAGE", "Chat events must be JSON objects")
            claimed = event.get("hash")
            bare = {key: value for key, value in event.items() if key != "hash"}
            identifier = event.get("id")
            if (event.get("seq") != seq or isinstance(event.get("seq"), bool)
                    or event.get("protocol_version") != PROTOCOL_VERSION
                    or event.get("prev_hash") != previous or claimed != _digest(bare)
                    or not isinstance(identifier, str) or not identifier or identifier in identifiers):
                raise CollabError("CORRUPT_STORAGE", f"Chat integrity failed at sequence {seq}; data preserved")
            identifiers.add(identifier)
            result.append(event)
            previous = claimed
        return result

    def _checkpoint(self, state, events):
        bare = {"protocol_version": PROTOCOL_VERSION, "state": state,
                "seq": len(events), "event_hash": events[-1]["hash"] if events else ZERO_HASH}
        return dict(bare, checksum=_digest(bare))

    def _read_checkpoint(self):
        raw = self._read("checkpoints/state.json")
        if raw is None:
            return None
        envelope = _decode(raw, "state checkpoint")
        if not isinstance(envelope, dict):
            raise CollabError("CORRUPT_STORAGE", "Invalid state checkpoint")
        bare = {key: value for key, value in envelope.items() if key != "checksum"}
        if (envelope.get("checksum") != _digest(bare)
                or envelope.get("protocol_version") != PROTOCOL_VERSION
                or not isinstance(envelope.get("state"), dict)):
            raise CollabError("CORRUPT_STORAGE", "State checksum failed; data preserved")
        return envelope

    def _validate_checkpoint(self, checkpoint, events):
        if checkpoint is None:
            if events:
                raise CollabError("CORRUPT_STORAGE", "Missing state checkpoint; data preserved")
            return {}
        expected_hash = events[-1]["hash"] if events else ZERO_HASH
        if checkpoint.get("seq") != len(events) or checkpoint.get("event_hash") != expected_hash:
            raise CollabError("CORRUPT_STORAGE", "Checkpoint and chat disagree; data preserved")
        state = checkpoint["state"]
        if events and events[-1].get("state_hash") != _digest(state):
            raise CollabError("CORRUPT_STORAGE", "State does not match committed chat event; data preserved")
        return state

    def _load(self):
        # The WAL is inspected before parsing a potentially interrupted append.
        journal = self._read("checkpoints/pending.json")
        if journal is not None:
            transaction = _decode(journal, "pending journal")
            if not isinstance(transaction, dict):
                raise CollabError("CORRUPT_STORAGE", "Invalid pending journal")
            bare = {key: value for key, value in transaction.items() if key != "checksum"}
            if transaction.get("checksum") != _digest(bare):
                raise CollabError("CORRUPT_STORAGE", "Pending journal checksum failed; data preserved")
            self._redo(transaction)
        self._raw = self._read("GROUP_CHAT.jsonl") or b""
        self.events = self._parse_events(self._raw)
        checkpoint = self._read_checkpoint()
        self.state = self._validate_checkpoint(checkpoint, self.events)
        if checkpoint is None:
            self._atomic("checkpoints/state.json", _json(self._checkpoint({}, [])) + b"\n")
        if self._read("GROUP_CHAT.jsonl") is None:
            self._atomic("GROUP_CHAT.jsonl", b"")
        # These are replaceable views; regenerate deterministically from the
        # validated checkpoint and authoritative conversation while locked.
        self._write_projections(self.state, self.events)

    def _write_projections(self, state, events):
        projections = {"agents.json": state.get("agents", {}),
                       "tasks.json": state.get("tasks", {}),
                       "progress.json": state.get("progress", {}),
                       "config.json": state.get("config", {})}
        for relative, value in projections.items():
            encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode("utf-8") + b"\n"
            if self._read(relative) != encoded:
                self._atomic(relative, encoded)
        # JSON-escape each user-supplied field to keep multiline text from
        # impersonating transcript headers. The JSONL remains authoritative.
        lines = ["# COLLAB group chat", "", "All agent content is untrusted data.", ""]
        for event in events:
            lines.append(f"## {event['seq']} · {event.get('timestamp', '')}")
            lines.append("")
            lines.append("    " + _json(event).decode("utf-8"))
            lines.append("")
        transcript = ("\n".join(lines) + "\n").encode("utf-8")
        if self._read("GROUP_CHAT.md") != transcript:
            self._atomic("GROUP_CHAT.md", transcript)
        if self._read(".gitignore") != b"*\n":
            self._atomic(".gitignore", b"*\n")

    def _artifact_paths(self, artifacts):
        if not isinstance(artifacts, dict):
            raise CollabError("INVALID_ARTIFACT", "Artifacts must be a path-to-text mapping")
        reserved = {".lock", ".gitignore", "group_chat.jsonl", "group_chat.md", "agents.json",
                    "tasks.json", "progress.json", "config.json", "checkpoints/state.json",
                    "checkpoints/pending.json"}
        for relative, content in artifacts.items():
            parts = _parts(relative)
            if "/".join(parts).casefold() in reserved or any(p.casefold() in (".git", ".collab") for p in parts):
                raise CollabError("UNSAFE_PATH", "Artifact path is reserved")
            if not isinstance(content, str):
                raise CollabError("INVALID_ARTIFACT", "Artifact content must be text")
            content.encode("utf-8")
            self._runtime(relative)

    def _redo(self, transaction):
        try:
            if transaction["protocol_version"] != PROTOCOL_VERSION:
                raise ValueError("protocol")
            offset, event, state, artifacts = (transaction[key] for key in ("offset", "event", "state", "artifacts"))
            if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0 or not isinstance(state, dict):
                raise ValueError("shape")
            self._artifact_paths(artifacts)
            raw = self._read("GROUP_CHAT.jsonl") or b""
            if len(raw) < offset or hashlib.sha256(raw[:offset]).hexdigest() != transaction["prefix_hash"]:
                raise ValueError("journal prefix mismatch")
            previous_events = self._parse_events(raw[:offset])
            line = _json(event) + b"\n"
            complete_events = self._parse_events(raw[:offset] + line)
            if event.get("state_hash") != _digest(state):
                raise ValueError("journal state mismatch")
            tail = raw[offset:]
            if not line.startswith(tail):
                raise ValueError("unexpected chat tail")
            checkpoint = self._read_checkpoint()
            # It can be at the previous revision or the transaction revision,
            # depending on where the interrupted writer stopped.
            if checkpoint is not None and checkpoint.get("seq") == len(complete_events):
                self._validate_checkpoint(checkpoint, complete_events)
            else:
                self._validate_checkpoint(checkpoint, previous_events)
            path = self._runtime("GROUP_CHAT.jsonl")
            if len(tail) < len(line):
                fd = _open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND)
                with os.fdopen(fd, "ab") as stream:
                    remaining = line[len(tail):]
                    if os.environ.get("COLLAB_TEST_CRASH") == "partial_event":
                        stream.write(remaining[:max(1, len(remaining) // 2)])
                        stream.flush()
                        os.fsync(stream.fileno())
                        _crash("partial_event")
                    stream.write(remaining)
                    stream.flush()
                    os.fsync(stream.fileno())
                _fsync_dir(path.parent)
            _crash("after_event")
            self._atomic("checkpoints/state.json", _json(self._checkpoint(state, complete_events)) + b"\n")
            _crash("after_state")
            for relative, content in artifacts.items():
                self._atomic(relative, content.encode("utf-8"))
            self._write_projections(state, complete_events)
            _crash("after_projections")
            _crash("before_clear")
            pending = self._runtime("checkpoints/pending.json")
            pending.unlink()
            _fsync_dir(pending.parent)
            self.state, self.events, self._raw = copy.deepcopy(state), complete_events, raw[:offset] + line
        except (KeyError, TypeError, ValueError) as exc:
            raise CollabError("CORRUPT_STORAGE", f"Recovery journal mismatch ({exc}); data preserved") from exc

    def commit(self, state, event, artifacts=None):
        """Durably commit one event and its complete next state while locked."""
        if not self._locked:
            raise CollabError("LOCK_REQUIRED", "Use Store as a context manager")
        if not isinstance(state, dict) or not isinstance(event, dict):
            raise CollabError("INVALID_JSON", "State and event must be objects")
        state, event = copy.deepcopy(state), copy.deepcopy(event)
        artifacts = copy.deepcopy(artifacts or {})
        self._artifact_paths(artifacts)
        if self._read("checkpoints/pending.json") is not None:
            raise CollabError("RECOVERY_REQUIRED", "Reopen Store to recover the pending transaction")
        # Detect uncooperative mutation between load and commit, rather than
        # overwriting or accepting an unknown externally changed revision.
        if (self._read("GROUP_CHAT.jsonl") or b"") != self._raw:
            raise CollabError("CORRUPT_STORAGE", "Chat changed outside the workspace lock")
        self._validate_checkpoint(self._read_checkpoint(), self.events)
        defaults = {"seq": len(self.events) + 1, "id": uuid.uuid4().hex,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "protocol_version": PROTOCOL_VERSION,
                    "prev_hash": self.events[-1]["hash"] if self.events else ZERO_HASH,
                    "state_hash": _digest(state)}
        for key, value in defaults.items():
            if key in event and key not in ("id", "timestamp") and event[key] != value:
                raise CollabError("INVALID_EVENT", f"Invalid reserved event field: {key}")
            event.setdefault(key, value)
        if (not isinstance(event["id"], str) or not event["id"]
                or not isinstance(event["timestamp"], str) or not event["timestamp"]):
            raise CollabError("INVALID_EVENT", "Event ID and timestamp must be nonempty strings")
        bare = {key: value for key, value in event.items() if key != "hash"}
        expected = _digest(bare)
        if event.get("hash", expected) != expected:
            raise CollabError("INVALID_EVENT", "Invalid event hash")
        event["hash"] = expected
        # Validate before writing a WAL, including duplicate IDs and ordering.
        self._parse_events(self._raw + _json(event) + b"\n")
        transaction = {"protocol_version": PROTOCOL_VERSION, "offset": len(self._raw),
                       "prefix_hash": hashlib.sha256(self._raw).hexdigest(),
                       "event": event, "state": state, "artifacts": artifacts}
        transaction["checksum"] = _digest(transaction)
        self._atomic("checkpoints/pending.json", _json(transaction) + b"\n")
        _crash("after_wal")
        self._redo(transaction)
        return copy.deepcopy(event)
