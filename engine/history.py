"""Every change lands here, and anything here can be undone."""
from __future__ import annotations

import json
import sqlite3

from .ids import uuid7
from .store import Store, now_iso


def record(con: sqlite3.Connection, *, app: str, action: str, tbl: str, row_key: str,
           before, after) -> str:
    hid = uuid7()
    con.execute(
        "INSERT INTO history(id, ts, app, action, tbl, row_key, before, after) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (hid, now_iso(), app, action, tbl, row_key,
         None if before is None else json.dumps(before),
         None if after is None else json.dumps(after)),
    )
    return hid


def _row(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["before"] = json.loads(d["before"]) if d["before"] else None
    d["after"] = json.loads(d["after"]) if d["after"] else None
    return d


def recent(store: Store, limit: int = 50, tbl: str | None = None) -> list[dict]:
    with store.read():
        if tbl:
            rows = store.con.execute(
                "SELECT * FROM history WHERE tbl=? ORDER BY id DESC LIMIT ?", (tbl, limit))
        else:
            rows = store.con.execute("SELECT * FROM history ORDER BY id DESC LIMIT ?", (limit,))
        return [_row(r) for r in rows]


def export(store: Store, *, since: str | None = None, until: str | None = None,
           tbl: str | None = None, row_key: str | None = None, app: str | None = None) -> list[dict]:
    """All matching history, oldest first, for a download. Filters are optional
    and combine; more will be added as the apps grow (see the Settings page)."""
    where, args = [], []
    if since:
        where.append("ts >= ?")
        args.append(since)
    if until:
        where.append("ts <= ?")
        args.append(until)
    if tbl:
        where.append("tbl = ?")
        args.append(tbl)
    if row_key:
        where.append("row_key = ?")
        args.append(row_key)
    if app:
        where.append("app = ?")
        args.append(app)
    sql = "SELECT * FROM history" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY id"
    with store.read():
        return [_row(r) for r in store.con.execute(sql, args)]


class NotFound(LookupError):
    pass


class AlreadyUndone(ValueError):
    pass


def undo(store: Store, history_id: str, app: str = "history") -> dict:
    """Put the row back the way it was before this change. The undo is itself
    a history entry, so an undo can be undone."""
    from . import settings as settings_mod  # local import: settings imports history

    with store.tx() as con:
        r = con.execute("SELECT * FROM history WHERE id=?", (history_id,)).fetchone()
        if not r:
            raise NotFound(history_id)
        entry = _row(r)
        if entry["undone_by"]:
            raise AlreadyUndone(entry["undone_by"])
        if entry["tbl"] == "settings":
            new_id = settings_mod.restore_row(con, entry["row_key"], entry["before"], app=app,
                                              action="history.undo")
        elif entry["tbl"] in ("entities", "links", "tags", "notes", "files") or entry["tbl"].startswith("trip_"):
            from . import records
            new_id = records.restore_row(con, entry["tbl"], entry["row_key"], entry["before"], app=app,
                                         action="history.undo")
        else:
            raise ValueError(f"undo not implemented for table {entry['tbl']}")
        con.execute("UPDATE history SET undone_by=? WHERE id=?", (new_id, history_id))
        return {"undone": history_id, "by": new_id}
