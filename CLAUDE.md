# Destination Helper — rules every session reads first

Read this, then `docs/how-it-works.md` (plain English), `docs/status.md`
(where we are) and `docs/changelog.md` (everything done, and what is open).
The spec is the brief, `docs/brief/destination-helper.md`.

## What this repo is
The Destination Helper: a trip co-pilot (plan, check the plan, prepare, run)
on its own copy of the MindScape engine (Python, FastAPI, SQLite), with the
Destinations atlas beside it. It stands alone: no link to `mindscape-app` or
the old workspace. Port 8772.

## Rules
- **Your data never enters git.** `vault/` and `.env` are ignored. Keys go in
  `.env` and are referenced by name; the API only ever says whether a key is
  set. `scripts/check_secrets.py` runs before every commit and in CI.
- **Apps never touch the vault directly.** Pages call `/v1/...`; writes go
  through actions (`engine/actions.py`, `POST /v1/actions/<app>.<verb>`),
  each with a typed input and a plain one-line description.
- **Every change is kept.** Writes go through `Store.tx()` and record a
  `history` row with before and after. A save with a stale version gets a
  409 with both versions.
- **Write it down first.** Before a feature: what it does and how we'll know
  it works, as a test in `tests/`. "Done" = tests pass, `scripts/check.sh` is
  clean, it works at phone width, `docs/status.md` is updated, and it can be
  explained in plain English.
- **The brief is the spec.** A new capability comes from the brief (a question
  code, a workflow, a guardrail). A new version of the brief is a re-extract
  (`scripts/extract_helper_doc.py <docx>`) and a rebuild (`packs/build_helper.py`).
  When a trip shows a mistake, it becomes a checker rule here and a guardrail
  in the next brief (W26).
- **The rules live in Settings → Logic:** any number or rule a feature decides
  by is a `logic.*` setting in `engine/settings.py` with a default, a plain
  help line, `extra.used_by`, and a `check`. Code reads it with
  `settings.get_value` and never hardcodes it.
- **Shared look, no copied code:** the look is the Organic design system from
  Malachi's mockup board (decision 0012): `ui-kit/organic.css`, mapped by
  tokens.css, then shell.css, app.css and app.js, then the page's own script.
  A page's `<style>` holds only what is unique to it. Page controls are pill
  rails, not a sidebar. User-facing words by default; engine detail goes
  behind the Developer switch (class `dev-only`, `App.isDev()`). When Malachi
  hands over a new mockup board, build from it.
- **Log every change** in `docs/changelog.md` (what, why, the commit) and keep
  its "Still open" list true.
- **AI suggests; the person decides.** Workflows ask the switchboard for a
  job, never a provider; they file suggestions, never change data. Nothing
  sends a message, places a call or deletes without the person's OK. Tests use
  the fake provider, never the network.
- **Tests never touch real data or the network.** `tests/conftest.py` gives
  every test its own vault and forces place and road lookups offline. Never
  point a test at `vault/`. Check screens on a scratch copy of the vault
  (`MINDSCAPE_VAULT=<copy> MINDSCAPE_PORT=8773`), not on the live trip.
- **Big decisions get a short note** in `docs/decisions/`.
- **Plain English in docs and help text.**

## Layout
    engine/            store (vault), settings, history + undo, records, sources, packs, tracking, analytics, predict, workflows, /v1 API
    engine/ai/         switchboard, providers, prompts, inbox, tests, the MCP plug
    apps/trips/        the co-pilot: server (tables, actions, queries, checks.py = the plan checker, routes.py = compare ways,
                       geo.py = places and road routes, tracking), web (the page)
    apps/destinations/ the atlas: server (queries over the pack, actions), web
    apps/ai/web/       the AI inbox
    apps/system/web/   Settings, Browse
    apps/launcher/web/ Home
    packs/             helper.sqlite (the brief as data), destinations.sqlite, build scripts, source JSON
    ui-kit/            organic.css (the design system), tokens.css, shell.css, app.css, app.js (+ User/Developer, photos), helper.js (the chat), tour.js
    scripts/           check.sh, check_secrets.py, backup.py, dev.sh, extract_helper_doc.py, import_thailand_trip.py, install_*.sh
    tests/             pytest; every test isolated
    docs/              how-it-works, status, changelog, decisions/, brief/ (the docx versions and the one-page Markdown)
    vault/             your data (ignored)

## Run
    .venv/bin/python -m engine        # http://127.0.0.1:8772
    scripts/check.sh                  # ruff + secrets scan + pytest
