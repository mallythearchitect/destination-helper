"""Prediction: a straight-line forecast with a band for every tracked level, written
back as observations marked 'predicted' so it can be scored against what happens."""
from __future__ import annotations

import math
from datetime import date, timedelta

from . import analytics, settings, tracking
from .store import Store


def forecast_series(points: list[dict], horizon_days: int = 30) -> dict:
    n = len(points)
    if n < 7:
        return {"method": "not enough history", "points": [], "band": None}
    t = analytics.trend(points)
    x0 = date.fromisoformat(points[0]["as_of"])
    xs = [(date.fromisoformat(p["as_of"]) - x0).days for p in points]
    ys = [p["value"] for p in points]
    my, mx = sum(ys) / n, sum(xs) / n
    intercept = my - t["slope_per_day"] * mx
    # weekly pattern: average residual by weekday
    resid_by_wd: dict[int, list[float]] = {}
    for p, x, y in zip(points, xs, ys, strict=True):
        wd = date.fromisoformat(p["as_of"]).weekday()
        resid_by_wd.setdefault(wd, []).append(y - (intercept + t["slope_per_day"] * x))
    wd_adj = {wd: sum(v) / len(v) for wd, v in resid_by_wd.items()}
    resid = [y - (intercept + t["slope_per_day"] * x) - wd_adj.get(date.fromisoformat(p["as_of"]).weekday(), 0) for p, x, y in zip(points, xs, ys, strict=True)]
    sd = math.sqrt(sum(r * r for r in resid) / max(1, len(resid) - 1))
    last = date.fromisoformat(points[-1]["as_of"])
    out = []
    for k in range(1, horizon_days + 1):
        d = last + timedelta(days=k)
        x = (d - x0).days
        v = intercept + t["slope_per_day"] * x + wd_adj.get(d.weekday(), 0)
        out.append({"as_of": d.isoformat(), "value": round(v, 2), "low": round(v - 1.28 * sd, 2), "high": round(v + 1.28 * sd, 2)})
    return {"method": "trend line + weekly pattern; band = 80% of residuals", "slope_per_day": t["slope_per_day"], "band_sd": round(sd, 2),
            "history_days": t["days"], "points": out}


def score(store: Store, metric_id: str, subject: str = "all") -> dict:
    """How past predictions did against what happened: mean absolute error, by how far ahead."""
    with store.read():
        preds = [dict(r) for r in store.con.execute(
            "SELECT as_of, value, created_at FROM observations WHERE metric_id=? AND subject=? AND confidence='predicted'", (metric_id, subject))]
    actual = {p["as_of"]: p["value"] for p in tracking.series(store, metric_id, subject)}
    errs = [abs(p["value"] - actual[p["as_of"]]) for p in preds if p["as_of"] in actual]
    return {"metric": metric_id, "subject": subject, "predictions": len(preds), "scored": len(errs),
            "mean_abs_error": round(sum(errs) / len(errs), 2) if errs else None}


def write_forecasts(store: Store, run_id: str | None = None) -> dict:
    """Nightly: forecast every level metric with enough history; store as 'predicted'."""
    written = 0
    try:
        L = settings.get_value(store, "logic.predict")
    except Exception:
        L = {}
    for m in tracking.metrics(store):
        if m["kind"] != "level":
            continue
        for subj in tracking.subjects(store, m["id"]):
            pts = tracking.series(store, m["id"], subj)
            fc = forecast_series(pts, int(L.get("series_days", 30)))
            for p in fc["points"]:
                tracking.observe(store, m["id"], subj, p["as_of"], p["value"], "predict.forecast_series", "predicted", run_id)
                written += 1
    return {"written": written}
