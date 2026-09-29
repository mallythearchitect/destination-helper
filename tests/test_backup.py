"""Phase 1 done-when: a setting survives deleting your data and restoring it."""


def test_setting_survives_delete_and_restore(client, env):
    client.put("/v1/settings/profile.home_city",
               json={"value": {"name": "New Haven, CT", "lat": 41.3083, "lon": -72.9279}})
    made = client.post("/v1/backups?note=test").json()
    assert made["file"].startswith("vault-") and made["bytes"] > 0

    # the restore test reads the backup back and compares it with the live vault
    t = client.post("/v1/backups/restore-test").json()
    assert t["ok"] and t["integrity"] == "ok" and t["changed_since_backup"] == []
    assert [f.name for f in (env / "backups").iterdir()] == [made["file"]]  # no scratch files left behind

    # now "delete your data": change it, then restore the backup over it
    client.put("/v1/settings/profile.home_city",
               json={"value": {"name": "Nowhere", "lat": 0, "lon": 0}})
    client.delete("/v1/settings/profile.home_city")
    assert client.get("/v1/settings/profile.home_city").json()["stored"] is False
    assert client.post("/v1/backups/restore", json={"file": made["file"]}).status_code == 400  # needs confirm
    r = client.post("/v1/backups/restore", json={"file": made["file"], "confirm": True})
    assert r.status_code == 200 and r.json()["safety_backup"].startswith("vault-")
    assert client.get("/v1/settings/profile.home_city").json()["value"]["name"] == "New Haven, CT"

    listing = client.get("/v1/backups").json()
    assert len(listing["backups"]) == 2
    kinds = [x["kind"] for x in listing["log"]]
    # the restored vault still knows about the backup it came from
    assert kinds == ["restore", "backup"]


def test_restore_test_with_no_backups(client):
    assert client.post("/v1/backups/restore-test").json() == {"ok": False, "reason": "no backups yet"}


def test_nightly_script_runs_without_server(env, monkeypatch):
    import scripts.backup as nightly
    from engine import settings
    from engine.store import Store
    s = Store()
    settings.set_value(s, "backup.destination", str(env / "b"), None)
    s.close()
    assert nightly.main() == 0
    assert len(list((env / "b").glob("vault-*.db"))) == 1
