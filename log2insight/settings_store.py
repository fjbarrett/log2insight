"""Read/write the user-editable tunables in ~/.log2insight/settings.json.

This is the write-side companion to the `_tunable()` layering in `config.py`.
The menu bar Settings pane reads `load()`, edits, then `save()`s; the daemon
picks the new values up the next time it starts. One schema (`FIELDS`) drives
both the form and validation so the two never drift.
"""

import json

from . import config

# (key, label, cast, default, minimum, help)
FIELDS = [
    ("interval", "Poll interval", float, 10, 1,
     "Seconds between collection cycles."),
    ("net_every", "Network every N cycles", int, 1, 1,
     "Sample per-process network I/O once every N cycles."),
    ("disk_every", "Disk every N cycles", int, 6, 1,
     "Sample disk throughput once every N cycles."),
    ("knowledge_every", "Screen Time every N cycles", int, 30, 1,
     "Import Apple Screen Time history once every N cycles."),
    ("idle_threshold", "Idle threshold", float, 60, 1,
     "Idle seconds before you're counted as inactive."),
]


def _coerce(cast, value, default, minimum):
    try:
        out = cast(value)
    except (TypeError, ValueError):
        out = cast(default)
    return cast(minimum) if out < minimum else out


def load():
    """Current settings as a dict, defaults filled in for anything missing."""
    try:
        with open(config.SETTINGS_PATH) as fh:
            raw = json.load(fh)
        if not isinstance(raw, dict):
            raw = {}
    except (OSError, ValueError):
        raw = {}
    return {
        key: _coerce(cast, raw.get(key, default), default, minimum)
        for key, _label, cast, default, minimum, _help in FIELDS
    }


def save(values):
    """Validate `values` against FIELDS and write settings.json. Returns the
    cleaned dict that was persisted."""
    clean = {
        key: _coerce(cast, values.get(key, default), default, minimum)
        for key, _label, cast, default, minimum, _help in FIELDS
    }
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.SETTINGS_PATH, "w") as fh:
        json.dump(clean, fh, indent=2)
        fh.write("\n")
    return clean
