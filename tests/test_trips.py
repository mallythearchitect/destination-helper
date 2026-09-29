"""Trips, the Destination Helper: the capability list as a pack, a trip as a
record, the checker catching the Thailand mistakes, costs per person and
group in two currencies, the before-you-go list, confirmations, the calendar
file, the track record, and the plug."""
from datetime import UTC, date, datetime, timedelta

import pytest


def act(client, action_name, **payload):
    r = client.post(f"/v1/actions/{action_name}", json=payload)
    assert r.status_code == 200, (action_name, r.text)
    return r.json()


def new_trip(client, **kw):
    base = {"name": "Thailand, Nov 2026", "headcount": 2, "travelers": ["Malachi", "J"], "start_date": "2026-11-13", "end_date": "2026-11-28",
            "region_pack": "thailand", "local_currency": "THB", "fx_rate": 33.4, "fx_date": "2026-09-28", "passport_expiry": "2028-01-01",
            "purpose_note": "active days, nightlife, water sports", "budget_night_cents": 8000}
    base.update(kw)
    return act(client, "trips.create", **base)


def test_helper_pack_is_the_capability_list(client):
    assert [p["name"] for p in client.get("/v1/packs").json()] == ["destinations", "helper"]
    h = client.get("/v1/trips/helper").json()
    assert h["meta"]["version"] == "v7" and len(h["questions"]) == 93 and [s["code"] for s in h["sections"]][:3] == ["GO", "READY", "GET"]
    codes = [w["code"] for w in h["workflows"]]
    assert codes[0] == "W01" and codes[-1] == "W29" and len(codes) == 29
    w02 = next(w for w in h["workflows"] if w["code"] == "W02")
    assert w02["title"] == "Every way from A to B" and len(w02["steps"]) == 6 and "Proven" in w02["track_record"]
    w07 = next(w for w in h["workflows"] if w["code"] == "W07")
    assert w07["steps"] == ["fixed times", "usable hours", "keep only what fits", "flag anything that risks missing the ride"]
    assert [g["code"] for g in h["guardrails"]] == [f"G{n:02d}" for n in range(1, 13)] and h["guardrails"][0]["why"].startswith("Thailand 2026")
    assert {"setup", "defaults", "sources", "checks", "formats", "region_template", "run_order"} <= set(h["methods"])
    assert any(m["sub"] == "Before you go" and m["new"] for m in h["methods"]["checks"])
    assert [b["heading"] for b in h["brief"]][:2] == ["What it is", 'What keeps it from being "Wanderlog part 2"']
    th = client.get("/v1/trips/helper/regions/thailand").json()
    assert th["currency"] == "THB" and th["time_zone"] == "Asia/Bangkok" and "whatsapp" in th["channels"]
    assert "Airports and airlines" in th["sections"] and len(th["worked_examples"]) == 73 and any("{a}" in s["url"] for s in th["sites"])
    assert client.get("/v1/trips/helper/regions/mars").status_code == 404
    # the helper's sites are in the source registry like everything else
    names = {s["name"] for s in client.get("/v1/sources").json()}
    assert {"12Go", "travel.state.gov", "Direct Ferries"} <= names


