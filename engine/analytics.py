"""Analytics over tracked series: rollups, trend, change, anomalies,
comparisons. Plain arithmetic, every number explainable."""
from __future__ import annotations

import math
from datetime import date, timedelta

from . import settings, tracking
from .store import Store


def _d(s: str) -> date:
    return date.fromisoformat(s)


def rollup(points: list[dict], step: str = "day", how: str = "last") -> list[dict]:
    """Group daily points into weeks or months. how: last (levels) | sum (flows) | mean."""
    if step == "day":
        return points
    buckets: dict[str, list[float]] = {}
    for p in points:
        d = _d(p["as_of"])
        key = (d - timedelta(days=d.weekday())).isoformat() if step == "week" else d.strftime("%Y-%m-01")
        buckets.setdefault(key, []).append(p["value"])
    agg = {"last": lambda v: v[-1], "sum": sum, "mean": lambda v: sum(v) / len(v), "min": min, "max": max}[how]
    return [{"as_of": k, "value": round(agg(v), 4), "n": len(v)} for k, v in sorted(buckets.items())]


def trend(points: list[dict]) -> dict:
    """Least-squares line through the series: slope per day, and the change over the window."""
    n = len(points)
    if n < 2:
        return {"n": n, "slope_per_day": 0.0, "change": 0.0, "change_pct": None, "first": points[0]["value"] if points else None,
                "last": points[-1]["value"] if points else None, "direction": "flat"}
    x0 = _d(points[0]["as_of"])
    xs = [(_d(p["as_of"]) - x0).days for p in points]
    ys = [p["value"] for p in points]
    mx, my = sum(xs) / n, sum(ys) / n
    den = sum((x - mx) ** 2 for x in xs) or 1.0
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / den
    change = ys[-1] - ys[0]
    pct = round(change / abs(ys[0]) * 100, 1) if ys[0] else None
    return {"n": n, "slope_per_day": round(slope, 4), "change": round(change, 2), "change_pct": pct, "first": ys[0], "last": ys[-1],
            "direction": "up" if slope > 0 else "down" if slope < 0 else "flat", "days": xs[-1]}


def moving_average(points: list[dict], window: int = 7) -> list[dict]:
    out = []
    for i, p in enumerate(points):
        w = [q["value"] for q in points[max(0, i - window + 1): i + 1]]
        out.append({"as_of": p["as_of"], "value": round(sum(w) / len(w), 4)})
    return out


def anomalies(points: list[dict], window: int = 30, z: float = 2.5) -> list[dict]:
    """Points more than z standard deviations from the trailing window's mean."""
    out = []
    for i, p in enumerate(points):
        prev = [q["value"] for q in points[max(0, i - window): i]]
        if len(prev) < 5:
            continue
        mean = sum(prev) / len(prev)
        sd = math.sqrt(sum((v - mean) ** 2 for v in prev) / len(prev)) or 0.0
        if sd == 0:
            continue
        score = (p["value"] - mean) / sd
        if abs(score) >= z:
            out.append({"as_of": p["as_of"], "value": p["value"], "expected": round(mean, 2), "z": round(score, 2)})
    return out


def compare(store: Store, metric_id: str, subjects: list[str], since: str | None = None, until: str | None = None,
            step: str = "day", how: str = "last") -> dict:
    out = {}
    for s in subjects:
        pts = rollup(tracking.series(store, metric_id, s, since, until), step, how)
        out[s] = {"points": pts, "trend": trend(pts), "latest": pts[-1]["value"] if pts else None,
                  "total": round(sum(p["value"] for p in pts), 2)}
    return {"metric": metric_id, "subjects": out}


def summary(store: Store, metric_id: str, subject: str = "all", since: str | None = None, until: str | None = None,
            step: str = "day", how: str = "last") -> dict:
    pts = rollup(tracking.series(store, metric_id, subject, since, until), step, how)
    try:
        L = settings.get_value(store, "logic.analytics")
    except Exception:
        L = {}
    return {"metric": metric_id, "subject": subject, "step": step, "points": pts, "trend": trend(pts),
            "moving_average": moving_average(pts, int(L.get("moving_average_days", 7)) if step == "day" else 3),
            "anomalies": anomalies(pts, int(L.get("anomaly_window_days", 30)), float(L.get("anomaly_z", 2.5))),
            "latest": pts[-1] if pts else None, "min": min((p["value"] for p in pts), default=None),
            "max": max((p["value"] for p in pts), default=None), "total": round(sum(p["value"] for p in pts), 2)}
