"""Bounded capture for finite, explicitly declared validation commands."""
import os
import signal
import subprocess
import threading

OUTPUT_LIMIT = 64000


def stop_process(process):
    if os.name == "nt":
        if process.poll() is None:
            try:
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
            except (OSError, subprocess.TimeoutExpired):
                pass
            if process.poll() is None:
                process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait(timeout=5)


def capture_check(argv, root, timeout):
    """Drain output continuously but retain at most OUTPUT_LIMIT bytes in memory."""
    env = {k: v for k, v in os.environ.items()
           if k != "COLLAB_TOKEN" and not k.startswith("COLLAB_TEST_")}
    try:
        process = subprocess.Popen(
            argv, cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, env=env, shell=False,
            start_new_session=os.name != "nt",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    except OSError as exc:
        return str(exc).encode("utf-8")[:OUTPUT_LIMIT], 127
    captured = bytearray()
    truncated = False
    read_failed = False

    def drain():
        nonlocal truncated, read_failed
        try:
            with process.stdout:
                while True:
                    chunk = process.stdout.read1(8192)
                    if not chunk:
                        break
                    remaining = OUTPUT_LIMIT - len(captured)
                    captured.extend(chunk[:remaining])
                    truncated |= len(chunk) > remaining
        except OSError:
            read_failed = True

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    suffix = b""
    try:
        code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        stop_process(process)
        code, suffix = 124, b"\nCOLLAB: check timed out"
    except BaseException:
        stop_process(process)
        raise
    reader.join(timeout=1)
    if reader.is_alive():
        # A descendant retained stdout after the command exited. Fail closed;
        # checks must be finite commands, not service launchers.
        stop_process(process)
        reader.join(timeout=1)
        code, suffix = 124, b"\nCOLLAB: check left an open output stream"
    if read_failed:
        code, suffix = 125, b"\nCOLLAB: check output could not be read"
    if truncated:
        suffix += b"\n[output truncated]"
    return bytes(captured) + suffix, code
