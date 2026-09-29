"""Reads over the destinations pack, merged with the person's own list
(records of type place carrying the pack id)."""
from __future__ import annotations

import json
import math

from engine import settings
from engine.store import Store

DOMAINS = ["career", "entrepreneurship", "tech", "network", "lifestyle", "safety", "affordability", "quality_of_life"]
DOMAIN_LABEL = {"career": "Career", "entrepreneurship": "Entrepreneurship", "tech": "Tech", "network": "Network", "lifestyle": "Lifestyle",
                "safety": "Safety", "affordability": "Affordability", "quality_of_life": "Quality of life"}
GOAL_LABEL = {"growth": "Growth", "entrepreneurship": "Entrepreneurship", "tech": "Tech", "network": "Network", "lifestyle": "Lifestyle",
              "affordable": "Affordable", "safe_and_calm": "Safe & calm", "balanced": "Balanced"}
KIND_LABEL = {"us_city": "US business city", "intl_city": "International business city", "leisure": "Leisure destination",
              "world_city": "World city", "us_place": "US place"}
POP_STEPS = [15000, 100000, 250000, 1000000, 5000000]
DEFAULTS = {"kind": "us_city", "goal": "growth", "min_population": 250000, "all_view_min_population": 1000000, "population_steps": POP_STEPS, "compare_limit": 4}


def defaults(store: Store) -> dict:
    return {**DEFAULTS, **settings.get_value(store, "logic.destinations.defaults")}
STATUSES = [["shortlist", "Shortlist"], ["want", "Want to go"], ["base", "Base candidate"], ["visited", "Visited"]]


def haversine_miles(lat1, lon1, lat2, lon2) -> float | None:
    if None in (lat1, lon1, lat2, lon2):
        return None
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)))


def home(store: Store) -> dict:
    return settings.get_value(store, "profile.home_city")


def _saved(con) -> dict[str, dict]:
    """The person's records for pack places: keyed by pack id."""
    out = {}
    for r in con.execute("SELECT id, data, external_ids, version FROM entities WHERE type='place' AND deleted_at IS NULL"):
        ext = json.loads(r["external_ids"])
        pid = ext.get("pack_place")
        if pid:
            d = json.loads(r["data"])
            n = con.execute("SELECT count(*) FROM notes WHERE entity_id=? AND deleted_at IS NULL", (r["id"],)).fetchone()[0]
            out[pid] = {"record_id": r["id"], "status": d.get("status"), "notes": n, "version": r["version"]}
    return out


def goal_weights(store: Store) -> dict[str, dict[str, float]]:
    """Settings → Logic → goals and their weights (the pack's table is the original source of the defaults)."""
    return settings.get_value(store, "logic.destinations.goal_weights")


def extra_domain_rules(store: Store) -> dict:
    return settings.get_value(store, "logic.destinations.extra_domains")


def extra_scores(rules: dict, index_values: dict[str, float]) -> dict[str, dict]:
    """Scores computed at read time from a city's index values, per the Logic setting."""
    out = {}
    for domain, spec in rules.items():
        v = index_values.get(spec["index"])
        if v is None:
            continue
        out[domain] = {"value": round(max(0, min(100, v * spec["multiply"] + spec["add"]))), "confidence": "index-derived",
                       "from_indexes": [spec["index"]]}
    return out


def _index_values(con) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for r in con.execute("SELECT place_id, index_id, value FROM pack_destinations.index_values"):
        out.setdefault(r["place_id"], {})[r["index_id"]] = r["value"]
    return out


TRAVEL = [
    ("directions", "Directions", "Google Maps, driving / transit from home", "https://www.google.com/maps/dir/?api=1&origin={home}&destination={dest}"),
    ("flights", "Flights", "Google Flights, live fares", "https://www.google.com/travel/flights?q=flights%20from%20{home_q}%20to%20{dest_q}"),
    ("all_modes", "All ways", "Rome2Rio: plane, train, bus, ferry, drive, with live times and prices", "https://www.rome2rio.com/map/{home_path}/{dest_path}"),
    ("train", "Train", "Amtrak (US only)", "https://www.amtrak.com/home.html"),
]


