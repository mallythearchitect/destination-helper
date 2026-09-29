"""Backups of the vault, and the test that proves they restore.

make_backup: SQLite's online backup API into <destination>/vault-<stamp>.db.
restore_test: open the newest backup, integrity-check it, and compare every
settings row with the live vault. That is the phase-1 "done when": a setting
survives deleting your data and restoring it.
restore: a safety backup first, then the chosen file replaces the vault.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import sqlite3
import time
from datetime import UTC, datetime, timedelta

from . import settings
from .ids import uuid7
from .store import ROOT, Store, now_iso

KEEP_AT_LEAST = 7


def destination(store: Store) -> pathlib.Path:
    d = pathlib.Path(settings.get_value(store, "backup.destination"))
    if not d.is_absolute():
        d = ROOT / d
    d.mkdir(parents=True, exist_ok=True)
    return d


def _log(store: Store, kind: str, file: str | None, ok: bool, detail: dict | str | None) -> str:
    bid = uuid7()
    with store.tx() as con:
        con.execute("INSERT INTO backup_log(id, ts, kind, file, ok, detail) VALUES(?,?,?,?,?,?)",
                    (bid, now_iso(), kind, file, int(ok),
                     json.dumps(detail) if isinstance(detail, dict) else detail))
    return bid


def list_backups(store: Store) -> list[dict]:
    d = destination(store)
    out = []
    for f in sorted(d.glob("vault-*.db"), reverse=True):
        st = f.stat()
        out.append({"file": f.name, "path": str(f), "bytes": st.st_size,
                    "modified": datetime.fromtimestamp(st.st_mtime, UTC).isoformat(timespec="seconds")})
    return out


def prune(store: Store) -> list[str]:
    keep_days = int(settings.get_value(store, "backup.keep_days"))
    keep_at_least = int(settings.get_value(store, "logic.backup.rules").get("keep_at_least", KEEP_AT_LEAST))
    cutoff = time.time() - keep_days * 86400
    files = sorted(destination(store).glob("vault-*.db"))
    removed = []
    for f in files[:-keep_at_least] if len(files) > keep_at_least else []:
        if f.stat().st_mtime < cutoff:
            f.unlink()
            removed.append(f.name)
    return removed


def make_backup(store: Store, note: str = "manual") -> dict:
    d = destination(store)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = d / f"vault-{stamp}.db"
    n = 1
    while target.exists():
        n += 1
        target = d / f"vault-{stamp}-{n}.db"
    # Log first, so the copy carries the record of its own making and a
    # restore from it still shows this backup in the log.
    bid = _log(store, "backup", target.name, True, {"note": note})
    with store.read():
        dst = sqlite3.connect(target)
        try:
            store.con.backup(dst)
        finally:
            dst.close()
    removed = prune(store)
    detail = {"note": note, "bytes": target.stat().st_size, "pruned": removed}
    with store.tx() as con:
        con.execute("UPDATE backup_log SET detail=? WHERE id=?", (json.dumps(detail), bid))
    return {"id": bid, "file": target.name, "path": str(target), **detail}


def _settings_rows(con: sqlite3.Connection) -> dict[str, tuple]:
    return {r[0]: (r[1], r[2]) for r in con.execute("SELECT key, value, version FROM settings")}


def restore_test(store: Store, file: str | None = None) -> dict:
    backups = list_backups(store)
    if not backups:
        _log(store, "restore_test", None, False, "no backups yet")
        return {"ok": False, "reason": "no backups yet"}
    chosen = next((b for b in backups if b["file"] == file), backups[0]) if file else backups[0]
    path = pathlib.Path(chosen["path"])
    # Restore into a scratch copy, exactly as a real restore would, then read it back.
    scratch = path.with_name(path.stem + ".restore-test.db")
    shutil.copyfile(path, scratch)
    try:
        con = sqlite3.connect(f"file:{scratch}?mode=ro&immutable=1", uri=True)
        try:
            integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
            restored = _settings_rows(con)
        finally:
            con.close()
    finally:
        for suffix in ("", "-wal", "-shm"):
            pathlib.Path(str(scratch) + suffix).unlink(missing_ok=True)
    with store.read():
        live = _settings_rows(store.con)
    changed_since = sorted(k for k in live if live[k] != restored.get(k))
    missing_live = sorted(k for k in restored if k not in live)
    ok = integrity == "ok"
    detail = {"integrity": integrity, "rows_in_backup": len(restored), "rows_live": len(live),
              "changed_since_backup": changed_since, "only_in_backup": missing_live}
    _log(store, "restore_test", chosen["file"], ok, detail)
    return {"ok": ok, "file": chosen["file"], **detail}


def restore(store: Store, file: str) -> dict:
    """Replace the live vault with a backup. Takes a safety backup first."""
    chosen = next((b for b in list_backups(store) if b["file"] == file), None)
    if not chosen:
        raise FileNotFoundError(file)
    safety = make_backup(store, note=f"before restore of {file}")
    src = pathlib.Path(chosen["path"])
    con = sqlite3.connect(f"file:{src}?mode=ro&immutable=1", uri=True)
    try:
        if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("backup fails integrity check; not restoring")
    finally:
        con.close()
    store.close()
    for suffix in ("", "-wal", "-shm"):
        p = pathlib.Path(str(store.path) + suffix)
        if suffix and p.exists():
            p.unlink()
    shutil.copyfile(src, store.path)
    store.reopen()
    bid = _log(store, "restore", file, True, {"safety_backup": safety["file"]})
    return {"id": bid, "restored": file, "safety_backup": safety["file"]}


def log(store: Store, limit: int = 20) -> list[dict]:
    with store.read():
        rows = store.con.execute("SELECT * FROM backup_log ORDER BY id DESC LIMIT ?", (limit,))
        out = []
        for r in rows:
            d = dict(r)
            d["ok"] = bool(d["ok"])
            try:
                d["detail"] = json.loads(d["detail"]) if d["detail"] else None
            except ValueError:
                pass
            out.append(d)
        return out


def next_run(store: Store) -> str:
    hh, _, mm = str(settings.get_value(store, "backup.time")).partition(":")
    now = datetime.now()
    run = now.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
    if run <= now:
        run += timedelta(days=1)
    return run.isoformat(timespec="minutes")
