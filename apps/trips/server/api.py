"""Trips' read endpoints. Writes go through /v1/actions/trips.*"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from . import queries

router = APIRouter(prefix="/v1/trips")


def _store(request: Request):
    return request.app.state.store


@router.get("")
def trips(request: Request):
    return queries.trips(_store(request))


@router.get("/options")
def options(request: Request):
    return queries.options(_store(request))


@router.get("/helper")
def helper(request: Request):
    """The capability list from the pack: questions with codes, workflows with steps, guardrails, methods, the brief."""
    return queries.helper(_store(request))


@router.get("/helper/regions/{rid}")
def region(rid: str, request: Request):
    try:
        return queries.region(_store(request), rid)
    except LookupError:
        raise HTTPException(404, f"no region pack {rid}")


@router.get("/briefing/{tid}")
def briefing(tid: str, request: Request):
    """The plan as plain text, what the helper chat reads."""
    try:
        return {"text": queries.briefing(_store(request), tid)}
    except LookupError:
        raise HTTPException(404, f"no trip {tid}")


@router.get("/{tid}/ways")
def ways(tid: str, request: Request):
    """Every leg with options: worked out (ride and door-to-door minutes, prices, why one is skipped) and ranked fastest, cheapest and balanced."""
    from . import routes
    return routes.groups(_store(request), tid)


@router.get("/{tid}/calendar.ics")
def calendar(tid: str, request: Request):
    """Every item and deadline as a calendar file (ADMIN-03): open it in Google Calendar or Apple Calendar."""
    try:
        body = queries.ics(_store(request), tid)
    except LookupError:
        raise HTTPException(404, f"no trip {tid}")
    return Response(body, media_type="text/calendar", headers={"Content-Disposition": f'attachment; filename="trip-{tid[:8]}.ics"'})


@router.get("/{tid}/costs")
def costs(tid: str, request: Request):
    try:
        return queries.costs(_store(request), tid)
    except LookupError:
        raise HTTPException(404, f"no trip {tid}")


@router.get("/{tid}/findings")
def findings(tid: str, request: Request, all: bool = False):
    s = _store(request)
    with s.read():
        return queries.findings(s.con, tid, all_=all)


@router.get("/{tid}")
def plan(tid: str, request: Request):
    """The whole plan: the trip, items by day with 'leave by' and live links, nights, tasks, expenses, confirmations, open findings, costs."""
    try:
        return queries.plan(_store(request), tid)
    except LookupError:
        raise HTTPException(404, f"no trip {tid}")