def test_a_trip_is_a_record_and_setup_asks_first(client):
    t = act(client, "trips.create", name="Saturday hike")
    assert t["stage"] == "plan" and t["headcount"] == 1 and t["home_currency"] == "USD" and t["passport_country"] == "USA"
    assert "who's going and how many" not in t["setup_missing"] and "the dates" in t["setup_missing"] and "budget caps (per night, per leg, per day)" in t["setup_missing"]
    e = client.get(f"/v1/entities/{t['entity_id']}").json()
    assert e["type"] == "trip" and e["name"] == "Saturday hike"
    assert client.get("/v1/search?q=saturday").json()[0]["id"] == t["entity_id"]
    t2 = new_trip(client)
    assert t2["time_zone"] == "Asia/Bangkok" and t2["local_currency"] == "THB" and t2["setup_missing"] == []
    assert t2["handling"] == "check_my_plan" and t2["may_contact"] == 0
    u = act(client, "trips.update", id=t2["id"], expected_version=1, name="Thailand guys' trip", headcount=3, handling="plan_for_me", may_contact=True)
    assert u["version"] == 2 and u["headcount"] == 3 and u["handling"] == "plan_for_me" and u["may_contact"] == 1
    assert client.post("/v1/actions/trips.update", json={"id": t2["id"], "handling": "do_everything"}).status_code == 400 and client.get(f"/v1/entities/{t2['entity_id']}").json()["name"] == "Thailand guys' trip"
    assert client.post("/v1/actions/trips.update", json={"id": t2["id"], "expected_version": 1, "name": "x"}).status_code == 409
    assert client.post("/v1/actions/trips.create", json={"name": "bad", "start_date": "2026-11-28", "end_date": "2026-11-13"}).status_code == 400
    assert client.post("/v1/actions/trips.create", json={"name": "bad", "region_pack": "mars"}).status_code == 400
    assert act(client, "trips.set_stage", id=t2["id"], stage="prepare")["stage"] == "prepare"
    assert client.post("/v1/actions/trips.set_stage", json={"id": t2["id"], "stage": "flying"}).status_code == 400
    lst = client.get("/v1/trips").json()
    assert [x["name"] for x in lst] == ["Thailand guys' trip", "Saturday hike"]
    act(client, "trips.add_note", trip_id=t2["id"], body="Nomads: ask about the bag hold.")
    assert client.get("/v1/search?q=nomads").json()[0]["id"] == t2["entity_id"]
    act(client, "trips.delete", id=t2["id"])
    assert [x["name"] for x in client.get("/v1/trips").json()] == ["Saturday hike"] and client.get(f"/v1/trips/{t2['id']}").status_code == 404
    h = client.get("/v1/history?limit=1").json()[0]
    assert h["action"] == "entities.delete"


def test_the_checker_catches_the_thailand_taxi(client):
    t = new_trip(client)
    tid = t["id"]
    flight = act(client, "trips.add_item", trip_id=tid, kind="flight", title="Nok Air DD 130 DMK → KBV", from_place="Don Mueang (DMK)", to_place="Krabi Airport",
                 start_at="2026-11-17T17:20", end_at="2026-11-17T18:45", status="booked", price_cents=10593, currency="USD", basis="group", confirmation="ABC123")
    taxi = act(client, "trips.add_item", trip_id=tid, kind="taxi", title="Airport taxi to Ao Nang", from_place="Krabi Airport", to_place="Nomads Ao Nang",
               start_at="2026-11-17T12:00", status="booked", price_cents=120000, currency="THB")
    r = act(client, "trips.run_checks", trip_id=tid)
    by = {f["rule"]: f for f in r["findings"]}
    assert client.get(f"/v1/trips/{tid}").json()["health"] == 100 - 25 - 8 * r["counts"]["warn"] - 2 * r["counts"]["info"]
    assert client.get("/v1/trips").json()[0]["health"] < 100
    assert r["counts"]["blocker"] == 1 and "12:00 PM" in by["pickup-before-arrival"]["message"] and "6:45 PM" in by["pickup-before-arrival"]["message"]
    assert "7:15 PM" in by["pickup-before-arrival"]["fix"] and by["pickup-before-arrival"]["item_id"] == taxi["id"]
    assert by["price-basis"]["item_id"] == taxi["id"] and by["night-without-stay"]["message"].startswith("No place to sleep from Nov 13 to Nov 27")
    assert "passport" not in " ".join(by)
    # fix the taxi: the blocker resolves, the basis warning goes, the row is kept as resolved
    act(client, "trips.update_item", id=taxi["id"], start_at="2026-11-17T19:15", basis="group")
    r = act(client, "trips.run_checks", trip_id=tid)
    assert r["counts"]["blocker"] == 0 and "price-basis" not in {f["rule"] for f in r["findings"]}
    allf = client.get(f"/v1/trips/{tid}/findings?all=true").json()
    assert {f["status"] for f in allf if f["rule"] in ("pickup-before-arrival", "price-basis")} == {"resolved"}
    # dismiss stays dismissed on the next run; reopen brings it back
    ns = next(f for f in r["findings"] if f["rule"] == "night-without-stay")
    act(client, "trips.dismiss_finding", id=ns["id"])
    assert "night-without-stay" not in {f["rule"] for f in act(client, "trips.run_checks", trip_id=tid)["findings"]}
    act(client, "trips.dismiss_finding", id=ns["id"], undo=True)
    assert "night-without-stay" in {f["rule"] for f in act(client, "trips.run_checks", trip_id=tid)["findings"]}
    # the plan: the flight's leave-by, live links, group and per-person prices, the night map
    p = client.get(f"/v1/trips/{tid}").json()
    f = next(i for i in p["items"] if i["id"] == flight["id"])
    assert f["leave"]["be_there_by"] == "2026-11-17T15:20" and f["leave"]["buffer_minutes"] == 120
    assert {k["key"] for k in f["links"]} >= {"directions", "flights", "all_modes", "ground", "status"} and "12go.asia" in next(k["url"] for k in f["links"] if k["key"] == "ground")
    assert "people=2" in next(k["url"] for k in f["links"] if k["key"] == "ground") and f["per_person_cents"] == 5297 and f["home_cents"] == 10593
    tx = next(i for i in p["items"] if i["id"] == taxi["id"])
    assert tx["home_cents"] == round(120000 / 33.4) and tx["group_cents"] == 120000
    assert len(p["days"]) == 16 and p["days"][4]["date"] == "2026-11-17" and set(p["days"][4]["items"]) == {flight["id"], taxi["id"]} and p["days"][4]["night"] is None
    # thresholds come from Settings → Logic
    client.put("/v1/settings/logic.trips.checks", json={"value": {**p["rules"], "airport_buffer_minutes": {"domestic": 60, "international": 180}}})
    assert client.get(f"/v1/trips/{tid}").json()["items"][0]["leave"]["be_there_by"] == "2026-11-17T16:20"
    assert client.put("/v1/settings/logic.trips.checks", json={"value": {"min_connection_minutes": 5}}).status_code == 400


