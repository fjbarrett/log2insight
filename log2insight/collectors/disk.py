"""System-wide disk throughput via `iostat`.

macOS does not expose per-process disk I/O without `sudo fs_usage` (a heavy
privileged stream), so v1 records per-device throughput snapshots. Needs no
special permission."""

from ..util import run, to_int


def disk_samples():
    """Return a list of (device, kb_per_transfer, transfers_per_sec, mb_per_sec)."""
    out = run(["iostat", "-d", "-w", "1", "-c", "2"], timeout=8)
    lines = [ln.rstrip() for ln in out.splitlines() if ln.strip()]
    if not lines:
        return []

    # Layout:
    #   disk0       disk2          <- device names
    #   KB/t  tps  MB/s  KB/t ...  <- repeating metric header
    #   <numbers>                  <- sample 1
    #   <numbers>                  <- sample 2 (we keep this one)
    metric_idx = next(
        (i for i, ln in enumerate(lines) if "KB/t" in ln and "MB/s" in ln),
        None,
    )
    if metric_idx is None or metric_idx == 0:
        return []

    devices = lines[metric_idx - 1].split()
    data_lines = [ln for ln in lines[metric_idx + 1:] if _is_numeric_row(ln)]
    if not data_lines:
        return []

    values = data_lines[-1].split()
    results = []
    for d, device in enumerate(devices):
        base = d * 3
        if base + 2 >= len(values):
            break
        results.append((
            device,
            _to_float(values[base]),
            _to_float(values[base + 1]),
            _to_float(values[base + 2]),
        ))
    return results


def _is_numeric_row(line):
    parts = line.split()
    return bool(parts) and all(to_int(p.replace(".", "", 1)) is not None for p in parts)


def _to_float(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None
