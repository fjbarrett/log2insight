"""Render the collected data as a self-contained HTML dashboard.

No external assets or network — everything (CSS included) is inlined so it
renders identically in the menu bar's WKWebView window and in a browser tab.
"""

import html
import time

from . import config, db
from .util import humanize_bytes, humanize_seconds


def _window(hours):
    return time.time() - hours * 3600.0


def _summary(conn, hours):
    since = _window(hours)
    total = conn.execute("SELECT COUNT(*) FROM activity").fetchone()[0]
    in_window = conn.execute(
        "SELECT COUNT(*) FROM activity WHERE epoch >= ?", (since,)
    ).fetchone()[0]
    active = conn.execute(
        "SELECT COUNT(*) FROM activity WHERE active = 1 AND epoch >= ?", (since,)
    ).fetchone()[0]
    last = conn.execute(
        "SELECT ts FROM activity ORDER BY epoch DESC LIMIT 1"
    ).fetchone()
    return {
        "total": total,
        "in_window": in_window,
        "active_seconds": active * config.INTERVAL,
        "last": last["ts"] if last else None,
    }


def _top_apps(conn, hours, top):
    rows = conn.execute(
        "SELECT frontmost_app AS app, COUNT(*) AS n FROM activity "
        "WHERE active = 1 AND epoch >= ? AND frontmost_app IS NOT NULL "
        "AND frontmost_app != '' GROUP BY frontmost_app ORDER BY n DESC LIMIT ?",
        (_window(hours), top),
    ).fetchall()
    return [(r["app"], r["n"] * config.INTERVAL, r["n"]) for r in rows]


def _top_network(conn, hours, top):
    rows = conn.execute(
        "SELECT process, SUM(bytes_in) AS bi, SUM(bytes_out) AS bo "
        "FROM net_samples WHERE epoch >= ? GROUP BY process "
        "ORDER BY (SUM(bytes_in) + SUM(bytes_out)) DESC LIMIT ?",
        (_window(hours), top),
    ).fetchall()
    return [
        (r["process"], (r["bi"] or 0), (r["bo"] or 0), (r["bi"] or 0) + (r["bo"] or 0))
        for r in rows
    ]


def _top_screentime(conn, hours, top):
    rows = conn.execute(
        "SELECT bundle_id, SUM(usage_seconds) AS s FROM app_usage "
        "WHERE start_epoch >= ? GROUP BY bundle_id ORDER BY s DESC LIMIT ?",
        (_window(hours), top),
    ).fetchall()
    return [(r["bundle_id"], r["s"] or 0) for r in rows]


def _bar_rows(items, label_of, value_of, fmt_of):
    """Build <tr>s with a proportional bar in the value cell."""
    peak = max((value_of(i) for i in items), default=0) or 1
    out = []
    for it in items:
        label = html.escape(str(label_of(it) or "—"))
        value = value_of(it)
        pct = max(2, round(100 * value / peak))
        out.append(
            f'<tr><td class="label">{label}</td>'
            f'<td class="barcell"><span class="bar" style="width:{pct}%"></span>'
            f'<span class="val">{html.escape(fmt_of(it))}</span></td></tr>'
        )
    return "\n".join(out) if out else (
        '<tr><td class="empty" colspan="2">No data in this window yet.</td></tr>'
    )


def _section(title, note, rows_html):
    note_html = f'<span class="note">{html.escape(note)}</span>' if note else ""
    return (
        f'<section><h2>{html.escape(title)}{note_html}</h2>'
        f'<table>{rows_html}</table></section>'
    )


