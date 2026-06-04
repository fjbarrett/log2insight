"""log2insight — a local, privacy-first "Screen Time for everything" tracker.

A lightweight polling daemon samples what you're doing on your Mac
(frontmost app, window title, per-process network I/O, disk throughput,
idle/active state, browser URL, and Apple's own Screen Time history) and
writes it to a local SQLite database for later analysis.

Nothing leaves your machine.
"""

__version__ = "0.1.0"