def ways_there(home: dict, p: dict) -> list[dict]:
    """Live links for getting from home to a place. First on the popup, before the information."""
    from urllib.parse import quote
    dest = p["name"] + (f", {p['region']}" if p.get("region") and p["kind"] != "leisure" else "") + (f", {p['country']}" if p.get("country") and p.get("country") != "United States" else "")
    if p["kind"] == "leisure" and p.get("hub"):
        dest = f"{p['hub']}, {p['name']}"
    h = home.get("name", "")
    out = []
    for key, label, means, url in TRAVEL:
        if key == "train" and p.get("country_code") not in ("US", None):
            continue
        out.append({"key": key, "label": label, "means": means, "live": True,
                    "url": url.format(home=quote(h), dest=quote(dest), home_q=quote(h), dest_q=quote(dest),
                                      home_path=quote(h.replace(", ", "-").replace(" ", "-")), dest_path=quote(dest.replace(", ", "-").replace(" ", "-")))})
    return out


def fit(scores: dict[str, float], weights: dict[str, float]) -> float | None:
    """Weighted average over the domains the goal names (a domain the goal doesn't mention counts nothing)."""
    if not scores or not weights:
        return None
    tot = sum(w for d, w in weights.items() if d in scores)
    return round(sum(scores[d] * w for d, w in weights.items() if d in scores) / tot, 1) if tot else None


def places(store: Store, kind: str | None = None, q: str = "", tier: str | None = None, max_cost: int | None = None,
           goal: str | None = None, saved_only: bool = False, sort: str = "fit", limit: int = 500, min_pop: int | None = None,
           country: str | None = None) -> list[dict]:
    """kind: us_city | intl_city | leisure | world_city | us_place | all. 'all' means every scored
    place plus world cities above min_pop (default 1,000,000 so the map stays readable); a search
    looks at every place regardless of size."""
    h = home(store)
    D = defaults(store)
    where, args = ["1=1"], []
    q = (q or "").strip()
    if kind and kind != "all":
        where.append("p.kind=?"); args.append(kind)  # noqa: E702
        if kind == "world_city" and not q:      # a search looks at every city, whatever its size
            where.append("p.population>=?"); args.append(min_pop if min_pop is not None else D["min_population"])  # noqa: E702
    elif q:
        pass                               # a search covers everything
    else:
        where.append("(p.kind IN ('us_city','intl_city','leisure') OR (p.kind='world_city' AND p.population>=?))")
        args.append(min_pop if min_pop is not None else D["all_view_min_population"])
    if country:
        where.append("p.country_code=?"); args.append(country.upper())  # noqa: E702
    if q:
        fields = [f for f in settings.get_value(store, "logic.destinations.search_fields") if f in ("name", "region", "country", "tags", "description", "hub", "timezone")] or ["name"]
        where.append("(" + " OR ".join(f"lower(p.{f}) LIKE ?" for f in fields) + ")")
        args += [f"%{q.lower()}%"] * len(fields)
    if tier:
        where.append("p.tier=?"); args.append(tier)  # noqa: E702
    if max_cost is not None:
        where.append("p.cost_per_day<=?"); args.append(max_cost)  # noqa: E702
    gw = goal_weights(store).get(goal or D["goal"], {})
    rules = extra_domain_rules(store)
    with store.read():
        con = store.con
        saved = _saved(con)
        rows = [dict(r) for r in con.execute(f"SELECT p.* FROM pack_destinations.places p WHERE {' AND '.join(where)} "
                                             "ORDER BY (p.kind='world_city'), p.population DESC LIMIT ?", [*args, max(limit * 4, 2000)])]
        sc: dict[str, dict] = {}
        for r in con.execute("SELECT place_id, domain, value, confidence FROM pack_destinations.scores"):
            sc.setdefault(r["place_id"], {})[r["domain"]] = r["value"]
        iv = _index_values(con)
    for pid, vals in iv.items():
        for dom, s in extra_scores(rules, vals).items():
            sc.setdefault(pid, {})[dom] = s["value"]
    out = []
    for p in rows:
        p["tags"] = json.loads(p["tags"])
        p["kind_label"] = KIND_LABEL.get(p["kind"], p["kind"])
        p["scores"] = sc.get(p["id"], {})
        p["fit"] = fit(p["scores"], gw) if p["scores"] else None
        p["distance_miles"] = haversine_miles(h.get("lat"), h.get("lon"), p["lat"], p["lon"])
        p.update(saved.get(p["id"], {"record_id": None, "status": None, "notes": 0}))
        if saved_only and not p["status"] and not p["notes"]:
            continue
        out.append(p)
    key = {"fit": lambda x: (-(x["fit"] or -1), -(x["population"] or 0)), "cost": lambda x: (x["cost_per_day"] is None, x["cost_per_day"] or 0),
           "population": lambda x: -(x["population"] or 0),
           "distance": lambda x: (x["distance_miles"] is None, x["distance_miles"] or 0), "name": lambda x: x["name"].lower(),
           "tier": lambda x: ({"S": 0, "A": 1, "B": 2, "C": 3, "D": 4, "core": 0, "expansion": 1, "watch": 2}.get(x["tier"], 9), x["name"])}
    out.sort(key=key.get(sort, key["fit"]))
    return out[:limit]


