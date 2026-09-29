"""Labelled examples and the score each model gets on them. A workflow moves
to another model only if its score holds up."""
from __future__ import annotations

import json

from ..ids import uuid7
from ..store import Store, now_iso


def add_example(store: Store, test_set: str, input_: dict, expected: dict, source: str = "hand") -> str:
    eid = uuid7()
    with store.tx() as con:
        con.execute("INSERT INTO ai_examples(id, ts, test_set, input, expected, source) VALUES(?,?,?,?,?,?)",
                    (eid, now_iso(), test_set, json.dumps(input_), json.dumps(expected), source))
    return eid


def examples(store: Store, test_set: str) -> list[dict]:
    with store.read():
        return [{**dict(r), "input": json.loads(r["input"]), "expected": json.loads(r["expected"])}
                for r in store.con.execute("SELECT * FROM ai_examples WHERE test_set=? ORDER BY id", (test_set,))]


def record_run(store: Store, *, test_set: str, model: str, prompt_version: str, n: int, correct: int,
               cost_cents: float, detail: list) -> dict:
    rid = uuid7()
    score = round(correct / n, 3) if n else 0.0
    with store.tx() as con:
        con.execute("INSERT INTO ai_test_runs(id, ts, test_set, model, prompt_version, examples, correct, score, cost_cents, detail) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?)", (rid, now_iso(), test_set, model, prompt_version, n, correct, score, cost_cents,
                                                    json.dumps(detail)[:20000]))
    return {"id": rid, "test_set": test_set, "model": model, "prompt_version": prompt_version, "examples": n,
            "correct": correct, "score": score, "cost_cents": cost_cents}


def runs(store: Store, test_set: str | None = None, limit: int = 50) -> list[dict]:
    with store.read():
        if test_set:
            rows = store.con.execute("SELECT * FROM ai_test_runs WHERE test_set=? ORDER BY id DESC LIMIT ?", (test_set, limit))
        else:
            rows = store.con.execute("SELECT * FROM ai_test_runs ORDER BY id DESC LIMIT ?", (limit,))
        out = []
        for r in rows:
            d = dict(r)
            d["detail"] = json.loads(d["detail"]) if d["detail"] else None
            out.append(d)
        return out
