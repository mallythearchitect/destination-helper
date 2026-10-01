"""Phase 4: the reference pack with sources, the person's list on top, the source checker."""


def act(client, action_name, **payload):
    r = client.post(f"/v1/actions/{action_name}", json=payload)
    assert r.status_code == 200, (action_name, r.text)
    return r.json()


def test_pack_is_attached_and_described(client):
    packs = client.get("/v1/packs").json()
    assert "destinations" in [p["name"] for p in packs]
    rows = next(p for p in packs if p["name"] == "destinations")["rows"]
    assert rows["places"] > 30000 and rows["indexes"] == 7 and rows["datasets"] == 7 and rows["scores"] > 300


def test_places_have_scores_distance_and_sources(client):
    ps = client.get("/v1/destinations/places?kind=us_city&sort=name").json()
    assert len(ps) == 30 and ps[0]["name"] == "Atlanta" or ps[0]["name"] <= ps[1]["name"]
    boston = next(p for p in ps if p["name"] == "Boston")
    assert boston["lat"] and boston["distance_miles"] and 80 < boston["distance_miles"] < 110      # from Hartford
    assert boston["scores"]["tech"] == 85 and boston["fit"] is not None and boston["kind_label"] == "US business city"
    detail = client.get(f"/v1/destinations/places/{boston['id']}").json()
    assert detail["dataset"]["confidence"] == "hand-set" and all(s["confidence"] == "hand-set" for s in detail["scores"] if s["domain"] in ("career", "tech", "network", "lifestyle", "entrepreneurship"))
    assert detail["goal_fits"]["tech"] and detail["home"]["name"] == "Hartford, CT"
    ways = {w["key"]: w for w in detail["ways_there"]}
    assert {"directions", "flights", "all_modes", "train"} <= set(ways) and "Hartford" in ways["directions"]["url"] and "Boston" in ways["flights"]["url"]
    assert all(w["live"] for w in detail["ways_there"])
    assert "train" not in {w["key"] for w in client.get("/v1/destinations/places/intl-toronto-ca").json()["ways_there"]}
    toronto = client.get("/v1/destinations/places/intl-toronto-ca").json()
    assert any(s["confidence"] == "index-derived" and s["from_indexes"] for s in toronto["scores"])
    assert any(iv["index_id"] == "gci" and iv["urls"] for iv in toronto["index_values"])
    leisure = client.get("/v1/destinations/places?kind=leisure&max_cost=45&sort=cost").json()
    assert leisure and all(p["cost_per_day"] <= 45 for p in leisure) and leisure[0]["hub"]
    assert {"Thailand", "Bangkok"} <= {p["name"] for p in client.get("/v1/destinations/places?q=bangkok").json()}   # the leisure hub and the city itself
    assert client.get("/v1/destinations/places/nope").status_code == 404


def test_home_city_moves_distances(client):
    before = client.get("/v1/destinations/places/us-boston-ma").json()["distance_miles"]
    client.put("/v1/settings/profile.home_city", json={"value": {"name": "New York, NY", "lat": 40.7128, "lon": -74.006}})
    after = client.get("/v1/destinations/places/us-boston-ma").json()["distance_miles"]
    assert after > before and 180 < after < 220


def test_your_list_lives_in_the_vault_as_records(client):
    r = act(client, "destinations.set_status", place_id="us-boston-ma", status="shortlist")
    assert r["type"] == "place" and r["external_ids"]["pack_place"] == "us-boston-ma" and r["data"]["status"] == "shortlist"
    act(client, "destinations.add_note", place_id="us-boston-ma", body="Amtrak from Hartford, 2h.")
    saved = client.get("/v1/destinations/places?saved=true").json()
    assert [p["name"] for p in saved] == ["Boston"] and saved[0]["status"] == "shortlist" and saved[0]["notes"] == 1
    assert client.get("/v1/search?q=amtrak").json()[0]["name"] == "Boston, MA"
    act(client, "destinations.set_status", place_id="us-boston-ma", status=None)
    assert client.get("/v1/destinations/places/us-boston-ma").json()["status"] is None
    assert client.post("/v1/actions/destinations.set_status", json={"place_id": "us-boston-ma", "status": "maybe"}).status_code == 400
    h = client.get("/v1/history?limit=1").json()[0]
    client.post(f"/v1/history/{h['id']}/undo")
    assert client.get("/v1/destinations/places/us-boston-ma").json()["status"] == "shortlist"


