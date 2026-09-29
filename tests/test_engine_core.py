"""The engine's own jobs: tracking, analytics, prediction, autonomous workflows, on Trips."""
from datetime import date, datetime, timedelta


def act(client, action_name, **payload):
    r = client.post(f"/v1/actions/{action_name}", json=payload)
    assert r.status_code == 200, (action_name, r.text)
    return r.json()


def test_tracking_defines_metrics_and_records_observations(client):
    act(client, "track.define", id="body.weight", label="Weight", unit="count", kind="level", app="you", meaning="morning weight in lb")
    act(client, "track.observe", metric_id="body.weight", subject="me", as_of="2026-09-01", value=180)
    act(client, "track.observe", metric_id="body.weight", subject="me", as_of="2026-09-02", value=179.5)
    act(client, "track.observe", metric_id="body.weight", subject="me", as_of="2026-09-02", value=179)     # same day: replaced
    s = client.get("/v1/track/series?metric=body.weight&subject=me").json()
    assert [p["value"] for p in s["points"]] == [180, 179] and s["subjects"] == ["me"]
    assert next(x for x in client.get("/v1/track/metrics").json() if x["id"] == "body.weight")["observations"] == 2
    assert client.post("/v1/actions/track.observe", json={"metric_id": "nope", "subject": "me", "as_of": "2026-09-01", "value": 1}).status_code == 404


def test_snapshot_tracks_every_trip(client):
    t = act(client, "trips.create", name="Thailand", headcount=2, start_date="2026-11-13", end_date="2026-11-28", local_currency="THB", fx_rate=33.4)
    act(client, "trips.add_item", trip_id=t["id"], kind="flight", title="DMK → KBV", start_at="2026-11-17T17:20", end_at="2026-11-17T18:45", status="booked", price_cents=10593, currency="USD", basis="group")
    act(client, "trips.add_item", trip_id=t["id"], kind="ferry", title="Boat", start_at="2026-11-20T15:00", status="to_book", price_cents=90000, currency="THB", basis="per_person")
    act(client, "trips.add_task", trip_id=t["id"], title="Arrival card", due="2026-11-10")
    act(client, "trips.run_checks", trip_id=t["id"])
    r = act(client, "track.snapshot")
    assert r["trips"] == 1 and r["observations"] == 7
    planned = client.get(f"/v1/track/series?metric=trips.planned_cost&subject={t['id']}").json()["points"]
    assert planned[-1]["value"] == 10593 + round(180000 / 33.4)
    assert client.get(f"/v1/track/series?metric=trips.to_book_cost&subject={t['id']}").json()["points"][-1]["value"] == round(180000 / 33.4)
    assert client.get(f"/v1/track/series?metric=trips.open_warnings&subject={t['id']}").json()["points"][-1]["value"] >= 1     # nights with no stay
    assert client.get(f"/v1/track/series?metric=trips.tasks_open&subject={t['id']}").json()["points"][-1]["value"] == 1
    a = client.get(f"/v1/analytics/summary?metric=trips.planned_cost&subject={t['id']}").json()
    assert a["latest"]["value"] == planned[-1]["value"]
    act(client, "trips.set_stage", id=t["id"], stage="done")
    assert act(client, "track.snapshot")["trips"] == 0


def test_series_forecast_and_scoring(client):
    act(client, "track.define", id="steps", label="Steps", unit="count", kind="level", app="you", meaning="")
    for i in range(30):
        act(client, "track.observe", metric_id="steps", subject="me", as_of=(date.today() - timedelta(days=30 - i)).isoformat(), value=8000 + i * 50 + (i % 7) * 100)
    f = client.get("/v1/predict/series?metric=steps&subject=me&days=14").json()
    assert len(f["points"]) == 14 and f["slope_per_day"] > 30 and f["points"][0]["low"] < f["points"][0]["value"] < f["points"][0]["high"]
    r = act(client, "predict.write_forecasts")
    assert r["written"] >= 14 and "cashflow" not in r
    assert len(client.get("/v1/track/series?metric=steps&subject=me&predicted=true").json()["points"]) > 30
    act(client, "track.observe", metric_id="steps", subject="me", as_of=(date.today() + timedelta(days=1)).isoformat(), value=9500)
    sc = client.get("/v1/predict/score?metric=steps&subject=me").json()
    assert sc["scored"] == 1 and sc["mean_abs_error"] is not None
    assert client.get("/v1/predict/cashflow").status_code == 404


def test_workflows_are_listed_scheduled_and_runnable(client):
    w = client.get("/v1/workflows").json()
    names = {x["name"]: x for x in w["workflows"]}
    assert set(names) == {"trips.check_all", "track.snapshot", "predict.forecasts", "sources.check", "backup.nightly"}
    assert names["trips.check_all"]["ready"] and names["track.snapshot"]["next_run"]
    t = act(client, "trips.create", name="T", headcount=1, start_date="2026-12-01", end_date="2026-12-03")
    r = client.post("/v1/workflows/trips.check_all/run").json()
    assert r["ok"] and r["result"]["trips"] == 1 and r["result"]["counts"][t["id"]]["warn"] >= 1
    runs = client.get("/v1/workflows").json()["runs"]
    assert runs[0]["name"] == "trips.check_all" and runs[0]["trigger"] == "you" and runs[0]["ok"] == 1
    assert client.post("/v1/workflows/nope/run").status_code == 404
    sched = client.get("/v1/settings/logic.workflows").json()["value"]
    sched["backup.nightly"]["enabled"] = False
    assert client.put("/v1/settings/logic.workflows", json={"value": sched}).status_code == 200
    assert next(x for x in client.get("/v1/workflows").json()["workflows"] if x["name"] == "backup.nightly")["next_run"] is None
    sched["backup.nightly"] = {"every": "day", "at": "25:00", "enabled": True}
    assert client.put("/v1/settings/logic.workflows", json={"value": sched}).status_code == 400
    from engine import workflows
    store = client.app.state.store
    sched = client.get("/v1/settings/logic.workflows").json()["value"]
    sched["sources.check"] = {"every": "day", "at": (datetime.now() - timedelta(minutes=5)).strftime("%H:%M"), "enabled": True}
    client.put("/v1/settings/logic.workflows", json={"value": sched})
    assert "sources.check" in workflows.due_now(store)
