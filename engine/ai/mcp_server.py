"""The plug: the engine's actions and reads offered as tools over MCP, so a
Claude chat (Claude Code, Claude Desktop) can press the same buttons the
pages have. Every write goes through the same actions, so it lands in
history and can be undone; actions marked dangerous say so in their
description, and the chat client asks before running them.

    .venv/bin/python -m engine.ai.mcp_server        (stdio)

Register it once: scripts/install_mcp.sh
"""
from __future__ import annotations

import json

from mcp.server.mcpserver import MCPServer

from .. import actions, records
from ..store import Store


def build(store: Store | None = None) -> MCPServer:
    import apps.destinations.server.actions  # noqa: F401  registers destinations.*
    import apps.trips.server.actions  # noqa: F401  registers trips.*

    store = store or Store()
    server = MCPServer("destination-helper", instructions=(
        "The Destination Helper: trips, their plans and checks, the helper's capability list, and destinations. "
        "Reads are free. Writes are actions; ones marked DANGEROUS remove things, ask the person first. "
        "Money is integer cents in the currency named on the row."))

    def make(a: actions.Action):
        model = a.model

        def run(input):
            result = a.run(store, input, "mcp")
            return json.dumps(result, default=str)
        run.__name__ = a.name.replace(".", "_")
        run.__annotations__ = {"input": model, "return": str}
        desc = ("DANGEROUS, ask first: " if a.dangerous else "") + a.description
        server.add_tool(run, name=run.__name__, description=desc)

    for a in actions.REGISTRY.values():
        make(a)

    @server.tool(name="search_records", description="Find any record (person, company, place, bill, clipping...) by any word in its name, details, tags or notes.")
    def search_records(q: str, type: str | None = None, limit: int = 20) -> str:
        return json.dumps(records.search(store, q=q, type=type, limit=limit), default=str)

    @server.tool(name="get_record", description="One record in full: details, tags, notes, files, links, history.")
    def get_record(id: str) -> str:
        return json.dumps(records.get_entity(store, id), default=str)

    from apps.destinations.server import queries as dq

    @server.tool(name="destinations_search", description="Find places: business cities, leisure destinations, or any world city of 15,000+ people. q = words; kind = us_city | intl_city | leisure | world_city | all; goal ranks by fit (growth, tech, affordable, safe_and_calm ...).")
    def destinations_search(q: str = "", kind: str = "all", goal: str = "growth", limit: int = 20) -> str:
        return json.dumps(dq.places(store, kind=kind, q=q, goal=goal, limit=limit), default=str)

    @server.tool(name="destinations_place", description="One place in full: scores with confidence and sources, cost per day split, distance from home, the person's status and notes, and the live 'ways to get there' links (directions, flights, all modes, train).")
    def destinations_place(place_id: str) -> str:
        return json.dumps(dq.place(store, place_id), default=str)

    @server.tool(name="destinations_trip_cost", description="Rough trip cost with every input visible: days × people × cost per day (split into lodging / food / transport / other; housing=false drops lodging) plus flights (guessed from distance unless flight_each is given).")
    def destinations_trip_cost(place_id: str, days: int = 7, people: int = 1, flight_each: int | None = None, housing: bool = True) -> str:
        from engine import settings as settings_mod
        p = dq.place(store, place_id)
        return json.dumps(dq.trip_cost(days, people, p["cost_per_day"], p["distance_miles"], flight_each, housing=housing, split=p["cost_split"],
                                       flight_rule=settings_mod.get_value(store, "logic.destinations.flight_guess")), default=str)


    from apps.trips.server import checks as tchecks
    from apps.trips.server import queries as tq

    @server.tool(name="trips_list", description="Every trip with its stage (plan / prepare / run / done), dates, headcount, how many items are still to book, open findings by severity, and the next item.")
    def trips_list() -> str:
        return json.dumps(tq.trips(store), default=str)

    @server.tool(name="trip_plan", description="One trip in full: items by day (legs, stays, activities, pickups) with per-person and group prices, home-currency totals, 'be there by / leave by' times, live links per leg (directions, flights, all ways, the region's booking site, flight status), nights covered, tasks with deadlines, expenses, confirmations, open findings, costs, the region pack summary.")
    def trip_plan(trip_id: str) -> str:
        return json.dumps(tq.plan(store, trip_id), default=str)

    @server.tool(name="trip_checks", description="Run the plan checker on a trip and return the open findings (blocker / warn / info) with a fix for each: pickups before landings, prices with no per-person/group basis, nights with no stay, overlaps, tight connections, airport buffers, last departures, late check-ins, budget caps, stale prices, passport validity, deadlines, unanswered confirmations.")
    def trip_checks(trip_id: str) -> str:
        return json.dumps(tchecks.check_trip(store, trip_id, "mcp"), default=str)

    @server.tool(name="trip_costs", description="A trip's costs with the working: planned vs booked, per person, I pay vs company pays, work vs personal, by kind and by day, actual expenses, what could not be converted and why.")
    def trip_costs(trip_id: str) -> str:
        return json.dumps(tq.costs(store, trip_id), default=str)

    @server.tool(name="trip_leg_options", description="W02 for real: every leg of a trip that has options, each worked out (ride minutes = distance ÷ speed × 60 unless a time is given; door-to-door adds time at the terminal; zero or negative distance or speed is skipped), with prices for the group, flags (misses the last departure, over budget), and the fastest, cheapest and best named. Add options with trips_add_option, pick one with trips_choose_option.")
    def trip_leg_options(trip_id: str) -> str:
        from apps.trips.server import routes as troutes
        return json.dumps(troutes.groups(store, trip_id), default=str)

    @server.tool(name="helper_workflow", description="A Destination Helper workflow by code (W01..W29): when it runs, its steps, what it gives, and its track record. Follow the steps when the person asks that kind of question; log the outcome with trips_log_workflow.")
    def helper_workflow(code: str) -> str:
        h = tq.helper(store)
        w = next((w for w in h["workflows"] if w["code"] == code.upper()), None)
        return json.dumps(w or {"error": f"no workflow {code}", "codes": [w["code"] + " " + w["title"] for w in h["workflows"]]}, default=str)

    @server.tool(name="helper_catalogue", description="The Destination Helper's capability list: the question codes by section (GO, READY, GET, TIME, STAY, DO, MONEY, BOOK, ADMIN, TALK), every workflow's title, the guardrails (G01..) with why each exists, the defaults for every answer, where answers come from, and the checks. section narrows the questions; 'guardrails', 'methods' or 'workflows' returns just that part.")
    def helper_catalogue(section: str | None = None) -> str:
        h = tq.helper(store)
        if section and section.lower() in ("guardrails", "methods", "workflows"):
            return json.dumps(h[section.lower()], default=str)
        if section:
            return json.dumps([q for q in h["questions"] if q["section"] == section.upper()], default=str)
        return json.dumps({"sections": h["sections"], "questions": h["questions"], "workflows": [{"code": w["code"], "title": w["title"], "runs_when": w["runs_when"]} for w in h["workflows"]],
                           "guardrails": h["guardrails"], "defaults": h["methods"].get("defaults", []), "setup": h["methods"].get("setup", [])}, default=str)

    @server.tool(name="helper_region", description="A region pack (e.g. thailand): money, airports and airlines, ground transport and its site's quirks, piers and stations, getting around, how businesses prefer to be messaged, luggage storage, fees, seasons, scams, entry rules, confusing names, stays, booking forms, worked examples, and the region's sites with URL templates.")
    def helper_region(region_id: str = "thailand") -> str:
        try:
            return json.dumps(tq.region(store, region_id), default=str)
        except LookupError:
            return json.dumps({"error": f"no region pack {region_id}", "regions": tq.helper(store)["regions"]})

    @server.tool(name="logic_settings", description="The rules behind every feature (Settings → Logic), as data: per-month factors, statement matching, assumed paid, cost split, flight guess, goal weights, extra domains, prompt overrides. Change one with settings_set.")
    def logic_settings() -> str:
        from engine import settings as settings_mod
        return json.dumps([s for sec in settings_mod.describe(store)["sections"] if sec["id"] == "logic" for s in sec["settings"]], default=str)

    @server.tool(name="settings_set", description="Change a setting by key (see logic_settings or GET /v1/settings). Validated; refused if the shape is wrong.")
    def settings_set(key: str, value: str) -> str:
        from engine import settings as settings_mod
        try:
            v = json.loads(value)
        except ValueError:
            v = value
        return json.dumps(settings_mod.set_value(store, key, v, None, app="mcp"), default=str)

    @server.tool(name="ai_inbox", description="Suggestions waiting for the person's OK (from AI workflows).")
    def ai_inbox() -> str:
        from . import inbox
        return json.dumps(inbox.pending(store), default=str)

    return server


def main() -> None:
    build().run("stdio")


if __name__ == "__main__":
    main()
