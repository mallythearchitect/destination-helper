"""The AI inbox. A workflow files suggestions here; nothing happens until the
person approves one, and approval runs an ordinary action (so it lands in
history and can be undone). Every decision also becomes a labelled example
for the test set."""
from __future__ import annotations

import json

from .. import actions
from ..ids import uuid7
from ..store import Store, now_iso


def file(store: Store, *, workflow: str, call_id: str | None, subject: str, summary: str, action: str, payload: dict,
         confidence: float | None, why: str | None) -> dict:
    sid = uuid7()
    with store.tx() as con:
        # one pending suggestion per subject per workflow: a new one supersedes the old
        con.execute("UPDATE ai_suggestions SET status='superseded', decided_at=? WHERE workflow=? AND subject=? AND status='pending'",
                    (now_iso(), workflow, subject))
        con.execute("INSERT INTO ai_suggestions(id, ts, workflow, call_id, subject, summary, action, payload, confidence, why) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (sid, now_iso(), workflow, call_id, subject, summary, action, json.dumps(payload), confidence, why))
    return get(store, sid)


def _row(r) -> dict:
    d = dict(r)
    d["payload"] = json.loads(d["payload"])
    d["result"] = json.loads(d["result"]) if d["result"] else None
    return d


def get(store: Store, sid: str) -> dict:
    with store.read():
        r = store.con.execute("SELECT * FROM ai_suggestions WHERE id=?", (sid,)).fetchone()
    if not r:
        raise LookupError(sid)
    return _row(r)


def pending(store: Store, workflow: str | None = None, limit: int = 200) -> list[dict]:
    with store.read():
        if workflow:
            rows = store.con.execute("SELECT * FROM ai_suggestions WHERE status='pending' AND workflow=? ORDER BY id DESC LIMIT ?",
                                     (workflow, limit))
        else:
            rows = store.con.execute("SELECT * FROM ai_suggestions WHERE status='pending' ORDER BY id DESC LIMIT ?", (limit,))
        return [_row(r) for r in rows]


def recent(store: Store, limit: int = 100) -> list[dict]:
    with store.read():
        return [_row(r) for r in store.con.execute("SELECT * FROM ai_suggestions ORDER BY id DESC LIMIT ?", (limit,))]


def approve(store: Store, sid: str, by: str = "you", payload_override: dict | None = None) -> dict:
    s = get(store, sid)
    if s["status"] != "pending":
        raise ValueError(f"already {s['status']}")
    payload = {**s["payload"], **(payload_override or {})}
    with store.tx() as con:
        result = actions.run(store, s["action"], dict(payload), "ai-inbox")
        con.execute("UPDATE ai_suggestions SET status='approved', decided_at=?, decided_by=?, payload=?, result=? WHERE id=?",
                    (now_iso(), by, json.dumps(payload), json.dumps(result, default=str), sid))
        _learn(con, s, payload, "corrected" if payload_override else "approved")
    return get(store, sid)


def reject(store: Store, sid: str, by: str = "you") -> dict:
    s = get(store, sid)
    if s["status"] != "pending":
        raise ValueError(f"already {s['status']}")
    with store.tx() as con:
        con.execute("UPDATE ai_suggestions SET status='rejected', decided_at=?, decided_by=? WHERE id=?", (now_iso(), by, sid))
    return get(store, sid)


def _learn(con, s: dict, final_payload: dict, source: str) -> None:
    """An approved (or corrected) suggestion is a labelled example."""
    example = s["payload"].get("_example")
    if not example:
        return
    expected = {k: v for k, v in final_payload.items() if not k.startswith("_")}
    con.execute("INSERT INTO ai_examples(id, ts, test_set, input, expected, source) VALUES(?,?,?,?,?,?)",
                (uuid7(), now_iso(), s["workflow"], json.dumps(example), json.dumps(expected), source))
