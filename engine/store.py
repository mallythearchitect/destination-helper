"""The vault: one SQLite file, WAL mode, STRICT tables, foreign keys on.

Every write goes through `Store.tx()`, which takes the process lock and runs
BEGIN IMMEDIATE ... COMMIT, so a write either fully happens or doesn't.
Migrations are numbered .sql files in engine/migrations, applied once each.
"""
from __future__ import annotations

import os
import pathlib
import sqlite3
import threading
from contextlib import contextmanager
from datetime import UTC, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
MIGRATIONS = pathlib.Path(__file__).resolve().parent / "migrations"
APPS = ROOT / "apps"


def migration_files() -> list[tuple[str, pathlib.Path]]:
    """Engine migrations first, then each app's (apps/<app>/server/migrations),
    each identified as '<app>/<file>' so the order within an app is kept."""
    files = [(f.name, f) for f in sorted(MIGRATIONS.glob("*.sql"))]
    for app_dir in sorted(APPS.glob("*/server/migrations")):
        app = app_dir.parent.parent.name
        files += [(f"{app}/{f.name}", f) for f in sorted(app_dir.glob("*.sql"))]
    return files


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def vault_path() -> pathlib.Path:
    return pathlib.Path(os.environ.get("MINDSCAPE_VAULT") or ROOT / "vault" / "vault.db")


def _connect(path: pathlib.Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    # URI mode, so read-only packs can be attached with ?mode=ro
    con = sqlite3.connect(path.resolve().as_uri(), isolation_level=None, check_same_thread=False, uri=True)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=5000")
    con.execute("PRAGMA synchronous=NORMAL")
    from . import packs  # read-only reference data, attached as pack_<name>
    packs.attach_all(con)
    return con


def migrate(con: sqlite3.Connection) -> list[str]:
    con.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations("
        "id TEXT PRIMARY KEY, applied_at TEXT NOT NULL) STRICT"
    )
    done = {r[0] for r in con.execute("SELECT id FROM schema_migrations")}
    applied = []
    for mid, f in migration_files():
        if mid in done:
            continue
        sql = f.read_text()
        con.executescript(
            "BEGIN;\n" + sql + "\nINSERT INTO schema_migrations(id, applied_at) VALUES("
            f"'{mid}', '{now_iso()}');\nCOMMIT;"
        )
        applied.append(mid)
    return applied


class Store:
    def __init__(self, path: pathlib.Path | None = None):
        self.path = pathlib.Path(path or vault_path())
        self._lock = threading.RLock()
        self._depth = 0
        self.con = _connect(self.path)
        migrate(self.con)

    @contextmanager
    def tx(self):
        """One write transaction. Nested calls join the outer one, so an action
        that touches several tables still either fully happens or doesn't."""
        with self._lock:
            if self._depth:
                self._depth += 1
                try:
                    yield self.con
                finally:
                    self._depth -= 1
                return
            self._depth = 1
            self.con.execute("BEGIN IMMEDIATE")
            try:
                yield self.con
            except BaseException:
                self.con.execute("ROLLBACK")
                raise
            else:
                self.con.execute("COMMIT")
            finally:
                self._depth = 0

    def read(self):
        """Reads outside a transaction still take the lock: one connection."""
        return self._lock

    def close(self):
        with self._lock:
            self.con.close()

    def reopen(self):
        with self._lock:
            self.con = _connect(self.path)
            migrate(self.con)