def test_stays_connections_last_ferry_and_budget(client):
    t = new_trip(client, budget_night_cents=5000, budget_leg_cents=15000)
    tid = t["id"]
    act(client, "trips.add_item", trip_id=tid, kind="stay", title="Charlie House", from_place="Bangkok", start_at="2026-11-13", end_at="2026-11-17", status="booked", price_cents=560000, currency="THB", basis="group")
    nomads = act(client, "trips.add_item", trip_id=tid, kind="stay", title="Nomads Ao Nang", from_place="Ao Nang", start_at="2026-11-17", end_at="2026-11-20", status="booked", price_cents=6000, currency="USD", basis="per_person")
    act(client, "trips.add_item", trip_id=tid, kind="stay", title="Mazi Design Hotel", from_place="Patong", start_at="2026-11-20", end_at="2026-11-22", status="booked", price_cents=30000, currency="USD", basis="group")
    # Nov 20: a full-day tour ending 17:00, then the last boat to Phuket at 15:30 with the leg itself at 16:00
    act(client, "trips.add_item", trip_id=tid, kind="activity", title="4 Islands tour", from_place="Ao Nang", start_at="2026-11-20T08:30", end_at="2026-11-20T17:00", status="to_book", price_cents=120000, currency="THB", basis="per_person")
    boat = act(client, "trips.add_item", trip_id=tid, kind="ferry", title="Speedboat Ao Nang → Rassada Pier", from_place="Nopparat Thara pier, Ao Nang", to_place="Rassada Pier, Phuket",
               start_at="2026-11-20T16:00", end_at="2026-11-20T18:00", status="to_book", price_cents=90000, currency="THB", basis="per_person", last_departure="15:30")
    act(client, "trips.add_item", trip_id=tid, kind="taxi", title="Grab to Patong", from_place="Rassada Pier", to_place="Mazi Design Hotel", start_at="2026-11-20T18:10", status="idea", price_cents=45000, currency="THB", basis="group")
    r = act(client, "trips.run_checks", trip_id=tid)
    rules = {f["rule"]: f for f in r["findings"]}
    assert "after-last-departure" in rules and rules["after-last-departure"]["severity"] == "blocker" and rules["after-last-departure"]["item_id"] == boat["id"]
    assert "overlap" in rules and "4 Islands tour" in rules["overlap"]["message"]
    assert rules["night-without-stay"]["message"].startswith("No place to sleep from Nov 22 to Nov 27 (6 nights)")
    assert "over-budget-night" in rules and "Mazi" in rules["over-budget-night"]["message"]       # 300 / 2 nights = 150 > 50 cap
    assert "over-budget-leg" not in rules                                                             # 900 THB × 2 = 1800 THB ≈ $54, under the $150 cap
    # per person: Nomads 60 × 2 = 120 for 3 nights = 40 a night, under the cap
    assert not any(f["item_id"] == nomads["id"] for f in r["findings"] if f["rule"] == "over-budget-night")
    p = client.get(f"/v1/trips/{tid}").json()
    assert p["days"][0]["night"]["title"] == "Charlie House" and p["days"][4]["night"]["title"] == "Nomads Ao Nang" and p["days"][9]["night"] is None
    # move the boat to 13:30 → the last-departure blocker and the overlap resolve; a tight connection with the taxi appears if under 90 min
    act(client, "trips.update_item", id=boat["id"], start_at="2026-11-20T13:30", end_at="2026-11-20T15:30")
    r = act(client, "trips.run_checks", trip_id=tid)
    rules = {f["rule"] for f in r["findings"]}
    assert "after-last-departure" not in rules and "overlap" in rules   # the tour still overlaps
    # the morning tour that fits before an afternoon transfer (W07)
    tour = next(i for i in client.get(f"/v1/trips/{tid}").json()["items"] if i["title"] == "4 Islands tour")
    act(client, "trips.update_item", id=tour["id"], end_at="2026-11-20T12:30")
    assert "overlap" not in {f["rule"] for f in act(client, "trips.run_checks", trip_id=tid)["findings"]}


