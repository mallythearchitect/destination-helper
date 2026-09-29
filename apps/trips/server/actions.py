"""What Trips can do. Every write is one all-or-nothing action with a typed
input, lands in history (undoable), and is described plainly enough for an
AI to press it. A trip is also a record (type trip), so notes, tags, files
and links come from the engine."""
from __future__ import annotations

import json
from datetime import date as date_type
from datetime import datetime, timedelta

from pydantic import BaseModel, Field

from engine import history, records
from engine.actions import action
from engine.ids import uuid7
from engine.store import Store, now_iso

from . import checks
from . import queries as q

TRIP_FIELDS = ("name", "purpose", "start_date", "end_date", "headcount", "travelers", "home_currency", "local_currency", "fx_rate", "fx_date",
               "passport_country", "passport_expiry", "budget_night_cents", "budget_leg_cents", "budget_day_cents", "region_pack", "time_zone", "purpose_note")
ITEM_FIELDS = ("kind", "title", "from_place", "to_place", "start_at", "end_at", "time_zone", "status", "price_cents", "currency", "basis", "headcount",
               "paid_by", "tag", "international", "confirmation", "link", "operator", "contact", "last_departure", "desk_hours", "lead_minutes", "notes")


def _date(s: str | None, what: str) -> str | None:
    if s is None or s == "":
        return None
    try:
        return date_type.fromisoformat(s).isoformat()
    except ValueError:
        raise ValueError(f"{what} must be YYYY-MM-DD")


def _when(s: str | None, what: str) -> str | None:
    if s is None or s == "":
        return None
    if q.parse_local(s, None) is None:
        raise ValueError(f"{what} must be YYYY-MM-DD or YYYY-MM-DDTHH:MM (local time)")
    return s[:16] if len(s) > 10 else s


def _words(store: Store, key: str) -> list[str]:
    return [x[0] for x in q.logic(store, "logic.trips.defaults")[key]]


def _need_trip(con, tid: str) -> dict:
    t = q.trip_row(con, tid)
    if not t:
        raise records.NotFound(tid)
    return t


def _need_item(con, iid: str) -> dict:
    r = con.execute("SELECT * FROM trip_items WHERE id=? AND deleted_at IS NULL", (iid,)).fetchone()
    if not r:
        raise records.NotFound(iid)
    return dict(r)


def _row(con, tbl: str, key: str) -> dict:
    return records._row(con, tbl, key)


def _bump(con, tbl: str, key: str, expected: int | None) -> dict:
    cur = _row(con, tbl, key)
    if not cur or cur.get("deleted_at"):
        raise records.NotFound(key)
    if expected is not None and cur.get("version") != expected:
        raise records.Conflict(yours={"version": expected}, theirs=cur)
    return cur


# ---- the trip -----------------------------------------------------------------------

class CreateTrip(BaseModel):
    name: str = Field(description="What you call it, e.g. Thailand, Nov 2026")
    purpose: str = Field("personal", description="personal, work, or mixed (work stretched into vacation days)")
    start_date: str | None = Field(None, description="YYYY-MM-DD")
    end_date: str | None = None
    headcount: int | None = Field(None, description="How many are going. Ask this first (G01).")
    travelers: list[str] = Field(default_factory=list, description="Names")
    home_currency: str | None = Field(None, description="e.g. USD")
    local_currency: str | None = Field(None, description="e.g. THB")
    fx_rate: float | None = Field(None, description="Local units per 1 home unit, the day it was checked")
    fx_date: str | None = None
    passport_country: str | None = None
    passport_expiry: str | None = Field(None, description="YYYY-MM-DD; the checker compares it with the trip's end")
    budget_night_cents: int | None = Field(None, description="Cap per night for the group, home currency cents. Ask before suggesting places (G02).")
    budget_leg_cents: int | None = None
    budget_day_cents: int | None = None
    region_pack: str | None = Field(None, description="A region pack id from the helper, e.g. thailand")
    time_zone: str | None = Field(None, description="The destination's zone, e.g. Asia/Bangkok; item times are local")
    purpose_note: str | None = Field(None, description="What the trip is for: active days, nightlife, water sports...")


def _setup_missing(t: dict) -> list[str]:
    """W24 / G01 / G02: what a new trip should have before the helper suggests anything."""
    out = []
    if not t.get("headcount"):
        out.append("who's going and how many")
    if not t.get("start_date") or not t.get("end_date"):
        out.append("the dates")
    if not any(t.get(k) for k in ("budget_night_cents", "budget_leg_cents", "budget_day_cents")):
        out.append("budget caps (per night, per leg, per day)")
    if not t.get("purpose_note"):
        out.append("what the trip is for")
    if not t.get("passport_country"):
        out.append("passport country")
    if t.get("local_currency") and not t.get("fx_rate"):
        out.append("today's exchange rate and its date")
    return out