def test_trip_cost_shows_its_working(client):
    t = client.get("/v1/destinations/trip-cost?place_id=leisure-thailand&days=10&people=2").json()
    assert t["daily_total"] == 45 * 10 * 2 and t["flight_each"] >= 120 and t["total"] == t["daily_total"] + t["flights_total"]
    t2 = client.get("/v1/destinations/trip-cost?place_id=leisure-thailand&days=10&people=2&flight_each=900").json()
    assert t2["flights_total"] == 1800 and t2["assumption"] is None
    assert [ln["part"] for ln in t2["lines"]] == ["lodging", "food", "transport", "other"] and t2["lines"][0]["per_day"] == 20.25
    t3 = client.get("/v1/destinations/trip-cost?place_id=leisure-thailand&days=10&people=2&flight_each=900&housing=false").json()
    assert t3["housing"] is False and t3["per_day_used"] == 24.75 and t3["daily_total"] == 495.0 and len(t3["lines"]) == 3


def test_the_whole_world_is_on_the_map(client):
    big = client.get("/v1/destinations/places?kind=world_city&min_pop=5000000&sort=population").json()
    assert len(big) > 20 and big[0]["population"] > 10_000_000 and big[0]["kind_label"] == "World city" and big[0]["country"]
    assert client.get("/v1/destinations/places?q=reykjav").json()[0]["country"] == "Iceland"
    opts = client.get("/v1/destinations/options").json()
    assert {k["id"]: k["count"] for k in opts["kinds"]}["world_city"] > 30000 and len(opts["goals"]) == 8
    assert [d["id"] for d in opts["domains"]][-3:] == ["safety", "affordability", "quality_of_life"]
    toronto = client.get("/v1/destinations/places/intl-toronto-ca").json()
    extra = {s["domain"]: s for s in toronto["scores"] if s["domain"] in ("safety", "affordability", "quality_of_life")}
    assert len(extra) == 3 and all(s["confidence"] == "index-derived" for s in extra.values()) and toronto["goal_fits"]["safe_and_calm"]
    assert toronto["cost_split"][0]["part"] == "lodging" and abs(sum(c["amount"] for c in toronto["cost_split"]) - toronto["cost_per_day"]) < 0.01
    # 'all' shows scored places plus the biggest world cities, and filters thin it
    allp = client.get("/v1/destinations/places?kind=all&limit=2000").json()
    kinds = {p["kind"] for p in allp}
    assert {"us_city", "intl_city", "leisure", "world_city"} <= kinds and all(p["population"] >= 1_000_000 for p in allp if p["kind"] == "world_city")
    assert client.get("/v1/destinations/places?kind=world_city&country=jp&min_pop=1000000").json()[0]["country"] == "Japan"


def test_sources_are_seeded_and_checked(client, monkeypatch):
    from engine import sources
    v = client.get("/v1/destinations/sources").json()
    assert len(v["indexes"]) == 7 and len(v["datasets"]) == 7 and v["method"]["domains"] and v["method"]["classification"]["leisure"]
    assert v["method"]["cost_split_shares"]["lodging"] == 0.45 and v["travel"][0]["label"] == "Directions" and len(v["logic_keys"]) == 4
    assert any(s["name"] == "Rome2Rio" for s in v["registry"])
    assert v["method"]["cost_per_day"]["split"][0][0] == "lodging"
    reg = client.get("/v1/sources").json()
    assert len(reg) >= 10 and all(s["status"] == "unchecked" for s in reg)
    # a fake fetcher: first URL fine, second 404, third unreachable
    calls = []
    def fake(url, timeout=15.0):
        calls.append(url)
        n = len(calls)
        return (200, b"same body", None) if n % 3 == 1 else (404, None, "HTTP Error 404") if n % 3 == 2 else (None, None, "timed out")
    monkeypatch.setattr(sources, "fetch", fake)
    res = sources.check(client.app.state.store, fetcher=fake)
    assert res["checked"] == len(reg) and res["ok"] >= 1 and res["dead"] >= 1
    reg2 = client.get("/v1/sources").json()
    assert {s["status"] for s in reg2} <= {"ok", "dead", "error"} and all(s["last_checked"] for s in reg2)
    # a second check with a changed body flags 'changed'
    ok_id = next(s["id"] for s in reg2 if s["status"] == "ok")
    res = sources.check(client.app.state.store, fetcher=lambda u, timeout=15.0: (200, b"different", None), only_ids=[ok_id])
    assert res["changed"] == 1
    r = client.post("/v1/sources", json={"name": "Census ACS", "url": "https://api.census.gov/", "kind": "api", "license": "public domain"})
    assert r.status_code == 201 and client.post("/v1/sources", json={"name": "x", "url": "https://api.census.gov/"}).status_code == 400


