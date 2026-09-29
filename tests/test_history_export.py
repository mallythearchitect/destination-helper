import csv
import io
import json


def _make_changes(client):
    client.put("/v1/settings/display.theme", json={"value": "light"})
    client.put("/v1/settings/display.bills_layout", json={"value": "table"})
    client.delete("/v1/settings/display.theme")


def test_download_all_time_as_json(client):
    _make_changes(client)
    r = client.get("/v1/history/export")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/json")
    assert 'filename="destination-helper-history-all-time-' in r.headers["content-disposition"]
    d = r.json()
    assert d["count"] == 4 and len(d["changes"]) == 4  # conftest sets backup.destination too
    assert [c["action"] for c in d["changes"]][-3:] == ["settings.set", "settings.set", "settings.reset"]
    assert d["changes"][0]["ts"] <= d["changes"][-1]["ts"]  # oldest first


def test_download_as_csv(client):
    _make_changes(client)
    r = client.get("/v1/history/export?format=csv")
    assert r.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert len(rows) == 4 and rows[-1]["action"] == "settings.reset" and rows[-1]["after"] == ""
    assert json.loads(rows[-2]["after"])["value"] == "table"


def test_filters_narrow_the_download(client):
    _make_changes(client)
    only_theme = client.get("/v1/history/export?key=display.theme").json()
    assert only_theme["count"] == 2 and {c["row_key"] for c in only_theme["changes"]} == {"display.theme"}
    future = client.get("/v1/history/export?since=2999-01-01").json()
    assert future["count"] == 0
    past_day = client.get("/v1/history/export?since=2000-01-01&until=2000-01-02").json()
    assert past_day["count"] == 0 and past_day["filters"]["until"] == "2000-01-02T23:59:59+00:00"
    assert client.get("/v1/history/export?format=xml").status_code == 400
