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
