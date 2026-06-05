"""Opt-in daily email report.

This is the one place in log2insight that touches the network, and it only does
so when you've explicitly configured it. The collection core stays offline; this
module is imported lazily by the CLI and the dedicated launchd emailer agent.

Config lives in ~/.log2insight/email.json (recipient, sender, SMTP host/port).
The SMTP app password is NOT stored there — it goes in the macOS Keychain and is
read back via the `security` CLI at send time, so no secret ever sits in a
plaintext file.
"""

import datetime
import html
import json
import smtplib
import ssl
import subprocess
from email.message import EmailMessage

from . import config, report


# --- which day does a given run report on? ----------------------------------

def previous_weekday(today=None):
    """The most recent Mon–Fri strictly before `today`.

    Run at 3pm, this makes Tue–Fri report the actual yesterday, and Monday
    report the previous Friday (so Friday's work is never dropped over the
    weekend)."""
    today = today or datetime.date.today()
    d = today - datetime.timedelta(days=1)
    while d.weekday() >= 5:          # 5 = Saturday, 6 = Sunday
        d -= datetime.timedelta(days=1)
    return d


def day_bounds(d):
    """Local-midnight [lo, hi) epoch bounds and a human label for date `d`."""
    start = datetime.datetime(d.year, d.month, d.day)
    lo = start.timestamp()
    hi = (start + datetime.timedelta(days=1)).timestamp()
    label = f"{d.strftime('%A, %b')} {d.day}"   # e.g. "Friday, Jun 6"
    return lo, hi, label


# --- email config (non-secret) ----------------------------------------------

_DEFAULTS = {"to": "", "from": "", "host": "smtp.gmail.com", "port": 465}


def load_config():
    try:
        with open(config.EMAIL_CONFIG_PATH) as fh:
            raw = json.load(fh)
        raw = raw if isinstance(raw, dict) else {}
    except (OSError, ValueError):
        raw = {}
    cfg = dict(_DEFAULTS)
    cfg.update({k: raw[k] for k in _DEFAULTS if k in raw})
    cfg["port"] = int(cfg["port"])
    return cfg


def save_config(cfg):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    keep = {k: cfg[k] for k in _DEFAULTS if k in cfg}
    with open(config.EMAIL_CONFIG_PATH, "w") as fh:
        json.dump(keep, fh, indent=2)
        fh.write("\n")


# --- secret in the macOS Keychain -------------------------------------------

def keychain_set(account, password):
    subprocess.run(
        ["security", "add-generic-password",
         "-a", account, "-s", config.KEYCHAIN_SERVICE, "-w", password, "-U"],
        check=True, capture_output=True, text=True,
    )


def keychain_get(account):
    result = subprocess.run(
        ["security", "find-generic-password",
         "-a", account, "-s", config.KEYCHAIN_SERVICE, "-w"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.rstrip("\n")


# --- sending ----------------------------------------------------------------

def send(cfg, password, subject, body):
    msg = EmailMessage()
    msg["From"] = cfg["from"]
    msg["To"] = cfg["to"]
    msg["Subject"] = subject
    msg.set_content(body)
    # Monospace HTML alternative so the aligned tables survive in Gmail.
    msg.add_alternative(
        "<html><body>"
        "<pre style=\"font:13px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace\">"
        f"{html.escape(body)}</pre></body></html>",
        subtype="html",
    )
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(cfg["host"], cfg["port"], context=ctx, timeout=30) as srv:
        srv.login(cfg["from"], password)
        srv.send_message(msg)


def run_scheduled(day=None, dry_run=False):
    """Build and send the report. This is what the launchd emailer invokes.

    `day` may be an ISO date string to override the default (previous weekday).
    `dry_run` prints the email to stdout instead of sending it."""
    d = datetime.date.fromisoformat(day) if day else previous_weekday()
    lo, hi, label = day_bounds(d)
    subject = f"log2insight — {label}"
    body = report.build_day_report(lo, hi, label)

    if dry_run:
        print(f"Subject: {subject}\nTo: {load_config()['to'] or '(unset)'}\n")
        print(body)
        return

    cfg = load_config()
    if not cfg["to"] or not cfg["from"]:
        raise SystemExit(
            "Email is not configured. Run:  log2insight email-setup")
    password = keychain_get(cfg["from"])
    if not password:
        raise SystemExit(
            "No app password found in the Keychain. Run:  log2insight email-setup")
    send(cfg, password, subject, body)
    print(f"Sent '{subject}' to {cfg['to']}")


def setup(to=None, sender=None, host=None, port=None):
    """Interactive one-time setup: persist email.json + store the app password."""
    import getpass

    cfg = load_config()
    if to:
        cfg["to"] = to
    if sender:
        cfg["from"] = sender
    if host:
        cfg["host"] = host
    if port:
        cfg["port"] = int(port)
    if not cfg["to"]:
        cfg["to"] = input("Recipient email: ").strip()
    if not cfg["from"]:
        cfg["from"] = input("Gmail address to send from: ").strip()
    save_config(cfg)

    prompt = (f"Gmail App Password for {cfg['from']} (16 chars, input hidden): ")
    # Google shows the app password grouped as "abcd efgh ijkl mnop"; the spaces
    # aren't part of it, so drop them.
    pw = getpass.getpass(prompt).replace(" ", "")
    if not pw:
        raise SystemExit("No password entered; aborted.")
    keychain_set(cfg["from"], pw)
    print(f"Saved {config.EMAIL_CONFIG_PATH} and stored the app password in "
          "your Keychain.")
    print("Preview the next report with:  log2insight email-report --dry-run")
    print("Schedule it (3pm Mon–Fri) with: log2insight install-emailer")
