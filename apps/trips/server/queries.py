"""Reads for Trips (the Destination Helper): the list, one trip's plan (a
timeline with 'leave by' times and live links per leg), costs with the
working shown, the calendar file, and the helper catalogue from the pack."""
from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime, timedelta
from urllib.parse import quote
from zoneinfo import ZoneInfo

from engine import settings
from engine.store import Store

FLIGHT_NO = re.compile(r"\b([A-Z][A-Z0-9]|[A-Z0-9][A-Z])\s?\d{2,4}\b")


def logic(store: Store, key: str):
    return settings.get_value(store, key)


def parse_local(s: str | None, tz: str | None) -> datetime | None:
    """'YYYY-MM-DD' (midnight) or 'YYYY-MM-DDTHH:MM' in the named zone (UTC if none)."""
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s if len(s) > 10 else s + "T00:00")
    except ValueError:
        return None
    if d.tzinfo is not None:
        return d
    try:
        z = ZoneInfo(tz) if tz else UTC
    except Exception:
        z = UTC
    return d.replace(tzinfo=z)


def has_time(s: str | None) -> bool:
    return bool(s) and len(s) > 10


def fmt_t(dt: datetime | None) -> str:
    return dt.strftime("%-I:%M %p") if dt else "?"


def fmt_d(s: str | None) -> str:
    if not s:
        return "?"
    return date.fromisoformat(s[:10]).strftime("%b %-d")


def local_iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M")


def _loads(s, default):
    try:
        return json.loads(s) if s else default
    except ValueError:
        return default


# ---- rows -------------------------------------------------------------------------

def trip_row(con, tid: str) -> dict | None:
    r = con.execute("SELECT * FROM trips WHERE id=? AND deleted_at IS NULL", (tid,)).fetchone()
    if not r:
        return None
    t = dict(r)
    t["travelers"] = _loads(t["travelers"], [])
    return t


def items(con, tid: str) -> list[dict]:
    out = []
    for r in con.execute("SELECT * FROM trip_items WHERE trip_id=? AND deleted_at IS NULL ORDER BY start_at IS NULL, start_at, created_at", (tid,)):
        d = dict(r)
        d["contact"] = _loads(d["contact"], {})
        out.append(d)
    return out


def tasks(con, tid: str) -> list[dict]:
    return [dict(r) for r in con.execute("SELECT * FROM trip_tasks WHERE trip_id=? AND deleted_at IS NULL ORDER BY done_at IS NOT NULL, due IS NULL, due, created_at", (tid,))]


def expenses(con, tid: str) -> list[dict]:
    return [dict(r) for r in con.execute("SELECT * FROM trip_expenses WHERE trip_id=? AND deleted_at IS NULL ORDER BY on_date DESC, id DESC", (tid,))]


def confirmations(con, tid: str) -> list[dict]:
    return [dict(r) for r in con.execute("SELECT * FROM trip_confirmations WHERE trip_id=? AND deleted_at IS NULL ORDER BY created_at DESC", (tid,))]


def findings(con, tid: str, all_: bool = False) -> list[dict]:
    order = "CASE severity WHEN 'blocker' THEN 0 WHEN 'warn' THEN 1 ELSE 2 END, first_seen"
    if all_:
        return [dict(r) for r in con.execute(f"SELECT * FROM trip_findings WHERE trip_id=? ORDER BY status='open' DESC, {order}", (tid,))]
    return [dict(r) for r in con.execute(f"SELECT * FROM trip_findings WHERE trip_id=? AND status='open' ORDER BY {order}", (tid,))]


def workflow_runs(con, tid: str) -> list[dict]:
    return [dict(r) for r in con.execute("SELECT * FROM trip_workflow_runs WHERE trip_id=? AND deleted_at IS NULL ORDER BY code, created_at", (tid,))]


def region_row(con, rid: str | None) -> dict | None:
    if not rid:
        return None
    r = con.execute("SELECT * FROM pack_helper.region_packs WHERE id=?", (rid,)).fetchone()
    if not r:
        return None
    d = dict(r)
    for k in ("sections", "worked_examples", "sites", "channels"):
        d[k] = _loads(d[k], {} if k == "sections" else [])
    return d


# ---- money ------------------------------------------------------------------------

