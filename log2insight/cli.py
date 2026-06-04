"""Command-line entrypoint: init / run / report / doctor / install / uninstall / status."""

import argparse

from . import agent, config, daemon, db, doctor, report


def _cmd_init(_args):
    conn = db.init_db()
    conn.close()
    print(f"Initialized database at {config.DB_PATH}")


def _cmd_run(_args):
    daemon.run_forever()


def _cmd_report(args):
    print(report.overview(hours=args.hours, top=args.top))


def _cmd_doctor(_args):
    print(doctor.run_checks())


def _cmd_install(_args):
    ok, msg = agent.install()
    print(msg)
    if ok:
        print("Run `log2insight doctor` to confirm permissions, then "
              "`log2insight report` after some data has accumulated.")


def _cmd_uninstall(_args):
    _ok, msg = agent.uninstall()
    print(msg)


def _cmd_status(_args):
    loaded = agent.is_loaded()
    print(f"launchd agent: {'loaded' if loaded else 'not loaded'}")
    conn = db.connect()
    try:
        for table in ("activity", "net_samples", "disk_samples", "app_usage"):
            try:
                n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except Exception:
                n = "—"
            print(f"  {table:<14} {n:>10} rows")
        last = conn.execute(
            "SELECT ts FROM activity ORDER BY epoch DESC LIMIT 1"
        ).fetchone()
        print(f"  last sample:   {last[0] if last else 'none yet'}")
    finally:
        conn.close()
    print(f"  database:      {config.DB_PATH}")


def build_parser():
    p = argparse.ArgumentParser(
        prog="log2insight",
        description="Local 'Screen Time for everything' tracker for macOS.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="create the database").set_defaults(func=_cmd_init)
    sub.add_parser("run", help="run the polling daemon in the foreground").set_defaults(func=_cmd_run)
    sub.add_parser("doctor", help="check collectors and permissions").set_defaults(func=_cmd_doctor)
    sub.add_parser("install", help="install + load the launchd background agent").set_defaults(func=_cmd_install)
    sub.add_parser("uninstall", help="unload + remove the launchd agent").set_defaults(func=_cmd_uninstall)
    sub.add_parser("status", help="show agent state and row counts").set_defaults(func=_cmd_status)

    rep = sub.add_parser("report", help="print usage summaries")
    rep.add_argument("--hours", type=float, default=24, help="lookback window (default 24)")
    rep.add_argument("--top", type=int, default=15, help="rows per section (default 15)")
    rep.set_defaults(func=_cmd_report)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
