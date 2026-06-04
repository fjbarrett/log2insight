"""Human Interface Device idle time — seconds since the last keyboard/mouse
input. Used to distinguish "app was frontmost" from "I was actually there."
Needs no special permission."""

from ..util import run


def idle_seconds():
    out = run(["ioreg", "-c", "IOHIDSystem"])
    for line in out.splitlines():
        if "HIDIdleTime" in line:
            try:
                # ...  "HIDIdleTime" = 12345678901 ;  (nanoseconds)
                raw = line.split("=", 1)[1].strip().strip(";").strip()
                return int(raw) / 1_000_000_000
            except (ValueError, IndexError):
                continue
    return 0.0