def group_total(price_cents: int | None, basis: str | None, headcount: int | None, trip_headcount: int) -> tuple[int | None, int | None, int]:
    """(for the group, per person, the headcount used). A price with no basis is treated as a group total but flagged by the checker."""
    n = max(1, headcount or trip_headcount or 1)
    if price_cents is None:
        return None, None, n
    group = price_cents * n if basis == "per_person" else price_cents
    return group, (group + n // 2) // n, n


def to_home(cents: int | None, currency: str | None, trip: dict) -> int | None:
    """Cents in the trip's home currency, or None when there is no rate to use."""
    if cents is None:
        return None
    cur = (currency or trip["home_currency"]).upper()
    if cur == trip["home_currency"].upper():
        return cents
    if trip.get("local_currency") and cur == trip["local_currency"].upper() and trip.get("fx_rate"):
        return round(cents / trip["fx_rate"])
    return None


COUNTED = ("to_book", "booked", "confirmed", "check_now", "done")


def costs(store: Store, tid: str) -> dict:
    with store.read():
        con = store.con
        trip = trip_row(con, tid)
        if not trip:
            raise LookupError(tid)
        its, exps = items(con, tid), expenses(con, tid)
    d = logic(store, "logic.trips.defaults")
    words = {"paid_by": dict(d["paid_by"]), "tags": dict(d["tags"]), "statuses": dict(d["statuses"])}
    zero = lambda keys: {k: 0 for k in keys}  # noqa: E731
    out = {"trip_id": tid, "home_currency": trip["home_currency"], "local_currency": trip["local_currency"], "fx_rate": trip["fx_rate"], "fx_date": trip["fx_date"],
           "headcount": trip["headcount"], "card_rate_markup_pct": d["card_rate_markup_pct"],
           "planned_home_cents": 0, "booked_home_cents": 0, "to_book_home_cents": 0,
           "by_paid_by": zero(words["paid_by"]), "by_tag": zero(words["tags"]), "by_kind": {}, "by_day": {}, "unconverted": [], "lines": [],
           "actual_home_cents": 0, "actual_by_paid_by": zero(words["paid_by"]), "actual_by_tag": zero(words["tags"]), "expenses": len(exps)}
    for it in its:
        if it["status"] not in COUNTED:
            continue
        g, pp, n = group_total(it["price_cents"], it["basis"], it["headcount"], trip["headcount"])
        if g is None:
            continue
        home = to_home(g, it["currency"], trip)
        line = {"item_id": it["id"], "title": it["title"], "kind": it["kind"], "status": it["status"], "day": (it["start_at"] or "")[:10] or None,
                "currency": (it["currency"] or trip["home_currency"]).upper(), "basis": it["basis"], "headcount": n,
                "group_cents": g, "per_person_cents": pp, "home_cents": home, "paid_by": it["paid_by"], "tag": it["tag"]}
        out["lines"].append(line)
        if home is None:
            out["unconverted"].append(line)
            continue
        out["planned_home_cents"] += home
        if it["status"] in ("booked", "confirmed", "done", "check_now"):
            out["booked_home_cents"] += home
        else:
            out["to_book_home_cents"] += home
        out["by_paid_by"][it["paid_by"]] = out["by_paid_by"].get(it["paid_by"], 0) + home
        out["by_tag"][it["tag"]] = out["by_tag"].get(it["tag"], 0) + home
        out["by_kind"][it["kind"]] = out["by_kind"].get(it["kind"], 0) + home
        if line["day"]:
            out["by_day"][line["day"]] = out["by_day"].get(line["day"], 0) + home
    for e in exps:
        g, pp, n = group_total(e["amount_cents"], e["basis"], None, trip["headcount"])
        home = to_home(g, e["currency"], trip)
        if home is None:
            continue
        out["actual_home_cents"] += home
        out["actual_by_paid_by"][e["paid_by"]] = out["actual_by_paid_by"].get(e["paid_by"], 0) + home
        out["actual_by_tag"][e["tag"]] = out["actual_by_tag"].get(e["tag"], 0) + home
    out["per_person_home_cents"] = round(out["planned_home_cents"] / max(1, trip["headcount"]))
    out["i_pay_home_cents"] = out["by_paid_by"].get("me", 0) + round(out["by_paid_by"].get("split", 0) / 2)
    out["company_pays_home_cents"] = out["by_paid_by"].get("company", 0) + round(out["by_paid_by"].get("split", 0) / 2)
    out["card_rate_note"] = (f"Converted at {trip['fx_rate']} {trip['local_currency']} per {trip['home_currency']} (checked {trip['fx_date'] or 'date not noted'}). "
                             f"Your card's rate is usually about {d['card_rate_markup_pct']}% worse.") if trip.get("fx_rate") else "No exchange rate set yet: local-currency prices are not converted."
    out["words"] = words
    return out


# ---- the plan ---------------------------------------------------------------------

def _slug(s: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def leg_links(trip: dict, it: dict, region: dict | None) -> list[dict]:
    """Live sites for one leg, first on the item: directions, flights, all ways, the region's ground-transport site, flight status."""
    a, b = it.get("from_place") or "", it.get("to_place") or ""
    day = (it.get("start_at") or trip.get("start_date") or "")[:10]
    out = []
    if a and b:
        out.append({"key": "directions", "label": "Directions", "url": f"https://www.google.com/maps/dir/?api=1&origin={quote(a)}&destination={quote(b)}"})
        out.append({"key": "all_modes", "label": "All ways", "url": f"https://www.rome2rio.com/map/{quote(_slug(a))}/{quote(_slug(b))}"})
        if it["kind"] == "flight":
            out.append({"key": "flights", "label": "Flights", "url": f"https://www.google.com/travel/flights?q=flights%20from%20{quote(a)}%20to%20{quote(b)}%20on%20{day}"})
        for s in (region or {}).get("sites", []):
            if "{a}" in s.get("url", ""):
                out.append({"key": "ground", "label": s["name"], "url": s["url"].format(a=_slug(a), b=_slug(b), date=day, n=it.get("headcount") or trip["headcount"])})
    if it["kind"] == "flight":
        m = FLIGHT_NO.search(it.get("title") or "")
        if m:
            out.append({"key": "status", "label": "Flight status", "url": f"https://www.google.com/search?q={quote(m.group(0) + ' flight status')}"})
    if it.get("link"):
        out.append({"key": "booking", "label": "Booking page", "url": it["link"]})
    return out


def buffers(store: Store) -> tuple[dict, dict]:
    return logic(store, "logic.trips.checks"), logic(store, "logic.trips.kinds")


def leave_by(it: dict, tz: str | None, rules: dict, kinds: dict) -> dict | None:
    """When to be at the start point and when to set off, for a leg with a time."""
    if it["kind"] not in kinds["transport"] or not has_time(it.get("start_at")):
        return None
    start = parse_local(it["start_at"], it.get("time_zone") or tz)
    if it["kind"] == "flight":
        buf = rules["airport_buffer_minutes"]["international" if it.get("international") else "domestic"]
    else:
        buf = kinds["buffer_minutes"].get(it["kind"], 0)
    there = start - timedelta(minutes=buf)
    leave = there - timedelta(minutes=it.get("lead_minutes") or 0)
    return {"be_there_by": local_iso(there), "leave_by": local_iso(leave), "buffer_minutes": buf, "lead_minutes": it.get("lead_minutes") or 0,
            "words": f"Be there by {fmt_t(there)}" + (f"; leave by {fmt_t(leave)}" if it.get("lead_minutes") else " (add travel time to this item for a leave-by)")}


def plan(store: Store, tid: str) -> dict:
    with store.read():
        con = store.con
        trip = trip_row(con, tid)
        if not trip:
            raise LookupError(tid)
        its, tks, exps, cfs, fds, runs = items(con, tid), tasks(con, tid), expenses(con, tid), confirmations(con, tid), findings(con, tid), workflow_runs(con, tid)
        region = region_row(con, trip["region_pack"])
    rules, kinds = buffers(store)
    tz = trip.get("time_zone") or (region or {}).get("time_zone")
    by_item = {}
    for it in its:
        g, pp, n = group_total(it["price_cents"], it["basis"], it["headcount"], trip["headcount"])
        it.update({"group_cents": g, "per_person_cents": pp, "headcount_used": n, "home_cents": to_home(g, it["currency"], trip),
                   "links": leg_links(trip, it, region), "leave": leave_by(it, tz, rules, kinds), "day": (it["start_at"] or "")[:10] or None,
                   "end_day": (it["end_at"] or "")[:10] or None, "is_stay": it["kind"] in kinds["stay"], "is_leg": it["kind"] in kinds["transport"],
                   "confirmations": [c for c in cfs if c["item_id"] == it["id"]], "findings": [f for f in fds if f["item_id"] == it["id"]]})
        by_item[it["id"]] = it
    days = []
    d0 = trip["start_date"] or min((it["day"] for it in its if it["day"]), default=None)
    d1 = trip["end_date"] or max((it["end_day"] or it["day"] for it in its if it["day"]), default=None)
    if d0 and d1:
        d, last = date.fromisoformat(d0), date.fromisoformat(d1)
        while d <= last:
            ds = d.isoformat()
            night = next((it for it in its if it["is_stay"] and it["day"] and it["day"] <= ds and (it["end_day"] or "9999") > ds and it["status"] != "cancelled"), None)
            days.append({"date": ds, "label": d.strftime("%a %b %-d"),
                         "items": [it["id"] for it in its if (it["day"] == ds and not it["is_stay"]) or (it["is_stay"] and it["day"] == ds)],
                         "night": {"item_id": night["id"], "title": night["title"], "status": night["status"]} if night else None,
                         "tasks": [t["id"] for t in tks if t["due"] == ds]})
            d += timedelta(days=1)
    unscheduled = [it["id"] for it in its if not it["day"]]
    sev = {"blocker": 0, "warn": 0, "info": 0}
    for f in fds:
        sev[f["severity"]] = sev.get(f["severity"], 0) + 1
    return {"trip": trip, "time_zone": tz, "items": its, "days": days, "unscheduled": unscheduled, "tasks": tks, "expenses": exps, "confirmations": cfs,
            "findings": fds, "finding_counts": sev, "workflow_runs": runs, "costs": costs(store, tid),
            "region": {k: region[k] for k in ("id", "name", "currency", "time_zone", "channels", "sites", "intro")} if region else None,
            "rules": rules, "today": date.today().isoformat()}


def trips(store: Store) -> list[dict]:
    with store.read():
        con = store.con
        out = []
        for r in con.execute("SELECT * FROM trips WHERE deleted_at IS NULL ORDER BY start_date IS NULL, start_date DESC"):
            t = dict(r)
            t["travelers"] = _loads(t["travelers"], [])
            t["items"] = con.execute("SELECT count(*) FROM trip_items WHERE trip_id=? AND deleted_at IS NULL", (t["id"],)).fetchone()[0]
            t["to_book"] = con.execute("SELECT count(*) FROM trip_items WHERE trip_id=? AND deleted_at IS NULL AND status IN ('to_book','check_now')", (t["id"],)).fetchone()[0]
            t["findings"] = {s: n for s, n in con.execute("SELECT severity, count(*) FROM trip_findings WHERE trip_id=? AND status='open' GROUP BY severity", (t["id"],))}
            t["tasks_open"] = con.execute("SELECT count(*) FROM trip_tasks WHERE trip_id=? AND deleted_at IS NULL AND done_at IS NULL", (t["id"],)).fetchone()[0]
            nxt = con.execute("SELECT title, start_at FROM trip_items WHERE trip_id=? AND deleted_at IS NULL AND start_at >= ? ORDER BY start_at LIMIT 1",
                              (t["id"], datetime.now().strftime("%Y-%m-%dT%H:%M"))).fetchone()
            t["next_item"] = dict(nxt) if nxt else None
            out.append(t)
    return out


# ---- the calendar file ------------------------------------------------------------

def _ics_text(s) -> str:
    return str(s or "").replace("\\", "\\\\").replace(";", r"\;").replace(",", "\\,").replace("\n", "\\n")


def ics(store: Store, tid: str) -> str:
    p = plan(store, tid)
    trip, tz = p["trip"], p["time_zone"] or "UTC"
    alarm = logic(store, "logic.trips.defaults")["ics_alarm_minutes"]
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    L = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//The MindScape//Trips//EN", "CALSCALE:GREGORIAN", f"X-WR-CALNAME:{_ics_text(trip['name'])}"]
    for it in p["items"]:
        if it["status"] == "cancelled" or not it["start_at"]:
            continue
        desc = " · ".join(x for x in [f"Status: {it['status']}", f"Confirmation {it['confirmation']}" if it["confirmation"] else "",
                                       f"{it['group_cents'] / 100:.2f} {it['currency'] or trip['home_currency']} for {it['headcount_used']}" if it["group_cents"] is not None else "",
                                       it["notes"] or ""] if x)
        L += ["BEGIN:VEVENT", f"UID:{it['id']}@mindscape", f"DTSTAMP:{stamp}", f"SUMMARY:{_ics_text(it['kind'].title() + ': ' + it['title'])}"]
        z = it["time_zone"] or tz
        if has_time(it["start_at"]):
            L.append(f"DTSTART;TZID={z}:{it['start_at'].replace('-', '').replace(':', '')}00")
            if it["end_at"] and has_time(it["end_at"]):
                L.append(f"DTEND;TZID={z}:{it['end_at'].replace('-', '').replace(':', '')}00")
            if alarm:
                L += ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{_ics_text(it['title'])}", f"TRIGGER:-PT{alarm}M", "END:VALARM"]
        else:
            L.append(f"DTSTART;VALUE=DATE:{it['start_at'][:10].replace('-', '')}")
            end = (it["end_at"] or "")[:10] or (date.fromisoformat(it["start_at"][:10]) + timedelta(days=1)).isoformat()
            L.append(f"DTEND;VALUE=DATE:{end.replace('-', '')}")
        if it["from_place"] or it["to_place"]:
            L.append(f"LOCATION:{_ics_text(' → '.join(x for x in (it['from_place'], it['to_place']) if x))}")
        if desc:
            L.append(f"DESCRIPTION:{_ics_text(desc)}")
        if it["link"]:
            L.append(f"URL:{it['link']}")
        L.append("END:VEVENT")
    for t in p["tasks"]:
        if t["due"] and not t["done_at"]:
            L += ["BEGIN:VEVENT", f"UID:{t['id']}@mindscape", f"DTSTAMP:{stamp}", f"SUMMARY:{_ics_text('Deadline: ' + t['title'])}",
                  f"DTSTART;VALUE=DATE:{t['due'].replace('-', '')}", f"DTEND;VALUE=DATE:{(date.fromisoformat(t['due']) + timedelta(days=1)).isoformat().replace('-', '')}", "END:VEVENT"]
    L.append("END:VCALENDAR")
    return "\r\n".join(L) + "\r\n"


# ---- the helper catalogue (the pack) -----------------------------------------------

def helper(store: Store) -> dict:
    with store.read():
        con = store.con
        meta = {r[0]: r[1] for r in con.execute("SELECT key, value FROM pack_helper.meta")}
        sections = [dict(r) for r in con.execute("SELECT code, label FROM pack_helper.sections ORDER BY ord")]
        qs = [dict(r) for r in con.execute("SELECT code, section, text, new FROM pack_helper.questions ORDER BY ord")]
        wfs = []
        for r in con.execute("SELECT * FROM pack_helper.workflows ORDER BY ord"):
            w = dict(r)
            w["steps"] = _loads(w["steps"], [])
            wfs.append(w)
        gs = [dict(r) for r in con.execute("SELECT code, rule, why FROM pack_helper.guardrails ORDER BY ord")]
        methods: dict[str, list] = {}
        for r in con.execute("SELECT grp, sub, name, text, new FROM pack_helper.methods ORDER BY ord"):
            methods.setdefault(r["grp"], []).append(dict(r))
        brief = [{"part": r["part"], "heading": r["heading"], "lines": _loads(r["lines"], [])} for r in con.execute("SELECT * FROM pack_helper.brief ORDER BY ord")]
        regions = [dict(r) for r in con.execute("SELECT id, name, country_code, currency, time_zone FROM pack_helper.region_packs ORDER BY name")]
    return {"meta": meta, "sections": sections, "questions": qs, "workflows": wfs, "guardrails": gs, "methods": methods, "brief": brief, "regions": regions}


def region(store: Store, rid: str) -> dict:
    with store.read():
        r = region_row(store.con, rid)
    if not r:
        raise LookupError(rid)
    return r


def options(store: Store) -> dict:
    d = logic(store, "logic.trips.defaults")
    kinds = logic(store, "logic.trips.kinds")
    conf = logic(store, "logic.trips.confirmation")
    with store.read():
        regions = [dict(r) for r in store.con.execute("SELECT id, name, country_code, currency, time_zone, channels FROM pack_helper.region_packs ORDER BY name")]
    for r in regions:
        r["channels"] = _loads(r["channels"], [])
    return {"defaults": d, "kinds": kinds, "kind_list": kinds["transport"] + kinds["stay"] + kinds["other"], "channels": conf["channels_order"],
            "regions": regions, "home": settings.get_value(store, "profile.home_city"), "checks": logic(store, "logic.trips.checks"),
            "task_kinds": ["entry", "health", "insurance", "permit", "phone", "safety", "pack", "confirm", "follow_up", "todo"]}
