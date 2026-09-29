"""Trips' tracked numbers: per trip, per day. Written nightly by track.snapshot
so the home screen can show how a plan firmed up over time (planned cost,
booked, still to book, open findings, open tasks)."""
from __future__ import annotations

from datetime import date

from engine import tracking
from engine.store import Store

from . import queries as q

METRICS = [
    ("trips.planned_cost", "Planned cost", "cents", "level", "Every counted item, home currency, for the group."),
    ("trips.booked_cost", "Booked cost", "cents", "level", "Booked, confirmed and done items, home currency."),
    ("trips.to_book_cost", "Still to book", "cents", "level", "Items still to book, home currency."),
    ("trips.open_blockers", "Open blockers", "count", "level", "Blockers the checker has open."),
    ("trips.open_warnings", "Open warnings", "count", "level", "Warnings the checker has open."),
    ("trips.tasks_open", "Tasks open", "count", "level", "Before-you-go and follow-up tasks not done."),
    ("trips.spent", "Actually spent", "cents", "level", "Logged expenses, home currency."),
]


def snapshot(store: Store, run_id: str | None = None, today: date | None = None) -> dict:
    today = (today or date.today()).isoformat()
    for mid, label, unit, kind, meaning in METRICS:
        tracking.define(store, mid, label, unit, kind, "trips", meaning)
    rows = []
    for t in q.trips(store):
        if t["stage"] == "done":
            continue
        c = q.costs(store, t["id"])
        f = t["findings"]
        vals = {"trips.planned_cost": c["planned_home_cents"], "trips.booked_cost": c["booked_home_cents"], "trips.to_book_cost": c["to_book_home_cents"],
                "trips.open_blockers": f.get("blocker", 0), "trips.open_warnings": f.get("warn", 0), "trips.tasks_open": t["tasks_open"], "trips.spent": c["actual_home_cents"]}
        for mid, v in vals.items():
            rows.append({"metric_id": mid, "subject": t["id"], "as_of": today, "value": v, "source": "track.snapshot", "confidence": "verified"})
    n = tracking.observe_many(store, rows, run_id=run_id)
    return {"observations": n, "trips": len({r["subject"] for r in rows}), "as_of": today}
