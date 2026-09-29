#!/bin/sh
# The automatic checks: tidy code, mistakes caught, no leaked keys, tests.
# Runs before every commit (.githooks/pre-commit) and on every push (CI).
set -e
cd "$(dirname "$0")/.."
PY=${PY:-.venv/bin/python}
[ -x "$PY" ] || PY=python3
# lint tracked files only, so another session's untracked work-in-progress never blocks a commit
"$PY" -m ruff check $(git ls-files "*.py"; git diff --cached --name-only --diff-filter=A -- "*.py")
"$PY" scripts/check_secrets.py "$@"
"$PY" -m pytest