_CSS = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body {
  font: 14px/1.5 -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
  margin: 0; padding: 24px 28px 40px; background: Canvas; color: CanvasText;
}
header { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
h1 { font-size: 20px; margin: 0; font-weight: 650; }
.sub { color: color-mix(in srgb, CanvasText 55%, transparent); font-size: 13px; }
.cards { display: flex; gap: 12px; flex-wrap: wrap; margin: 18px 0 8px; }
.card {
  flex: 1 1 150px; background: color-mix(in srgb, CanvasText 6%, Canvas);
  border: 1px solid color-mix(in srgb, CanvasText 12%, transparent);
  border-radius: 12px; padding: 12px 14px;
}
.card .k { font-size: 12px; color: color-mix(in srgb, CanvasText 55%, transparent); }
.card .v { font-size: 22px; font-weight: 650; margin-top: 2px; }
section { margin-top: 26px; }
h2 { font-size: 14px; font-weight: 650; margin: 0 0 8px; }
h2 .note { font-weight: 400; font-size: 12px; margin-left: 8px;
  color: color-mix(in srgb, CanvasText 50%, transparent); }
table { width: 100%; border-collapse: collapse; }
td { padding: 5px 0; vertical-align: middle; }
td.label { width: 230px; white-space: nowrap; overflow: hidden;
  text-overflow: ellipsis; padding-right: 14px; }
td.barcell { position: relative; }
.bar { display: inline-block; height: 16px; border-radius: 5px; vertical-align: middle;
  background: color-mix(in srgb, AccentColor 80%, transparent); min-width: 3px; }
.val { font-variant-numeric: tabular-nums; margin-left: 8px;
  color: color-mix(in srgb, CanvasText 70%, transparent); font-size: 13px; }
.empty { color: color-mix(in srgb, CanvasText 45%, transparent); padding: 10px 0; }
footer { margin-top: 32px; font-size: 12px;
  color: color-mix(in srgb, CanvasText 45%, transparent); }
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%;
  margin-right: 6px; vertical-align: middle; }
.on { background: #34c759; } .off { background: #ff3b30; }
"""


def render(hours=24, top=10, agent_running=None):
    conn = db.connect()
    try:
        s = _summary(conn, hours)
        apps = _top_apps(conn, hours, top)
        net = _top_network(conn, hours, top)
        st = _top_screentime(conn, hours, top)
    finally:
        conn.close()

    apps_html = _bar_rows(
        apps, lambda r: r[0], lambda r: r[1], lambda r: humanize_seconds(r[1])
    )
    net_html = _bar_rows(
        net, lambda r: r[0], lambda r: r[3],
        lambda r: f"{humanize_bytes(r[3])}  ({humanize_bytes(r[1])}↓ {humanize_bytes(r[2])}↑)",
    )
    st_html = _bar_rows(
        st, lambda r: r[0], lambda r: r[1], lambda r: humanize_seconds(r[1])
    )

    if agent_running is None:
        status_html = ""
    elif agent_running:
        status_html = '<span class="sub"><span class="dot on"></span>collecting</span>'
    else:
        status_html = '<span class="sub"><span class="dot off"></span>stopped</span>'

    last = html.escape(s["last"]) if s["last"] else "no samples yet"

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>log2insight</title>
<style>{_CSS}</style></head>
<body>
<header>
  <h1>log2insight</h1>
  <span class="sub">last {html.escape(str(int(hours)))}h</span>
  {status_html}
</header>
<div class="cards">
  <div class="card"><div class="k">Active time</div>
    <div class="v">{html.escape(humanize_seconds(s['active_seconds']))}</div></div>
  <div class="card"><div class="k">Samples (window)</div>
    <div class="v">{s['in_window']:,}</div></div>
  <div class="card"><div class="k">Samples (all time)</div>
    <div class="v">{s['total']:,}</div></div>
  <div class="card"><div class="k">Last sample</div>
    <div class="v" style="font-size:15px">{last}</div></div>
</div>
{_section('Top apps by active time', None, apps_html)}
{_section('Top processes by network I/O', None, net_html)}
{_section('Apple Screen Time', 'imported from knowledgeC.db', st_html)}
<footer>All data stays on this machine · {html.escape(str(config.DB_PATH))}</footer>
</body></html>"""
