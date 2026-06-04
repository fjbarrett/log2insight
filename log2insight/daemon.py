"""The polling daemon. One cycle samples the cheap signals every time and the
expensive ones (network, disk, Screen Time import) on their own cadences."""

import datetime
import signal
import sys
import time

from . import config, db
from .collectors import browser, disk, frontmost, idle, knowledge, network


def _now():
    t = time.time()
    return t, datetime.datetime.fromtimestamp(t).isoformat(timespec="seconds")


def _collect_cycle(conn, cycle):
    epoch, ts = _now()

    # --- cheap signals, every cycle ---
    app = frontmost.frontmost_app()
    title = frontmost.window_title()
    idle_s = idle.idle_seconds()
    active = 1 if idle_s < config.IDLE_ACTIVE_THRESHOLD else 0
    url = browser.browser_url(app) if active else None

    conn.execute(
        "INSERT INTO activity(ts, epoch, frontmost_app, window_title, "
        "browser_url, idle_seconds, active) VALUES(?,?,?,?,?,?,?)",
        (ts, epoch, app, title, url, idle_s, active),
    )

    # --- network, on its cadence ---
    if cycle % config.NET_EVERY == 0:
        rows = network.network_samples()
        if rows:
            conn.executemany(
                "INSERT INTO net_samples(ts, epoch, process, pid, bytes_in, "
                "bytes_out) VALUES(?,?,?,?,?,?)",
                [(ts, epoch, name, pid, bi, bo) for name, pid, bi, bo in rows],
            )

    # --- disk, on its cadence ---
    if cycle % config.DISK_EVERY == 0:
        rows = disk.disk_samples()
        if rows:
            conn.executemany(
                "INSERT INTO disk_samples(ts, epoch, device, kb_per_transfer, "
                "transfers_per_sec, mb_per_sec) VALUES(?,?,?,?,?,?)",
                [(ts, epoch, dev, kbt, tps, mbs) for dev, kbt, tps, mbs in rows],
            )

    # --- Apple Screen Time import, on its cadence ---
    if cycle % config.KNOWLEDGE_EVERY == 0:
        _import_knowledge(conn)

    conn.commit()


def _import_knowledge(conn):
    since = float(db.get_meta(conn, "last_knowledge_epoch", 0.0) or 0.0)
    rows = knowledge.fetch_app_usage(since_epoch=since)
    if not rows:
        return
    payload = []
    max_end = since
    for bundle_id, start_e, end_e, usage in rows:
        payload.append((
            bundle_id,
            start_e,
            end_e,
            datetime.datetime.fromtimestamp(start_e).isoformat(timespec="seconds"),
            datetime.datetime.fromtimestamp(end_e).isoformat(timespec="seconds"),
            usage,
        ))
        max_end = max(max_end, end_e)
    conn.executemany(
        "INSERT OR IGNORE INTO app_usage(bundle_id, start_epoch, end_epoch, "
        "start, end, usage_seconds) VALUES(?,?,?,?,?,?)",
        payload,
    )
    db.set_meta(conn, "last_knowledge_epoch", max_end)


def run_forever():
    conn = db.init_db()
    stop = {"flag": False}

    def _handle(_sig, _frame):
        stop["flag"] = True

    signal.signal(signal.SIGTERM, _handle)
    signal.signal(signal.SIGINT, _handle)

    print(f"log2insight daemon started; writing to {config.DB_PATH}", flush=True)
    cycle = 0
    while not stop["flag"]:
        cycle += 1
        try:
            _collect_cycle(conn, cycle)
        except Exception as exc:  # never let one bad cycle kill the daemon
            print(f"[cycle {cycle}] error: {exc}", file=sys.stderr, flush=True)

        slept = 0.0
        while slept < config.INTERVAL and not stop["flag"]:
            step = min(1.0, config.INTERVAL - slept)
            time.sleep(step)
            slept += step

    conn.close()
    print("log2insight daemon stopped.", flush=True)