def test_over_budget_leg_uses_home_currency(client):
    t = new_trip(client, budget_leg_cents=4000)
    boat = act(client, "trips.add_item", trip_id=t["id"], kind="ferry", title="Boat", start_at="2026-11-20T13:30", end_at="2026-11-20T15:30", status="to_book", price_cents=90000, currency="THB", basis="per_person")
    r = act(client, "trips.run_checks", trip_id=t["id"])
    f = next(f for f in r["findings"] if f["rule"] == "over-budget-leg")
    assert f["item_id"] == boat["id"] and "54 USD" in f["message"]                     # 1800 THB / 33.4 = 53.89


def test_costs_per_person_group_currency_and_who_pays(client):
    t = new_trip(client, purpose="mixed")
    tid = t["id"]
    act(client, "trips.add_item", trip_id=tid, kind="flight", title="JFK → BKK", start_at="2026-11-12T01:00", end_at="2026-11-13T06:00", status="booked", price_cents=90000, currency="USD", basis="per_person", tag="work", paid_by="company", international=True)
    act(client, "trips.add_item", trip_id=tid, kind="stay", title="Charlie House", start_at="2026-11-13", end_at="2026-11-17", status="booked", price_cents=560000, currency="THB", basis="group", tag="work", paid_by="split")
    act(client, "trips.add_item", trip_id=tid, kind="activity", title="Jet ski", start_at="2026-11-21T10:00", status="to_book", price_cents=250000, currency="THB", basis="per_person")
    act(client, "trips.add_item", trip_id=tid, kind="activity", title="Maybe a hike", status="idea", price_cents=100, currency="USD", basis="group")
    act(client, "trips.add_item", trip_id=tid, kind="meal", title="Dinner in euros", status="booked", price_cents=5000, currency="EUR", basis="group")
    c = client.get(f"/v1/trips/{tid}/costs").json()
    flights, stay, jet = 180000, round(560000 / 33.4), round(500000 / 33.4)
    assert c["planned_home_cents"] == flights + stay + jet and c["booked_home_cents"] == flights + stay and c["to_book_home_cents"] == jet
    assert c["per_person_home_cents"] == round((flights + stay + jet) / 2)
    assert c["by_paid_by"]["company"] == flights and c["by_paid_by"]["split"] == stay and c["by_paid_by"]["me"] == jet
    assert c["company_pays_home_cents"] == flights + round(stay / 2) and c["i_pay_home_cents"] == jet + round(stay / 2)
    assert c["by_tag"]["work"] == flights + stay and c["by_tag"]["personal"] == jet
    assert [x["title"] for x in c["unconverted"]] == ["Dinner in euros"] and "33.4" in c["card_rate_note"]
    e = act(client, "trips.log_expense", trip_id=tid, amount_cents=1000, currency="THB", basis="per_person", tag="personal", paid_by="me", note="pad thai")
    assert e["on_date"] == date.today().isoformat()
    c = client.get(f"/v1/trips/{tid}/costs").json()
    assert c["actual_home_cents"] == round(2000 / 33.4) and c["actual_by_tag"]["personal"] == c["actual_home_cents"]
    act(client, "trips.delete_expense", id=e["id"])
    assert client.get(f"/v1/trips/{tid}/costs").json()["actual_home_cents"] == 0
    # no rate: nothing converts and the checker says so
    t2 = act(client, "trips.create", name="No rate", headcount=2, local_currency="THB", start_date="2026-11-13", end_date="2026-11-14")
    act(client, "trips.add_item", trip_id=t2["id"], kind="taxi", title="x", status="booked", price_cents=100, currency="THB", basis="group")
    assert "fx-missing" in {f["rule"] for f in act(client, "trips.run_checks", trip_id=t2["id"])["findings"]}
    assert client.get(f"/v1/trips/{t2['id']}/costs").json()["planned_home_cents"] == 0


