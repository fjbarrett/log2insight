"""Runtime configuration. Tunables resolve as: environment variable, then the
user's settings.json (written by the menu bar Settings pane), then a built-in
default — so the launchd agent, ad-hoc runs, and the GUI all share one source
of truth. These constants are read once at import; changing settings.json takes
effect the next time the daemon starts (the menu bar restarts it on save)."""

import json
import os
from pathlib import Path

HOME = Path.home()

# Where the database and logs live.
DATA_DIR = Path(os.environ.get("LOG2INSIGHT_DIR", HOME / ".log2insight"))
DB_PATH = Path(os.environ.get("LOG2INSIGHT_DB", DATA_DIR / "activity.db"))
LOG_DIR = DATA_DIR
SETTINGS_PATH = DATA_DIR / "settings.json"


def _load_settings():
    try:
        with open(SETTINGS_PATH) as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


_SETTINGS = _load_settings()


def _tunable(env_key, json_key, default, cast):
    """env var > settings.json > default, coerced through `cast`."""
    if env_key in os.environ:
        try:
            return cast(os.environ[env_key])
        except (TypeError, ValueError):
            pass
    if json_key in _SETTINGS:
        try:
            return cast(_SETTINGS[json_key])
        except (TypeError, ValueError):
            pass
    return cast(default)


# Poll cadence (seconds between cycles) and how often each expensive
# collector runs, expressed in whole cycles.
INTERVAL = _tunable("LOG2INSIGHT_INTERVAL", "interval", 10, float)
NET_EVERY = _tunable("LOG2INSIGHT_NET_EVERY", "net_every", 1, int)
DISK_EVERY = _tunable("LOG2INSIGHT_DISK_EVERY", "disk_every", 6, int)
KNOWLEDGE_EVERY = _tunable("LOG2INSIGHT_KNOWLEDGE_EVERY", "knowledge_every", 30, int)

# Below this many seconds of HID idle, we count you as "active".
IDLE_ACTIVE_THRESHOLD = _tunable(
    "LOG2INSIGHT_IDLE_THRESHOLD", "idle_threshold", 60, float
)

# Apple's Screen Time database (needs Full Disk Access to read).
KNOWLEDGE_DB = HOME / "Library/Application Support/Knowledge/knowledgeC.db"

# Hard cap on any subprocess so a hung helper never freezes the daemon.
SUBPROCESS_TIMEOUT = 15

# launchd identifiers.
AGENT_LABEL = "com.log2insight.agent"
AGENT_PLIST = HOME / "Library/LaunchAgents" / f"{AGENT_LABEL}.plist"

# Optional login item for the menu bar app (separate from the collection agent).
MENUBAR_LABEL = "com.log2insight.menubar"
MENUBAR_PLIST = HOME / "Library/LaunchAgents" / f"{MENUBAR_LABEL}.plist"

# Map a frontmost-app name -> (AppleScript app name, tab expression).
# Only queried when that browser is the frontmost app. Needs Automation
# permission (prompts once per browser).
BROWSER_SCRIPTS = {
    "Safari": ("Safari", "current tab of front window"),
    "Google Chrome": ("Google Chrome", "active tab of front window"),
    "Google Chrome Canary": ("Google Chrome Canary", "active tab of front window"),
    "Brave Browser": ("Brave Browser", "active tab of front window"),
    "Microsoft Edge": ("Microsoft Edge", "active tab of front window"),
    "Arc": ("Arc", "active tab of front window"),
    "Vivaldi": ("Vivaldi", "active tab of front window"),
}
