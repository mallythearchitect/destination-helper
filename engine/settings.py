"""The settings registry and service.

Every setting is declared here once: key, section, type, default, help. The
page renders itself from this registry (GET /v1/settings), so adding a setting
is one line. Stored rows live in the vault's `settings` table; a setting that
was never changed has no row and reads its default.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from typing import Any
from zoneinfo import available_timezones

from . import history, secrets
from .store import Store, now_iso

SECTIONS = [
    ("profile", "Profile", "Who and where you are. Destinations and Trips read these."),
    ("maps", "Maps", "Map keys: Google Maps for street view and 3D, Mapillary for street photos. Optional."),
    ("display", "Display", "Light or dark, layouts, Focus Mode picks."),
    ("data", "Data", "Which outside sources are on, and how often each one refreshes."),
    ("ai", "AI", "Keys for each AI service, which model does which job, the backup model, "
            "the monthly cap, what each model may see."),
    ("backup", "Backup", "Schedule, where backups go, and the restore test."),
    ("logic", "Logic", "How each feature decides: the numbers and rules behind it, as data. Edit them here and the whole "
                       "engine follows. Every one says which feature reads it and where its default came from."),
]

SOURCES = [
    ("google_news", "Google News RSS", "hourly"),
    ("nominatim", "OpenStreetMap / Nominatim (finding places)", "on demand"),
    ("osrm", "OSRM road routes on OpenStreetMap", "on demand"),
    ("gcal_ics", "Google Calendar iCal", "hourly"),
    ("yahoo_prices", "Yahoo prices (build time)", "daily"),
    ("census_acs", "Census ACS (build time)", "monthly"),
    ("openfreemap", "OpenFreeMap tiles", "on demand"),
]
REFRESH = ["on demand", "hourly", "daily", "weekly", "monthly"]
MODELS = ["claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5", "ollama/llama3.2", "none"]
JOBS = [("sort", "Sort and classify"), ("read", "Read and extract"),
        ("draft", "Draft text"), ("answer", "Answer questions (Ask)")]
VISIBILITY_SCOPES = [("trip_data", "Trips: bookings, prices, operator contacts"), ("records", "Records and notes")]
VISIBILITY_OPTIONS = ["cloud", "local", "none"]


@dataclass(frozen=True)
class Setting:
    key: str
    section: str
    label: str
    type: str          # text | integer | number | select | multiselect | toggle | list | map | place
                       # | time_zone | time | sources | jobs | visibility
    default: Any
    help: str = ""
    options: list | None = None
    min: int | None = None
    max: int | None = None
    unit: str | None = None
    extra: dict = field(default_factory=dict)
    check: Any = None      # for json settings: a function that raises ValueError if the shape is wrong


REGISTRY: list[Setting] = [
    # Profile
    Setting("profile.home_city", "profile", "Home city", "place",
            {"name": "Hartford, CT", "lat": 41.7658, "lon": -72.6734},
            "Distances in Destinations and Trip Cost start here."),
    Setting("profile.time_zone", "profile", "Time zone", "time_zone", "America/New_York",
            "Times are stored in UTC and shown in this zone."),
    # Maps
    Setting("maps.default_view", "maps", "Default view", "select", "map",
            "What a place's map opens with.", options=["map", "satellite", "street", "3d"]),
    # Display
    Setting("display.theme", "display", "Theme", "select", "system", "Light, dark, or follow the system.", options=["dark", "light", "system"]),
    Setting("display.bills_layout", "display", "Bills layout", "select", "cards",
            "The Bills & Finance layout variant.", options=["cards", "table", "compact"]),
    Setting("display.focus_mode_picks", "display", "Focus Mode picks", "list", [],
            "The app ids the home screen shows in Focus Mode. One per line."),
    # Data
    Setting("data.sources", "data", "Sources", "sources",
            [{"id": i, "label": lbl, "on": True, "refresh": r} for i, lbl, r in SOURCES],
            "Turn a source off and nothing pulls from it.", options=REFRESH),
    # AI
    Setting("ai.jobs", "ai", "Which model does which job", "jobs",
            {"sort": {"model": "claude-haiku-4-5", "fallback": "claude-sonnet-5"},
             "read": {"model": "claude-sonnet-5", "fallback": "claude-haiku-4-5"},
             "draft": {"model": "claude-opus-5", "fallback": "claude-sonnet-5"},
             "answer": {"model": "claude-opus-5", "fallback": "claude-sonnet-5"}},
            "A cheap model for easy jobs (sorting), a strong one for hard jobs (answering, drafting), and a backup "
            "that takes over if the first fails. ollama/... is a model on this machine, once Ollama is installed.", options=MODELS,  # noqa: E501
            extra={"jobs": JOBS}),
    Setting("ai.monthly_cap_cents", "ai", "Monthly spending cap", "integer", 2000,
            "Across every AI service. Background jobs stop when it is reached.", min=0, unit="cents"),
    Setting("ai.visibility", "ai", "What each model may see", "visibility",
            {"trip_data": "cloud", "records": "cloud"},
            "cloud = any model; local = only a model on this machine (needs Ollama); none = no model.",
            options=VISIBILITY_OPTIONS, extra={"scopes": VISIBILITY_SCOPES}),
    # Logic: the rules behind features, editable. Defaults are what the code did before they were settings.
    Setting("logic.destinations.cost_split", "logic", "Destinations · what cost per day covers", "json",
            {"lodging": 0.45, "food": 0.30, "transport": 0.10, "other": 0.15},
            "Cost per day is one person's typical day. These shares split it into parts; 'no housing needed' drops lodging. "
            "They must add up to 1. Read by Trip cost and each place's detail. Default: an estimate applied to every place the same way.",
            extra={"used_by": ["destinations.trip_cost", "destinations.place"]}, check=lambda v: _check_shares(v)),
    Setting("logic.destinations.flight_guess", "logic", "Destinations · guessing a flight", "json",
            {"dollars_per_mile_each_way": 0.11, "floor": 120},
            "When you don't give a flight price, Trip cost guesses one from the distance: miles × this × 2, never under the floor. "
            "Read by destinations.trip_cost.", extra={"used_by": ["destinations.trip_cost"]},
            check=lambda v: _check_keys(v, {"dollars_per_mile_each_way": (int, float), "floor": (int, float)})),
    Setting("logic.destinations.goal_weights", "logic", "Destinations · goals and their weights", "json",
            {"growth": {"career": 2, "entrepreneurship": 2, "network": 2, "tech": 1, "lifestyle": 1},
             "entrepreneurship": {"entrepreneurship": 3, "network": 2, "tech": 1, "career": 1, "lifestyle": 1},
             "tech": {"tech": 3, "career": 2, "entrepreneurship": 1, "network": 1, "lifestyle": 1},
             "network": {"network": 3, "career": 2, "entrepreneurship": 1, "tech": 1, "lifestyle": 1},
             "lifestyle": {"lifestyle": 3, "network": 1, "career": 1, "entrepreneurship": 1, "tech": 1},
             "affordable": {"affordability": 3, "lifestyle": 1, "career": 1},
             "safe_and_calm": {"safety": 3, "quality_of_life": 2, "lifestyle": 1},
             "balanced": {"career": 1, "entrepreneurship": 1, "tech": 1, "network": 1, "lifestyle": 1, "safety": 1, "affordability": 1, "quality_of_life": 1}},
            "A goal weights the domain scores; fit = the weighted average. Add a goal by adding a key. Domains: career, entrepreneurship, "
            "tech, network, lifestyle, safety, affordability, quality_of_life. Read by the Destinations list, detail and compare. "
            "Default: the five from the old City2City app plus three added 2026-09-28.",
            extra={"used_by": ["destinations.places", "destinations.place", "destinations.compare"]}, check=lambda v: _check_goal_weights(v)),
    Setting("logic.destinations.extra_domains", "logic", "Destinations · scores computed from indexes", "json",
            {"safety": {"index": "safety", "multiply": 1, "add": 0},
             "affordability": {"index": "col", "multiply": -1, "add": 130},
             "quality_of_life": {"index": "qol", "multiply": 0.588, "add": -35.3}},
            "Domains computed at read time from a city's index values (Numbeo: safety, col = cost of living where New York is 100, "
            "qol = quality of life): score = clamp(value × multiply + add, 0–100). Marked index-derived on the page. "
            "Read by the Destinations list, detail and compare.", extra={"used_by": ["destinations.places", "destinations.place"]},
            check=lambda v: _check_extra_domains(v)),
    Setting("logic.destinations.defaults", "logic", "Destinations · defaults and limits", "json",
            {"kind": "us_city", "goal": "growth", "min_population": 250000, "all_view_min_population": 1000000,
             "population_steps": [15000, 100000, 250000, 1000000, 5000000], "compare_limit": 4},
            "What the page opens with, the smallest world city shown by default (and in the combined view), the population filter's "
            "steps, and how many places Compare holds.", extra={"used_by": ["destinations.options", "destinations.places", "destinations.compare"]},
            check=lambda v: _check_keys(v, {"kind": str, "goal": str, "min_population": int, "all_view_min_population": int, "population_steps": list, "compare_limit": int})),
    Setting("logic.destinations.search_fields", "logic", "Destinations · what a search looks at", "json",
            ["name", "region", "country", "tags", "description", "hub"],
            "The fields a search in the Atlas matches against. Choices: name, region, country, tags, description, hub, timezone.",
            extra={"used_by": ["destinations.places"]}, check=lambda v: _check_list_of_strings(v, allowed={"name", "region", "country", "tags", "description", "hub", "timezone"})),
    Setting("logic.ai.prices", "logic", "AI · what each model costs", "json",
            {"claude-opus-5": [5.0, 25.0], "claude-sonnet-5": [2.0, 10.0], "claude-haiku-4-5": [1.0, 5.0], "claude-fable-5-1": [10.0, 50.0], "claude-opus-4-8": [5.0, 25.0]},
            "Dollars per million tokens, [in, out], used to cost every call and enforce the monthly cap. Update when the price list changes. "
            "A model not listed costs 0 (local ones).", extra={"used_by": ["ai.switchboard"]}, check=lambda v: _check_prices(v)),
    Setting("logic.ai.inbox", "logic", "AI · the inbox", "json", {"sure_threshold": 0.85},
            "'Approve all sure ones' takes suggestions at or above this confidence (0–1).", extra={"used_by": ["ai.inbox"]},
            check=lambda v: _check_keys(v, {"sure_threshold": (int, float)})),
    Setting("logic.ai.visibility_scopes", "logic", "AI · kinds of data a model may or may not see", "json",
            [["trip_data", "Trips: bookings, prices, operator contacts"], ["records", "Records and notes"]],
            "The list behind Settings → AI → 'what each model may see'. A workflow names the scope it touches; add one here when an app "
            "brings new data.", extra={"used_by": ["ai.switchboard", "settings.ai.visibility"]}, check=lambda v: _check_pairs(v)),
    Setting("logic.records.types", "logic", "Records · kinds of record", "json",
            [["person", "Person"], ["company", "Company"], ["place", "Place"], ["bill", "Bill"], ["income", "Income"], ["transaction", "Transaction"],
             ["customer", "Customer"], ["visit", "Visit"], ["job", "Job"], ["clipping", "Clipping"], ["media", "Media"], ["bet", "Bet"],
             ["headline", "Headline"], ["source", "Source"], ["trip", "Trip"], ["note", "Note"], ["other", "Other"]],
            "The record types Browse offers ([id, label]). Any lowercase word is accepted by the engine; this is the menu.",
            extra={"used_by": ["browse", "records.types"]}, check=lambda v: _check_pairs(v)),
    Setting("logic.records.relations", "logic", "Records · how two records can relate", "json",
            {"about": {"out": "is about", "in": "is about this"}, "for": {"out": "is for", "in": "is for this"},
             "part_of": {"out": "is part of", "in": "is part of this"}, "related": {"out": "is related to", "in": "is related to this"},
             "same_as": {"out": "is the same as", "in": "is the same as this"}, "mentions": {"out": "mentions", "in": "mentions this"}},
            "The relationship words for links, with how each reads from either side. Add one by adding a key.",
            extra={"used_by": ["browse", "records.link"]}, check=lambda v: _check_relations(v)),
    Setting("logic.sources.checker", "logic", "Sources · the link checker", "json", {"timeout_seconds": 15, "dead_http_codes": [404, 410]},
            "How long to wait for each source, and which HTTP codes mean a link is dead (others over 400 are 'error').",
            extra={"used_by": ["sources.check"]}, check=lambda v: _check_keys(v, {"timeout_seconds": (int, float), "dead_http_codes": list})),
    Setting("logic.backup.rules", "logic", "Backups · keeping copies", "json", {"keep_at_least": 7},
            "However old, never remove more than leaves this many backups.", extra={"used_by": ["backup.prune"]},
            check=lambda v: _check_keys(v, {"keep_at_least": int})),
    Setting("logic.limits", "logic", "Engine · size limits", "json", {"attachment_max_mb": 50, "csv_max_mb": 20},
            "The largest file that can be attached to a record, and the largest CSV an importer reads.",
            extra={"used_by": ["records.attach_file"]}, check=lambda v: _check_keys(v, {"attachment_max_mb": (int, float), "csv_max_mb": (int, float)})),
    Setting("logic.workflows", "logic", "Workflows · when each runs", "json",
            {"trips.check_all": {"every": "day", "at": "06:00", "enabled": True}, "track.snapshot": {"every": "day", "at": "00:05", "enabled": True},
             "predict.forecasts": {"every": "day", "at": "00:10", "enabled": True},
             "sources.check": {"every": "week", "at": "03:00", "weekday": 0, "enabled": True}, "backup.nightly": {"every": "day", "at": "02:30", "enabled": True}},
            "The autonomous workflows: every = day | week | hour, at = HH:MM in your time zone, weekday 0 = Monday, enabled on/off. "
            "A run missed while the Mac slept happens as soon as the engine is up. Runs are listed at /v1/workflows.",
            extra={"used_by": ["workflows.runner"]}, check=lambda v: _check_workflows(v)),
    Setting("logic.predict", "logic", "Prediction · horizon", "json", {"series_days": 30},
            "How far the series forecasts look ahead.", extra={"used_by": ["predict.write_forecasts"]},
            check=lambda v: _check_keys(v, {"series_days": int})),
    Setting("logic.analytics", "logic", "Analytics · windows", "json", {"moving_average_days": 7, "anomaly_window_days": 30, "anomaly_z": 2.5},
            "The moving-average window, and how many standard deviations from the trailing window marks an anomaly.",
            extra={"used_by": ["analytics.summary"]}, check=lambda v: _check_keys(v, {"moving_average_days": int, "anomaly_window_days": int, "anomaly_z": (int, float)})),
    Setting("logic.trips.checks", "logic", "Trips · the checker's thresholds", "json",
            {"airport_buffer_minutes": {"domestic": 120, "international": 180}, "min_connection_minutes": 90, "transfer_after_arrival_minutes": 30,
             "price_recheck_days": 7, "passport_valid_months": 6, "deadline_warn_days": 3, "late_checkin_hour": 22, "book_flights_weeks_out": 6},
            "What the plan checker calls a problem: how early to be at the airport (domestic / international flights), the smallest gap between "
            "two legs, how long after landing a pickup should be set, when a price is stale, how long a passport must stay valid after the trip, "
            "how many days before a deadline to warn, what counts as a late check-in, and how far out budget fares should be booked. "
            "Read by trips.run_checks and the Timeline's 'leave by'.", extra={"used_by": ["trips.run_checks", "trips.plan"]},
            check=lambda v: _check_keys(v, {"airport_buffer_minutes": dict, "min_connection_minutes": int, "transfer_after_arrival_minutes": int,
                                            "price_recheck_days": int, "passport_valid_months": int, "deadline_warn_days": int,
                                            "late_checkin_hour": int, "book_flights_weeks_out": int})),
    Setting("logic.trips.kinds", "logic", "Trips · kinds of item", "json",
            {"transport": ["flight", "train", "bus", "van", "ferry", "taxi", "transfer", "drive"], "pickup": ["taxi", "transfer"],
             "stay": ["stay"], "other": ["activity", "storage", "meal", "other"], "buffer_minutes": {"ferry": 30, "train": 30, "bus": 30, "van": 15}},
            "Which item kinds are legs, which are pickups that must wait for an arrival, which are stays; and the buffer before a non-flight leg. "
            "Read by the Timeline, the checker and the item form.", extra={"used_by": ["trips.add_item", "trips.run_checks", "trips.plan"]},
            check=lambda v: _check_keys(v, {"transport": list, "pickup": list, "stay": list, "other": list, "buffer_minutes": dict})),
    Setting("logic.trips.confirmation", "logic", "Trips · confirming a booking", "json",
            {"message": "Hi {operator}, this is {traveler}. We have a booking with you ({confirmation}) for {headcount} on {date}: {title}. {question} Thank you!",
             "reply_hours": 24, "channels_order": ["whatsapp", "line", "app", "sms", "email", "call"],
             "call_opening": "Hello, this is an automated assistant calling on behalf of {traveler} about booking {confirmation} on {date}. {question}"},
            "Message first, call only if there is no reply. The message template ({operator}, {traveler}, {confirmation}, {headcount}, {date}, {title}, "
            "{question}), how many hours to wait for a reply before the checker says to call, which channel to try first, and what a call says up front "
            "(it says it is automated). Read by trips.draft_confirmation and the checker.", extra={"used_by": ["trips.draft_confirmation", "trips.run_checks"]},
            check=lambda v: _check_keys(v, {"message": str, "reply_hours": int, "channels_order": list, "call_opening": str})),
    Setting("logic.trips.before_you_go", "logic", "Trips · the before-you-go checklist", "json",
            [{"kind": "entry", "title": "Entry rules for your passport: visa, arrival form, fees, passport validity", "days_before": 30},
             {"kind": "health", "title": "Health rules and vaccines (CDC Travelers' Health)", "days_before": 45},
             {"kind": "insurance", "title": "Travel insurance that covers what you'll actually do (scooters, water sports)", "days_before": 14},
             {"kind": "permit", "title": "Driving or scooter permits (International Driving Permit from AAA)", "days_before": 21},
             {"kind": "phone", "title": "Phone and data plan (local SIM, eSIM or roaming); plug type", "days_before": 7},
             {"kind": "safety", "title": "Safety warnings, local laws, emergency number, embassy", "days_before": 7},
             {"kind": "pack", "title": "Pack for the weather and the activities", "days_before": 2}],
            "The tasks W25 (Before-you-go check) creates for a trip, each due this many days before departure. Read by trips.before_you_go.",
            extra={"used_by": ["trips.before_you_go"]}, check=lambda v: _check_task_templates(v)),
    Setting("logic.trips.defaults", "logic", "Trips · defaults and words", "json",
            {"headcount": 1, "home_currency": "USD", "passport_country": "USA", "card_rate_markup_pct": 2, "ics_alarm_minutes": 120,
             "stages": [["plan", "Plan"], ["prepare", "Prepare"], ["run", "Run"], ["done", "Done"]],
             "statuses": [["idea", "Idea"], ["to_book", "To book"], ["booked", "Booked"], ["confirmed", "Confirmed"], ["check_now", "Check now"], ["cancelled", "Cancelled"], ["done", "Done"]],
             "paid_by": [["me", "I pay"], ["company", "Company pays"], ["split", "Split"]], "tags": [["personal", "Personal"], ["work", "Work"]],
             "purposes": [["personal", "Personal"], ["work", "Work"], ["mixed", "Work + personal"]],
             "handling": [["plan_for_me", "Plan it for me"], ["check_my_plan", "Check my plan"], ["just_remind", "Just remind me"]],
             "health_weights": {"blocker": 25, "warn": 8, "info": 2}},
            "What a new trip starts as, how much worse a card's exchange rate usually is than the published one, the calendar alarm, the words "
            "for stages, statuses, who pays, the work/personal tag and how much the app should handle, and the trip health score's weights "
            "(100 minus these per open finding, never under 0). Read by every Trips screen.", extra={"used_by": ["trips.create", "trips.options", "trips.costs"]},
            check=lambda v: _check_keys(v, {"headcount": int, "home_currency": str, "passport_country": str, "card_rate_markup_pct": (int, float),
                                            "ics_alarm_minutes": int, "stages": list, "statuses": list, "paid_by": list, "tags": list, "purposes": list,
                                            "handling": list, "health_weights": dict})),
    Setting("logic.trips.route_options", "logic", "Trips · comparing ways to do a leg", "json",
            {"speed_mph": {"flight": 450, "train": 55, "bus": 40, "van": 45, "ferry": 18, "taxi": 25, "transfer": 30, "drive": 45},
             "terminal_minutes": {"flight": 150, "ferry": 30, "train": 15, "bus": 15, "van": 10},
             "road_factor": 1.3, "rank_by": "fastest", "faster_by_minutes": 15, "max_options": 10,
             "road_routing": True, "road_minutes_factor": {"drive": 1.0, "taxi": 1.0, "transfer": 1.0, "van": 1.0, "bus": 1.15}, "cache_days": 90},
            "How the options for one leg are worked out and ranked (W02). Ride minutes = distance ÷ speed × 60 when no time is given; "
            "a distance or speed of zero or less is skipped as invalid; the fastest wins. Speed is the mode's usual speed when none is "
            "given; distance, when none is given, is the straight line between the two places (GeoNames) times road_factor for ground "
            "modes. With road_routing on, road legs (car, taxi, transfer, van, bus) use a real road route instead: the road distance and the "
            "driving time from OSRM on OpenStreetMap, times road_minutes_factor for the mode; places are found with OpenStreetMap "
            "(Nominatim) or GeoNames; lookups are cached for cache_days and made only when a way is saved. "
            "terminal_minutes is time at the airport, pier or station, added for the door-to-door figure. rank_by is fastest, "
            "cheapest or balanced. faster_by_minutes is how much quicker an unchosen option must be before the checker mentions it. "
            "max_options caps the options on one leg. Read by trips.leg_options, trips.add_option and the checker.",
            extra={"used_by": ["trips.leg_options", "trips.add_option", "trips.run_checks"]}, check=lambda v: _check_route_options(v)),
    Setting("logic.ai.prompts", "logic", "AI · prompt overrides", "json", {},
            "Replace a workflow's prompt text: {\"trips.draft_message\": \"...\"}. Empty means the built-in prompt "
            "(engine/ai/prompts.py). An override is logged as version 'custom'. Score it on the Test scores tab before relying on it.",
            extra={"used_by": ["ai.switchboard"]}, check=lambda v: _check_map_of_strings(v)),
    # Backup
    Setting("backup.time", "backup", "Nightly backup at", "time", "02:30",
            "Local time. scripts/install_backup_schedule.sh installs the schedule."),
    Setting("backup.destination", "backup", "Backups go to", "text", "vault/backups",
            "A folder. Relative paths are inside the repo; the repo ignores vault/."),
    Setting("backup.keep_days", "backup", "Keep backups for", "integer", 30, "", min=1, max=3650, unit="days"),
]
BY_KEY = {s.key: s for s in REGISTRY}


def _check_map_of_numbers(v):
    if not isinstance(v, dict) or not v or not all(isinstance(k, str) and isinstance(x, (int, float)) and not isinstance(x, bool) for k, x in v.items()):
        raise ValueError("expected {\"name\": number, ...}")


def _check_map_of_strings(v):
    if not isinstance(v, dict) or not all(isinstance(k, str) and isinstance(x, str) for k, x in v.items()):
        raise ValueError("expected {\"name\": \"text\", ...}")


def _check_keys(v, spec: dict):
    if not isinstance(v, dict):
        raise ValueError("expected an object")
    names = {int: "whole number", float: "number", (int, float): "number", bool: "true or false", str: "text", list: "list", dict: "object"}
    for k, typ in spec.items():
        if k not in v:
            raise ValueError(f"missing {k}")
        if (isinstance(v[k], bool) and typ is not bool) or not isinstance(v[k], typ):
            raise ValueError(f"{k} must be a {names.get(typ, 'value of the right kind')}")


def _check_shares(v):
    _check_map_of_numbers(v)
    if abs(sum(v.values()) - 1) > 0.001:
        raise ValueError(f"the shares add up to {round(sum(v.values()), 3)}, not 1")
    if "lodging" not in v:
        raise ValueError("a 'lodging' share is needed (it is what 'no housing' removes)")


def _check_list_of_strings(v, allowed: set | None = None):
    if not isinstance(v, list) or not v or not all(isinstance(x, str) and x for x in v):
        raise ValueError("expected a list of words")
    if allowed and any(x not in allowed for x in v):
        raise ValueError(f"choices are {sorted(allowed)}")


def _check_pairs(v):
    if not isinstance(v, list) or not v or not all(isinstance(p, list) and len(p) == 2 and all(isinstance(x, str) for x in p) for p in v):
        raise ValueError("expected [[id, label], ...]")


def _check_prices(v):
    if not isinstance(v, dict) or not all(isinstance(p, list) and len(p) == 2 and all(isinstance(x, (int, float)) for x in p) for p in v.values()):
        raise ValueError("expected {model: [dollars per million in, out]}")


def _check_relations(v):
    if not isinstance(v, dict) or not v:
        raise ValueError("expected {word: {out, in}}")
    for k, spec in v.items():
        if not isinstance(k, str) or not k.isidentifier():
            raise ValueError(f"{k!r}: a relationship word is one lowercase word (underscores ok)")
        _check_keys(spec, {"out": str, "in": str})


def _check_workflows(v):
    if not isinstance(v, dict):
        raise ValueError("expected {workflow: {every, at, enabled}}")
    for n, s in v.items():
        if not isinstance(s, dict) or s.get("every") not in ("day", "week", "hour"):
            raise ValueError(f"{n}: every must be day, week or hour")
        hh, _, mm = str(s.get("at", "00:00")).partition(":")
        if not (hh.isdigit() and mm.isdigit() and 0 <= int(hh) < 24 and 0 <= int(mm) < 60):
            raise ValueError(f"{n}: at must be HH:MM")


def _check_goal_weights(v):
    if not isinstance(v, dict) or not v:
        raise ValueError("expected {goal: {domain: weight}}")
    for w in v.values():
        _check_map_of_numbers(w)


def _check_task_templates(v):
    if not isinstance(v, list) or not v:
        raise ValueError("expected [{kind, title, days_before}, ...]")
    for t in v:
        _check_keys(t, {"kind": str, "title": str, "days_before": int})


def _check_route_options(v):
    _check_keys(v, {"speed_mph": dict, "terminal_minutes": dict, "road_factor": (int, float), "rank_by": str, "faster_by_minutes": int, "max_options": int})
    _check_map_of_numbers(v["speed_mph"])
    if any(x <= 0 for x in v["speed_mph"].values()):
        raise ValueError("every usual speed must be above zero")
    if v["terminal_minutes"]:
        _check_map_of_numbers(v["terminal_minutes"])
    if v["rank_by"] not in ("fastest", "cheapest", "balanced"):
        raise ValueError("rank_by is fastest, cheapest or balanced")
    if v["max_options"] < 1:
        raise ValueError("max_options is at least 1")
    if "road_routing" in v and not isinstance(v["road_routing"], bool):
        raise ValueError("road_routing is true or false")
    if v.get("road_minutes_factor"):
        _check_map_of_numbers(v["road_minutes_factor"])
        if any(x <= 0 for x in v["road_minutes_factor"].values()):
            raise ValueError("every road_minutes_factor must be above zero")
    if "cache_days" in v and (not isinstance(v["cache_days"], int) or isinstance(v["cache_days"], bool) or v["cache_days"] < 0):
        raise ValueError("cache_days is a whole number, 0 or more")


def _check_extra_domains(v):
    if not isinstance(v, dict):
        raise ValueError("expected {domain: {index, multiply, add}}")
    for spec in v.values():
        _check_keys(spec, {"index": str, "multiply": (int, float), "add": (int, float)})


class Conflict(Exception):
    def __init__(self, yours: dict, theirs: dict):
        super().__init__("version conflict")
        self.yours, self.theirs = yours, theirs


def validate(s: Setting, v: Any) -> Any:
    t = s.type
    if t in ("text", "time_zone", "time", "select"):
        if not isinstance(v, str):
            raise ValueError(f"{s.key}: expected text")
        if t == "select" and v not in (s.options or []):
            raise ValueError(f"{s.key}: {v!r} is not one of {s.options}")
        if t == "time_zone" and v not in available_timezones():
            raise ValueError(f"{s.key}: unknown time zone {v!r}")
        if t == "time":
            hh, _, mm = v.partition(":")
            if not (hh.isdigit() and mm.isdigit() and 0 <= int(hh) < 24 and 0 <= int(mm) < 60):
                raise ValueError(f"{s.key}: time must be HH:MM")
        return v
    if t == "integer":
        if isinstance(v, bool) or not isinstance(v, int):
            raise ValueError(f"{s.key}: expected a whole number")
        if s.min is not None and v < s.min or s.max is not None and v > s.max:
            raise ValueError(f"{s.key}: must be between {s.min} and {s.max}")
        return v
    if t == "number":
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError(f"{s.key}: expected a number")
        return v
    if t == "toggle":
        if not isinstance(v, bool):
            raise ValueError(f"{s.key}: expected true or false")
        return v
    if t in ("multiselect", "list"):
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            raise ValueError(f"{s.key}: expected a list of text")
        if t == "multiselect" and any(x not in (s.options or []) for x in v):
            raise ValueError(f"{s.key}: unknown option")
        return v
    if t == "map":
        if not isinstance(v, dict) or not all(isinstance(k, str) and isinstance(x, str) for k, x in v.items()):
            raise ValueError(f"{s.key}: expected text = text pairs")
        return v
    if t == "place":
        if not isinstance(v, dict) or not isinstance(v.get("name"), str) or not v["name"].strip():
            raise ValueError(f"{s.key}: a place needs a name")
        lat, lon = v.get("lat"), v.get("lon")
        if not (isinstance(lat, (int, float)) and isinstance(lon, (int, float))
                and -90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError(f"{s.key}: lat/lon out of range")
        return {"name": v["name"].strip(), "lat": float(lat), "lon": float(lon)}
    if t == "sources":
        if not isinstance(v, list):
            raise ValueError(f"{s.key}: expected a list")
        out = []
        for row in v:
            if not isinstance(row, dict) or not isinstance(row.get("id"), str):
                raise ValueError(f"{s.key}: bad source row")
            if row.get("refresh") not in (s.options or []):
                raise ValueError(f"{s.key}: bad refresh {row.get('refresh')!r}")
            out.append({"id": row["id"], "label": str(row.get("label", row["id"])),
                        "on": bool(row.get("on")), "refresh": row["refresh"]})
        return out
    if t == "jobs":
        if not isinstance(v, dict):
            raise ValueError(f"{s.key}: expected a map of jobs")
        for job, cfg in v.items():
            if job not in dict(s.extra["jobs"]) or not isinstance(cfg, dict):
                raise ValueError(f"{s.key}: unknown job {job!r}")
            for k in ("model", "fallback"):
                m = cfg.get(k)
                if m not in (s.options or []) and not (isinstance(m, str) and m.startswith(("ollama/", "fake/"))):
                    raise ValueError(f"{s.key}: {job}.{k} must be one of {s.options}, or ollama/<model>")
        return {j: {"model": v[j]["model"], "fallback": v[j]["fallback"]} for j in v}
    if t == "visibility":
        if not isinstance(v, dict):
            raise ValueError(f"{s.key}: expected a map")
        for k, x in v.items():
            if not isinstance(k, str) or x not in (s.options or []):
                raise ValueError(f"{s.key}: bad scope or level")
        return dict(v)
    if t == "json":
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except ValueError:
                raise ValueError(f"{s.key}: not valid JSON")
        if s.check:
            try:
                s.check(v)
            except ValueError as e:
                raise ValueError(f"{s.key}: {e}")
        return v
    raise ValueError(f"{s.key}: unknown type {t}")


def _stored(con: sqlite3.Connection) -> dict[str, dict]:
    return {r["key"]: {"value": json.loads(r["value"]), "version": r["version"],
                       "updated_at": r["updated_at"], "updated_by": r["updated_by"]}
            for r in con.execute("SELECT * FROM settings")}


def _live_extra(store: Store, s: Setting) -> dict:
    """A few settings take their choices from a logic setting."""
    extra = {k: v for k, v in s.extra.items() if k != "check"}
    if s.key == "ai.visibility":
        try:
            extra["scopes"] = get_value(store, "logic.ai.visibility_scopes")
        except Exception:
            pass
    return extra


def describe(store: Store) -> dict:
    with store.read():
        stored = _stored(store.con)
    secret_rows = secrets.status()
    sections = []
    for sid, label, blurb in SECTIONS:
        items = []
        for s in REGISTRY:
            if s.section != sid:
                continue
            row = stored.get(s.key)
            items.append({
                "key": s.key, "label": s.label, "type": s.type, "help": s.help,
                "options": s.options, "min": s.min, "max": s.max, "unit": s.unit, "extra": _live_extra(store, s),
                "default": s.default,
                "value": row["value"] if row else s.default,
                "version": row["version"] if row else 0,
                "stored": bool(row),
                "updated_at": row["updated_at"] if row else None,
                "updated_by": row["updated_by"] if row else None,
            })
        sections.append({"id": sid, "label": label, "blurb": blurb, "settings": items,
                         "secrets": [x for x in secret_rows if x["section"] == sid]})
    return {"sections": sections}


def get_value(store: Store, key: str) -> Any:
    """What the engine's own code calls: the stored value, else the default."""
    s = BY_KEY[key]
    with store.read():
        r = store.con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return json.loads(r["value"]) if r else s.default


