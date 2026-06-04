"""Small subprocess helpers. Every external command is wrapped so a failure
or hang degrades to an empty result instead of crashing the daemon."""

import subprocess

from .config import SUBPROCESS_TIMEOUT


def run(cmd, timeout=SUBPROCESS_TIMEOUT):
    """Run a command, return stdout (str). Returns "" on any failure."""
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return proc.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def osa(script, timeout=5):
    """Run a one-line AppleScript via osascript and return trimmed stdout."""
    return run(["osascript", "-e", script], timeout=timeout).strip()


def to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def humanize_bytes(n):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024.0:
            return f"{n:,.1f} {unit}"
        n /= 1024.0
    return f"{n:,.1f} PB"


def humanize_seconds(s):
    s = int(s or 0)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {sec}s"
    return f"{sec}s"
