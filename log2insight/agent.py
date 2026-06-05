"""Install / remove the launchd agent so the daemon runs in the background
and survives logout and reboot."""

import plistlib
import subprocess
import sys

from . import config


def _plist_dict():
    return {
        "Label": config.AGENT_LABEL,
        "ProgramArguments": [sys.executable, "-m", "log2insight", "run"],
        "RunAtLoad": True,
        "KeepAlive": True,
        "ProcessType": "Background",
        "EnvironmentVariables": {
            "LOG2INSIGHT_DIR": str(config.DATA_DIR),
        },
        "StandardOutPath": str(config.LOG_DIR / "agent.out.log"),
        "StandardErrorPath": str(config.LOG_DIR / "agent.err.log"),
    }


def install():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.AGENT_PLIST.parent.mkdir(parents=True, exist_ok=True)
    with open(config.AGENT_PLIST, "wb") as fh:
        plistlib.dump(_plist_dict(), fh)

    # Reload cleanly if it was already loaded.
    subprocess.run(
        ["launchctl", "unload", str(config.AGENT_PLIST)],
        capture_output=True, check=False,
    )
    result = subprocess.run(
        ["launchctl", "load", "-w", str(config.AGENT_PLIST)],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return False, result.stderr.strip() or "launchctl load failed"
    return True, f"Installed and loaded {config.AGENT_LABEL}"


def uninstall():
    subprocess.run(
        ["launchctl", "unload", str(config.AGENT_PLIST)],
        capture_output=True, check=False,
    )
    if config.AGENT_PLIST.exists():
        config.AGENT_PLIST.unlink()
    return True, f"Unloaded and removed {config.AGENT_LABEL}"


def restart():
    """Reload the collection agent so it re-reads settings.json on next start.
    Installs it first if it isn't present yet."""
    if not config.AGENT_PLIST.exists():
        return install()
    subprocess.run(
        ["launchctl", "unload", str(config.AGENT_PLIST)],
        capture_output=True, check=False,
    )
    result = subprocess.run(
        ["launchctl", "load", "-w", str(config.AGENT_PLIST)],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return False, result.stderr.strip() or "launchctl load failed"
    return True, "Reloaded collection agent"


def is_loaded():
    result = subprocess.run(
        ["launchctl", "list"], capture_output=True, text=True, check=False,
    )
    return config.AGENT_LABEL in result.stdout


# --- Optional: run the menu bar app itself as a login item ---------------

def _menubar_plist_dict():
    return {
        "Label": config.MENUBAR_LABEL,
        "ProgramArguments": [sys.executable, "-m", "log2insight", "menubar"],
        "RunAtLoad": True,
        # No KeepAlive: quitting from the menu should stick until next login.
        "ProcessType": "Interactive",
        "EnvironmentVariables": {
            "LOG2INSIGHT_DIR": str(config.DATA_DIR),
        },
        "StandardOutPath": str(config.LOG_DIR / "menubar.out.log"),
        "StandardErrorPath": str(config.LOG_DIR / "menubar.err.log"),
    }


def install_menubar():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.MENUBAR_PLIST.parent.mkdir(parents=True, exist_ok=True)
    with open(config.MENUBAR_PLIST, "wb") as fh:
        plistlib.dump(_menubar_plist_dict(), fh)
    subprocess.run(
        ["launchctl", "unload", str(config.MENUBAR_PLIST)],
        capture_output=True, check=False,
    )
    result = subprocess.run(
        ["launchctl", "load", "-w", str(config.MENUBAR_PLIST)],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return False, result.stderr.strip() or "launchctl load failed"
    return True, f"Installed {config.MENUBAR_LABEL} — menu bar app launches at login."


def uninstall_menubar():
    subprocess.run(
        ["launchctl", "unload", str(config.MENUBAR_PLIST)],
        capture_output=True, check=False,
    )
    if config.MENUBAR_PLIST.exists():
        config.MENUBAR_PLIST.unlink()
    return True, f"Unloaded and removed {config.MENUBAR_LABEL}"


def menubar_is_loaded():
    result = subprocess.run(
        ["launchctl", "list"], capture_output=True, text=True, check=False,
    )
    return config.MENUBAR_LABEL in result.stdout


# --- Optional: a separate agent that emails the daily report -----------------

def _emailer_plist_dict():
    return {
        "Label": config.EMAILER_LABEL,
        "ProgramArguments": [sys.executable, "-m", "log2insight", "email-report"],
        # 3pm, Monday–Friday (Weekday: 1=Mon … 5=Fri). One run per matching day.
        "StartCalendarInterval": [
            {"Hour": 15, "Minute": 0, "Weekday": wd} for wd in (1, 2, 3, 4, 5)
        ],
        "RunAtLoad": False,
        "ProcessType": "Background",
        "EnvironmentVariables": {
            "LOG2INSIGHT_DIR": str(config.DATA_DIR),
        },
        "StandardOutPath": str(config.LOG_DIR / "emailer.out.log"),
        "StandardErrorPath": str(config.LOG_DIR / "emailer.err.log"),
    }


def install_emailer():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.EMAILER_PLIST.parent.mkdir(parents=True, exist_ok=True)
    with open(config.EMAILER_PLIST, "wb") as fh:
        plistlib.dump(_emailer_plist_dict(), fh)
    subprocess.run(
        ["launchctl", "unload", str(config.EMAILER_PLIST)],
        capture_output=True, check=False,
    )
    result = subprocess.run(
        ["launchctl", "load", "-w", str(config.EMAILER_PLIST)],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return False, result.stderr.strip() or "launchctl load failed"
    return True, (
        f"Installed {config.EMAILER_LABEL} — emails the prior weekday's "
        "report at 3pm, Mon–Fri."
    )


def uninstall_emailer():
    subprocess.run(
        ["launchctl", "unload", str(config.EMAILER_PLIST)],
        capture_output=True, check=False,
    )
    if config.EMAILER_PLIST.exists():
        config.EMAILER_PLIST.unlink()
    return True, f"Unloaded and removed {config.EMAILER_LABEL}"


def emailer_is_loaded():
    result = subprocess.run(
        ["launchctl", "list"], capture_output=True, text=True, check=False,
    )
    return config.EMAILER_LABEL in result.stdout