def values(store: Store) -> dict[str, Any]:
    with store.read():
        stored = _stored(store.con)
    return {s.key: stored[s.key]["value"] if s.key in stored else s.default for s in REGISTRY}


def _current(con: sqlite3.Connection, key: str) -> dict | None:
    r = con.execute("SELECT * FROM settings WHERE key=?", (key,)).fetchone()
    if not r:
        return None
    return {"value": json.loads(r["value"]), "version": r["version"],
            "updated_at": r["updated_at"], "updated_by": r["updated_by"]}


def set_value(store: Store, key: str, value: Any, expected_version: int | None, app: str = "settings") -> dict:
    s = BY_KEY.get(key)
    if not s:
        raise KeyError(key)
    value = validate(s, value)
    with store.tx() as con:
        cur = _current(con, key)
        cur_version = cur["version"] if cur else 0
        if expected_version is not None and expected_version != cur_version:
            raise Conflict(yours={"value": value, "version": expected_version},
                           theirs={"value": cur["value"] if cur else s.default, "version": cur_version,
                                   "updated_at": cur["updated_at"] if cur else None,
                                   "updated_by": cur["updated_by"] if cur else None})
        new_version = cur_version + 1
        ts = now_iso()
        con.execute(
            "INSERT INTO settings(key, value, version, updated_at, updated_by) VALUES(?,?,?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, version=excluded.version, "
            "updated_at=excluded.updated_at, updated_by=excluded.updated_by",
            (key, json.dumps(value), new_version, ts, app))
        after = {"value": value, "version": new_version}
        hid = history.record(con, app=app, action="settings.set", tbl="settings", row_key=key,
                             before={"value": cur["value"], "version": cur["version"]} if cur else None,
                             after=after)
    return {"key": key, "value": value, "version": new_version, "updated_at": ts, "updated_by": app,
            "stored": True, "history_id": hid}