@action("trips.create", "Start a trip (W24). Asks for headcount, dates, budget caps, what it's for and the passport first; the answer lists what is still missing. The trip becomes a record too.", CreateTrip)
def create_trip(store: Store, i: CreateTrip, app: str = "trips") -> dict:
    d = q.logic(store, "logic.trips.defaults")
    if not i.name.strip():
        raise ValueError("a trip needs a name")
    if i.purpose not in _words(store, "purposes"):
        raise ValueError(f"purpose must be one of {_words(store, 'purposes')}")
    if i.start_date and i.end_date and i.end_date < i.start_date:
        raise ValueError("the end date is before the start")
    with store.tx() as con:
        region = q.region_row(con, i.region_pack) if i.region_pack else None
        if i.region_pack and not region:
            raise ValueError(f"no region pack {i.region_pack}")
        e = records.create_entity(store, type="trip", name=i.name.strip(), data={"purpose": i.purpose, "start_date": i.start_date, "end_date": i.end_date},
                                  source="trips", app=app)
        tid, ts = uuid7(), now_iso()
        con.execute("INSERT INTO trips(id, entity_id, name, purpose, stage, start_date, end_date, headcount, travelers, home_currency, local_currency, fx_rate, fx_date, "
                    "passport_country, passport_expiry, budget_night_cents, budget_leg_cents, budget_day_cents, region_pack, time_zone, purpose_note, version, created_at, updated_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?)",
                    (tid, e["id"], i.name.strip(), i.purpose, "plan", _date(i.start_date, "start_date"), _date(i.end_date, "end_date"), i.headcount or d["headcount"],
                     json.dumps(i.travelers), (i.home_currency or d["home_currency"]).upper(), (i.local_currency or (region or {}).get("currency") or None),
                     i.fx_rate, _date(i.fx_date, "fx_date"), i.passport_country or d["passport_country"], _date(i.passport_expiry, "passport_expiry"),
                     i.budget_night_cents, i.budget_leg_cents, i.budget_day_cents, i.region_pack, i.time_zone or (region or {}).get("time_zone"), i.purpose_note, ts, ts))
        if i.local_currency:
            con.execute("UPDATE trips SET local_currency=? WHERE id=?", (i.local_currency.upper(), tid))
        after = _row(con, "trips", tid)
        history.record(con, app=app, action="trips.create", tbl="trips", row_key=tid, before=None, after=after)
    t = q.trip_row(store.con, tid)
    t["setup_missing"] = _setup_missing(t)
    return t


class UpdateTrip(BaseModel):
    id: str
    expected_version: int | None = Field(None, description="The version you saw; a stale one is refused with both versions")
    name: str | None = None
    purpose: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    headcount: int | None = None
    travelers: list[str] | None = None
    home_currency: str | None = None
    local_currency: str | None = None
    fx_rate: float | None = None
    fx_date: str | None = None
    passport_country: str | None = None
    passport_expiry: str | None = None
    budget_night_cents: int | None = None
    budget_leg_cents: int | None = None
    budget_day_cents: int | None = None
    region_pack: str | None = None
    time_zone: str | None = None
    purpose_note: str | None = None
    clear: list[str] = Field(default_factory=list, description="Field names to blank out (e.g. budget_leg_cents)")


@action("trips.update", "Change a trip's details: dates, headcount, currencies and rate, passport, budget caps, region pack, time zone.", UpdateTrip)
def update_trip(store: Store, i: UpdateTrip, app: str = "trips") -> dict:
    with store.tx() as con:
        cur = _bump(con, "trips", i.id, i.expected_version)
        new = dict(cur)
        for k in TRIP_FIELDS:
            v = getattr(i, k)
            if v is not None:
                new[k] = v
        for k in i.clear:
            if k in TRIP_FIELDS and k not in ("name", "purpose", "headcount", "home_currency"):
                new[k] = None
        if not str(new["name"]).strip():
            raise ValueError("a trip needs a name")
        if new["purpose"] not in _words(store, "purposes"):
            raise ValueError(f"purpose must be one of {_words(store, 'purposes')}")
        if new["headcount"] is not None and new["headcount"] < 1:
            raise ValueError("headcount is at least 1")
        for k in ("start_date", "end_date", "fx_date", "passport_expiry"):
            new[k] = _date(new[k], k)
        if new["start_date"] and new["end_date"] and new["end_date"] < new["start_date"]:
            raise ValueError("the end date is before the start")
        if new["region_pack"] and not q.region_row(con, new["region_pack"]):
            raise ValueError(f"no region pack {new['region_pack']}")
        trav = new["travelers"] if isinstance(new["travelers"], str) else json.dumps(new["travelers"])
        con.execute("UPDATE trips SET name=?, purpose=?, start_date=?, end_date=?, headcount=?, travelers=?, home_currency=?, local_currency=?, fx_rate=?, fx_date=?, "
                    "passport_country=?, passport_expiry=?, budget_night_cents=?, budget_leg_cents=?, budget_day_cents=?, region_pack=?, time_zone=?, purpose_note=?, "
                    "version=version+1, updated_at=? WHERE id=?",
                    (str(new["name"]).strip(), new["purpose"], new["start_date"], new["end_date"], new["headcount"], trav, str(new["home_currency"]).upper(),
                     (new["local_currency"] or None) and str(new["local_currency"]).upper(), new["fx_rate"], new["fx_date"], new["passport_country"], new["passport_expiry"],
                     new["budget_night_cents"], new["budget_leg_cents"], new["budget_day_cents"], new["region_pack"], new["time_zone"], new["purpose_note"], now_iso(), i.id))
        after = _row(con, "trips", i.id)
        history.record(con, app=app, action="trips.update", tbl="trips", row_key=i.id, before=cur, after=after)
        if after["name"] != cur["name"] or after["start_date"] != cur["start_date"] or after["end_date"] != cur["end_date"]:
            records.update_entity(store, cur["entity_id"], {"name": after["name"], "data": {"purpose": after["purpose"], "start_date": after["start_date"], "end_date": after["end_date"]}}, None, app=app)
    t = q.trip_row(store.con, i.id)
    t["setup_missing"] = _setup_missing(t)
    return t


class SetStage(BaseModel):
    id: str
    stage: str = Field(description="plan, prepare, run or done")


@action("trips.set_stage", "Move a trip between stages: Plan (routes, timing, costs, checks), Prepare (confirm bookings, before-you-go list), Run (live), Done (wrap up, W26).", SetStage)
def set_stage(store: Store, i: SetStage, app: str = "trips") -> dict:
    if i.stage not in _words(store, "stages"):
        raise ValueError(f"stage must be one of {_words(store, 'stages')}")
    with store.tx() as con:
        cur = _bump(con, "trips", i.id, None)
        con.execute("UPDATE trips SET stage=?, version=version+1, updated_at=? WHERE id=?", (i.stage, now_iso(), i.id))
        after = _row(con, "trips", i.id)
        history.record(con, app=app, action="trips.set_stage", tbl="trips", row_key=i.id, before=cur, after=after)
    return q.trip_row(store.con, i.id)


class ById(BaseModel):
    id: str


@action("trips.delete", "Remove a trip and everything in it (undoable from history).", ById, dangerous=True)
def delete_trip(store: Store, i: ById, app: str = "trips") -> dict:
    ts = now_iso()
    with store.tx() as con:
        cur = _bump(con, "trips", i.id, None)
        con.execute("UPDATE trips SET deleted_at=?, version=version+1, updated_at=? WHERE id=?", (ts, ts, i.id))
        after = _row(con, "trips", i.id)
        history.record(con, app=app, action="trips.delete", tbl="trips", row_key=i.id, before=cur, after=after)
        records.delete_entity(store, cur["entity_id"], app=app)
    return after


class TripNote(BaseModel):
    trip_id: str
    body: str


@action("trips.add_note", "Add a note to a trip (it is a record, so the note is searchable).", TripNote)
def add_trip_note(store: Store, i: TripNote, app: str = "trips") -> dict:
    with store.read():
        t = _need_trip(store.con, i.trip_id)
    return records.add_note(store, t["entity_id"], i.body, app=app)


# ---- items ------------------------------------------------------------------------

class AddItem(BaseModel):
    trip_id: str
    kind: str = Field(description="flight, train, bus, van, ferry, taxi, transfer, drive, stay, activity, storage, meal or other")
    title: str = Field(description="e.g. 'Nok Air DD 130 DMK → KBV' or 'Nomads Ao Nang'")
    from_place: str | None = Field(None, description="Where it starts (legs) or the area (stays)")
    to_place: str | None = None
    start_at: str | None = Field(None, description="Local time YYYY-MM-DDTHH:MM, or YYYY-MM-DD for a stay's check-in")
    end_at: str | None = Field(None, description="Arrival, or check-out day for a stay")
    time_zone: str | None = Field(None, description="Only if different from the trip's")
    status: str = Field("to_book", description="idea, to_book, booked, confirmed, check_now, cancelled, done")
    price_cents: int | None = Field(None, description="In `currency` cents")
    currency: str | None = Field(None, description="e.g. THB; the trip's home currency if empty")
    basis: str | None = Field(None, description="per_person or group. Always say which (G03); the checker flags a price without it")
    headcount: int | None = Field(None, description="On the booking, if not the whole group")
    paid_by: str = Field("me", description="me, company, or split")
    tag: str = Field("personal", description="personal or work")
    international: bool = Field(False, description="Flights: crosses a border (longer airport buffer)")
    confirmation: str | None = None
    link: str | None = None
    operator: str | None = Field(None, description="The airline, hotel, tour or taxi company")
    contact: dict = Field(default_factory=dict, description="{phone, whatsapp, line, email, app}")
    last_departure: str | None = Field(None, description="HH:MM: the last one of the day on this route, when it matters (the last ferry)")
    desk_hours: str | None = Field(None, description="Stays: front desk hours, e.g. 24h")
    lead_minutes: int | None = Field(None, description="Travel time to reach the start point, for 'leave by'")
    notes: str | None = None


