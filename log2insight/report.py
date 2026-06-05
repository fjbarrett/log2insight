"""Read-side: turn the collected samples into human-readable summaries."""

import time

from . import config, db
from .util import humanize_bytes, humanize_seconds


def _window(hours):
    return time.time() - hours * 3600.0


def _table(rows, headers, aligns=None):
    cols = list(zip(*([headers] + rows))) if rows else [[h] for h in headers]
    widths = [max(len(str(c)) for c in col) for col in cols]
    aligns = aligns or ["<"] * len(headers)
    fmt = "  ".join(f"{{:{a}{w}}}" for a, w in zip(aligns, widths))
    out = [fmt.format(*headers), fmt.format(*["-" * w for w in widths])]
    for row in rows:
        out.append(fmt.format(*[str(c) for c in row]))
    return "\n".join(out)


def top_apps(conn, hours, top):
    rows = conn.execute(
        "SELECT frontmost_app AS app, COUNT(*) AS n FROM activity "
        "WHERE active = 1 AND epoch >= ? AND frontmost_app IS NOT NULL "
        "AND frontmost_app != '' GROUP BY frontmost_app ORDER BY n DESC LIMIT ?",
        (_window(hours), top),
    ).fetchall()
    data = [
        (r["app"], humanize_seconds(r["n"] * config.INTERVAL), r["n"])
        for r in rows
    ]
    return _table(data, ["App", "Active time", "Samples"], ["<", ">", ">"])


def top_network(conn, hours, top):
    rows = conn.execute(
        "SELECT process, SUM(bytes_in) AS bi, SUM(bytes_out) AS bo "
        "FROM net_samples WHERE epoch >= ? GROUP BY process "
        "ORDER BY (SUM(bytes_in) + SUM(bytes_out)) DESC LIMIT ?",
        (_window(hours), top),
    ).fetchall()
    data = [
        (r["process"], humanize_bytes(r["bi"]), humanize_bytes(r["bo"]),
         humanize_bytes((r["bi"] or 0) + (r["bo"] or 0)))
        for r in rows
    ]
    return _table(data, ["Process", "In", "Out", "Total"], ["<", ">", ">", ">"])


def top_screentime(conn, hours, top):
    rows = conn.execute(
        "SELECT bundle_id, SUM(usage_seconds) AS s FROM app_usage "
        "WHERE start_epoch >= ? GROUP BY bundle_id ORDER BY s DESC LIMIT ?",
        (_window(hours), top),
    ).fetchall()
    data = [(r["bundle_id"], humanize_seconds(r["s"])) for r in rows]
    return _table(data, ["Bundle ID (Apple Screen Time)", "Usage"], ["<", ">"])


# --- Date-scoped "what did I do that day" report (used by the emailer) ------

def _domain(url):
    """Reduce a URL to its host, e.g. https://github.com/x/y -> github.com."""
    if not url:
        return None
    if url.startswith("file://"):
        return "(local file)"
    host = url.split("://", 1)[-1].split("/", 1)[0]
    return host or url


# Terminal multiplexers (and Claude Code) animate the window title with spinner
# frames; stripping them keeps one task from fragmenting into a row per frame.
_SPINNER_EXTRA = set("✳✶✻✺✷✸✹◂◃▸▹◜◝◞◟")


def _clean_title(title):
    kept = [
        ch for ch in title
        if not (0x2800 <= ord(ch) <= 0x28FF) and ch not in _SPINNER_EXTRA
    ]
    return " ".join("".join(kept).split())


def _day_apps(conn, lo, hi, top):
    rows = conn.execute(
        "SELECT frontmost_app AS app, COUNT(*) AS n FROM activity "
        "WHERE active = 1 AND epoch >= ? AND epoch < ? AND frontmost_app "
        "IS NOT NULL AND frontmost_app != '' GROUP BY app ORDER BY n DESC LIMIT ?",
        (lo, hi, top),
    ).fetchall()
    data = [(r["app"], humanize_seconds(r["n"] * config.INTERVAL)) for r in rows]
    return _table(data, ["App", "Active time"], ["<", ">"])


def _day_titles(conn, lo, hi, top):
    rows = conn.execute(
        "SELECT window_title AS t, frontmost_app AS app, COUNT(*) AS n "
        "FROM activity WHERE active = 1 AND epoch >= ? AND epoch < ? "
        "AND window_title IS NOT NULL AND window_title != '' "
        "GROUP BY window_title, frontmost_app",
        (lo, hi),
    ).fetchall()
    agg = {}
    for r in rows:
        key = (_clean_title(r["t"]), r["app"])
        agg[key] = agg.get(key, 0) + r["n"]
    ranked = sorted(agg.items(), key=lambda kv: kv[1], reverse=True)[:top]
    data = [
        (app, (title[:60] + "…") if len(title) > 61 else title,
         humanize_seconds(n * config.INTERVAL))
        for (title, app), n in ranked
    ]
    return _table(data, ["App", "Window / task", "Time"], ["<", "<", ">"])


def _day_domains(conn, lo, hi, top):
    rows = conn.execute(
        "SELECT browser_url AS url FROM activity WHERE active = 1 "
        "AND epoch >= ? AND epoch < ? AND browser_url IS NOT NULL "
        "AND browser_url != ''",
        (lo, hi),
    ).fetchall()
    counts = {}
    for r in rows:
        host = _domain(r["url"])
        if host:
            counts[host] = counts.get(host, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:top]
    data = [
        ((host[:45] + "…") if len(host) > 46 else host,
         humanize_seconds(n * config.INTERVAL))
        for host, n in ranked
    ]
    return _table(data, ["Browser domain", "Time"], ["<", ">"])


