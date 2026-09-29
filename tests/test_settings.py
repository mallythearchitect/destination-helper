from engine import settings


def test_defaults_come_from_registry(client):
    d = client.get("/v1/settings").json()
    ids = [s["id"] for s in d["sections"]]
    assert ids == ["profile", "maps", "display", "data", "ai", "backup", "logic"]
    home = client.get("/v1/settings/profile.home_city").json()
    assert home["value"]["name"] == "Hartford, CT" and home["stored"] is False and home["version"] == 0


def test_save_and_read_back(client):
    r = client.put("/v1/settings/backup.keep_days", json={"value": 12, "version": 0})
    assert r.status_code == 200 and r.json()["version"] == 1
    assert client.get("/v1/settings/values").json()["backup.keep_days"] == 12


def test_bad_values_are_refused(client):
    assert client.put("/v1/settings/backup.keep_days", json={"value": 0}).status_code == 400
    assert client.put("/v1/settings/display.theme", json={"value": "purple"}).status_code == 400
    assert client.put("/v1/settings/profile.time_zone", json={"value": "Mars/Olympus"}).status_code == 400
    assert client.put("/v1/settings/nope.nothing", json={"value": 1}).status_code == 404


def test_second_window_cannot_overwrite(client):
    client.put("/v1/settings/display.theme", json={"value": "light", "version": 0})
    r = client.put("/v1/settings/display.theme", json={"value": "system", "version": 0})
    assert r.status_code == 409
    d = r.json()["detail"]
    assert d["theirs"]["value"] == "light" and d["yours"]["value"] == "system"
    assert client.get("/v1/settings/display.theme").json()["value"] == "light"


def test_every_change_is_kept_and_can_be_undone(client):
    client.put("/v1/settings/display.theme", json={"value": "light"})
    client.put("/v1/settings/display.theme", json={"value": "system"})
    h = client.get("/v1/history?tbl=settings").json()
    assert [x["action"] for x in h[:2]] == ["settings.set", "settings.set"]
    last = h[0]
    assert last["before"]["value"] == "light" and last["after"]["value"] == "system"
    r = client.post(f"/v1/history/{last['id']}/undo")
    assert r.status_code == 200
    assert client.get("/v1/settings/display.theme").json()["value"] == "light"
    assert client.post(f"/v1/history/{last['id']}/undo").status_code == 409  # already undone
    # the undo is itself a change, so it can be undone too
    undo_entry = client.get("/v1/history?limit=1").json()[0]
    client.post(f"/v1/history/{undo_entry['id']}/undo")
    assert client.get("/v1/settings/display.theme").json()["value"] == "system"


def test_reset_returns_to_default(client):
    client.put("/v1/settings/display.theme", json={"value": "light"})
    r = client.delete("/v1/settings/display.theme")
    assert r.json() == {"key": "display.theme", "value": "system", "version": 0, "stored": False}
    first = client.get("/v1/history?limit=1").json()[0]
    assert first["action"] == "settings.reset" and first["after"] is None
    client.post(f"/v1/history/{first['id']}/undo")
    assert client.get("/v1/settings/display.theme").json()["value"] == "light"


def test_engine_reads_values_directly(store):
    assert settings.get_value(store, "profile.time_zone") == "America/New_York"
    settings.set_value(store, "profile.time_zone", "Europe/London", None)
    assert settings.get_value(store, "profile.time_zone") == "Europe/London"
