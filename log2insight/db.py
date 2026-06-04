"""SQLite schema and connection helpers."""

import sqlite3

from .config import DATA_DIR, DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS activity (
    id            INTEGER PRIMARY KEY,
    ts            TEXT NOT NULL,        -- ISO local timestamp
    epoch         REAL NOT NULL,        -- unix seconds
    frontmost_app TEXT,
    window_title  TEXT,
    browser_url   TEXT,
    idle_seconds  REAL,
    active        INTEGER               -- 1 if user was active this sample
);
CREATE INDEX IF NOT EXISTS idx_activity_epoch ON activity(epoch);
CREATE INDEX IF NOT EXISTS idx_activity_app   ON activity(frontmost_app);

CREATE TABLE IF NOT EXISTS net_samples (
    id        INTEGER PRIMARY KEY,
    ts        TEXT NOT NULL,
    epoch     REAL NOT NULL,
    process   TEXT,
    pid       INTEGER,
    bytes_in  INTEGER,                  -- bytes over the ~1s nettop window
    bytes_out INTEGER
);
CREATE INDEX IF NOT EXISTS idx_net_epoch   ON net_samples(epoch);
CREATE INDEX IF NOT EXISTS idx_net_process ON net_samples(process);

CREATE TABLE IF NOT EXISTS disk_samples (
    id                INTEGER PRIMARY KEY,
    ts                TEXT NOT NULL,
    epoch             REAL NOT NULL,
    device            TEXT,
    kb_per_transfer   REAL,
    transfers_per_sec REAL,
    mb_per_sec        REAL
);
CREATE INDEX IF NOT EXISTS idx_disk_epoch ON disk_samples(epoch);

CREATE TABLE IF NOT EXISTS app_usage (
    id            INTEGER PRIMARY KEY,
    bundle_id     TEXT,
    start_epoch   REAL,
    end_epoch     REAL,
    start         TEXT,
    end           TEXT,
    usage_seconds REAL,
    source        TEXT DEFAULT 'knowledgeC',
    UNIQUE(bundle_id, start_epoch, end_epoch)
);
CREATE INDEX IF NOT EXISTS idx_usage_start  ON app_usage(start_epoch);
CREATE INDEX IF NOT EXISTS idx_usage_bundle ON app_usage(bundle_id);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = connect()
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def get_meta(conn, key, default=None):
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_meta(conn, key, value):
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )
