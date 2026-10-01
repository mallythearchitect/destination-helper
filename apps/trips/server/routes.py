"""Ways to do one leg, compared (W02, "Every way from A to B").

The core rule is a simple route optimizer: for each option, ride minutes =
distance / speed x 60; an option with a distance or speed of zero or less is
skipped as invalid; the fastest one wins. Around that rule: a time you know
beats the arithmetic, the mode's usual speed fills in a missing speed, the
straight-line distance between the two places fills in a missing distance,
time at the terminal makes it door-to-door, and price ranks it too. Every
number says where it came from. Every rule is in Settings → Logic →
Trips · comparing ways to do a leg."""
from __future__ import annotations

import math
import re
from datetime import timedelta

from engine.store import Store

from . import queries as q

SUFFIX = re.compile(r"\b(international airport|airport|bus terminal|terminal|station|pier|town|city|centre|center)\b", re.I)
GROUND = {"bus", "van", "taxi", "transfer", "drive", "train"}
ROAD = {"bus", "van", "taxi", "transfer", "drive"}       # legs a road route answers; trains and ferries do not


def rules(store: Store) -> dict:
    return q.logic(store, "logic.trips.route_options")


def _candidates(place: str | None) -> list[str]:
    """'Rassada Pier, Phuket Town' → ['Rassada', 'Phuket', ...]: names worth looking up."""
    if not place:
        return []
    out = []
    for part in re.split(r"[,()·→/]| - ", place):
        part = part.strip()
        if not part:
            continue
        for c in (part, SUFFIX.sub("", part).strip(" -")):
            c = re.sub(r"\s+", " ", c).strip()
            if c and c.lower() not in [x.lower() for x in out]:
                out.append(c)
    return out


def locate(store: Store, place: str | None) -> dict | None:
    """The biggest place in the reference pack whose name matches a part of `place`."""
    with store.read():
        for c in _candidates(place):
            r = store.con.execute("SELECT name, country, lat, lon FROM pack_destinations.places WHERE lower(name)=lower(?) AND lat IS NOT NULL "
                                  "ORDER BY population IS NULL, population DESC LIMIT 1", (c,)).fetchone()
            if r:
                return dict(r)
    return None


def _miles(a: dict, b: dict) -> float:
    r = 3958.8
    p1, p2 = math.radians(a["lat"]), math.radians(b["lat"])
    dp, dl = math.radians(b["lat"] - a["lat"]), math.radians(b["lon"] - a["lon"])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def estimate_distance(store: Store, a: str | None, b: str | None, mode: str, R: dict) -> tuple[float | None, str | None]:
    pa, pb = locate(store, a), locate(store, b)
    if not pa or not pb or (pa["lat"], pa["lon"]) == (pb["lat"], pb["lon"]):
        return None, None
    d = _miles(pa, pb)
    if mode in GROUND:
        return round(d * R["road_factor"], 1), f"{pa['name']} → {pb['name']}, straight line × {R['road_factor']} (GeoNames)"
    return round(d, 1), f"{pa['name']} → {pb['name']}, straight line (GeoNames)"


def short(place: str | None) -> str:
    return (place or "").split(",")[0].split("(")[0].strip() or "?"


def estimate(store: Store, o: dict, R: dict, online: bool = True) -> dict:
    """Stored on a way when it is saved: its distance (and, for road legs, the road time), and where they came from.
    Road legs get a real road route; trains get the straight line times road_factor; ferries and flights the straight line."""
    blank = {"est_distance_miles": None, "est_minutes": None, "est_source": None}
    if o.get("minutes") is not None or (o.get("distance_miles") is not None and o.get("speed_mph") is not None):
        return blank                                   # nothing to estimate: you gave the numbers
    if not (o.get("from_place") and o.get("to_place")):
        return blank
    from . import geo
    a, b = geo.geocode(store, o["from_place"], R, online), geo.geocode(store, o["to_place"], R, online)
    if not a or not b or (round(a["lat"], 4), round(a["lon"], 4)) == (round(b["lat"], 4), round(b["lon"], 4)):
        return blank
    names = f"{short(o['from_place'])} → {short(o['to_place'])}"
    where = "OpenStreetMap" if "nominatim" in (a["source"], b["source"]) else "GeoNames"
    if o["mode"] in ROAD:
        r = geo.road(store, a, b, R, online)
        if r:
            return {"est_distance_miles": r["miles"], "est_minutes": r["minutes"], "est_source": f"{names}, {r['source']}"}
    d = _miles(a, b)
    if o["mode"] in GROUND:
        return {"est_distance_miles": round(d * R["road_factor"], 1), "est_minutes": None, "est_source": f"{names}, straight line × {R['road_factor']} ({where})"}
    over = "over water" if o["mode"] == "ferry" else "great circle" if o["mode"] == "flight" else "straight line"
    return {"est_distance_miles": round(d, 1), "est_minutes": None, "est_source": f"{names}, {over} ({where})"}


