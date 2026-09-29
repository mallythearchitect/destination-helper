"""The plan checker: the part Wanderlog doesn't do. Plain rules over the
trip's items, tasks and confirmations, every threshold from Settings →
Logic (logic.trips.checks). Each finding says what is wrong and the fix.
Findings are kept in trip_findings so a dismissed one stays dismissed and a
fixed one is marked resolved, not forgotten."""
from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

from engine.ids import uuid7
from engine.store import Store, now_iso

from . import queries as q


def _same_place(a: str | None, b: str | None) -> bool:
    """Unknown counts as a match; otherwise one name inside the other, or a shared word of 4+ letters."""
    a, b = (a or "").casefold().strip(), (b or "").casefold().strip()
    if not a or not b:
        return True
    if a in b or b in a:
        return True
    wa = {w for w in a.replace(",", " ").split() if len(w) >= 4}
    wb = {w for w in b.replace(",", " ").split() if len(w) >= 4}
    return bool(wa & wb)


def _months(d: date, n: int) -> date:
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    return date(y, m, min(d.day, 28))


def run(store: Store, trip: dict, items: list[dict], tasks: list[dict], confirmations: list[dict], today: date | None = None,
        now: datetime | None = None) -> list[dict]:
    rules = q.logic(store, "logic.trips.checks")
    kinds = q.logic(store, "logic.trips.kinds")
    conf = q.logic(store, "logic.trips.confirmation")
    today = today or date.today()
    now = now or datetime.now(UTC)
    tz = trip.get("time_zone")
    live = [it for it in items if it["status"] != "cancelled"]
    for it in live:
        z = it.get("time_zone") or tz
        it["_start"], it["_end"] = q.parse_local(it.get("start_at"), z), q.parse_local(it.get("end_at"), z)
        it["_day"] = (it.get("start_at") or "")[:10] or None
        it["_timed"] = q.has_time(it.get("start_at"))
    legs = [it for it in live if it["kind"] in kinds["transport"]]
    pickups = [it for it in live if it["kind"] in kinds["pickup"]]
    arrivals = [it for it in legs if it["kind"] not in kinds["pickup"] and it["_end"]]
    stays = [it for it in live if it["kind"] in kinds["stay"]]
    out: list[dict] = []

    def add(rule, key, severity, message, fix=None, item=None, fix_action=None):
        out.append({"rule": rule, "key": f"{rule}:{key}", "severity": severity, "message": message, "fix": fix, "item_id": item["id"] if item else None,
                    "fix_action": fix_action})

    # 1. A pickup set before the ride it meets has arrived (the Thailand taxi: 12:00 PM against a 6:45 PM landing).
    wait = rules["transfer_after_arrival_minutes"]
    for p in pickups:
        if not p["_timed"]:
            continue
        for a in arrivals:
            if a["_day"] == p["_day"] and _same_place(a.get("to_place"), p.get("from_place")) and p["_start"] < a["_end"]:
                new_t = a["_end"] + timedelta(minutes=wait)
                add("pickup-before-arrival", p["id"], "blocker",
                    f"{p['title']} is set for {q.fmt_t(p['_start'])} but {a['title']} only arrives at {q.fmt_t(a['_end'])} on {q.fmt_d(a['_day'])}.",
                    f"Move the pickup to about {q.fmt_t(new_t)}, add the flight or ferry number to the booking, and message the operator.", p,
                    fix_action={"label": f"Move it to {q.fmt_t(new_t)}", "action": "trips.update_item", "payload": {"id": p["id"], "start_at": q.local_iso(new_t)}})
                break

    # 2. Prices that don't say per person or for the group (G03, G04).
    for it in live:
        if it.get("price_cents") is not None and not it.get("basis"):
            add("price-basis", it["id"], "warn", f"{it['title']}: the price doesn't say whether it is per person or for the group.",
                "Open the booking page and mark it per person or group; the totals change with it.", it,
                fix_action={"label": "It's per person", "action": "trips.update_item", "payload": {"id": it["id"], "basis": "per_person"},
                            "alt": {"label": "For the group", "action": "trips.update_item", "payload": {"id": it["id"], "basis": "group"}}})
        if it.get("headcount") and it["headcount"] != trip["headcount"]:
            add("headcount", it["id"], "warn", f"{it['title']} is for {it['headcount']}, but {trip['headcount']} are travelling.",
                "Check the passenger count on the booking page.", it)

    # 3. Nights with nowhere to sleep; nights booked twice (G07).
    if trip.get("start_date") and trip.get("end_date"):
        d, last = date.fromisoformat(trip["start_date"]), date.fromisoformat(trip["end_date"])
        missing: list[date] = []
        while d < last:
            ds = d.isoformat()
            cover = [s for s in stays if s["_day"] and s["_day"] <= ds < ((s.get("end_at") or "9999")[:10])]
            if not cover:
                missing.append(d)
            elif len(cover) > 1:
                add("stays-overlap", ds, "info", f"Two stays cover the night of {q.fmt_d(ds)}: {' and '.join(s['title'] for s in cover)}.", "Cancel one, or check the dates.")
            d += timedelta(days=1)
        if missing:
            runs, start = [], missing[0]
            for a, b in zip(missing, missing[1:] + [None], strict=False):
                if b is None or (b - a).days > 1:
                    runs.append((start, a))
                    start = b
            for a, b in runs:
                n = (b - a).days + 1
                add("night-without-stay", a.isoformat(), "warn",
                    f"No place to sleep {'on ' + q.fmt_d(a.isoformat()) if n == 1 else 'from ' + q.fmt_d(a.isoformat()) + ' to ' + q.fmt_d(b.isoformat()) + f' ({n} nights)'}.",
                    "Add the stay, or mark the night as covered (a night bus, a friend's place).",
                    fix_action={"label": "Add a stay", "ui": "add_stay", "start": a.isoformat(), "end": (b + timedelta(days=1)).isoformat()})

    # 4. Timed items that overlap; legs too close together; the airport buffer.
    timed = sorted([it for it in live if it["_timed"] and it["kind"] not in kinds["stay"]], key=lambda x: x["_start"])
    for i, a in enumerate(timed):
        for b in timed[i + 1:]:
            if a["_end"] and b["_start"] < a["_end"] and a["kind"] not in kinds["pickup"] and b["kind"] not in kinds["pickup"]:
                add("overlap", f"{a['id']}:{b['id']}", "warn", f"{a['title']} ({q.fmt_t(a['_start'])}–{q.fmt_t(a['_end'])}) overlaps {b['title']} ({q.fmt_t(b['_start'])}).",
                    "One of them has to move.", b)
    for i, b in enumerate(timed):
        if b["kind"] not in kinds["transport"] or b["kind"] in kinds["pickup"]:
            continue
        prev = next((a for a in reversed(timed[:i]) if a["_end"] and a["_end"] <= b["_start"] and a["_day"] == b["_day"]), None)
        if not prev:
            continue
        gap = (b["_start"] - prev["_end"]).total_seconds() / 60
        if b["kind"] == "flight":
            need = rules["airport_buffer_minutes"]["international" if b.get("international") else "domestic"] + (b.get("lead_minutes") or 0)
            if gap < need:
                add("airport-buffer", b["id"], "warn", f"Only {int(gap)} min between {prev['title']} ending and the {q.fmt_t(b['_start'])} flight; you need about {need} min"
                    f"{' including the ride to the airport' if b.get('lead_minutes') else ' at the airport'}.",
                    f"Leave {prev['title']} by {q.fmt_t(b['_start'] - timedelta(minutes=need))}, or move one of them.", b)
        elif prev["kind"] in kinds["transport"] and gap < rules["min_connection_minutes"]:
            add("tight-connection", b["id"], "warn", f"Only {int(gap)} min between {prev['title']} arriving and {b['title']} leaving.",
                f"Under {rules['min_connection_minutes']} min is tight for separate bookings; pick a later departure or confirm the operator waits.", b)

    # 5. The last departure of the day.
    for it in legs:
        ld = it.get("last_departure")
        if not ld or not it["_day"]:
            continue
        last = q.parse_local(f"{it['_day']}T{ld}", it.get("time_zone") or tz)
        if it["_timed"] and it["_start"] > last:
            add("after-last-departure", it["id"], "blocker", f"{it['title']} at {q.fmt_t(it['_start'])} is after the last departure of the day ({ld}).",
                "Take an earlier one, or move this to the next morning.", it)
            continue
        feeder = next((a for a in arrivals if a["_day"] == it["_day"] and a is not it and _same_place(a.get("to_place"), it.get("from_place")) and a["_end"] <= (it["_start"] or last)), None)
        if feeder and feeder["_end"] + timedelta(minutes=wait) > last:
            add("miss-last-departure", it["id"], "blocker", f"{feeder['title']} arrives {q.fmt_t(feeder['_end'])}; the last {it['kind']} ({it['title']}) leaves at {ld}.",
                "Arrive earlier, or stay the night and take the first one in the morning.", it)

    # 6. Late check-in with no word on the front desk.
    late = rules["late_checkin_hour"]
    for s in stays:
        if not s["_day"] or s.get("desk_hours"):
            continue
        arr = max((a["_end"] for a in arrivals if a["_day"] == s["_day"] and a["_end"]), default=None)
        t = s["_start"] if s["_timed"] else arr
        if t and t.hour >= late:
            add("late-checkin", s["id"], "warn", f"You reach {s['title']} around {q.fmt_t(t)} on {q.fmt_d(s['_day'])}; nothing says the front desk is open then.",
                "Message the property with your arrival time and note the desk hours on the stay.", s)

    # 7. Budget caps (G02).
    if trip.get("budget_night_cents"):
        for s in stays:
            g = q.to_home(q.group_total(s.get("price_cents"), s.get("basis"), s.get("headcount"), trip["headcount"])[0], s.get("currency"), trip)
            if g is not None and s["_day"] and s.get("end_at"):
                nights = max(1, (date.fromisoformat(s["end_at"][:10]) - date.fromisoformat(s["_day"])).days)
                if g / nights > trip["budget_night_cents"]:
                    add("over-budget-night", s["id"], "warn", f"{s['title']} is {g / nights / 100:,.0f} {trip['home_currency']} a night against a cap of {trip['budget_night_cents'] / 100:,.0f}.",
                        "Find a cheaper place in the same area, or raise the cap on purpose.", s)
    if trip.get("budget_leg_cents"):
        for it in legs:
            g = q.to_home(q.group_total(it.get("price_cents"), it.get("basis"), it.get("headcount"), trip["headcount"])[0], it.get("currency"), trip)
            if g is not None and g > trip["budget_leg_cents"]:
                add("over-budget-leg", it["id"], "warn", f"{it['title']} costs {g / 100:,.0f} {trip['home_currency']} for the group against a cap of {trip['budget_leg_cents'] / 100:,.0f} per leg.",
                    "Compare every way from A to B (W02): a bus, a ferry, another airport.", it)
    if trip.get("budget_day_cents"):
        per_day: dict[str, int] = {}
        for it in live:
            if it["_day"] and it["kind"] not in kinds["stay"] and it["status"] in q.COUNTED:
                g = q.to_home(q.group_total(it.get("price_cents"), it.get("basis"), it.get("headcount"), trip["headcount"])[0], it.get("currency"), trip)
                if g:
                    per_day[it["_day"]] = per_day.get(it["_day"], 0) + g
        for ds, g in per_day.items():
            if g > trip["budget_day_cents"]:
                add("over-budget-day", ds, "warn", f"{q.fmt_d(ds)} adds up to {g / 100:,.0f} {trip['home_currency']} against a cap of {trip['budget_day_cents'] / 100:,.0f} a day.",
                    "Drop or move one thing that day.")

    # 8. Stale prices; budget flights left late; booked things with no price (G05).
    stale = today - timedelta(days=rules["price_recheck_days"])
    for it in live:
        if it["status"] in ("to_book", "idea") and it.get("price_cents") is not None:
            pc = (it.get("price_checked_at") or it.get("updated_at") or "")[:10]
            if pc and date.fromisoformat(pc) < stale:
                add("price-stale", it["id"], "info", f"{it['title']}: the price was last checked {q.fmt_d(pc)}.", "Re-check before deciding; fares move.", it)
        if it["kind"] == "flight" and it["status"] == "to_book" and it["_day"]:
            weeks = (date.fromisoformat(it["_day"]) - today).days / 7
            if 0 <= weeks < rules["book_flights_weeks_out"]:
                add("book-flight-now", it["id"], "warn", f"{it['title']} is {weeks:.0f} week(s) away and not booked; budget fares climb from about {rules['book_flights_weeks_out']} weeks out.",
                    "Book it, or decide to skip it.", it, fix_action={"label": "Open it", "ui": "edit_item", "item_id": it["id"]})
        if it["status"] in ("booked", "confirmed") and it.get("price_cents") is None:
            add("booked-no-price", it["id"], "info", f"{it['title']} is booked but no price is logged.", "Add the price from the confirmation so the totals are real.", it,
                fix_action={"label": "Add the price", "ui": "edit_item", "item_id": it["id"]})
        if it["status"] in ("booked", "confirmed") and it["_day"] and trip.get("start_date") and trip.get("end_date") and not (trip["start_date"] <= it["_day"] <= trip["end_date"]):
            add("booked-outside-dates", it["id"], "warn", f"{it['title']} is booked for {q.fmt_d(it['_day'])}, outside the trip dates.", "Booked for the old plan? Change or cancel it.", it)

    # 9. Passport and money basics (READY-01, MONEY-03).
    international = bool(trip.get("region_pack")) or (trip.get("local_currency") and trip["local_currency"].upper() != trip["home_currency"].upper())
    if trip.get("end_date"):
        need = _months(date.fromisoformat(trip["end_date"]), rules["passport_valid_months"])
        if trip.get("passport_expiry"):
            if date.fromisoformat(trip["passport_expiry"]) < need:
                add("passport-validity", "trip", "blocker", f"The passport expires {q.fmt_d(trip['passport_expiry'])}; many countries want {rules['passport_valid_months']} months past the trip ({q.fmt_d(need.isoformat())}).",
                    "Renew it, or confirm this country's rule on travel.state.gov.")
        elif international:
            add("passport-unchecked", "trip", "info", "Passport expiry not entered, so its validity can't be checked.", "Add it to the trip (Settings on the trip).",
                fix_action={"label": "Add it", "ui": "trip_settings"})
    if international and any(it.get("currency") and it["currency"].upper() != trip["home_currency"].upper() for it in live) and not trip.get("fx_rate"):
        add("fx-missing", "trip", "info", "Prices in the local currency can't be converted: no exchange rate on the trip.", "Look it up today (TradingView) and note the date.")

    # 10. Deadlines and confirmations waiting on a reply.
    soon = today + timedelta(days=rules["deadline_warn_days"])
    for t in tasks:
        if t.get("done_at") or not t.get("due"):
            continue
        due = date.fromisoformat(t["due"])
        done = {"label": "Done", "action": "trips.complete_task", "payload": {"id": t["id"], "done": True}}
        if due < today:
            add("deadline-overdue", t["id"], "blocker", f"Overdue: {t['title']} (was due {q.fmt_d(t['due'])}).", "Do it now, or move the date on purpose.", fix_action=done)
        elif due <= soon:
            add("deadline-soon", t["id"], "warn", f"Due {q.fmt_d(t['due'])}: {t['title']}.", None, fix_action=done)
    for c in confirmations:
        if c["status"] == "sent" and c.get("sent_at"):
            sent = datetime.fromisoformat(c["sent_at"])
            if sent.tzinfo is None:
                sent = sent.replace(tzinfo=UTC)
            if now - sent > timedelta(hours=conf["reply_hours"]):
                it = next((x for x in items if x["id"] == c["item_id"]), None)
                add("confirmation-no-reply", c["id"], "warn", f"No reply in {conf['reply_hours']}h to the {c['channel']} about {it['title'] if it else 'a booking'}.",
                    "Mark it 'no reply' and call; the call says up front that it's automated.", it)
        elif c["status"] == "call":
            it = next((x for x in items if x["id"] == c["item_id"]), None)
            add("confirmation-call", c["id"], "info", f"Call pending: {it['title'] if it else 'a booking'} ({c['question']}).", None, it)
    return out


