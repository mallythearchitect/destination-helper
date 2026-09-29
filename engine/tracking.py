"""Tracking: every number worth watching, as observations over time.

Apps define metrics once and write observations whenever they know a value
(a snapshot job does it nightly for every trip). Analytics reads series from
here; prediction extends them forward and writes its forecasts back as
observations marked 'predicted', so a forecast can later be scored against
what happened."""
from __future__ import annotations

from datetime import date

from .ids import uuid7
from .store import Store, now_iso


def define(store: Store, id: str, label: str, unit: str, kind: str, app: str, meaning: str) -> dict:
    with store.tx() as con:
        con.execute("INSERT INTO metrics(id, label, unit, kind, app, meaning, created_at) VALUES(?,?,?,?,?,?,?) "
                    "ON CONFLICT(id) DO UPDATE SET label=excluded.label, unit=excluded.unit, kind=excluded.kind, meaning=excluded.meaning",
                    (id, label, unit, kind, app, meaning, now_iso()))
        return dict(con.execute("SELECT * FROM metrics WHERE id=?", (id,)).fetchone())


def metrics(store: Store, app: str | None = None) -> list[dict]:
    with store.read():
        q = "SELECT m.*, (SELECT count(*) FROM observations o WHERE o.metric_id=m.id) AS observations, "\
            "(SELECT max(as_of) FROM observations o WHERE o.metric_id=m.id) AS latest FROM metrics m"
        rows = store.con.execute(q + (" WHERE m.app=?" if app else "") + " ORDER BY m.app, m.id", (app,) if app else ())
        return [dict(r) for r in rows]


def observe(store: Store, metric_id: str, subject: str, as_of: str | date, value: float, source: str,
            confidence: str = "verified", run_id: str | None = None) -> dict:
    """One value. The same metric/subject/date/source is replaced, not duplicated."""
    as_of = as_of.isoformat() if isinstance(as_of, date) else as_of
    with store.tx() as con:
        if not con.execute("SELECT 1 FROM metrics WHERE id=?", (metric_id,)).fetchone():
            raise LookupError(f"no metric {metric_id}; define it first")
        con.execute("INSERT INTO observations(id, metric_id, subject, as_of, value, source, confidence, run_id, created_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(metric_id, subject, as_of, source) DO UPDATE SET value=excluded.value, "
                    "confidence=excluded.confidence, run_id=excluded.run_id, created_at=excluded.created_at",
                    (uuid7(), metric_id, subject, as_of, float(value), source, confidence, run_id, now_iso()))
        r = con.execute("SELECT * FROM observations WHERE metric_id=? AND subject=? AND as_of=? AND source=?",
                        (metric_id, subject, as_of, source)).fetchone()
        return dict(r)


def observe_many(store: Store, rows: list[dict], run_id: str | None = None) -> int:
    n = 0
    for r in rows:
        observe(store, r["metric_id"], r["subject"], r["as_of"], r["value"], r["source"], r.get("confidence", "verified"), run_id)
        n += 1
    return n


def series(store: Store, metric_id: str, subject: str = "all", since: str | None = None, until: str | None = None,
           include_predicted: bool = False, limit: int = 5000) -> list[dict]:
    where, args = ["metric_id=?", "subject=?"], [metric_id, subject]
    if since:
        where.append("as_of>=?"); args.append(since)  # noqa: E702
    if until:
        where.append("as_of<=?"); args.append(until)  # noqa: E702
    if not include_predicted:
        where.append("confidence<>'predicted'")
    with store.read():
        rows = store.con.execute(f"SELECT as_of, value, source, confidence FROM observations WHERE {' AND '.join(where)} "
                                 "ORDER BY as_of, created_at LIMIT ?", [*args, limit])
        seen = {}
        for r in rows:              # one value per day: the latest written wins
            seen[r["as_of"]] = dict(r)
        return list(seen.values())


def subjects(store: Store, metric_id: str) -> list[str]:
    with store.read():
        return [r[0] for r in store.con.execute("SELECT DISTINCT subject FROM observations WHERE metric_id=? ORDER BY subject", (metric_id,))]


def latest(store: Store, metric_id: str, subject: str = "all") -> dict | None:
    s = series(store, metric_id, subject)
    return s[-1] if s else None
