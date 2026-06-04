"""Frontmost application + focused window title.

Frontmost app comes from `lsappinfo`, which needs NO special permission.
The window title comes from the Accessibility API via System Events, which
DOES require Accessibility permission (and returns "" until granted)."""

import re

from ..util import osa, run

_NAME_RE = re.compile(r'=\s*"(.*)"\s*$')


def frontmost_app():
    """Return the name of the frontmost app, or None."""
    asn = run(["lsappinfo", "front"]).strip()
    if asn:
        info = run(["lsappinfo", "info", "-only", "name", asn])
        for line in info.splitlines():
            m = _NAME_RE.search(line.strip())
            if m and m.group(1):
                return m.group(1)
    # Fallback (needs Automation permission for System Events).
    name = osa(
        "tell application \"System Events\" to get name of first "
        "application process whose frontmost is true"
    )
    return name or None


def window_title():
    """Return the title of the focused window, or None.

    Requires Accessibility permission; returns None until it is granted."""
    title = osa(
        "tell application \"System Events\" to tell (first application "
        "process whose frontmost is true) to get value of attribute "
        "\"AXTitle\" of front window"
    )
    return title or None