def test_logic_settings_drive_the_engine(client):
    # cost split: change the shares, and trip cost and every place's split follow
    r = client.put("/v1/settings/logic.destinations.cost_split", json={"value": {"lodging": 0.5, "food": 0.3, "transport": 0.1, "other": 0.1}})
    assert r.status_code == 200
    t = client.get("/v1/destinations/trip-cost?place_id=leisure-thailand&days=1&people=1&flight_each=0&housing=false").json()
    assert t["per_day_used"] == 22.5
    assert client.put("/v1/settings/logic.destinations.cost_split", json={"value": {"lodging": 0.9, "food": 0.3}}).status_code == 400   # doesn't add to 1
    # flight guess: floor
    client.put("/v1/settings/logic.destinations.flight_guess", json={"value": {"dollars_per_mile_each_way": 0.11, "floor": 999}})
    assert client.get("/v1/destinations/trip-cost?place_id=us-boston-ma&days=1").json()["flight_each"] == 999
    # a new goal appears and ranks
    gw = client.get("/v1/settings/logic.destinations.goal_weights").json()["value"]
    gw["nightlife"] = {"lifestyle": 5}
    client.put("/v1/settings/logic.destinations.goal_weights", json={"value": gw})
    assert "nightlife" in [g["id"] for g in client.get("/v1/destinations/options").json()["goals"]]
    top = client.get("/v1/destinations/places?kind=us_city&goal=nightlife").json()[0]
    assert top["fit"] == top["scores"]["lifestyle"]
    # an extra domain rule changes an index-derived score
    rules = client.get("/v1/settings/logic.destinations.extra_domains").json()["value"]
    rules["safety"] = {"index": "safety", "multiply": 0, "add": 42}
    client.put("/v1/settings/logic.destinations.extra_domains", json={"value": rules})
    tor = client.get("/v1/destinations/places/intl-toronto-ca").json()
    assert next(s for s in tor["scores"] if s["domain"] == "safety")["value"] == 42
    # a logic setting is in history like any other
    assert client.get("/v1/history?tbl=settings&limit=1").json()[0]["row_key"].startswith("logic.")


def test_more_rules_drive_the_engine(client, env):
    # Records: types and relations; sources checker; backups; limits
    client.put("/v1/settings/logic.records.types", json={"value": [["person", "Person"], ["horse", "Horse"]]})
    assert [t["type"] for t in client.get("/v1/types").json()["types"]][:2] == ["person", "horse"]
    client.put("/v1/settings/logic.records.relations", json={"value": {"owns": {"out": "owns", "in": "is owned by this"}}})
    assert client.get("/v1/types").json()["relations"]["owns"]["in"] == "is owned by this"
    assert client.put("/v1/settings/logic.records.relations", json={"value": {"has space": {"out": "x", "in": "y"}}}).status_code == 400
    client.put("/v1/settings/logic.sources.checker", json={"value": {"timeout_seconds": 1, "dead_http_codes": [418]}})
    from engine import sources
    res = sources.check(client.app.state.store, fetcher=lambda u, timeout=15.0: (418, None, "teapot"))
    assert res["dead"] == res["checked"] > 0
    client.put("/v1/settings/logic.limits", json={"value": {"attachment_max_mb": 0.00001, "csv_max_mb": 20}})
    person = client.post("/v1/entities", json={"type": "person", "name": "x"}).json()
    assert client.post(f"/v1/entities/{person['id']}/files", files={"file": ("a.txt", b"0123456789" * 20, "text/plain")}).status_code == 413
    assert len([s for sec in client.get("/v1/settings").json()["sections"] if sec["id"] == "logic" for s in sec["settings"]]) == 24