def test_before_you_go_deadlines_and_the_calendar_file(client):
    t = new_trip(client)
    tid = t["id"]
    r = act(client, "trips.before_you_go", trip_id=tid)
    titles = [x["title"] for x in r["created"]]
    assert r["count"] == 9 and titles[0].startswith("Entry rules") and any("arrival card" in x.lower() for x in titles) and any("Visa-free" in x for x in titles)
    entry = next(x for x in r["created"] if x["kind"] == "entry" and x["title"].startswith("Entry"))
    assert entry["due"] == "2026-10-14"                                                              # 30 days before Nov 13
    tdac = next(x for x in r["created"] if "arrival card" in x["title"].lower())
    assert tdac["due"] == "2026-11-10"                                                               # 3 days before
    assert act(client, "trips.before_you_go", trip_id=tid)["count"] == 0                             # idempotent
    # deadlines: overdue blocks, soon warns; done clears
    old = act(client, "trips.add_task", trip_id=tid, title="Renew AAA membership", due=(date.today() - timedelta(days=1)).isoformat())
    soon = act(client, "trips.add_task", trip_id=tid, title="Set up Grab and Bolt", due=(date.today() + timedelta(days=2)).isoformat())
    rules = {f["rule"]: f for f in act(client, "trips.run_checks", trip_id=tid)["findings"]}
    assert "AAA" in rules["deadline-overdue"]["message"] and rules["deadline-overdue"]["severity"] == "blocker" and "Grab" in rules["deadline-soon"]["message"]
    act(client, "trips.complete_task", id=old["id"])
    act(client, "trips.complete_task", id=soon["id"], due=(date.today() + timedelta(days=30)).isoformat())
    msgs = " ".join(f["message"] for f in act(client, "trips.run_checks", trip_id=tid)["findings"] if f["rule"].startswith("deadline"))
    assert "AAA" not in msgs and "Grab" not in msgs and "Health rules" in msgs                       # the W25 health task really is due tomorrow
    # passport: 6 months past the trip
    act(client, "trips.update", id=tid, passport_expiry="2027-01-15")
    f = next(f for f in act(client, "trips.run_checks", trip_id=tid)["findings"] if f["rule"] == "passport-validity")
    assert f["severity"] == "blocker" and "May 28" in f["message"]
    # the calendar file
    act(client, "trips.add_item", trip_id=tid, kind="flight", title="Nok Air DD 130", from_place="DMK", to_place="KBV", start_at="2026-11-17T17:20", end_at="2026-11-17T18:45", status="booked", confirmation="ABC123", link="https://www.nokair.com/")
    act(client, "trips.add_item", trip_id=tid, kind="stay", title="Nomads, Ao Nang", start_at="2026-11-17", end_at="2026-11-20", status="booked", notes="ask about bags; high floor, please")
    ics = client.get(f"/v1/trips/{tid}/calendar.ics")
    assert ics.status_code == 200 and ics.headers["content-type"].startswith("text/calendar")
    body = ics.text
    assert "DTSTART;TZID=Asia/Bangkok:20261117T172000" in body and "DTEND;TZID=Asia/Bangkok:20261117T184500" in body and "SUMMARY:Flight: Nok Air DD 130" in body
    assert "DTSTART;VALUE=DATE:20261117" in body and "DTEND;VALUE=DATE:20261120" in body and "SUMMARY:Stay: Nomads\\, Ao Nang" in body
    assert "Confirmation ABC123" in body and "URL:https://www.nokair.com/" in body and "TRIGGER:-PT120M" in body and "ask about bags\\; high floor" in body
    assert "SUMMARY:Deadline: Set up Grab and Bolt" in body and body.count("BEGIN:VEVENT") == 2 + 1 + 9   # items + the one open task with a date... plus the W25 tasks
    assert client.get("/v1/trips/nope/calendar.ics").status_code == 404