def place(store: Store, pid: str) -> dict:
    h = home(store)
    with store.read():
        con = store.con
        r = con.execute("SELECT * FROM pack_destinations.places WHERE id=?", (pid,)).fetchone()
        if not r:
            raise LookupError(pid)
        p = dict(r)
        p["tags"] = json.loads(p["tags"])
        p["kind_label"] = KIND_LABEL.get(p["kind"], p["kind"])
        p["scores"] = [{"domain": x["domain"], "value": x["value"], "confidence": x["confidence"], "from_indexes": json.loads(x["from_indexes"])}
                       for x in con.execute("SELECT * FROM pack_destinations.scores WHERE place_id=? ORDER BY domain", (pid,))]
        base = {s["domain"] for s in p["scores"]}
        ivals = {r["index_id"]: r["value"] for r in con.execute("SELECT index_id, value FROM pack_destinations.index_values WHERE place_id=?", (pid,))}
        for dom, s in extra_scores(extra_domain_rules(store), ivals).items():
            if dom not in base:
                p["scores"].append({"domain": dom, **s})
        idx = {x["id"]: dict(x) for x in con.execute("SELECT * FROM pack_destinations.indexes")}
        p["index_values"] = [{"index_id": x["index_id"], "value": x["value"], "name": (idx.get(x["index_id"]) or {}).get("name", x["index_id"]),
                              "edition": (idx.get(x["index_id"]) or {}).get("edition"), "urls": json.loads((idx.get(x["index_id"]) or {}).get("urls", "[]"))}
                             for x in con.execute("SELECT * FROM pack_destinations.index_values WHERE place_id=?", (pid,))]
        ds = con.execute("SELECT * FROM pack_destinations.datasets WHERE id=?", (p["dataset_id"],)).fetchone()
        p["dataset"] = dict(ds) if ds else None
        p["distance_miles"] = haversine_miles(h.get("lat"), h.get("lon"), p["lat"], p["lon"])
        p["home"] = h
        p.update(_saved(con).get(pid, {"record_id": None, "status": None, "notes": 0}))
        p["goal_fits"] = {g: fit({s["domain"]: s["value"] for s in p["scores"]}, w) for g, w in goal_weights(store).items()} if p["scores"] else {}
        for s in p["scores"]:
            s["label"] = DOMAIN_LABEL.get(s["domain"], s["domain"])
        p["cost_split"] = cost_split(store, p["cost_per_day"])
    p["ways_there"] = ways_there(h, p)
    return p


