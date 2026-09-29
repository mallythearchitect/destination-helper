"""Destinations reads. Writes go through /v1/actions/destinations.*"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from engine import settings, sources

from . import queries

router = APIRouter(prefix="/v1/destinations")


def _store(request: Request):
    return request.app.state.store


@router.get("/options")
def options(request: Request):
    s = _store(request)
    goals = list(queries.goal_weights(s))
    with s.read():
        tiers = [r[0] for r in s.con.execute("SELECT DISTINCT tier FROM pack_destinations.places WHERE tier IS NOT NULL ORDER BY tier")]
    counts = {}
    with s.read():
        for r in s.con.execute("SELECT kind, count(*) FROM pack_destinations.places GROUP BY kind"):
            counts[r[0]] = r[1]
    return {"kinds": [{"id": k, "label": v, "count": counts.get(k, 0)} for k, v in queries.KIND_LABEL.items()],
            "goals": [{"id": g, "label": queries.GOAL_LABEL.get(g, g)} for g in goals], "tiers": tiers,
            "statuses": queries.STATUSES, "domains": [{"id": d, "label": queries.DOMAIN_LABEL[d]} for d in queries.DOMAINS],
            "pop_steps": queries.defaults(s)["population_steps"], "defaults": queries.defaults(s), "home": queries.home(s)}


@router.get("/places")
def places(request: Request, kind: str | None = None, q: str = "", tier: str | None = None, max_cost: int | None = None,
           goal: str | None = None, saved: bool = False, sort: str = "fit", limit: int = Query(500, ge=1, le=2000),
           min_pop: int | None = None, country: str | None = None):
    return queries.places(_store(request), kind=kind, q=q, tier=tier, max_cost=max_cost, goal=goal, saved_only=saved, sort=sort,
                          limit=limit, min_pop=min_pop, country=country)


@router.get("/places/{pid}")
def place(pid: str, request: Request):
    try:
        return queries.place(_store(request), pid)
    except LookupError:
        raise HTTPException(404, "no such place")


@router.get("/trip-cost")
def trip_cost(request: Request, place_id: str, days: int = Query(7, ge=1, le=365), people: int = Query(1, ge=1, le=20),
              flight_each: int | None = None, housing: bool = True):
    p = queries.place(_store(request), place_id)
    return {"place": {"id": p["id"], "name": p["name"], "hub": p["hub"]},
            **queries.trip_cost(days, people, p["cost_per_day"], p["distance_miles"], flight_each, housing=housing, split=p["cost_split"],
                                flight_rule=settings.get_value(_store(request), "logic.destinations.flight_guess"))}


@router.get("/sources")
def sources_view(request: Request):
    return queries.sources_view(_store(request))


@router.post("/sources/check")
def sources_check(request: Request, id: str | None = None):
    """Re-fetch every source (or one) and flag what changed or died. Real network."""
    return sources.check(_store(request), only_ids=[id] if id else None)


@router.post("/sources/seed")
def sources_seed(request: Request):
    return {"added": sources.seed_from_packs(_store(request))}