def test_confirmations_message_first_then_call(client):
    t = new_trip(client)
    tid = t["id"]
    nomads = act(client, "trips.add_item", trip_id=tid, kind="stay", title="Nomads Ao Nang", operator="Nomads Hostel", start_at="2026-11-17", end_at="2026-11-20", status="booked",
                 confirmation="NM-778", contact={"whatsapp": "+66 81 234 5678", "phone": "+66 75 000 000"})
    c = act(client, "trips.draft_confirmation", trip_id=tid, item_id=nomads["id"], question="Can you hold our bags from checkout at 11 AM until about 3 PM on Nov 20?")
    assert c["channel"] == "whatsapp" and c["to_address"] == "+66 81 234 5678" and c["status"] == "draft"
    assert c["message"].startswith("Hi Nomads Hostel, this is Malachi.") and "NM-778" in c["message"] and "for 2 on Nov 17" in c["message"] and c["message"].endswith("Thank you!")
    assert c["send_link"].startswith("https://wa.me/66812345678?text=Hi%20Nomads")
    # a place with only a phone, in a region that prefers messaging, gets a text first
    ch = act(client, "trips.add_item", trip_id=tid, kind="stay", title="Charlie House", start_at="2026-11-13", end_at="2026-11-17", status="booked", contact={"phone": "+66 2 000 0000"})
    c2 = act(client, "trips.draft_confirmation", trip_id=tid, item_id=ch["id"], question="Do you hold bags after checkout?")
    assert c2["channel"] == "sms" and c2["send_link"].startswith("sms:+66 2 000 0000&body=")
    # sent → no reply after the set hours → the checker says call; the call says it's automated
    act(client, "trips.update_confirmation", id=c["id"], status="sent", sent_at=(datetime.now(UTC) - timedelta(hours=30)).isoformat())
    r = act(client, "trips.run_checks", trip_id=tid)
    f = next(f for f in r["findings"] if f["rule"] == "confirmation-no-reply")
    assert "24h" in f["message"] and "call" in f["fix"] and f["item_id"] == nomads["id"]
    c = act(client, "trips.update_confirmation", id=c["id"], status="no_reply")
    assert c["status"] == "call" and c["channel"] == "call"
    call = act(client, "trips.draft_confirmation", trip_id=tid, item_id=nomads["id"], question="Can you hold our bags on Nov 20?", channel="call")
    assert call["status"] == "call" and call["message"].startswith("Hello, this is an automated assistant calling on behalf of Malachi")
    assert {f["rule"] for f in act(client, "trips.run_checks", trip_id=tid)["findings"]} >= {"confirmation-call"}
    # an answer that changes the plan flags the booking
    c = act(client, "trips.update_confirmation", id=call["id"], status="answered", reply="Only until 1 PM, sorry.", changed=True)
    assert c["reply"] == "Only until 1 PM, sorry." and c["replied_at"]
    it = next(i for i in client.get(f"/v1/trips/{tid}").json()["items"] if i["id"] == nomads["id"])
    assert it["status"] == "check_now"
    c2 = act(client, "trips.update_confirmation", id=c2["id"], status="answered", reply="Yes, free of charge.")
    assert next(i for i in client.get(f"/v1/trips/{tid}").json()["items"] if i["id"] == ch["id"])["status"] == "confirmed"
    # the template is a logic setting
    client.put("/v1/settings/logic.trips.confirmation", json={"value": {"message": "Yo {operator}: {question}", "reply_hours": 2, "channels_order": ["email", "whatsapp", "sms", "call"], "call_opening": "AI here. {question}"}})
    c3 = act(client, "trips.draft_confirmation", trip_id=tid, item_id=nomads["id"], question="Late check-in ok?")
    assert c3["message"] == "Yo Nomads Hostel: Late check-in ok?" and c3["channel"] == "whatsapp"