def work_out(store: Store, o: dict, trip: dict, R: dict) -> dict:
    """One option's numbers: ride and door-to-door minutes, arrival, prices, and why it is skipped if it is."""
    out = {**o, "skip": None, "distance_used": None, "distance_source": None, "speed_used": None, "speed_source": None,
           "ride_minutes": None, "minutes_source": None, "terminal_minutes": int(R["terminal_minutes"].get(o["mode"], 0)),
           "door_minutes": None, "arrive_at": None, "flags": []}
    if o.get("minutes") is not None:
        if o["minutes"] <= 0:
            out["skip"] = "The time is invalid, so this option is skipped."
        else:
            out["ride_minutes"], out["minutes_source"] = int(o["minutes"]), "you"
    # the route optimizer's validity rule: a distance or speed of zero or less is skipped
    elif o.get("distance_miles") is not None and o["distance_miles"] <= 0:
        out["skip"] = "The distance is invalid, so this option is skipped."
    elif o.get("speed_mph") is not None and o["speed_mph"] <= 0:
        out["skip"] = "The speed is invalid, so this option is skipped."
    else:
        if o.get("distance_miles") is not None:
            out["distance_used"], out["distance_source"] = float(o["distance_miles"]), "you"
        elif o.get("est_distance_miles"):
            out["distance_used"], out["distance_source"] = float(o["est_distance_miles"]), o.get("est_source")
        else:
            out["distance_used"], out["distance_source"] = estimate_distance(store, o.get("from_place"), o.get("to_place"), o["mode"], R)
        factor = float((R.get("road_minutes_factor") or {}).get(o["mode"], 1.0))
        if o.get("speed_mph") is not None:
            out["speed_used"], out["speed_source"] = float(o["speed_mph"]), "you"
        elif o.get("est_minutes") and o.get("distance_miles") is None:
            # a real road route gave a driving time: use it, scaled for the mode (a bus stops more than a car)
            out["ride_minutes"] = round(float(o["est_minutes"]) * factor)
            out["minutes_source"] = "road time" + (f" × {factor:g} for a {o['mode']}" if factor != 1 else "")
        else:
            sp = R["speed_mph"].get(o["mode"])
            out["speed_used"], out["speed_source"] = (float(sp), f"usual {o['mode']} speed") if sp else (None, None)
        if out["ride_minutes"] is None and out["distance_used"] and out["speed_used"]:
            out["ride_minutes"] = round(out["distance_used"] / out["speed_used"] * 60)
            out["minutes_source"] = "distance ÷ speed × 60"
    if out["ride_minutes"] is not None:
        out["door_minutes"] = out["ride_minutes"] + out["terminal_minutes"]
        start = q.parse_local(o.get("depart_at"), trip.get("time_zone"))
        if start and q.has_time(o.get("depart_at")):
            out["arrive_at"] = q.local_iso(start + timedelta(minutes=out["ride_minutes"]))
    g, pp, n = q.group_total(o.get("price_cents"), o.get("basis"), None, trip["headcount"])
    out.update({"group_cents": g, "per_person_cents": pp, "headcount_used": n, "home_cents": q.to_home(g, o.get("currency"), trip)})
    if o.get("last_departure") and q.has_time(o.get("depart_at")) and o["depart_at"][11:16] > o["last_departure"]:
        out["flags"].append(f"leaves after the last one of the day ({o['last_departure']})")
    if trip.get("budget_leg_cents") and out["home_cents"] is not None and out["home_cents"] > trip["budget_leg_cents"]:
        out["flags"].append("over the per-leg budget")
    return out


