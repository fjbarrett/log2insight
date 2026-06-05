# log2insight

A local, privacy-first **"Screen Time for everything"** tracker for macOS.

A small Python daemon polls what you're doing every few seconds and writes it
to a local SQLite database for later analysis. **Nothing leaves your machine** —
there is no network code, no telemetry, no cloud.

## What it tracks

| Signal | Source | Permission needed |
|---|---|---|
| Frontmost app | `lsappinfo` | none |
| Focused window title | Accessibility API (System Events) | **Accessibility** (+ Screen Recording on Sequoia+) |
| Per-process network I/O | `nettop` | none |
| System disk throughput | `iostat` | none |
| Idle / active state | `ioreg` HID idle time | none |
| Browser tab URL | AppleScript (Safari/Chrome/Edge/Brave/Arc) | **Automation** (per browser) |
| Apple Screen Time history | `knowledgeC.db` | **Full Disk Access** |

A "zero-permission" core (app + network + disk + idle) works immediately; the
richer signals light up as you grant permissions.

## Quick start

```bash
cd log2insight

# 1. See what works right now and what needs a permission.
python3 -m log2insight doctor

# 2. Create the database.
python3 -m log2insight init

# 3. Try one foreground run (Ctrl-C to stop). Let it gather a few samples.
python3 -m log2insight run

# 4. See a summary.
python3 -m log2insight report --hours 24
```

Install it as a background agent that survives reboot:

```bash
python3 -m log2insight install     # writes a launchd plist and loads it
python3 -m log2insight status      # agent state + row counts
python3 -m log2insight uninstall   # stop and remove
```

Optionally install the console script so you can drop the `python3 -m` prefix:

```bash
pip install -e .
log2insight doctor
```

## Granting permissions

System Settings → Privacy & Security:

- **Accessibility** → window titles
- **Screen Recording** → window titles on macOS Sequoia and later
- **Full Disk Access** → Apple Screen Time history (`knowledgeC.db`)
- **Automation** → browser tab URLs (prompts the first time per browser)

Grant them to **whichever app runs the daemon** — your terminal app for a
foreground `run`, or the `python3` binary that the launchd agent launches.

## Configuration

All via environment variables (read at startup):

| Variable | Default | Meaning |
|---|---|---|
| `LOG2INSIGHT_DIR` | `~/.log2insight` | data + log directory |
| `LOG2INSIGHT_DB` | `<dir>/activity.db` | database path |
| `LOG2INSIGHT_INTERVAL` | `10` | seconds between cycles |
| `LOG2INSIGHT_NET_EVERY` | `1` | collect network every N cycles |
| `LOG2INSIGHT_DISK_EVERY` | `6` | collect disk every N cycles |
| `LOG2INSIGHT_KNOWLEDGE_EVERY` | `30` | import Screen Time every N cycles |
| `LOG2INSIGHT_IDLE_THRESHOLD` | `60` | idle seconds before counted inactive |

## Data model

Everything lands in `~/.log2insight/activity.db`:

- `activity` — one row per cycle: frontmost app, window title, browser URL, idle seconds, active flag
- `net_samples` — per-process bytes in/out over a ~1s window
- `disk_samples` — per-device throughput snapshots
- `app_usage` — Apple Screen Time events imported from `knowledgeC.db`
- `meta` — bookkeeping (e.g. last Screen Time import watermark)

It's plain SQLite — point any tool at it (`sqlite3`, Datasette, a notebook).

## Daily email report (opt-in)

A separate launchd agent can email you a narrative of the previous weekday's
activity — what you worked on (most-focused windows), apps by active time,
browser domains, a focus/presence summary, network by process, and Apple
Screen Time totals. It runs at **3pm, Monday–Friday**; each run reports the
**most recent prior weekday** (so Monday's email covers the previous Friday).

This is the only part of log2insight that sends anything off the machine, and
only once you configure it. Sending uses your own Gmail account over SMTP, so
you need a **[Gmail App Password](https://myaccount.google.com/apppasswords)**
(your normal password won't work, and you'll need 2-Step Verification on). The
app password is stored in the **macOS Keychain**, never in a plaintext file.

```bash
# 1. One-time setup (prompts for the app password; nothing is echoed).
.venv/bin/python -m log2insight email-setup \
    --to you@example.com --from you@gmail.com

# 2. Preview without sending.
.venv/bin/python -m log2insight email-report --dry-run

# 3. Schedule it (3pm Mon–Fri).
.venv/bin/python -m log2insight install-emailer

# Stop it later:
.venv/bin/python -m log2insight uninstall-emailer
```

Non-secret settings (recipient, sender, SMTP host/port) live in
`~/.log2insight/email.json`. `email-report --day YYYY-MM-DD` re-sends any past
day; `--dry-run` prints to the terminal instead of emailing.

## Privacy note

This records a detailed history of everything you do, including window titles
and URLs. The database is unencrypted on disk. Treat it as sensitive; it's
`.gitignore`d so you don't commit it by accident.

The collector itself makes **no network connections**. The only feature that
sends data off the machine is the opt-in [daily email report](#daily-email-report-opt-in),
and it emails a summary only to the address you configure, via your own Gmail
account.
