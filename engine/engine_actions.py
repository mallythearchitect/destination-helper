"""The engine's own actions: tracking, prediction, workflows, sources. Registered
like an app's, so pages, the scheduler and the AI plug all press the same buttons."""
from __future__ import annotations

from pydantic import BaseModel, Field

from . import predict, sources, tracking, workflows
from .actions import action
from .store import Store


class Observe(BaseModel):
    metric_id: str = Field(description="e.g. trips.planned_cost; define it first with track.define if new")
    subject: str = Field("all", description="what it is about: an account id, a category, a place id, or 'all'")
    as_of: str = Field(description="YYYY-MM-DD")
    value: float
    source: str = Field("you", description="where the number came from")
    confidence: str = Field("verified", description="verified | estimate | predicted")


@action("track.observe", "Record one tracked value: a metric, what it is about, the date, the value, and where it came from.", Observe)
def observe(store: Store, i: Observe, app: str = "track") -> dict:
    return tracking.observe(store, i.metric_id, i.subject, i.as_of, i.value, i.source, i.confidence)


class Define(BaseModel):
    id: str
    label: str
    unit: str = Field("count", description="cents | count | score | percent | miles")
    kind: str = Field("level", description="level (a balance, a score) | flow (per period) | event")
    app: str = "you"
    meaning: str = ""


@action("track.define", "Define a metric to track: what it measures, in what unit, level or flow.", Define)
def define(store: Store, i: Define, app: str = "track") -> dict:
    if i.kind not in ("level", "flow", "event"):
        raise ValueError("kind is level, flow or event")
    return tracking.define(store, i.id, i.label, i.unit, i.kind, i.app, i.meaning)


class Snapshot(BaseModel):
    run_id: str | None = None


@action("track.snapshot", "Write today's tracked numbers for every trip: planned cost, booked, still to book, open blockers and warnings, tasks open.", Snapshot)
def snapshot(store: Store, i: Snapshot, app: str = "track") -> dict:
    from apps.trips.server import tracking as tt
    return tt.snapshot(store, run_id=i.run_id)


class Forecasts(BaseModel):
    run_id: str | None = None


@action("predict.write_forecasts", "Forecast every tracked level 30 days ahead; store as 'predicted' so the forecasts can be scored later.", Forecasts)
def write_forecasts(store: Store, i: Forecasts, app: str = "predict") -> dict:
    return predict.write_forecasts(store, i.run_id)


class CheckSources(BaseModel):
    pass


@action("sources.check", "Re-fetch every registered source link and flag what changed or died.", CheckSources)
def check_sources(store: Store, i: CheckSources, app: str = "sources") -> dict:
    r = sources.check(store)
    r.pop("details", None)
    return r


class Backup(BaseModel):
    pass


@action("backup.nightly", "Back up the vault, prune old copies, and run the restore test.", Backup)
def nightly_backup(store: Store, i: Backup, app: str = "backup") -> dict:
    from . import backup
    made = backup.make_backup(store, note="workflow")
    test = backup.restore_test(store, file=made["file"])
    return {"file": made["file"], "restore_test_ok": test["ok"]}


# ---- the autonomous workflows -------------------------------------------------------

workflows.register(workflows.Workflow("trips.check_all", "Re-run the plan checker on every trip that is not done, so new blockers (deadlines, stale prices, unanswered messages) show by morning.",
                                      "trips.check_all", {}, {"every": "day", "at": "06:00", "enabled": True}))
workflows.register(workflows.Workflow("track.snapshot", "Write today's tracked numbers for every trip.", "track.snapshot", {},
                                      {"every": "day", "at": "00:05", "enabled": True}))
workflows.register(workflows.Workflow("predict.forecasts", "Forecast tracked numbers 30 days ahead.", "predict.write_forecasts", {},
                                      {"every": "day", "at": "00:10", "enabled": True}))
workflows.register(workflows.Workflow("sources.check", "Re-check every source link.", "sources.check", {},
                                      {"every": "week", "at": "03:00", "weekday": 0, "enabled": True}))
workflows.register(workflows.Workflow("backup.nightly", "Back up the vault and prove it restores.", "backup.nightly", {},
                                      {"every": "day", "at": "02:30", "enabled": True}))