def _check_item(store: Store, v: dict) -> None:
    kinds = q.logic(store, "logic.trips.kinds")
    if v["kind"] not in kinds["transport"] + kinds["stay"] + kinds["other"]:
        raise ValueError(f"kind must be one of {kinds['transport'] + kinds['stay'] + kinds['other']}")
    if not str(v["title"]).strip():
        raise ValueError("an item needs a title")
    if v["status"] not in _words(store, "statuses"):
        raise ValueError(f"status must be one of {_words(store, 'statuses')}")
    if v["basis"] not in (None, "per_person", "group"):
        raise ValueError("basis is per_person or group")
    if v["paid_by"] not in _words(store, "paid_by"):
        raise ValueError(f"paid_by must be one of {_words(store, 'paid_by')}")
    if v["tag"] not in _words(store, "tags"):
        raise ValueError(f"tag must be one of {_words(store, 'tags')}")
    if v["price_cents"] is not None and v["price_cents"] < 0:
        raise ValueError("a price is not negative")
    if v["last_departure"] and q.parse_local(f"2000-01-01T{v['last_departure']}", None) is None:
        raise ValueError("last_departure is HH:MM")
    for k in ("start_at", "end_at"):
        v[k] = _when(v[k], k)
    if v["start_at"] and v["end_at"] and v["end_at"] < v["start_at"]:
        raise ValueError("end_at is before start_at")


@action("trips.add_item", "Add a leg, stay, activity or pickup to a trip's plan, with its time, price (per person or group), who pays and the work/personal tag. Run the checks after.", AddItem)
def add_item(store: Store, i: AddItem, app: str = "trips") -> dict:
    v = i.model_dump()
    _check_item(store, v)
    iid, ts = uuid7(), now_iso()
    with store.tx() as con:
        t = _need_trip(con, i.trip_id)
        con.execute("INSERT INTO trip_items(id, trip_id, kind, title, from_place, to_place, start_at, end_at, time_zone, status, price_cents, currency, basis, headcount, paid_by, tag, "
                    "international, confirmation, link, operator, contact, last_departure, desk_hours, lead_minutes, price_checked_at, notes, version, created_at, updated_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?)",
                    (iid, i.trip_id, v["kind"], v["title"].strip(), v["from_place"], v["to_place"], v["start_at"], v["end_at"], v["time_zone"], v["status"], v["price_cents"],
                     (v["currency"] or t["home_currency"]).upper() if v["price_cents"] is not None or v["currency"] else None, v["basis"], v["headcount"], v["paid_by"], v["tag"],
                     int(v["international"]), v["confirmation"], v["link"], v["operator"], json.dumps(v["contact"]), v["last_departure"], v["desk_hours"], v["lead_minutes"],
                     ts if v["price_cents"] is not None else None, v["notes"], ts, ts))
        after = _row(con, "trip_items", iid)
        history.record(con, app=app, action="trips.add_item", tbl="trip_items", row_key=iid, before=None, after=after)
    after["contact"] = v["contact"]
    return after


class UpdateItem(BaseModel):
    id: str
    expected_version: int | None = None
    kind: str | None = None
    title: str | None = None
    from_place: str | None = None
    to_place: str | None = None
    start_at: str | None = None
    end_at: str | None = None
    time_zone: str | None = None
    status: str | None = None
    price_cents: int | None = None
    currency: str | None = None
    basis: str | None = None
    headcount: int | None = None
    paid_by: str | None = None
    tag: str | None = None
    international: bool | None = None
    confirmation: str | None = None
    link: str | None = None
    operator: str | None = None
    contact: dict | None = None
    last_departure: str | None = None
    desk_hours: str | None = None
    lead_minutes: int | None = None
    notes: str | None = None
    price_checked: bool = Field(False, description="True to note that the price was re-checked today (G05)")
    clear: list[str] = Field(default_factory=list, description="Field names to blank out")


