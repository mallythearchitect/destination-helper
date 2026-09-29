"""Autonomous workflows: things the engine does on its own, on a schedule,
each a registered action, each run recorded, each result landing where it
should (observations, the AI inbox, the log). Settings → Logic → workflows
says when each runs and whether it is on."""
from __future__ import annotations

import json
import threading
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import actions, settings
from .ids import uuid7
from .store import Store, now_iso


@dataclass(frozen=True)
class Workflow:
    name: str
    description: str
    action: str                 # the action to run
    payload: dict
    default: dict               # {"every": "day"|"week"|"hour", "at": "HH:MM", "enabled": bool}
    needs: str | None = None    # a secret that must be set, e.g. ANTHROPIC_API_KEY


REGISTRY: dict[str, Workflow] = {}


def register(w: Workflow) -> None:
    REGISTRY[w.name] = w


def schedule(store: Store) -> dict[str, dict]:
    """Per-workflow schedule: the Logic setting over the built-in default."""
    try:
        override = settings.get_value(store, "logic.workflows")
    except Exception:
        override = {}
    return {n: {**w.default, **(override.get(n) or {})} for n, w in REGISTRY.items()}


def describe(store: Store) -> list[dict]:
    from . import secrets
    sched = schedule(store)
    with store.read():
        last = {r["name"]: dict(r) for r in store.con.execute(
            "SELECT name, started_at, finished_at, ok, error FROM workflow_runs WHERE id IN (SELECT max(id) FROM workflow_runs GROUP BY name)")}
    out = []
    for n, w in REGISTRY.items():
        s = sched[n]
        out.append({"name": n, "description": w.description, "action": w.action, "schedule": s,
                    "needs": w.needs, "ready": not w.needs or secrets.is_set(w.needs), "last_run": last.get(n),
                    "next_run": next_run(store, n).isoformat(timespec="minutes") if s.get("enabled", True) else None})
    return out


def _tz(store: Store) -> ZoneInfo:
    try:
        return ZoneInfo(settings.get_value(store, "profile.time_zone"))
    except Exception:
        return ZoneInfo("America/New_York")


def next_run(store: Store, name: str, after: datetime | None = None) -> datetime:
    s = schedule(store)[name]
    now = after or datetime.now(_tz(store))
    hh, _, mm = str(s.get("at", "00:00")).partition(":")
    every = s.get("every", "day")
    if every == "hour":
        return (now.replace(minute=int(mm or 0), second=0, microsecond=0) + timedelta(hours=1)) if now.minute >= int(mm or 0) else now.replace(minute=int(mm or 0), second=0, microsecond=0)
    run = now.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
    if every == "week":
        target = int(s.get("weekday", 0))          # 0 = Monday
        run += timedelta(days=(target - run.weekday()) % 7)
    if run <= now:
        run += timedelta(days=7 if every == "week" else 1)
    return run


def last_run_at(store: Store, name: str) -> datetime | None:
    with store.read():
        r = store.con.execute("SELECT started_at FROM workflow_runs WHERE name=? AND trigger IN ('schedule','startup') ORDER BY id DESC LIMIT 1", (name,)).fetchone()
    return datetime.fromisoformat(r[0]).astimezone(_tz(store)) if r else None


def run(store: Store, name: str, trigger: str = "you") -> dict:
    w = REGISTRY.get(name)
    if not w:
        raise KeyError(name)
    rid = uuid7()
    with store.tx() as con:
        con.execute("INSERT INTO workflow_runs(id, name, trigger, started_at) VALUES(?,?,?,?)", (rid, name, trigger, now_iso()))
    try:
        payload = dict(w.payload)
        if w.action == "track.snapshot" or w.action == "predict.write_forecasts":
            payload["run_id"] = rid
        result = actions.run(store, w.action, payload, "workflow")
        ok, err = True, None
    except Exception as e:
        result, ok, err = None, False, f"{e}"
        traceback.print_exc()
    with store.tx() as con:
        con.execute("UPDATE workflow_runs SET finished_at=?, ok=?, result=?, error=? WHERE id=?",
                    (now_iso(), int(ok), json.dumps(result, default=str)[:20000] if result is not None else None, err, rid))
    return {"run_id": rid, "name": name, "ok": ok, "result": result, "error": err}


def runs(store: Store, name: str | None = None, limit: int = 50) -> list[dict]:
    with store.read():
        q = "SELECT * FROM workflow_runs" + (" WHERE name=?" if name else "") + " ORDER BY id DESC LIMIT ?"
        out = []
        for r in store.con.execute(q, (name, limit) if name else (limit,)):
            d = dict(r)
            d["result"] = json.loads(d["result"]) if d["result"] else None
            out.append(d)
        return out


def due_now(store: Store) -> list[str]:
    """Workflows whose scheduled time has passed since their last scheduled run (or never ran)."""
    from . import secrets
    out = []
    now = datetime.now(_tz(store))
    for n, w in REGISTRY.items():
        s = schedule(store)[n]
        if not s.get("enabled", True) or (w.needs and not secrets.is_set(w.needs)):
            continue
        last = last_run_at(store, n)
        # the most recent scheduled moment at or before now
        prev = next_run(store, n, now - timedelta(days=8 if s.get("every") == "week" else 1 if s.get("every") == "day" else 0, hours=1 if s.get("every") == "hour" else 0))
        while prev > now:
            prev -= timedelta(days=7 if s.get("every") == "week" else 1) if s.get("every") != "hour" else timedelta(hours=1)
        if last is None or last < prev:
            out.append(n)
    return out


class Runner:
    """A thread that wakes every minute, runs what is due, and catches up
    after the Mac was asleep (a due run that was missed runs at once)."""

    def __init__(self, store: Store):
        self.store, self.stop = store, threading.Event()
        self.thread = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        self.thread.start()

    def _loop(self):
        if self.stop.wait(5):
            return
        while not self.stop.is_set():
            try:
                for name in due_now(self.store):
                    run(self.store, name, trigger="schedule")
            except Exception as e:
                print("workflow runner:", e)
            if self.stop.wait(60):
                return
