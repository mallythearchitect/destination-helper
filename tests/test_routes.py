"""Ways to do a leg (W02): the route-optimizer rule (minutes = distance ÷ speed × 60,
skip a zero or negative distance or speed, the fastest wins), grown into the trip's
sequence with prices, door-to-door time, choosing, and the checker."""


def act(client, action_name, **payload):
    r = client.post(f"/v1/actions/{action_name}", json=payload)
    assert r.status_code == 200, (action_name, r.text)
    return r.json()


def trip(client, **kw):
    base = {"name": "Thailand", "headcount": 2, "start_date": "2026-11-13", "end_date": "2026-11-28", "region_pack": "thailand", "fx_rate": 33.4, "budget_leg_cents": 6000}
    base.update(kw)
    return act(client, "trips.create", **base)


def ways(client, tid):
    return client.get(f"/v1/trips/{tid}/ways").json()


def test_the_route_rule(client):
    t = trip(client)
    leg = dict(trip_id=t["id"], from_place="Ao Nang", to_place="Phuket", day="2026-11-20")
    act(client, "trips.add_option", **leg, mode="drive", label="Car A", distance_miles=100, speed_mph=40)
    act(client, "trips.add_option", **leg, mode="drive", label="Car B", distance_miles=90, speed_mph=60)
    act(client, "trips.add_option", **leg, mode="drive", label="Zero distance", distance_miles=0, speed_mph=40)
    act(client, "trips.add_option", **leg, mode="drive", label="Negative speed", distance_miles=50, speed_mph=-5)
    g = ways(client, t["id"])[0]
    by = {o["label"]: o for o in g["options"]}
    assert by["Car A"]["ride_minutes"] == 150 and by["Car B"]["ride_minutes"] == 90          # 100/40*60, 90/60*60
    assert by["Car A"]["minutes_source"] == "distance ÷ speed × 60"
    assert by["Zero distance"]["skip"] == "The distance is invalid, so this option is skipped."
    assert by["Negative speed"]["skip"] == "The speed is invalid, so this option is skipped."
    assert by["Car B"]["id"] == g["fastest_id"] and g["valid"] == 2 and len(g["skipped"]) == 2
    assert [o["label"] for o in g["options"]] == ["Car B", "Car A", "Zero distance", "Negative speed"]   # skipped ones last
    # a time you know beats the arithmetic; a zero time is skipped too
    act(client, "trips.add_option", **leg, mode="ferry", label="Ferry", minutes=50, distance_miles=500, speed_mph=1)
    act(client, "trips.add_option", **leg, mode="ferry", label="Zero time", minutes=0)
    g = ways(client, t["id"])[0]
    by = {o["label"]: o for o in g["options"]}
    assert by["Ferry"]["ride_minutes"] == 50 and by["Ferry"]["minutes_source"] == "you" and by["Ferry"]["door_minutes"] == 80   # + 30 min at the pier
    assert by["Zero time"]["skip"].startswith("The time is invalid")
    assert g["fastest_id"] == by["Ferry"]["id"]


def test_defaults_estimates_prices_and_flags(client):
    t = trip(client)
    leg = dict(trip_id=t["id"], from_place="Rassada Pier, Phuket Town", to_place="Krabi Airport", day="2026-11-20")
    v = act(client, "trips.add_option", **leg, mode="van", label="Minivan", price_cents=35000, currency="THB", basis="per_person")
    f = act(client, "trips.add_option", **leg, mode="ferry", label="Afternoon ferry", minutes=135, depart_at="2026-11-20T16:00", last_departure="15:30", price_cents=90000, currency="THB", basis="per_person")
    c = act(client, "trips.add_option", **leg, mode="drive", label="Private car", minutes=150, price_cents=280000, currency="THB", basis="group")
    g = ways(client, t["id"])[0]
    by = {o["id"]: o for o in g["options"]}
    van = by[v["id"]]
    assert van["speed_used"] == 45 and van["speed_source"] == "usual van speed"
    assert "Phuket → Krabi" in van["distance_source"] and "× 1.3" in van["distance_source"] and 40 < van["distance_used"] < 70
    assert van["ride_minutes"] == round(van["distance_used"] / 45 * 60) and van["door_minutes"] == van["ride_minutes"] + 10
    assert van["group_cents"] == 70000 and van["per_person_cents"] == 35000 and van["home_cents"] == round(70000 / 33.4)
    ferry = by[f["id"]]
    assert ferry["arrive_at"] == "2026-11-20T18:15" and ferry["flags"] == ["leaves after the last one of the day (15:30)"]
    car = by[c["id"]]
    assert car["home_cents"] == round(280000 / 33.4) and "over the per-leg budget" in car["flags"]      # $83.83 > $60
    assert g["cheapest_id"] == v["id"] and g["best_id"] == v["id"]
    # ranking follows the Logic setting; balanced weighs time and money
    assert g["orders"]["cheapest"][0] == v["id"] and g["rank_by"] == "fastest"
    rules = client.get("/v1/settings/logic.trips.route_options").json()["value"]
    client.put("/v1/settings/logic.trips.route_options", json={"value": {**rules, "speed_mph": {**rules["speed_mph"], "van": 15}, "rank_by": "cheapest"}})
    g = ways(client, t["id"])[0]
    assert g["rank_by"] == "cheapest" and g["options"][0]["id"] == v["id"] and {o["id"]: o for o in g["options"]}[v["id"]]["speed_used"] == 15
    assert client.put("/v1/settings/logic.trips.route_options", json={"value": {**rules, "rank_by": "prettiest"}}).status_code == 400
    assert client.put("/v1/settings/logic.trips.route_options", json={"value": {**rules, "speed_mph": {"van": 0}}}).status_code == 400


