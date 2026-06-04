"""Per-process network I/O via `nettop`.

`nettop -P -x -L 2 -J bytes_in,bytes_out` prints two snapshots of *cumulative*
per-process byte counters, each block prefixed by a `,bytes_in,bytes_out,`
header. We diff the last two blocks to get the bytes transferred over nettop's
sample interval (~1s), so summing rows over time is meaningful. Needs no
special permission."""

from ..util import run, to_int


def network_samples():
    """Return a list of (process_name, pid, bytes_in, bytes_out) for the
    most recent sample interval."""
    out = run(
        ["nettop", "-P", "-x", "-L", "2", "-J", "bytes_in,bytes_out"],
        timeout=10,
    )
    blocks = _parse_blocks(out)
    if not blocks:
        return []

    if len(blocks) >= 2:
        prev, last = blocks[-2], blocks[-1]
        rows = []
        for label, (b_in, b_out) in last.items():
            p_in, p_out = prev.get(label, (0, 0))
            d_in = b_in - p_in
            d_out = b_out - p_out
            # A negative delta means the process (and its counter) restarted;
            # fall back to the absolute value for this interval.
            d_in = b_in if d_in < 0 else d_in
            d_out = b_out if d_out < 0 else d_out
            if d_in == 0 and d_out == 0:
                continue
            name, pid = _split_label(label)
            rows.append((name, pid, d_in, d_out))
        return rows

    # Single block: report cumulative counters as-is.
    rows = []
    for label, (b_in, b_out) in blocks[-1].items():
        if b_in == 0 and b_out == 0:
            continue
        name, pid = _split_label(label)
        rows.append((name, pid, b_in, b_out))
    return rows


def _parse_blocks(out):
    """Split nettop output into a list of {process_label: (bytes_in, bytes_out)}
    dicts, one per sample block."""
    blocks = []
    current = None
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split(",")
        if "bytes_in" in line and parts[0].strip() == "":
            current = {}
            blocks.append(current)
            continue
        if current is None:                     # data before any header
            current = {}
            blocks.append(current)
        if len(parts) < 3:
            continue
        b_in, b_out = to_int(parts[1]), to_int(parts[2])
        if b_in is None or b_out is None:
            continue
        current[parts[0]] = (b_in, b_out)
    return blocks


def _split_label(label):
    """'Google Chrome.12345' -> ('Google Chrome', 12345)."""
    name, _, pid = label.rpartition(".")
    if not name:
        return label, None
    return name, to_int(pid)