def sync(store: Store, trip_id: str, found: list[dict], app: str) -> dict:
    """Write the findings: new ones open, seen ones refreshed, dismissed ones left alone, missing ones resolved."""
    ts = now_iso()
    with store.tx() as con:
        have = {r["key"]: dict(r) for r in con.execute("SELECT * FROM trip_findings WHERE trip_id=?", (trip_id,))}
        seen = set()
        for f in found:
            seen.add(f["key"])
            cur = have.get(f["key"])
            if cur is None:
                con.execute("INSERT INTO trip_findings(id, trip_id, item_id, rule, key, severity, message, fix, status, first_seen, last_seen, updated_at, fix_action) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (uuid7(), trip_id, f["item_id"], f["rule"], f["key"], f["severity"], f["message"], f["fix"], "open", ts, ts, ts, json.dumps(f.get("fix_action")) if f.get("fix_action") else None))
            else:
                status = "dismissed" if cur["status"] == "dismissed" else "open"
                con.execute("UPDATE trip_findings SET item_id=?, severity=?, message=?, fix=?, status=?, last_seen=?, updated_at=?, fix_action=? WHERE id=?",
                            (f["item_id"], f["severity"], f["message"], f["fix"], status, ts, ts, json.dumps(f.get("fix_action")) if f.get("fix_action") else None, cur["id"]))
        for key, cur in have.items():
            if key not in seen and cur["status"] == "open":
                con.execute("UPDATE trip_findings SET status='resolved', updated_at=? WHERE id=?", (ts, cur["id"]))
        rows = q.findings(con, trip_id)
        counts = {"blocker": 0, "warn": 0, "info": 0}
        for r in rows:
            counts[r["severity"]] = counts.get(r["severity"], 0) + 1
    return {"findings": rows, "counts": counts, "checked_at": ts}


def check_trip(store: Store, trip_id: str, app: str = "trips", today: date | None = None, now: datetime | None = None) -> dict:
    with store.read():
        con = store.con
        trip = q.trip_row(con, trip_id)
        if not trip:
            raise LookupError(trip_id)
        its, tks, cfs = q.items(con, trip_id), q.tasks(con, trip_id), q.confirmations(con, trip_id)
    return sync(store, trip_id, run(store, trip, its, tks, cfs, today=today, now=now), app)