def test_choosing_writes_the_leg_and_the_checker_follows(client):
    t = trip(client, budget_leg_cents=None)
    leg = dict(trip_id=t["id"], from_place="Ao Nang", to_place="Phuket", day="2026-11-20")
    slow = act(client, "trips.add_option", **leg, mode="drive", label="Long way round", minutes=240, depart_at="2026-11-20T13:00", price_cents=200000, currency="THB", basis="group")
    quick = act(client, "trips.add_option", **leg, mode="ferry", label="Ferry via Ko Yao", minutes=135, depart_at="2026-11-20T14:00", price_cents=90000, currency="THB", basis="per_person")
    r = act(client, "trips.run_checks", trip_id=t["id"])
    und = next(f for f in r["findings"] if f["rule"] == "undecided-leg")
    assert "Ao Nang to Phuket on Nov 20: 2 ways" in und["message"] and und["fix_action"] == {"label": "Use Ferry via Ko Yao", "action": "trips.choose_option", "payload": {"id": quick["id"]}}
    # choose the slow one: it becomes the leg; the checker says a faster way exists
    c = act(client, "trips.choose_option", id=slow["id"])
    it = c["item"]
    assert it["kind"] == "drive" and it["title"] == "Long way round" and it["start_at"] == "2026-11-20T13:00" and it["end_at"] == "2026-11-20T17:00" and it["status"] == "to_book"
    assert it["price_cents"] == 200000 and it["basis"] == "group"
    g = ways(client, t["id"])[0]
    assert g["item_id"] == it["id"] and g["chosen_id"] == slow["id"] and len(g["options"]) == 2
    r = act(client, "trips.run_checks", trip_id=t["id"])
    assert "undecided-leg" not in {f["rule"] for f in r["findings"]}
    fast = next(f for f in r["findings"] if f["rule"] == "faster-option")
    assert "about 1 h 15 sooner" in fast["message"] and fast["item_id"] == it["id"] and fast["fix_action"]["payload"] == {"id": quick["id"]}
    # the one-tap fix switches the leg; the finding resolves
    act(client, "trips.choose_option", id=quick["id"])
    plan = client.get(f"/v1/trips/{t['id']}").json()
    leg_item = next(i for i in plan["items"] if i["id"] == it["id"])
    assert leg_item["kind"] == "ferry" and leg_item["title"] == "Ferry via Ko Yao" and leg_item["end_at"] == "2026-11-20T16:15" and leg_item["basis"] == "per_person"
    assert leg_item["ways"]["count"] == 2 and leg_item["ways"]["chosen_id"] == quick["id"] and leg_item["ways"]["fastest_id"] == quick["id"]
    assert "faster-option" not in {f["rule"] for f in act(client, "trips.run_checks", trip_id=t["id"])["findings"]}
    # options on a leg already in the plan inherit its places; the cap holds; undo works
    for n in range(8):
        act(client, "trips.add_option", trip_id=t["id"], item_id=it["id"], mode="bus", label=f"Bus {n}", minutes=300 + n)
    assert ways(client, t["id"])[0]["options"][-1]["from_place"] == "Ao Nang"
    assert client.post("/v1/actions/trips.add_option", json={"trip_id": t["id"], "item_id": it["id"], "mode": "bus", "minutes": 1}).status_code == 400
    assert client.post("/v1/actions/trips.add_option", json={"trip_id": t["id"], "mode": "rocket", "from_place": "a", "to_place": "b"}).status_code == 400
    assert client.post("/v1/actions/trips.add_option", json={"trip_id": t["id"], "mode": "bus", "minutes": 5}).status_code == 400   # no leg, no places
    h = client.get("/v1/history?limit=1").json()[0]
    assert h["action"] == "trips.add_option"
    client.post(f"/v1/history/{h['id']}/undo")
    assert len(ways(client, t["id"])[0]["options"]) == 9
    u = act(client, "trips.update_option", id=slow["id"], minutes=60)
    assert u["minutes"] == 60 and ways(client, t["id"])[0]["fastest_id"] == slow["id"]
    act(client, "trips.delete_option", id=slow["id"])
    assert slow["id"] not in {o["id"] for o in ways(client, t["id"])[0]["options"]}
    # the helper's briefing carries the comparison
    assert "Ways to do Ao Nang → Phuket on 2026-11-20 (in the plan)" in client.get(f"/v1/trips/briefing/{t['id']}").json()["text"]
