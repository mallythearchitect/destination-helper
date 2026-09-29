"""Reference data packs: read-only SQLite files in packs/, attached to the
vault connection as pack_<name>. Your notes about a place live in the vault
(records); updating a pack never touches them."""
from __future__ import annotations

import pathlib
import sqlite3

from .store import ROOT

PACKS_DIR = ROOT / "packs"


def pack_files() -> list[pathlib.Path]:
    return sorted(PACKS_DIR.glob("*.sqlite"))


def attach_all(con: sqlite3.Connection) -> list[str]:
    names = []
    for f in pack_files():
        name = f.stem
        try:
            con.execute(f"ATTACH DATABASE ? AS pack_{name}", (f.resolve().as_uri() + "?mode=ro",))
        except sqlite3.OperationalError as e:
            if "already in use" not in str(e):
                raise
        names.append(name)
    return names


def describe(con: sqlite3.Connection) -> list[dict]:
    out = []
    for f in pack_files():
        name = f.stem
        meta = {r[0]: r[1] for r in con.execute(f"SELECT key, value FROM pack_{name}.meta")}
        tables = [r[0] for r in con.execute(f"SELECT name FROM pack_{name}.sqlite_master WHERE type='table'")]
        rows = {t: con.execute(f"SELECT count(*) FROM pack_{name}.{t}").fetchone()[0] for t in tables}
        out.append({"name": name, "file": f.name, "bytes": f.stat().st_size, "meta": meta, "rows": rows})
    return out