@action("trips.update_item", "Change an item: move its time, set the price and basis, mark it booked with the confirmation number, add the operator's contact, note the last departure.", UpdateItem)
def update_item(store: Store, i: UpdateItem, app: str = "trips") -> dict:
    with store.tx() as con:
        cur = _bump(con, "trip_items", i.id, i.expected_version)
        new = dict(cur)
        new["contact"] = json.loads(cur["contact"] or "{}")
        new["international"] = bool(cur["international"])
        for k in ITEM_FIELDS:
            v = getattr(i, k)
            if v is not None:
                new[k] = v
        for k in i.clear:
            if k in ITEM_FIELDS and k not in ("kind", "title", "status", "paid_by", "tag"):
                new[k] = {} if k == "contact" else None
        _check_item(store, new)
        t = _need_trip(con, cur["trip_id"])
        checked = now_iso() if (i.price_checked or (i.price_cents is not None and i.price_cents != cur["price_cents"])) else cur["price_checked_at"]
        con.execute("UPDATE trip_items SET kind=?, title=?, from_place=?, to_place=?, start_at=?, end_at=?, time_zone=?, status=?, price_cents=?, currency=?, basis=?, headcount=?, paid_by=?, tag=?, "
                    "international=?, confirmation=?, link=?, operator=?, contact=?, last_departure=?, desk_hours=?, lead_minutes=?, price_checked_at=?, notes=?, version=version+1, updated_at=? WHERE id=?",
                    (new["kind"], str(new["title"]).strip(), new["from_place"], new["to_place"], new["start_at"], new["end_at"], new["time_zone"], new["status"], new["price_cents"],
                     ((new["currency"] or t["home_currency"]).upper() if new["price_cents"] is not None or new["currency"] else None), new["basis"], new["headcount"], new["paid_by"], new["tag"],
                     int(bool(new["international"])), new["confirmation"], new["link"], new["operator"], json.dumps(new["contact"]), new["last_departure"], new["desk_hours"], new["lead_minutes"],
                     checked, new["notes"], now_iso(), i.id))
        after = _row(con, "trip_items", i.id)
        history.record(con, app=app, action="trips.update_item", tbl="trip_items", row_key=i.id, before=cur, after=after)
    after["contact"] = new["contact"]
    return after


@action("trips.delete_item", "Remove an item from the plan (undoable).", ById, dangerous=True)
def delete_item(store: Store, i: ById, app: str = "trips") -> dict:
    ts = now_iso()
    with store.tx() as con:
        cur = _bump(con, "trip_items", i.id, None)
        con.execute("UPDATE trip_items SET deleted_at=?, version=version+1, updated_at=? WHERE id=?", (ts, ts, i.id))
        after = _row(con, "trip_items", i.id)
        history.record(con, app=app, action="trips.delete_item", tbl="trip_items", row_key=i.id, before=cur, after=after)
    return after


# ---- expenses and tasks -------------------------------------------------------------

class LogExpense(BaseModel):
    trip_id: str
    amount_cents: int = Field(description="What was actually paid, in `currency` cents")
    currency: str | None = None
    on_date: str | None = Field(None, description="YYYY-MM-DD, today if empty")
    item_id: str | None = Field(None, description="The item this paid for, if any")
    basis: str = Field("group", description="per_person or group")
    paid_by: str = "me"
    tag: str = "personal"
    note: str | None = None


