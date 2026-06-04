# CLAUDE.md

Guidance for Claude Code (and humans) working in this repository.

## What this is

`log2insight` — a local, privacy-first "Screen Time for everything" tracker for
macOS. A Python daemon polls activity signals every few seconds into a local
SQLite DB. **No network code, no telemetry, no cloud.** See `README.md` for the
full picture.

## Environment & setup

- macOS only. Targets the Homebrew Python (`/usr/local/opt/python@3.14`).
- The Homebrew Python is **externally managed (PEP 668)** — do not `pip install`
  into it. All dependencies live in the project venv at `./.venv`.
- Bootstrap: `python3 -m venv .venv && .venv/bin/python -m pip install -e .`
- **Gotcha:** the launchd collection agent's plist points at `./.venv/bin/python`
  (it's derived from `sys.executable` at install time). If you move or delete the
  repo or the venv, the agent crash-loops with `No module named log2insight`.
  Re-run `install` from a valid interpreter after relocating.

## Common commands

Run everything through the venv interpreter:

```bash
.venv/bin/python -m log2insight doctor     # collector + permission readiness
.venv/bin/python -m log2insight status      # agent state + row counts
.venv/bin/python -m log2insight report      # usage summary
.venv/bin/python -m log2insight install      # (re)install + load the launchd agent
```

After any change, sanity-check with `doctor` and `status`.

## Git workflow — MANDATORY

These rules are enforced; `.githooks/pre-push` rejects direct pushes to `main`
(wired via `git config core.hooksPath .githooks`, set up at clone time).

1. **Never commit or push directly to `main`.** All work happens on a branch.
2. **Branch from `main`**, named by type:
   `feat/…`, `fix/…`, `chore/…`, `docs/…`, `refactor/…`.
   Example: `feat/menu-bar-app`.
3. **Commit regularly and small.** One logical change per commit; commit at every
   working checkpoint rather than batching a day's work into one blob. Don't mix
   unrelated changes in a single commit.
4. **Commit message format:** imperative subject ≤ 72 chars, blank line, then a
   body explaining *why* (not just what).
5. **Every change reaches `main` through a Pull Request.** No exceptions, no
   fast-forward merges to `main` from the CLI.
6. **Before opening a PR:** run `doctor` (and any relevant manual checks); state
   in the PR body what you tested.
7. **PRs are focused.** A PR does one thing; keep the diff reviewable. Open a
   draft early if the work is large.

### Quick reference

```bash
git switch -c feat/my-thing main      # start work
git add -p && git commit              # small, frequent commits
git push -u origin feat/my-thing      # hook blocks this only for main
gh pr create --fill                   # open the PR
```

## Notes

- Don't commit the activity database or logs — `.gitignore` already excludes
  `*.db`, `*.log`, and `.log2insight/`. The DB is sensitive (window titles, URLs).
- Keep the collection core dependency-free; GUI/menu-bar code may depend on the
  `menubar` extra (`rumps`, `pyobjc`) but the daemon must stay importable without it.
