"""Runtime configuration. Everything is overridable via environment variables
so the launchd agent and ad-hoc runs can be tuned without code edits."""

import os
from pathlib import Path

HOME = Path.home()

# Where the database and logs live.
DATA_DIR = Path(os.environ.get("LOG2INSIGHT_DIR", HOME / ".log2insight"))
DB_PATH = Path(os.environ.get("LOG2INSIGHT_DB", DATA_DIR / "activity.db"))
LOG_DIR = DATA_DIR

# Opt-in daily email report: non-secret config in this file, the SMTP app
# password in the macOS Keychain (service below).
EMAIL_CONFIG_PATH = DATA_DIR / "email.json"
KEYCHAIN_SERVICE = "com.log2insight.smtp"

# Poll cadence (seconds between cycles) and how often each expensive
# collector runs, expressed in whole cycles.
INTERVAL = float(os.environ.get("LOG2INSIGHT_INTERVAL", "10"))
NET_EVERY = int(os.environ.get("LOG2INSIGHT_NET_EVERY", "1"))
DISK_EVERY = int(os.environ.get("LOG2INSIGHT_DISK_EVERY", "6"))
KNOWLEDGE_EVERY = int(os.environ.get("LOG2INSIGHT_KNOWLEDGE_EVERY", "30"))

# Below this many seconds of HID idle, we count you as "active".
IDLE_ACTIVE_THRESHOLD = float(os.environ.get("LOG2INSIGHT_IDLE_THRESHOLD", "60"))

# Apple's Screen Time database (needs Full Disk Access to read).
KNOWLEDGE_DB = HOME / "Library/Application Support/Knowledge/knowledgeC.db"

# Hard cap on any subprocess so a hung helper never freezes the daemon.
SUBPROCESS_TIMEOUT = 15

# launchd identifiers.
AGENT_LABEL = "com.log2insight.agent"
AGENT_PLIST = HOME / "Library/LaunchAgents" / f"{AGENT_LABEL}.plist"

# Separate launchd agent that emails the daily report (3pm on weekdays).
EMAILER_LABEL = "com.log2insight.emailer"
EMAILER_PLIST = HOME / "Library/LaunchAgents" / f"{EMAILER_LABEL}.plist"

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