def test_track_record_history_and_the_plug(client):
    t = new_trip(client)
    r = act(client, "trips.log_workflow", trip_id=t["id"], code="w02", outcome="proven", note="Krabi → Phuket: boat + Grab")
    assert r["code"] == "W02"
    assert client.post("/v1/actions/trips.log_workflow", json={"trip_id": t["id"], "code": "W99", "outcome": "proven"}).status_code == 400
    p = client.get(f"/v1/trips/{t['id']}").json()
    assert p["workflow_runs"][0]["outcome"] == "proven" and p["region"]["name"] == "Thailand" and p["costs"]["headcount"] == 2
    # undo works on trip tables like everything else
    it = act(client, "trips.add_item", trip_id=t["id"], kind="bus", title="Night bus", status="idea")
    act(client, "trips.update_item", id=it["id"], title="Day bus")
    h = client.get("/v1/history?limit=1").json()[0]
    assert h["action"] == "trips.update_item" and h["before"]["title"] == "Night bus"
    client.post(f"/v1/history/{h['id']}/undo")
    assert next(i for i in client.get(f"/v1/trips/{t['id']}").json()["items"] if i["id"] == it["id"])["title"] == "Night bus"
    acts = {a["name"]: a for a in client.get("/v1/actions").json()}
    assert {"trips.create", "trips.add_item", "trips.run_checks", "trips.draft_confirmation", "trips.before_you_go"} <= set(acts)
    assert acts["trips.delete"]["dangerous"] and not acts["trips.run_checks"]["dangerous"]
    opts = client.get("/v1/trips/options").json()
    assert opts["kind_list"][0] == "flight" and "stay" in opts["kind_list"] and opts["regions"][0]["id"] == "thailand" and opts["channels"][0] == "whatsapp"


@pytest.mark.anyio
async def test_mcp_offers_trips_and_the_helper(env, store):
    import json

    from engine.ai.mcp_server import build
    server = build(store)
    tools = {t.name: t for t in await server.list_tools()}
    assert {"trips_create", "trips_add_item", "trips_run_checks", "trips_list", "trip_plan", "trip_checks", "trip_costs", "helper_workflow", "helper_catalogue", "helper_region", "destinations_set_status"} <= set(tools)
    assert tools["trips_delete_item"].description.startswith("DANGEROUS")

    def text(res):
        return res[0].text if isinstance(res, list) else res.content[0].text
    w = json.loads(text(await server.call_tool("helper_workflow", {"code": "w24"})))
    assert w["title"] == "Start a new trip" and len(w["steps"]) == 5
    cat = json.loads(text(await server.call_tool("helper_catalogue", {"section": "GET"})))
    assert len(cat) == 19 and cat[0]["code"] == "GET-01"
    t = json.loads(text(await server.call_tool("trips_create", {"input": {"name": "Plug trip", "headcount": 2, "start_date": "2026-12-01", "end_date": "2026-12-03"}})))
    assert t["setup_missing"] and json.loads(text(await server.call_tool("trips_list", {})))[0]["name"] == "Plug trip"
    r = json.loads(text(await server.call_tool("trip_checks", {"trip_id": t["id"]})))
    assert r["counts"]["warn"] >= 1 and any(f["rule"] == "night-without-stay" for f in r["findings"])
    th = json.loads(text(await server.call_tool("helper_region", {"region_id": "thailand"})))
    assert "Money" in th["sections"]