def _rank(opts: list[dict], by: str) -> list[str]:
    usable = [o for o in opts if not o["skip"]]
    timed = [o for o in usable if o["door_minutes"] is not None]
    priced = [o for o in usable if o["home_cents"] is not None]
    if by == "cheapest":
        key = lambda o: (o["home_cents"] is None, o["home_cents"] or 0, o["door_minutes"] if o["door_minutes"] is not None else 10**9)  # noqa: E731
    elif by == "balanced" and timed and priced:
        tmin, tmax = min(o["door_minutes"] for o in timed), max(o["door_minutes"] for o in timed)
        cmin, cmax = min(o["home_cents"] for o in priced), max(o["home_cents"] for o in priced)
        def key(o):
            t = (o["door_minutes"] - tmin) / (tmax - tmin) if o["door_minutes"] is not None and tmax > tmin else (0 if o["door_minutes"] is not None else 1)
            c = (o["home_cents"] - cmin) / (cmax - cmin) if o["home_cents"] is not None and cmax > cmin else (0 if o["home_cents"] is not None else 1)
            return (t + c) / 2
    else:   # fastest: the route optimizer's rule
        key = lambda o: (o["door_minutes"] is None, o["door_minutes"] if o["door_minutes"] is not None else 0, o["home_cents"] or 0)  # noqa: E731
    return [o["id"] for o in sorted(usable, key=key)] + [o["id"] for o in opts if o["skip"]]


def _norm(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def groups(store: Store, tid: str, trip: dict | None = None) -> list[dict]:
    """Every leg with options: the options worked out, ranked three ways, with the fastest, cheapest and best named."""
    R = rules(store)
    with store.read():
        con = store.con
        trip = trip or q.trip_row(con, tid)
        rows = [dict(r) for r in con.execute("SELECT * FROM trip_options WHERE trip_id=? AND deleted_at IS NULL ORDER BY created_at", (tid,))]
        live_items = {r[0] for r in con.execute("SELECT id FROM trip_items WHERE trip_id=? AND deleted_at IS NULL", (tid,))}
    by: dict[str, dict] = {}
    for o in rows:
        if o["item_id"] and o["item_id"] not in live_items:
            continue
        key = o["item_id"] or f"{o['day'] or (o['depart_at'] or '')[:10]}|{_norm(o['from_place'])}|{_norm(o['to_place'])}"
        g = by.setdefault(key, {"key": key, "item_id": o["item_id"], "day": o["day"] or (o["depart_at"] or "")[:10] or None,
                                "from_place": o["from_place"], "to_place": o["to_place"], "options": []})
        g["options"].append(work_out(store, o, trip, R))
    out = []
    for g in by.values():
        opts = g["options"]
        usable = [o for o in opts if not o["skip"]]
        timed = [o for o in usable if o["door_minutes"] is not None]
        priced = [o for o in usable if o["home_cents"] is not None]
        g["orders"] = {k: _rank(opts, k) for k in ("fastest", "cheapest", "balanced")}
        g["rank_by"] = R["rank_by"]
        g["fastest_id"] = min(timed, key=lambda o: o["door_minutes"])["id"] if timed else None
        g["cheapest_id"] = min(priced, key=lambda o: o["home_cents"])["id"] if priced else None
        ok = [i for i in g["orders"][R["rank_by"]] if next(o for o in opts if o["id"] == i)["skip"] is None
              and not next(o for o in opts if o["id"] == i)["flags"]]
        g["best_id"] = ok[0] if ok else None
        g["chosen_id"] = next((o["id"] for o in opts if o["chosen_at"]), None)
        g["valid"], g["skipped"] = len(usable), [o for o in opts if o["skip"]]
        order = {i: n for n, i in enumerate(g["orders"][R["rank_by"]])}
        g["options"] = sorted(opts, key=lambda o: order.get(o["id"], 99))
        out.append(g)
    return sorted(out, key=lambda g: (g["day"] or "9999", g["key"]))


def fmt_minutes(m: int | None) -> str:
    if m is None:
        return "time unknown"
    h, mm = divmod(int(m), 60)
    return f"{h} h {mm:02d}" if h else f"{mm} min"