def _day_network(conn, lo, hi, top):
    rows = conn.execute(
        "SELECT process, SUM(bytes_in) AS bi, SUM(bytes_out) AS bo "
        "FROM net_samples WHERE epoch >= ? AND epoch < ? GROUP BY process "
        "ORDER BY (SUM(bytes_in) + SUM(bytes_out)) DESC LIMIT ?",
        (lo, hi, top),
    ).fetchall()
    data = [
        (r["process"], humanize_bytes(r["bi"]), humanize_bytes(r["bo"]),
         humanize_bytes((r["bi"] or 0) + (r["bo"] or 0)))
        for r in rows
    ]
    return _table(data, ["Process", "In", "Out", "Total"], ["<", ">", ">", ">"])


def _day_screentime(conn, lo, hi, top):
    rows = conn.execute(
        "SELECT bundle_id, SUM(usage_seconds) AS s FROM app_usage "
        "WHERE start_epoch >= ? AND start_epoch < ? GROUP BY bundle_id "
        "ORDER BY s DESC LIMIT ?",
        (lo, hi, top),
    ).fetchall()
    data = [(r["bundle_id"], humanize_seconds(r["s"])) for r in rows]
    return _table(data, ["Bundle ID (Apple Screen Time)", "Usage"], ["<", ">"])


def _focus_summary(conn, lo, hi):
    """Active share, longest away gap, app switches, and busiest hour."""
    rows = conn.execute(
        "SELECT epoch, frontmost_app, idle_seconds, active FROM activity "
        "WHERE epoch >= ? AND epoch < ? ORDER BY epoch",
        (lo, hi),
    ).fetchall()
    if not rows:
        return None
    total = len(rows)
    active = sum(1 for r in rows if r["active"])
    longest_idle = max((r["idle_seconds"] or 0) for r in rows)
    switches = 0
    prev = None
    hour_active = {}
    for r in rows:
        app = r["frontmost_app"]
        if app and prev and app != prev:
            switches += 1
        if app:
            prev = app
        if r["active"]:
            hr = time.strftime("%H:00", time.localtime(r["epoch"]))
            hour_active[hr] = hour_active.get(hr, 0) + 1
    busiest = max(hour_active.items(), key=lambda kv: kv[1]) if hour_active else None
    lines = [
        f"  Active:        {humanize_seconds(active * config.INTERVAL)} "
        f"of {humanize_seconds(total * config.INTERVAL)} sampled "
        f"({100.0 * active / total:.0f}% at the keyboard)",
        f"  App switches:  {switches} context switches",
        f"  Longest away:  {humanize_seconds(longest_idle)} idle stretch",
    ]
    if busiest:
        lines.append(
            f"  Busiest hour:  {busiest[0]} "
            f"({humanize_seconds(busiest[1] * config.INTERVAL)} active)"
        )
    return "\n".join(lines)


def build_day_report(lo, hi, label, top=12):
    """A rich, single-day narrative report for [lo, hi) epochs.

    `label` is the human day name, e.g. "Friday, Jun 6". Returns plain text
    suitable for a terminal or an email body."""
    conn = db.connect()
    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM activity WHERE epoch >= ? AND epoch < ?",
            (lo, hi),
        ).fetchone()[0]
        active = conn.execute(
            "SELECT COUNT(*) FROM activity "
            "WHERE active = 1 AND epoch >= ? AND epoch < ?",
            (lo, hi),
        ).fetchone()[0]
        usage = conn.execute(
            "SELECT COALESCE(SUM(usage_seconds), 0) FROM app_usage "
            "WHERE start_epoch >= ? AND start_epoch < ?",
            (lo, hi),
        ).fetchone()[0]

        header = f"log2insight — {label}"
        rule = "=" * len(header)
        if not total and not usage:
            return (
                f"{header}\n{rule}\n\n"
                "No activity was recorded for this day. The collection agent "
                "may have been off, or the Mac was asleep.\n"
            )

        sections = [header, rule, ""]
        if total:
            focus = _focus_summary(conn, lo, hi)
            sections += [
                f"You were at the keyboard for about "
                f"{humanize_seconds(active * config.INTERVAL)}.\n",
                "▌ What you worked on (most-focused windows)",
                _day_titles(conn, lo, hi, top),
                "\n▌ Apps by active time",
                _day_apps(conn, lo, hi, top),
                "\n▌ Browser domains",
                _day_domains(conn, lo, hi, top),
                "\n▌ Focus & presence",
                focus or "  (no samples)",
                "\n▌ Network by process",
                _day_network(conn, lo, hi, top),
            ]
        else:
            sections.append(
                "No high-resolution activity was captured for this day (the "
                "collector wasn't running yet). Showing Apple Screen Time only.\n")
        if usage:
            sections += [
                "\n▌ Apple Screen Time (foreground app totals)",
                _day_screentime(conn, lo, hi, top),
            ]
        return "\n".join(sections) + "\n"
    finally:
        conn.close()


def overview(hours=24, top=15):
    conn = db.connect()
    try:
        total = conn.execute("SELECT COUNT(*) FROM activity").fetchone()[0]
        sections = [
            f"log2insight — last {hours}h  ({total:,} activity samples on record)",
            "",
            "▌ Top apps by active time",
            top_apps(conn, hours, top),
            "",
            "▌ Top processes by network I/O",
            top_network(conn, hours, top),
            "",
            "▌ Apple Screen Time (imported from knowledgeC.db)",
            top_screentime(conn, hours, top),
        ]
        return "\n".join(sections)
    finally:
        conn.close()