def reset(store: Store, key: str, app: str = "settings") -> dict:
    s = BY_KEY.get(key)
    if not s:
        raise KeyError(key)
    with store.tx() as con:
        cur = _current(con, key)
        if cur:
            con.execute("DELETE FROM settings WHERE key=?", (key,))
            history.record(con, app=app, action="settings.reset", tbl="settings", row_key=key,
                           before={"value": cur["value"], "version": cur["version"]}, after=None)
    return {"key": key, "value": s.default, "version": 0, "stored": False}


def restore_row(con: sqlite3.Connection, key: str, before: dict | None, *, app: str, action: str) -> str:
    """Used by undo: put a settings row back to `before` (None = no row)."""
    cur = _current(con, key)
    if before is None:
        con.execute("DELETE FROM settings WHERE key=?", (key,))
        after = None
    else:
        new_version = (cur["version"] if cur else 0) + 1
        con.execute(
            "INSERT INTO settings(key, value, version, updated_at, updated_by) VALUES(?,?,?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, version=excluded.version, "
            "updated_at=excluded.updated_at, updated_by=excluded.updated_by",
            (key, json.dumps(before["value"]), new_version, now_iso(), app))
        after = {"value": before["value"], "version": new_version}
    return history.record(con, app=app, action=action, tbl="settings", row_key=key,
                          before={"value": cur["value"], "version": cur["version"]} if cur else None,
                          after=after)
