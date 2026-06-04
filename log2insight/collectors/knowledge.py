"""Read Apple's own Screen Time history from knowledgeC.db.

The DB is copied to a temp location first (it is usually open with a WAL),
then queried read-only. Requires Full Disk Access to read the source; without
it the copy raises PermissionError and we return an empty list."""

import shutil
import sqlite3
import tempfile
from pathlib import Path

from ..config import KNOWLEDGE_DB

# Core Data timestamps are seconds since 2001-01-01; offset to the unix epoch.
APPLE_EPOCH = 978_307_200

_QUERY = """
SELECT ZVALUESTRING AS bundle_id, ZSTARTDATE AS start, ZENDDATE AS end
FROM ZOBJECT
WHERE ZSTREAMNAME = '/app/usage'
  AND ZVALUESTRING IS NOT NULL
  AND (ZSTARTDATE + ?) > ?
ORDER BY ZSTARTDATE DESC
LIMIT ?
"""


def fetch_app_usage(since_epoch=0.0, limit=5000):
    """Return rows of (bundle_id, start_epoch, end_epoch, usage_seconds).

    Only events whose start is after `since_epoch` (unix) are returned, so
    callers can import incrementally."""
    if not KNOWLEDGE_DB.exists():
        return []

    tmpdir = None
    try:
        tmpdir = Path(tempfile.mkdtemp(prefix="l2i_know_"))
        dst = tmpdir / "knowledgeC.db"
        shutil.copy2(KNOWLEDGE_DB, dst)
        for suffix in ("-wal", "-shm"):
            src = KNOWLEDGE_DB.with_name(KNOWLEDGE_DB.name + suffix)
            if src.exists():
                shutil.copy2(src, dst.with_name(dst.name + suffix))

        conn = sqlite3.connect(dst)
        try:
            rows = conn.execute(_QUERY, (APPLE_EPOCH, since_epoch, limit)).fetchall()
        finally:
            conn.close()
    except (PermissionError, OSError, sqlite3.Error):
        return []
    finally:
        if tmpdir is not None:
            shutil.rmtree(tmpdir, ignore_errors=True)

    out = []
    for bundle_id, start, end in rows:
        if start is None or end is None:
            continue
        out.append((
            bundle_id,
            start + APPLE_EPOCH,
            end + APPLE_EPOCH,
            max(0.0, end - start),
        ))
    return out
