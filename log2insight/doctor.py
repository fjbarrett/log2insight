"""Pre-flight checks: which collectors will work right now, and which need a
permission you must grant in System Settings → Privacy & Security."""

import shutil

from . import config
from .collectors import frontmost, knowledge, network


def _check(name, ok, detail):
    mark = "✓" if ok else "✗"
    return f"  {mark}  {name:<22} {detail}"


def run_checks():
    lines = ["log2insight doctor — collector readiness", ""]

    # Tools on PATH (all ship with macOS, but check anyway).
    for tool in ("lsappinfo", "nettop", "ioreg", "iostat", "osascript", "launchctl"):
        lines.append(_check(
            tool, shutil.which(tool) is not None,
            "found on PATH" if shutil.which(tool) else "MISSING from PATH",
        ))

    lines.append("")

    # Frontmost app (no permission needed).
    app = frontmost.frontmost_app()
    lines.append(_check(
        "frontmost app", bool(app),
        f"reading '{app}'" if app else "could not read frontmost app",
    ))

    # Window title (needs Accessibility).
    title = frontmost.window_title()
    lines.append(_check(
        "window title", bool(title),
        f"reading '{title[:40]}'" if title
        else "empty — grant Accessibility (and Screen Recording on Sequoia+)",
    ))

    # Network (no permission needed).
    net = network.network_samples()
    lines.append(_check(
        "network I/O", bool(net),
        f"{len(net)} processes sampled" if net else "no samples returned",
    ))

    # Apple Screen Time (needs Full Disk Access).
    exists = config.KNOWLEDGE_DB.exists()
    usage = knowledge.fetch_app_usage(limit=1) if exists else []
    ok = bool(usage)
    detail = (
        "readable" if ok
        else ("present but unreadable — grant Full Disk Access"
              if exists else "knowledgeC.db not found")
    )
    lines.append(_check("Apple Screen Time", ok, detail))

    lines += [
        "",
        "Permissions are granted in System Settings → Privacy & Security:",
        "  • Accessibility      → window titles",
        "  • Screen Recording   → window titles on macOS Sequoia and later",
        "  • Full Disk Access   → Apple Screen Time history (knowledgeC.db)",
        "  • Automation         → browser tab URLs (prompts per browser)",
        "",
        "Grant them to whichever app runs the daemon (e.g. your terminal,",
        "or the python3 binary used by the launchd agent).",
    ]
    return "\n".join(lines)
