# Destination Helper

A trip co-pilot. It plans the trip, **checks the plan** for the mistakes
that cost money, helps you prepare, then runs the trip live. Work and
personal on one trip, any size: two weeks abroad or a Saturday outing.

What makes it different from a planner like Wanderlog, in one line: **it
knows when your plan is wrong and helps you fix it.** A taxi booked before
you land, a price that is per person and not total, the last ferry leaving
before you arrive, a night with no bed, a passport that runs out too soon,
a deadline missed, a message nobody answered.

The product brief, market scan and the full capability list (93 question
codes, 29 workflows, 12 guardrails, the region packs) are one page:
[`docs/brief/destination-helper.md`](docs/brief/destination-helper.md).
How the app works, in plain English: [`docs/how-it-works.md`](docs/how-it-works.md).

## Start it

```sh
cd ~/Desktop/destination-helper
scripts/dev.sh              # the engine on http://127.0.0.1:8772
open http://127.0.0.1:8772  # Home; Trips is the app
```

First time only:

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
git config core.hooksPath .githooks         # the pre-commit checks
.venv/bin/python scripts/import_thailand_trip.py   # the first test trip (optional)
scripts/install_mcp.sh                      # let a Claude Code chat use it (optional)
scripts/install_backup_schedule.sh          # nightly backup (optional, macOS)
```

## What's here

| Thing | What it does | Where |
|---|---|---|
| Trips | Plan → Prepare → Run. Timeline by day with leave-by times and live links per leg; the checker with a fix on every finding; costs per person and group, company vs me, work vs personal; the before-you-go list; confirmations (message first, call if no reply); the calendar file; the helper's capability list and region packs | `/apps/trips/web/` |
| Destinations | Places scored with a source on every figure, cost per day, distance from home, ways to get there, your shortlist | `/apps/destinations/web/` |
| The helper pack | The brief's capability list as data, built from the docx: `scripts/extract_helper_doc.py` → `packs/build_helper.py` | `packs/helper.sqlite` |
| The vault | One SQLite file holding everything, with a history of every change | `vault/vault.db` (ignored by git) |
| Settings → Logic | Every rule a feature decides by, as data you can edit: the checker's thresholds, the confirmation template, the before-you-go list | `/apps/system/web/settings.html#logic` |
| The AI plug | Every action and read offered to a Claude chat over MCP: "check my trip", "compare every way from Krabi to Phuket" (W02) | `scripts/install_mcp.sh` |
| Checks | Before every commit: code tidy, no leaked keys, tests pass. Same on GitHub. | `scripts/check.sh` |

## Where it came from

Built 2026-09-28 out of two earlier pieces: the Destinations page of the
old workspace (City2City, City Viewer and Trip Mode folded together) and the
MindScape engine (`mindscape-app`), whose engine, ui-kit and Destinations app
this repo copies. It runs on its own; nothing here talks to those repos.
Decision notes in `docs/decisions/`.