@action("trips.log_expense", "Log money actually spent on the trip (MONEY-09), split company / me and work / personal.", LogExpense)
def log_expense(store: Store, i: LogExpense, app: str = "trips") -> dict:
    if i.basis not in ("per_person", "group"):
        raise ValueError("basis is per_person or group")
    if i.paid_by not in _words(store, "paid_by") or i.tag not in _words(store, "tags"):
        raise ValueError("paid_by or tag is not one of the choices")
    eid, ts = uuid7(), now_iso()
    with store.tx() as con:
        t = _need_trip(con, i.trip_id)
        if i.item_id:
            _need_item(con, i.item_id)
        con.execute("INSERT INTO trip_expenses(id, trip_id, item_id, on_date, amount_cents, currency, basis, paid_by, tag, note, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (eid, i.trip_id, i.item_id, _date(i.on_date, "on_date") or date_type.today().isoformat(), i.amount_cents, (i.currency or t["home_currency"]).upper(), i.basis, i.paid_by, i.tag, i.note, ts))
        after = _row(con, "trip_expenses", eid)
        history.record(con, app=app, action="trips.log_expense", tbl="trip_expenses", row_key=eid, before=None, after=after)
    return after


@action("trips.delete_expense", "Remove a logged expense (undoable).", ById, dangerous=True)
def delete_expense(store: Store, i: ById, app: str = "trips") -> dict:
    ts = now_iso()
    with store.tx() as con:
        cur = _row(con, "trip_expenses", i.id)
        if not cur or cur["deleted_at"]:
            raise records.NotFound(i.id)
        con.execute("UPDATE trip_expenses SET deleted_at=? WHERE id=?", (ts, i.id))
        after = _row(con, "trip_expenses", i.id)
        history.record(con, app=app, action="trips.delete_expense", tbl="trip_expenses", row_key=i.id, before=cur, after=after)
    return after


class AddTask(BaseModel):
    trip_id: str
    title: str
    kind: str = Field("todo", description="entry, health, insurance, permit, phone, safety, pack, confirm, follow_up or todo")
    due: str | None = Field(None, description="YYYY-MM-DD; the checker warns before it and blocks after")
    item_id: str | None = None
    notes: str | None = None


@action("trips.add_task", "Add a before-you-go or follow-up task with a deadline (the arrival card, the permit, 'ask the hostel to hold bags').", AddTask)
def add_task(store: Store, i: AddTask, app: str = "trips") -> dict:
    if not i.title.strip():
        raise ValueError("a task needs a title")
    tid, ts = uuid7(), now_iso()
    with store.tx() as con:
        _need_trip(con, i.trip_id)
        if i.item_id:
            _need_item(con, i.item_id)
        con.execute("INSERT INTO trip_tasks(id, trip_id, item_id, title, kind, due, notes, version, created_at, updated_at) VALUES(?,?,?,?,?,?,?,1,?,?)",
                    (tid, i.trip_id, i.item_id, i.title.strip(), i.kind, _date(i.due, "due"), i.notes, ts, ts))
        after = _row(con, "trip_tasks", tid)
        history.record(con, app=app, action="trips.add_task", tbl="trip_tasks", row_key=tid, before=None, after=after)
    return after


class CompleteTask(BaseModel):
    id: str
    done: bool = True
    due: str | None = Field(None, description="Move the deadline instead")


@action("trips.complete_task", "Tick a task done (or undone), or move its deadline.", CompleteTask)
def complete_task(store: Store, i: CompleteTask, app: str = "trips") -> dict:
    ts = now_iso()
    with store.tx() as con:
        cur = _bump(con, "trip_tasks", i.id, None)
        due = _date(i.due, "due") if i.due else cur["due"]
        done_at = cur["done_at"] if i.due else (ts if i.done else None)
        con.execute("UPDATE trip_tasks SET done_at=?, due=?, version=version+1, updated_at=? WHERE id=?", (done_at, due, ts, i.id))
        after = _row(con, "trip_tasks", i.id)
        history.record(con, app=app, action="trips.complete_task", tbl="trip_tasks", row_key=i.id, before=cur, after=after)
    return after


@action("trips.delete_task", "Remove a task (undoable).", ById, dangerous=True)
def delete_task(store: Store, i: ById, app: str = "trips") -> dict:
    ts = now_iso()
    with store.tx() as con:
        cur = _bump(con, "trip_tasks", i.id, None)
        con.execute("UPDATE trip_tasks SET deleted_at=?, version=version+1, updated_at=? WHERE id=?", (ts, ts, i.id))
        after = _row(con, "trip_tasks", i.id)
        history.record(con, app=app, action="trips.delete_task", tbl="trip_tasks", row_key=i.id, before=cur, after=after)
    return after


class TripId(BaseModel):
    trip_id: str


@action("trips.before_you_go", "W25: create the before-you-go checklist for a trip (entry rules, health, insurance, permits, phone, safety, packing), each with a deadline before departure. Safe to run again: it skips tasks that exist.", TripId)
def before_you_go(store: Store, i: TripId, app: str = "trips") -> dict:
    templates = q.logic(store, "logic.trips.before_you_go")
    made = []
    with store.tx() as con:
        t = _need_trip(con, i.trip_id)
        have = {r[0] for r in con.execute("SELECT title FROM trip_tasks WHERE trip_id=? AND deleted_at IS NULL", (i.trip_id,))}
        region = q.region_row(con, t["region_pack"])
        extra = []
        if region:
            for line in region["sections"].get("Entry rules (US passport)", []) + region["sections"].get("Entry rules", []):
                if "arrival card" in line.lower() or "visa" in line.lower():
                    extra.append({"kind": "entry", "title": f"{region['name']}: {line.split('.')[0]}.", "days_before": 3 if "arrival card" in line.lower() else 30})
        for tpl in templates + extra:
            if tpl["title"] in have:
                continue
            due = (date_type.fromisoformat(t["start_date"]) - timedelta(days=tpl["days_before"])).isoformat() if t.get("start_date") else None
            made.append(add_task(store, AddTask(trip_id=i.trip_id, title=tpl["title"], kind=tpl["kind"], due=due), app))
    return {"created": made, "count": len(made)}


# ---- the checker ---------------------------------------------------------------------

@action("trips.run_checks", "Check the plan: pickups before landings, prices with no per-person/group basis, nights with no stay, overlaps, tight connections and airport buffers, last departures, late check-ins, budget caps, stale prices, passport validity, deadlines, confirmations with no reply. Findings are kept; fixed ones resolve, dismissed ones stay dismissed.", TripId)
def run_checks(store: Store, i: TripId, app: str = "trips") -> dict:
    with store.read():
        _need_trip(store.con, i.trip_id)
    return checks.check_trip(store, i.trip_id, app)


class Dismiss(BaseModel):
    id: str
    undo: bool = Field(False, description="True to reopen a dismissed finding")


@action("trips.dismiss_finding", "Dismiss a finding you have judged (it stays dismissed on later runs), or reopen it.", Dismiss)
def dismiss_finding(store: Store, i: Dismiss, app: str = "trips") -> dict:
    ts = now_iso()
    with store.tx() as con:
        cur = _row(con, "trip_findings", i.id)
        if not cur:
            raise records.NotFound(i.id)
        con.execute("UPDATE trip_findings SET status=?, updated_at=? WHERE id=?", ("open" if i.undo else "dismissed", ts, i.id))
        after = _row(con, "trip_findings", i.id)
        history.record(con, app=app, action="trips.dismiss_finding", tbl="trip_findings", row_key=i.id, before=cur, after=after)
    return after


# ---- confirmations (W27) --------------------------------------------------------------

class DraftConfirmation(BaseModel):
    trip_id: str
    item_id: str
    question: str = Field(description="The exact yes/no you need, e.g. 'Can you hold our bags from checkout at 11 AM until about 3 PM?'")
    channel: str | None = Field(None, description="whatsapp, line, sms, email, app or call; guessed from the operator's contact if empty")
    traveler: str | None = Field(None, description="Who is asking; the first traveler if empty")


@action("trips.draft_confirmation", "W27: draft the message that confirms a booking detail (a bag hold, a late check-in, a pickup time). Message first; a call only if there is no reply, and the call says it's automated. Nothing is sent by the engine: you send it and mark it sent.", DraftConfirmation)
def draft_confirmation(store: Store, i: DraftConfirmation, app: str = "trips") -> dict:
    conf = q.logic(store, "logic.trips.confirmation")
    if i.channel and i.channel not in conf["channels_order"]:
        raise ValueError(f"channel must be one of {conf['channels_order']}")
    if not i.question.strip():
        raise ValueError("say exactly what you need confirmed")
    with store.tx() as con:
        t = _need_trip(con, i.trip_id)
        it = _need_item(con, i.item_id)
        contact = json.loads(it["contact"] or "{}")
        region = q.region_row(con, t["region_pack"])
        order = [c for c in (region["channels"] if region else conf["channels_order"]) if c in conf["channels_order"]] or conf["channels_order"]
        channel = i.channel or next((c for c in order if contact.get(c) or (c == "sms" and contact.get("phone")) or (c == "call" and contact.get("phone"))), order[0])
        to = contact.get(channel) or (contact.get("phone") if channel in ("sms", "call") else None)
        traveler = i.traveler or (t["travelers"][0] if t["travelers"] else "a guest")
        fields = {"operator": it["operator"] or it["title"], "traveler": traveler, "confirmation": it["confirmation"] or "no confirmation number yet",
                  "headcount": it["headcount"] or t["headcount"], "date": q.fmt_d(it["start_at"]) if it["start_at"] else "our dates", "title": it["title"], "question": i.question.strip()}
        message = (conf["call_opening"] if channel == "call" else conf["message"]).format(**fields)
        cid, ts = uuid7(), now_iso()
        con.execute("INSERT INTO trip_confirmations(id, trip_id, item_id, question, channel, to_address, message, status, version, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,1,?,?)",
                    (cid, i.trip_id, i.item_id, i.question.strip(), channel, to, message, "call" if channel == "call" else "draft", ts, ts))
        after = _row(con, "trip_confirmations", cid)
        history.record(con, app=app, action="trips.draft_confirmation", tbl="trip_confirmations", row_key=cid, before=None, after=after)
    after["send_link"] = _send_link(channel, to, message)
    return after


def _send_link(channel: str, to: str | None, message: str) -> str | None:
    from urllib.parse import quote
    if channel == "whatsapp" and to:
        return f"https://wa.me/{''.join(ch for ch in to if ch.isdigit())}?text={quote(message)}"
    if channel == "sms" and to:
        return f"sms:{to}&body={quote(message)}"
    if channel == "email" and to:
        return f"mailto:{to}?subject={quote('Booking question')}&body={quote(message)}"
    if channel == "call" and to:
        return f"tel:{to}"
    return None


class ConfirmationUpdate(BaseModel):
    id: str
    status: str = Field(description="sent (you sent the message), answered (with the reply), no_reply (time's up: call next), or call (the call is pending)")
    reply: str | None = Field(None, description="What they said, when status is answered")
    changed: bool = Field(False, description="True if the reply changes the plan; the item is flagged Check now")
    sent_at: str | None = Field(None, description="When it was sent, if not now (ISO)")


@action("trips.update_confirmation", "Record what happened to a confirmation: sent, answered (log the reply; flag the booking if it changes the plan), no reply (call next), call pending.", ConfirmationUpdate)
def update_confirmation(store: Store, i: ConfirmationUpdate, app: str = "trips") -> dict:
    if i.status not in ("sent", "answered", "no_reply", "call"):
        raise ValueError("status is sent, answered, no_reply or call")
    ts = now_iso()
    with store.tx() as con:
        cur = _bump(con, "trip_confirmations", i.id, None)
        sent_at = cur["sent_at"] or (i.sent_at or ts if i.status == "sent" else cur["sent_at"])
        if i.status == "sent" and i.sent_at:
            sent_at = datetime.fromisoformat(i.sent_at).isoformat(timespec="seconds")
        channel = cur["channel"]
        status = i.status
        if i.status == "no_reply":
            status, channel = "call", "call"
        con.execute("UPDATE trip_confirmations SET status=?, channel=?, sent_at=?, reply=?, replied_at=?, version=version+1, updated_at=? WHERE id=?",
                    (status, channel, sent_at, i.reply if i.status == "answered" else cur["reply"], ts if i.status == "answered" else cur["replied_at"], ts, i.id))
        after = _row(con, "trip_confirmations", i.id)
        history.record(con, app=app, action="trips.update_confirmation", tbl="trip_confirmations", row_key=i.id, before=cur, after=after)
        if i.status == "answered":
            it = _need_item(con, cur["item_id"])
            new_status = "check_now" if i.changed else ("confirmed" if it["status"] in ("booked", "confirmed") else it["status"])
            if new_status != it["status"]:
                con.execute("UPDATE trip_items SET status=?, version=version+1, updated_at=? WHERE id=?", (new_status, ts, it["id"]))
                history.record(con, app=app, action="trips.update_item", tbl="trip_items", row_key=it["id"], before=it, after=_row(con, "trip_items", it["id"]))
    return after


# ---- the helper's track record (W26) -------------------------------------------------

class LogWorkflow(BaseModel):
    trip_id: str
    code: str = Field(description="W01..W29 from the helper")
    outcome: str = Field(description="proven (booked or decided with it), adopted (went with it, nothing booked), open (hit a wall), rejected (turned down)")
    note: str | None = None


@action("trips.log_workflow", "Add a track-record line: how a helper workflow did on this trip (W26 wraps up a trip by doing this for each workflow used).", LogWorkflow)
def log_workflow(store: Store, i: LogWorkflow, app: str = "trips") -> dict:
    if i.outcome not in ("proven", "adopted", "open", "rejected"):
        raise ValueError("outcome is proven, adopted, open or rejected")
    rid, ts = uuid7(), now_iso()
    with store.tx() as con:
        _need_trip(con, i.trip_id)
        if not con.execute("SELECT 1 FROM pack_helper.workflows WHERE code=?", (i.code.upper(),)).fetchone():
            raise ValueError(f"no workflow {i.code}")
        con.execute("INSERT INTO trip_workflow_runs(id, trip_id, code, outcome, note, created_at) VALUES(?,?,?,?,?,?)", (rid, i.trip_id, i.code.upper(), i.outcome, i.note, ts))
        after = _row(con, "trip_workflow_runs", rid)
        history.record(con, app=app, action="trips.log_workflow", tbl="trip_workflow_runs", row_key=rid, before=None, after=after)
    return after


class CheckAll(BaseModel):
    pass


@action("trips.check_all", "Run the plan checker on every trip that is not done. The nightly workflow uses this so new deadlines, stale prices and unanswered messages show by morning.", CheckAll)
def check_all(store: Store, i: CheckAll, app: str = "trips") -> dict:
    out = {}
    for t in q.trips(store):
        if t["stage"] != "done":
            out[t["id"]] = checks.check_trip(store, t["id"], app)["counts"]
    return {"trips": len(out), "counts": out}