def cost_method(con) -> dict:
    r = con.execute("SELECT value FROM pack_destinations.method WHERE key='cost_per_day'").fetchone()
    return json.loads(r[0]) if r else {"split": []}


def cost_split(store: Store, cost_per_day: int | None) -> list[dict]:
    """Shares from Settings → Logic; what each part means from the pack's method text."""
    if cost_per_day is None:
        return []
    shares = settings.get_value(store, "logic.destinations.cost_split")
    with store.read():
        means = {part: m for part, _, m in cost_method(store.con)["split"]}
    return [{"part": part, "share": share, "means": means.get(part, ""), "amount": round(cost_per_day * share, 2)} for part, share in shares.items()]


def sources_view(store: Store) -> dict:
    from engine import sources
    with store.read():
        con = store.con
        datasets = [dict(r) for r in con.execute("SELECT * FROM pack_destinations.datasets")]
        indexes = [{**dict(r), "urls": json.loads(r["urls"])} for r in con.execute("SELECT * FROM pack_destinations.indexes")]
        services = [dict(r) for r in con.execute("SELECT * FROM pack_destinations.services")]
        method = {r["key"]: json.loads(r["value"]) for r in con.execute("SELECT * FROM pack_destinations.method")}
        meta = {r["key"]: r["value"] for r in con.execute("SELECT * FROM pack_destinations.meta")}
    method["goal_weights"] = goal_weights(store)
    method["extra_domains"] = extra_domain_rules(store)
    method["cost_split_shares"] = settings.get_value(store, "logic.destinations.cost_split")
    method["flight_guess"] = settings.get_value(store, "logic.destinations.flight_guess")
    return {"pack": meta, "datasets": datasets, "indexes": indexes, "services": services, "method": method,
            "travel": [{"key": k, "label": lbl, "means": m, "url": u.split("{")[0]} for k, lbl, m, u in TRAVEL],
            "registry": sources.all_sources(store), "logic_keys": ["logic.destinations.goal_weights", "logic.destinations.extra_domains",
                                                                  "logic.destinations.cost_split", "logic.destinations.flight_guess"]}


def trip_cost(days: int, people: int, cost_per_day: int | None, distance_miles: int | None, flight_each: int | None = None,
              housing: bool = True, split: list[dict] | None = None, flight_rule: dict | None = None) -> dict:
    """A rough figure, every input visible. Cost per day is split into lodging, food,
    transport and other by the pack's shares; 'no housing needed' drops lodging.
    Flights: your number, else a distance-based guess (about $0.11 a mile each way, floor $120)."""
    guessed = flight_each is None
    if guessed:
        fr = flight_rule or {"dollars_per_mile_each_way": 0.11, "floor": 120}
        flight_each = 0 if not distance_miles else max(int(fr["floor"]), round(distance_miles * fr["dollars_per_mile_each_way"] * 2))
    parts = [dict(s) for s in (split or [])]
    if not housing:
        parts = [s for s in parts if s["part"] != "lodging"]
    per_day = round(sum(s["amount"] for s in parts), 2) if parts else (cost_per_day or 0)
    lines = [{"part": s["part"], "per_day": s["amount"], "total": round(s["amount"] * days * people, 2), "means": s["means"]} for s in parts]
    daily = round(per_day * days * people, 2)
    flights = flight_each * people
    return {"days": days, "people": people, "cost_per_day": cost_per_day, "per_day_used": per_day, "housing": housing, "lines": lines,
            "daily_total": daily, "flight_each": flight_each, "flights_total": flights, "total": round(daily + flights, 2),
            "assumption": "flight guessed from distance" if guessed and flight_each else None}
