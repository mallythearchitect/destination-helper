"""Records: one row per thing, with links, tags, notes, files and search.

Every write is one transaction, records a history row (a full before/after
snapshot, so undo is just "put the snapshot back"), and reindexes the record
for search. Deletes are soft: the row stays, marked deleted_at.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sqlite3
from typing import Any

from . import history
from .ids import uuid7
from .store import Store, now_iso

TYPES = [
    ("person", "Person"), ("company", "Company"), ("place", "Place"), ("bill", "Bill"), ("income", "Income"),
    ("transaction", "Transaction"), ("customer", "Customer"), ("visit", "Visit"), ("job", "Job"),
    ("clipping", "Clipping"), ("media", "Media"), ("bet", "Bet"), ("headline", "Headline"),
    ("source", "Source"), ("note", "Note"), ("other", "Other"),
]
TYPE_LABEL = dict(TYPES)
RELS = ["about", "for", "part_of", "related", "same_as", "mentions"]
TYPE_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
TAG_RE = re.compile(r"^[^\s,][^,]{0,63}$")


class Conflict(Exception):
    def __init__(self, yours: dict, theirs: dict):
        super().__init__("version conflict")
        self.yours, self.theirs = yours, theirs


class NotFound(LookupError):
    pass


def files_dir(store: Store) -> pathlib.Path:
    d = store.path.parent / "files"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---- snapshots ---------------------------------------------------------------

def _entity_row(con: sqlite3.Connection, eid: str, include_deleted=True) -> dict | None:
    r = con.execute("SELECT * FROM entities WHERE id=?", (eid,)).fetchone()
    if not r or (not include_deleted and r["deleted_at"]):
        return None
    d = dict(r)
    d["data"] = json.loads(d["data"])
    d["external_ids"] = json.loads(d["external_ids"])
    return d


PK: dict[str, str] = {}                    # tables whose key column isn't `id`
HARD_DELETE_ON_UNDO = {"trip_findings"}    # tables without deleted_at


def _row(con: sqlite3.Connection, tbl: str, key: str) -> dict | None:
    if tbl == "entities":
        return _entity_row(con, key)
    if tbl == "tags":
        eid, _, tag = key.partition(":")
        r = con.execute("SELECT * FROM tags WHERE entity_id=? AND tag=?", (eid, tag)).fetchone()
        return dict(r) if r else None
    r = con.execute(f"SELECT * FROM {tbl} WHERE {PK.get(tbl, 'id')}=?", (key,)).fetchone()  # noqa: S608 - ours
    return dict(r) if r else None


def _put_row(con: sqlite3.Connection, tbl: str, snap: dict) -> None:
    """Write a full snapshot back (used by undo)."""
    snap = dict(snap)
    if tbl == "entities":
        snap["data"] = json.dumps(snap["data"])
        snap["external_ids"] = json.dumps(snap["external_ids"])
    cols = list(snap)
    con.execute(
        f"INSERT OR REPLACE INTO {tbl}({', '.join(cols)}) VALUES({', '.join('?' * len(cols))})",  # noqa: S608
        [snap[c] for c in cols])


def _flatten(v: Any, out: list[str]) -> None:
    if isinstance(v, dict):
        for k, x in v.items():
            out.append(str(k))
            _flatten(x, out)
    elif isinstance(v, list):
        for x in v:
            _flatten(x, out)
    elif v is not None:
        out.append(str(v))


def reindex(con: sqlite3.Connection, eid: str) -> None:
    con.execute("DELETE FROM search WHERE id=?", (eid,))
    e = _entity_row(con, eid)
    if not e or e["deleted_at"]:
        return
    parts: list[str] = []
    _flatten(e["data"], parts)
    _flatten(e["external_ids"], parts)
    parts += [r[0] for r in con.execute("SELECT tag FROM tags WHERE entity_id=?", (eid,))]
    parts += [r[0] for r in con.execute("SELECT body FROM notes WHERE entity_id=? AND deleted_at IS NULL", (eid,))]
    parts += [r[0] for r in con.execute("SELECT name FROM files WHERE entity_id=? AND deleted_at IS NULL", (eid,))]
    if e["source"]:
        parts.append(e["source"])
    con.execute("INSERT INTO search(id, type, name, text) VALUES(?,?,?,?)", (eid, e["type"], e["name"], " ".join(parts)))  # noqa: E501


# ---- entities ------------------------------------------------------------------

def _validate_entity(type_: str, name: str, data: Any, external_ids: Any) -> None:
    if not TYPE_RE.match(type_ or ""):
        raise ValueError("type must be a short lowercase word, like person or company")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("a record needs a name")
    if not isinstance(data, dict):
        raise ValueError("data must be an object of details")
    if not isinstance(external_ids, dict) or not all(isinstance(v, str) for v in external_ids.values()):
        raise ValueError("external_ids must be name → id text")


def create_entity(store: Store, *, type: str, name: str, data: dict | None = None,
                  external_ids: dict | None = None, source: str | None = None, app: str = "browse") -> dict:
    data, external_ids = data or {}, external_ids or {}
    _validate_entity(type, name, data, external_ids)
    eid, ts = uuid7(), now_iso()
    with store.tx() as con:
        con.execute(
            "INSERT INTO entities(id, type, name, data, external_ids, source, version, created_at, updated_at, updated_by) "  # noqa: E501
            "VALUES(?,?,?,?,?,?,1,?,?,?)",
            (eid, type, name.strip(), json.dumps(data), json.dumps(external_ids), source, ts, ts, app))
        after = _entity_row(con, eid)
        history.record(con, app=app, action="entities.create", tbl="entities", row_key=eid, before=None, after=after)
        reindex(con, eid)
    return after


def get_entity(store: Store, eid: str) -> dict:
    with store.read():
        con = store.con
        e = _entity_row(con, eid)
        if not e:
            raise NotFound(eid)
        e["tags"] = [r[0] for r in con.execute("SELECT tag FROM tags WHERE entity_id=? ORDER BY tag", (eid,))]
        e["notes"] = [dict(r) for r in con.execute(
            "SELECT * FROM notes WHERE entity_id=? AND deleted_at IS NULL ORDER BY id DESC", (eid,))]
        e["files"] = [dict(r) for r in con.execute(
            "SELECT id, name, media_type, bytes, created_at, created_by FROM files "
            "WHERE entity_id=? AND deleted_at IS NULL ORDER BY id DESC", (eid,))]
        e["links"] = [dict(r) for r in con.execute(
            "SELECT l.id, l.rel, l.note, l.created_at, "
            "CASE WHEN l.from_id=? THEN 'out' ELSE 'in' END AS direction, "
            "o.id AS other_id, o.type AS other_type, o.name AS other_name "
            "FROM links l JOIN entities o ON o.id = CASE WHEN l.from_id=? THEN l.to_id ELSE l.from_id END "
            "WHERE (l.from_id=? OR l.to_id=?) AND l.deleted_at IS NULL AND o.deleted_at IS NULL ORDER BY l.id DESC",
            (eid, eid, eid, eid))]
        e["history"] = [history._row(r) for r in con.execute(
            "SELECT * FROM history WHERE (tbl='entities' AND row_key=?) OR row_key LIKE ? "
            "OR (tbl IN ('links','notes','files') AND (json_extract(after,'$.entity_id')=? OR json_extract(before,'$.entity_id')=? "  # noqa: E501
            "OR json_extract(after,'$.from_id')=? OR json_extract(before,'$.from_id')=? "
            "OR json_extract(after,'$.to_id')=? OR json_extract(before,'$.to_id')=?)) ORDER BY id DESC LIMIT 50",
            (eid, eid + ":%", eid, eid, eid, eid, eid, eid))]
    return e


def update_entity(store: Store, eid: str, patch: dict, expected_version: int | None, app: str = "browse") -> dict:
    with store.tx() as con:
        cur = _entity_row(con, eid)
        if not cur or cur["deleted_at"]:
            raise NotFound(eid)
        if expected_version is not None and expected_version != cur["version"]:
            raise Conflict(yours={"patch": patch, "version": expected_version},
                           theirs={k: cur[k] for k in ("name", "type", "data", "external_ids", "source", "version",
                                                        "updated_at", "updated_by")})
        new = {k: patch.get(k, cur[k]) for k in ("type", "name", "data", "external_ids", "source")}
        _validate_entity(new["type"], new["name"], new["data"], new["external_ids"])
        con.execute(
            "UPDATE entities SET type=?, name=?, data=?, external_ids=?, source=?, version=version+1, updated_at=?, updated_by=? "  # noqa: E501
            "WHERE id=?",
            (new["type"], new["name"].strip(), json.dumps(new["data"]), json.dumps(new["external_ids"]), new["source"],
             now_iso(), app, eid))
        after = _entity_row(con, eid)
        history.record(con, app=app, action="entities.update", tbl="entities", row_key=eid, before=cur, after=after)
        reindex(con, eid)
    return after


def delete_entity(store: Store, eid: str, app: str = "browse") -> dict:
    with store.tx() as con:
        cur = _entity_row(con, eid)
        if not cur or cur["deleted_at"]:
            raise NotFound(eid)
        con.execute("UPDATE entities SET deleted_at=?, version=version+1, updated_at=?, updated_by=? WHERE id=?",
                    (now_iso(), now_iso(), app, eid))
        after = _entity_row(con, eid)
        history.record(con, app=app, action="entities.delete", tbl="entities", row_key=eid, before=cur, after=after)
        reindex(con, eid)
    return after


def _fts_query(q: str) -> str:
    toks = re.findall(r"[\w'-]+", q)
    return " ".join('"' + t.replace('"', "") + '"*' for t in toks)


def search(store: Store, q: str = "", type: str | None = None, tag: str | None = None, limit: int = 50,
           include_deleted: bool = False) -> list[dict]:
    q = (q or "").strip()
    where, args = [], []
    if type:
        where.append("e.type=?")
        args.append(type)
    if tag:
        where.append("e.id IN (SELECT entity_id FROM tags WHERE tag=?)")
        args.append(tag)
    if not include_deleted:
        where.append("e.deleted_at IS NULL")
    with store.read():
        if q:
            sql = ("SELECT e.id, e.type, e.name, e.source, e.updated_at, e.deleted_at, bm25(search) AS rank, "
                   "snippet(search, 3, '[', ']', '…', 12) AS snippet FROM search JOIN entities e ON e.id=search.id "
                   "WHERE search MATCH ?" + ("".join(" AND " + w for w in where)) + " ORDER BY rank LIMIT ?")
            rows = store.con.execute(sql, [_fts_query(q), *args, limit])
        else:
            sql = ("SELECT e.id, e.type, e.name, e.source, e.updated_at, e.deleted_at, NULL AS rank, NULL AS snippet FROM entities e"  # noqa: E501
                   + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY e.updated_at DESC LIMIT ?")
            rows = store.con.execute(sql, [*args, limit])
        out = [dict(r) for r in rows]
        for r in out:
            r["tags"] = [t[0] for t in store.con.execute("SELECT tag FROM tags WHERE entity_id=? ORDER BY tag", (r["id"],))]  # noqa: E501
        return out


def known_types(store: Store) -> list[tuple[str, str]]:
    from . import settings
    try:
        return [tuple(p) for p in settings.get_value(store, "logic.records.types")]
    except Exception:
        return TYPES


def relations(store: Store) -> dict:
    from . import settings
    try:
        return settings.get_value(store, "logic.records.relations")
    except Exception:
        return {r: {"out": r.replace("_", " "), "in": r.replace("_", " ") + " this"} for r in RELS}


def types_with_counts(store: Store) -> list[dict]:
    with store.read():
        counts = {r[0]: r[1] for r in store.con.execute(
            "SELECT type, count(*) FROM entities WHERE deleted_at IS NULL GROUP BY type")}
    known = [{"type": t, "label": lbl, "count": counts.pop(t, 0)} for t, lbl in known_types(store)]
    return known + [{"type": t, "label": t, "count": n} for t, n in sorted(counts.items())]


def all_tags(store: Store) -> list[dict]:
    with store.read():
        return [{"tag": r[0], "count": r[1]} for r in store.con.execute(
            "SELECT t.tag, count(*) FROM tags t JOIN entities e ON e.id=t.entity_id WHERE e.deleted_at IS NULL "
            "GROUP BY t.tag ORDER BY count(*) DESC, t.tag")]


# ---- links, tags, notes, files ------------------------------------------------------

def _need(con: sqlite3.Connection, eid: str) -> dict:
    e = _entity_row(con, eid)
    if not e or e["deleted_at"]:
        raise NotFound(eid)
    return e


def link(store: Store, from_id: str, to_id: str, rel: str = "related", note: str | None = None, app: str = "browse") -> dict:  # noqa: E501
    if not TYPE_RE.match(rel or ""):
        raise ValueError("rel must be a short lowercase word, like about or for")
    if from_id == to_id:
        raise ValueError("a record can't link to itself")
    lid = uuid7()
    with store.tx() as con:
        _need(con, from_id)
        _need(con, to_id)
        con.execute("INSERT INTO links(id, from_id, to_id, rel, note, created_at, created_by) VALUES(?,?,?,?,?,?,?)",
                    (lid, from_id, to_id, rel, note, now_iso(), app))
        after = _row(con, "links", lid)
        history.record(con, app=app, action="links.create", tbl="links", row_key=lid, before=None, after=after)
    return after


def unlink(store: Store, lid: str, app: str = "browse") -> dict:
    with store.tx() as con:
        cur = _row(con, "links", lid)
        if not cur or cur["deleted_at"]:
            raise NotFound(lid)
        con.execute("UPDATE links SET deleted_at=? WHERE id=?", (now_iso(), lid))
        after = _row(con, "links", lid)
        history.record(con, app=app, action="links.delete", tbl="links", row_key=lid, before=cur, after=after)
    return after


def tag(store: Store, eid: str, tag_: str, app: str = "browse") -> list[str]:
    tag_ = (tag_ or "").strip().lower()
    if not TAG_RE.match(tag_):
        raise ValueError("a tag is a short word or phrase without commas")
    with store.tx() as con:
        _need(con, eid)
        key = f"{eid}:{tag_}"
        if not _row(con, "tags", key):
            con.execute("INSERT INTO tags(entity_id, tag) VALUES(?,?)", (eid, tag_))
            history.record(con, app=app, action="tags.add", tbl="tags", row_key=key, before=None,
                           after={"entity_id": eid, "tag": tag_})
            reindex(con, eid)
        return [r[0] for r in con.execute("SELECT tag FROM tags WHERE entity_id=? ORDER BY tag", (eid,))]


def untag(store: Store, eid: str, tag_: str, app: str = "browse") -> list[str]:
    with store.tx() as con:
        key = f"{eid}:{tag_}"
        cur = _row(con, "tags", key)
        if not cur:
            raise NotFound(key)
        con.execute("DELETE FROM tags WHERE entity_id=? AND tag=?", (eid, tag_))
        history.record(con, app=app, action="tags.remove", tbl="tags", row_key=key, before=cur, after=None)
        reindex(con, eid)
        return [r[0] for r in con.execute("SELECT tag FROM tags WHERE entity_id=? ORDER BY tag", (eid,))]


def add_note(store: Store, eid: str, body: str, app: str = "browse") -> dict:
    if not isinstance(body, str) or not body.strip():
        raise ValueError("a note needs some text")
    nid = uuid7()
    with store.tx() as con:
        _need(con, eid)
        con.execute("INSERT INTO notes(id, entity_id, body, created_at, created_by) VALUES(?,?,?,?,?)",
                    (nid, eid, body.strip(), now_iso(), app))
        after = _row(con, "notes", nid)
        history.record(con, app=app, action="notes.add", tbl="notes", row_key=nid, before=None, after=after)
        reindex(con, eid)
    return after


def delete_note(store: Store, nid: str, app: str = "browse") -> dict:
    with store.tx() as con:
        cur = _row(con, "notes", nid)
        if not cur or cur["deleted_at"]:
            raise NotFound(nid)
        con.execute("UPDATE notes SET deleted_at=? WHERE id=?", (now_iso(), nid))
        after = _row(con, "notes", nid)
        history.record(con, app=app, action="notes.delete", tbl="notes", row_key=nid, before=cur, after=after)
        reindex(con, cur["entity_id"])
    return after


def attach_file(store: Store, eid: str, name: str, media_type: str, content: bytes, app: str = "browse") -> dict:
    if not content:
        raise ValueError("the file is empty")
    name = pathlib.Path(name or "file").name
    sha = hashlib.sha256(content).hexdigest()
    target = files_dir(store) / sha[:2] / sha
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(content)
    fid = uuid7()
    with store.tx() as con:
        _need(con, eid)
        con.execute("INSERT INTO files(id, entity_id, name, media_type, bytes, sha256, created_at, created_by) "
                    "VALUES(?,?,?,?,?,?,?,?)", (fid, eid, name, media_type or "application/octet-stream",
                                                len(content), sha, now_iso(), app))
        after = _row(con, "files", fid)
        history.record(con, app=app, action="files.attach", tbl="files", row_key=fid, before=None, after=after)
        reindex(con, eid)
    return after


def get_file(store: Store, fid: str) -> tuple[dict, pathlib.Path]:
    with store.read():
        f = _row(store.con, "files", fid)
    if not f or f["deleted_at"]:
        raise NotFound(fid)
    return f, files_dir(store) / f["sha256"][:2] / f["sha256"]


def delete_file(store: Store, fid: str, app: str = "browse") -> dict:
    """Soft: the row is marked deleted and the bytes stay, so undo brings it back."""
    with store.tx() as con:
        cur = _row(con, "files", fid)
        if not cur or cur["deleted_at"]:
            raise NotFound(fid)
        con.execute("UPDATE files SET deleted_at=? WHERE id=?", (now_iso(), fid))
        after = _row(con, "files", fid)
        history.record(con, app=app, action="files.delete", tbl="files", row_key=fid, before=cur, after=after)
        if cur["entity_id"]:
            reindex(con, cur["entity_id"])
    return after


# ---- undo ----------------------------------------------------------------------

def restore_row(con: sqlite3.Connection, tbl: str, key: str, before: dict | None, *, app: str, action: str) -> str:
    """Put a row back to its snapshot. before=None means the row didn't exist:
    a created row is soft-deleted (tags: removed) so its history stays intact."""
    cur = _row(con, tbl, key)
    if before is None:
        if tbl == "tags":
            eid, _, tag_ = key.partition(":")
            con.execute("DELETE FROM tags WHERE entity_id=? AND tag=?", (eid, tag_))
        elif tbl == "entities":
            con.execute("UPDATE entities SET deleted_at=?, version=version+1, updated_at=?, updated_by=? WHERE id=?",
                        (now_iso(), now_iso(), app, key))
        elif tbl in HARD_DELETE_ON_UNDO:
            con.execute(f"DELETE FROM {tbl} WHERE {PK.get(tbl, 'id')}=?", (key,))  # noqa: S608
        else:
            con.execute(f"UPDATE {tbl} SET deleted_at=? WHERE id=?", (now_iso(), key))  # noqa: S608
    else:
        snap = dict(before)
        if tbl == "entities":
            snap["version"] = (cur["version"] if cur else 0) + 1
            snap["updated_at"], snap["updated_by"] = now_iso(), app
        _put_row(con, tbl, snap)
    after = _row(con, tbl, key)
    hid = history.record(con, app=app, action=action, tbl=tbl, row_key=key, before=cur, after=after)
    touched = (after or cur or {})
    eid = key if tbl == "entities" else key.partition(":")[0] if tbl == "tags" else touched.get("entity_id")
    for e in {eid, touched.get("from_id"), touched.get("to_id")} - {None}:
        reindex(con, e)
    return hid
